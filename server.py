import socket
import sys
from threading import Thread
import borderbot
import json
from datetime import datetime
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
	bot = None
	connection.send(str.encode(json.JSONEncoder().encode({'msg' : 'Connected.'})))
	values = None
	data = None
	complete_reply = None
	connected = True
	f = open('config.json', 'r')
	config_list = list(json.JSONEncoder().encode(json.JSONDecoder().decode(f.read())))
	f.close()
	while (connected):
		r = conn.recv(5000)
		if (r.decode('utf-8')):
			try:
				data = json.JSONDecoder().decode(r.decode('utf-8'))
			except:
				data = None
				print('La entrada no es JSON.')

			if (data and (data['type'] == 'config')):
				if (data['sub-type'] == 'get_config'):
					config = ''
					for i in range(900):
						if (len(config_list)):
							config += config_list.pop(0)
					reply = json.JSONEncoder().encode({'reply' : 'get_config', 'config' : config})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'set_pair'):
					bot = borderbot.BorderBot([data['pair']], 'real_time')
					connection.send(str.encode('{}'))

			if (data and (data['type'] == 'SQL')):
				if (data['sub-type'] == 'get_next_strategy_to_test'):
					if (data['first_reply']):
						print(bot.coin1 + '-' + bot.coin2 + ', get_next_strategy_to_test')
						v, m = bot.db.get_next_strategy_to_test(bot.coin1, bot.coin2, bot.timer, bot.config, {'p_s_u' : 0, 'p_c_u' : 0, 'p_s_d' : 0, 'p_c_d' : 0, 'e_p_u' : 0, 'e_p_d' : 0})
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
							'comp_pl' : float(v.comp_pl),
							'p_s_u' : float(m['p_s_u']),
							'p_c_u' : m['p_c_u'],
							'p_s_d' : float(m['p_s_d']),
							'p_c_d' : m['p_c_d'],
							'e_p_u' : float(m['e_p_u']),
							'e_p_d' : float(m['e_p_d'])
						}))

					reply = ''
					while ((len(reply) <= 1000) and len(complete_reply)):
						reply += complete_reply.pop(0)
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'get_prices'):
					if ((not values) and data['data']):
						values = bot.db.get_prices(bot.coin1, bot.coin2, bot.timer, data['data'], data['last_timestamp'])
						first_timestamp = values['first_timestamp']
					prices = []
					if (values):
						timer = values['timer']
						for i in range(50):
							if (len(values['prices'])):
								prices.append(values['prices'].pop(0))
						if (not len(values['prices'])):
							values = None
					reply = json.JSONEncoder().encode({'reply' : 'get_prices', 'first_timestamp' : first_timestamp, 'prices' : prices, 'timer' : timer})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'save_trader'):
					print(bot.coin1 + '-' + bot.coin2 + ', save_trader')
					bot.db.save_trader(None, 'backtesting', data['data'])
					reply = json.JSONEncoder().encode({'reply' : 'save_trader'})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'update_trader'):
					bot.db.update_trader(None, 'backtesting', data['data'])
					reply = json.JSONEncoder().encode({'reply' : 'update_trader'})
					connection.send(str.encode(reply))
				if (data['sub-type'] == 'save_strategy'):
					comp = None
					if (not data['ready']):
						if (not values):
							print(bot.coin1 + '-' + bot.coin2 + ', save_strategy')
							values = ''
						values += data['data']
					else:
						bot.db.save_strategy(None, 'backtesting', values)
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
						comp = bot.db.update_strategy(None, 'backtesting', values, data['timer'], data['coin1'], data['coin2'], update_comp = data['update_comp'])
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
