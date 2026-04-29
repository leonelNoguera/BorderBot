import socket
import sys
from threading import Thread
import db
import json
from datetime import datetime
import time
import psutil
my_socket = socket.socket(family = socket.AF_INET, type = socket.SOCK_STREAM, proto = 0, fileno = None)
print('Socket created.')
hostname = 'localhost'
port = 7000
args = sys.argv[1:]
if (args):
	port = int(args[0])
print(socket.gethostname())
my_socket.bind(('', port))
my_socket.listen(5)
def threaded_client(connection):
	import db
	db = db.Db()
	bot = None
	connection.send(str.encode(json.JSONEncoder().encode({'msg' : 'Connected.'})))
	values = None
	last_i = 0
	data = None
	complete_reply = None
	connected = True
	f = open('config.json', 'r')
	txt = f.read()
	config = json.JSONDecoder().decode(txt)
	config_list = list(txt)
	f.close()
	config_cpu_temp = None
	timer = 10
	coin1 = None
	coin2 = None
	while (connected):
		r = conn.recv(5000)
		if (r.decode('utf-8')):
			try:
				data = json.JSONDecoder().decode(r.decode('utf-8'))
			except:
				data = None
				print('La entrada no es JSON.')

			if (data and (data['type'] == 'check_connection')):
				connection.send(str.encode('{}'))

			if (data and (data['type'] == 'config')):
				if (data['sub-type'] == 'get_config'):
					config_l = ''
					for i in range(900):
						if (len(config_list)):
							config_l += config_list.pop(0)
					reply = json.JSONEncoder().encode({'reply' : 'get_config', 'config' : config_l})
					db.set_config(config, 'backtesting', coin1, coin2)
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'set_pair'):
					coin1 = data['pair'].split('-')[0]
					coin2 = data['pair'].split('-')[1]
					connection.send(str.encode('{}'))

			if (data and (data['type'] == 'SQL')):
				if (data['sub-type'] == 'get_next_strategy_to_test'):
					config_ok = False
					while (not config_ok):
						config_ok = True
						f = open('config_cpu_temp.json', 'r')
						d = f.read()
						try:
							if (config_cpu_temp):
								config_cpu_temp['max_temp'] = json.JSONDecoder().decode(d)['max_temp']
								config_cpu_temp['no_pause_periods'] = json.JSONDecoder().decode(d)['no_pause_periods']
							else:
								config_cpu_temp = json.JSONDecoder().decode(d)
						except:
							config_ok = False
						f.close()
						if (config_cpu_temp):
							f = open('config_cpu_temp.json', 'w')
							f.write(json.JSONEncoder().encode(config_cpu_temp))
							f.close()
					config_cpu_temp['total_server_pause_seconds'] = 0
					config_cpu_temp['server_pause_seconds'] = 0
					#{"status" : "on"}
					f = open('config_server.json', 'r')
					status = json.JSONDecoder().decode(f.read())['status']
					f.close()
					if (status.lower() != 'on'):
						print('Pausa para mantenimiento...')
						while (status.lower() != 'on'):
							time.sleep(1)
							f = open('config_server.json', 'r')
							status = json.JSONDecoder().decode(f.read())['status']
							f.close()
						print('Continuando...')
					if (data['first_reply']):
						v = db.get_next_strategy_to_test(coin1, coin2, timer)
						complete_reply = list(json.JSONEncoder().encode({'reply' : 'get_next_strategy_to_test', 'initial_config' : v.initial_config,
							'last_timestamp' : float(v.last_timestamp),
							'derivatives' : v.derivatives,
							'stop_loss' : float(v.stop_loss),
							'trade_type' : v.trade['type'],
							'trade_timestamp' : float(v.trade['time']),
							'trade_prev_timestamp' : float(v.trade['prev_time']),
							'trade_price' : float(v.trade['price']),
							'trade_prev_price' : float(v.trade['prev_price']),
							'leverage_s' : v.leverage_s,
							'leverage_l' : v.leverage_l,
							'pl' : float(v.pl),
							'prev_pl' : float(v.prev_pl),
							'l_l_ok' : float(v.l_l_ok),
							'l_s_ok' : float(v.l_s_ok),
							'l_l_no' : float(v.l_l_no),
							'l_s_no' : float(v.l_s_no),
							'zoom_s' : float(v.zoom_s),
							'zoom_l' : float(v.zoom_l),
							'far_price' : float(v.far_price),
							'comp_initial_config' : v.comp_initial_config,
							'comp_last_timestamp' : float(v.comp_last_timestamp),
							'comp_prev_pl' : float(v.comp_prev_pl),
							'comp_pl' : float(v.comp_pl)
						}))

					reply = ''
					while ((len(reply) <= 600) and len(complete_reply)):
						reply += complete_reply.pop(0)
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'get_prices'):
					temp = psutil.sensors_temperatures()['acpitz'][0].current
					if (temp >= config_cpu_temp['max_temp']):
						config_cpu_temp['server_pause_seconds'] += 1
						config_cpu_temp['total_server_pause_seconds'] += config_cpu_temp['server_pause_seconds']
						print('Pausa de ' + str(config_cpu_temp['server_pause_seconds']) + ' segundos para enfriar procesador.')
						time.sleep(config_cpu_temp['server_pause_seconds'])
					else:
						if (config_cpu_temp['server_pause_seconds'] > 1):
							config_cpu_temp['server_pause_seconds'] -= 1
					if ((not values) and data['data']):
						values = db.get_prices(coin1, coin2, data['data'])
						last_i = 0
					prices = ''
					if (values):
						for i in range(750):
							if (last_i < len(values)):
								prices += values[last_i]
								last_i += 1
						if (last_i >= len(values)):
							values = None
					reply = json.JSONEncoder().encode({'reply' : 'get_prices', 'prices' : prices})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'save_trader'):
					db.save_trader(data['data'])
					reply = json.JSONEncoder().encode({'reply' : 'save_trader'})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'update_trader'):
					db.update_trader('backtesting', data['data'])
					reply = json.JSONEncoder().encode({'reply' : 'update_trader'})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'get_init_timestamps'):
					if ((not values) and (data['first'])):
						values = db.get_init_timestamps(data['st_last_timestamp'])
					init_timestamps = []
					if (values):
						for i in range(10):
							if (len(values)):
								init_timestamps.append(values.pop(0))
						if (not len(values)):
							values = None
					reply = json.JSONEncoder().encode({'reply' : 'get_init_timestamps', 'init_timestamps' : init_timestamps})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'get_db_update_timestamp'):
					u , i = db.get_db_update_timestamp(data['data'])
					reply = json.JSONEncoder().encode({'reply' : 'get_db_update_timestamp', 'update_timestamp' : float(u), 'init_timestamp' : float(i)})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'save_strategy'):
					if (not data['ready']):
						if (not values):
							values = ''
						values += data['data']
					else:
						db.save_strategy(None, 'backtesting', values)
						values = None
					reply = json.JSONEncoder().encode({'reply' : 'save_strategy'})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'update_strategy'):
					comp = None
					if (not data['ready']):
						if (not values):
							values = ''
						values += data['data']
					else:
						comp = db.update_strategy(None, 'backtesting', values, data['timer'], data['coin1'], data['coin2'], update_comp = data['update_comp'])
						values = None
					reply = json.JSONEncoder().encode({'reply' : 'update_strategy', 'comp' : comp})
					connection.send(str.encode(reply))
		else:
			connected = False
			connection.close()
			print('cliente desconectado')

while (True):
	conn, addr = my_socket.accept()
	thread = Thread(target = threaded_client, args = (conn, ))
	thread.start()
my_socket.close()
