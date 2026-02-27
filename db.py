from datetime import datetime
import random
import json
import time
import strategy
import psutil
class Db(object):
	def __init__(self, config = None, mode = None, coin1 = None, coin2 = None, socket = None):
		super(Db, self).__init__()
		self.coin1 = coin1
		self.coin2 = coin2
		if (config and coin1 and coin2):
			self.coin1_decimals = config[self.coin1 + '-' + self.coin2]['decimals']
			self.timer = config['timer']
		self.mode = mode
		self.socket = socket
		self.last_check = datetime.now().timestamp()
		if (self.mode != 'backtesting'):
			print('Conectando a la db.')
		self.config = config
		self.values_dict = {}
		self.config_cpu_temp = None
		self.reset_values()

	def reset_values(self):
		self.init_timestamp = 0
		self.last_price_in_list = None
		self.db_update_timestamp = 0
		self.init_timestamps = []

		if (self.config_cpu_temp):
			f = open('config_cpu_temp.json', 'r')
			self.config_cpu_temp['max_temp'] = json.JSONDecoder().decode(f.read())['max_temp']
			f.close()
			f = open('config_cpu_temp.json', 'w')
			f.write(json.JSONEncoder().encode(self.config_cpu_temp))
			f.close()
		else:
			f = open('config_cpu_temp.json', 'r')
			self.config_cpu_temp = json.JSONDecoder().decode(f.read())
			f.close()
		self.config_cpu_temp['total_client_pause_seconds'] = 0
		self.config_cpu_temp['client_pause_seconds'] = 0


	def read_prices_local(self, it):
		fixed_time_prices = []
		more_data = False
		file_exists = False
		t = ''
		local_ut = 0
		if (self.values_dict.get(str(it['init_timestamp']) + '_updated')):
			local_ut = self.values_dict[str(it['init_timestamp']) + '_updated']
		else:
			try:
				f = open(f"prices/tmp/{self.coin1}-{self.coin2}/{self.coin1}-{self.coin2}_{self.timer}_{it['init_timestamp']}_updated.txt", 'r')
				local_ut = float(f.read().strip())
				f.close()
			except:
				f = open(f"prices/tmp/{self.coin1}-{self.coin2}/{self.coin1}-{self.coin2}_{self.timer}_{it['init_timestamp']}_updated.txt", 'w')
				f.write(str(it['update_timestamp']))
				f.close()
		if (it['update_timestamp'] <= local_ut):
			if (self.values_dict.get(str(it['init_timestamp']))):
				fixed_time_prices = self.values_dict[str(it['init_timestamp'])]['fixed_time_prices']
				self.last_price_in_list = self.values_dict[str(it['init_timestamp'])]['last_price_in_list']
				more_data = True
				file_exists = True
			if (not fixed_time_prices):
				try:
					f = open(f"prices/tmp/{self.coin1}-{self.coin2}/{self.coin1}-{self.coin2}_{self.timer}_{it['init_timestamp']}.txt", 'r')
					t = f.read()
					t = t.strip().split('\n')
					more_data = True
					f.close()
					file_exists = True
				except:
					0
		return (fixed_time_prices, more_data, file_exists, t)

	def get_prices_local(self, prices_gap_tolerance_seconds, st_last_timestamp):
		c1 = self.coin1
		c2 = self.coin2
		if ((datetime.now().timestamp() - self.last_check) > 240):
			self.socket.send(json.JSONEncoder().encode({'type' : 'check_connection'}).encode())
			self.socket.recv(5000)
			self.last_check = datetime.now().timestamp()
		if (len(self.init_timestamps) < 2):
			self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_init_timestamps', 'first' : True, 'st_last_timestamp' : st_last_timestamp}).encode())
			msg_in = json.JSONDecoder().decode(self.socket.recv(5000).decode())
			while (len(msg_in['init_timestamps'])):
				for it in msg_in['init_timestamps']:
					self.init_timestamps.append(it)
				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_init_timestamps', 'first' : False}).encode())
				msg_in = json.JSONDecoder().decode(self.socket.recv(5000).decode())
		more_data = False
		for it in self.init_timestamps:
			if (it['first_t'] > st_last_timestamp):
				file_exists = False
				fixed_time_prices, more_data, file_exists, t = self.read_prices_local(it)
				if (file_exists): # Los precios de esa lista ya estaban almacenados locálmente y se actualizaron antes del último backtesting.
					if (not fixed_time_prices):
						first = t[0].split(',')
						first[0] = float(first[0])
						first[1] = float(first[1])
						first.reverse()
						ft = None
						if (t[1] != 'None'):
							ft = float(t[1])
						l = t[2:-1]
						if (self.last_price_in_list):
							if (ft and ((ft - float(self.last_price_in_list['time'])) <= prices_gap_tolerance_seconds)):
								p = self.fix_prices([[self.last_price_in_list['price'], self.last_price_in_list['time']], first], self.timer)
								if (len(p['prices'])):
									fixed_time_prices.append({'price': p['prices'][0], 'time' : p['first_timestamp']})
						if (ft):
							for p in l:
								fixed_time_prices.append({'price': float(p), 'time' : float(ft + (self.timer * len(fixed_time_prices)))})
						t = t[-1].split(',')
						if (t[0] != 'None'):
							self.last_price_in_list = {'price' : float(t[1]), 'time' : float(t[0])}
						self.values_dict[str(it['init_timestamp'])] = {'fixed_time_prices' : fixed_time_prices.copy(), 'last_price_in_list' : self.last_price_in_list.copy()}
						self.values_dict[str(it['init_timestamp']) + '_updated'] = it['update_timestamp']
				else:#Los precios de esa lista no estaban almacenados locálmente o se actualizaron antes del último backtesting. Se debe generar el archivo correspondiente. El primer dato debe ser el calculado en base al último dato de la lista anterior; si no supera el 'prices_gap_tolerance_seconds'.
					self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_prices', 'data' : f"{it['init_timestamp']}{it['source']}" }).encode())
					msg_in = json.JSONDecoder().decode(self.socket.recv(5000).decode())
					prices_joined = []
					prices = ''
					while (len(msg_in['prices'])):
						prices += msg_in['prices']
						self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_prices', 'data' : ''}).encode())
						msg_in = json.JSONDecoder().decode(self.socket.recv(5000).decode())
					if (prices):
						more_data = True
					prices = prices.split('\n')
					p = 0
					if (self.last_price_in_list):
						if ((float(prices[0][1]) - float(self.last_price_in_list['time'])) <= prices_gap_tolerance_seconds):
							prices_joined.append([self.last_price_in_list['price'], self.last_price_in_list['time']])
							p = 1
					for i in range(len(prices)):
						p = prices[i].split(',')
						p.reverse()
						p[0] = float(p[0])
						p[1] = float(p[1])
						prices[i] = p
					prices_joined.extend(prices)
					fixed_prices = self.fix_prices(prices_joined, self.timer)
					f = None
					path = f"prices/tmp/{c1}-{c2}/{c1}-{c2}_{self.timer}_{it['init_timestamp']}.txt"
					f = open(path, 'w')
					f.write(str(prices_joined[0][1]) + ',' + str(prices_joined[0][0]) + '\n')
					f.close()
					f = open(path, 'a')
					f.write(str(fixed_prices['first_timestamp']) + '\n')
					fixed_time_prices = []
					if (self.last_price_in_list):
						if ((prices_joined[0][1] - float(self.last_price_in_list['time'])) <= prices_gap_tolerance_seconds):
							p = self.fix_prices([[self.last_price_in_list['price'], self.last_price_in_list['time']], prices_joined[0]], self.timer)
							if (len(p['prices'])):
								fixed_time_prices.append({'price': p['prices'][0], 'time' : p['first_timestamp']})
					for p in fixed_prices['prices']:
						fixed_time_prices.append({'price': p, 'time' : float(fixed_prices['first_timestamp'] + (self.timer * len(fixed_time_prices)))})
						f.write(str(p) + '\n')
					self.last_price_in_list = {'price' : prices_joined[-1][0], 'time' : prices_joined[-1][1]}
					f.write(str(self.last_price_in_list['time']) + ',' + str(self.last_price_in_list['price']))
					f.close()
					f = open(f"prices/tmp/{c1}-{c2}/{c1}-{c2}_{self.timer}_{it['init_timestamp']}_updated.txt", 'w')
					f.write(str(it['update_timestamp']))
					f.close()
					self.values_dict[str(it['init_timestamp'])] = {'fixed_time_prices' : fixed_time_prices.copy(), 'last_price_in_list' : self.last_price_in_list.copy()}
					self.values_dict[str(it['init_timestamp']) + '_updated'] = it['update_timestamp']
				return (fixed_time_prices, more_data)
		return ([], False)

	def get_init_timestamps(self, st_last_timestamp):
		c1 = self.coin1
		c2 = self.coin2
		ts = []
		f = open(f'prices/{c1}-{c2}/lists.txt', 'r')
		lists = f.read().strip().split('\n')
		f.close()
		for l in lists:
			it = float(l.split('_')[0])
			src = ''
			try:
				src = '_' + l.split('_')[1]
			except:
				0
			#prices/DRIFT-USDT/DRIFT-USDT_1771508156.480666_jupiter.txt
			f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{l}.txt', 'r')
			first_t = float(f.read().split('\n')[0].split(',')[0]) # ['1769427124.441381_jupiter', '1769431333.370391_jupiter', ...]
			f.close()
			if (first_t > st_last_timestamp):
				f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{l}_updated.txt', 'r')
				ts.append({'init_timestamp' : it, 'update_timestamp' : float(f.read().strip()), 'source' : src, 'first_t' : first_t})
				f.close()
		return ts

	def get_prices(self, coin1, coin2, timer_now, st = None, last_timestamp = 0, prices_gap_tolerance_seconds = None):
		self.init_timestamp = last_timestamp
		prices_joined = []
		fixed_time_prices = []
		if (self.mode == 'backtesting'):
			more_data = False
			# Verificar si la lista correspondiente está almacenada en archivos locales.
			fixed_time_prices, more_data = self.get_prices_local(prices_gap_tolerance_seconds, last_timestamp)
			temp = psutil.sensors_temperatures()['acpitz'][0].current
			if (temp >= self.config_cpu_temp['max_temp']):
				self.config_cpu_temp['client_pause_seconds'] += 1
				self.config_cpu_temp['total_client_pause_seconds'] += self.config_cpu_temp['client_pause_seconds']
				print('Pausa de ' + str(self.config_cpu_temp['client_pause_seconds']) + ' segundos para enfriar procesador.')
				time.sleep(self.config_cpu_temp['client_pause_seconds'])
			else:
				if (self.config_cpu_temp['client_pause_seconds'] > 1):
					self.config_cpu_temp['client_pause_seconds'] -= 1
			return (fixed_time_prices, more_data)
		else:
			f = open(f'prices/{coin1}-{coin2}/{coin1}-{coin2}_{st}.txt', 'r')
			prices = f.read().strip()
			f.close()
			return prices


	def fix_prices(self, prices, timer_now):
		this_timestamp = timer_now * int(prices[0][1] / timer_now)
		if (this_timestamp < prices[0][1]):
			this_timestamp += timer_now
		first_timestamp = None
		i = 1
		fixed_prices = {'first_timestamp' : first_timestamp, 'prices' : []}
		j = 1
		prev_price = {'price': float(prices[0][0]), 'time' : float(prices[0][1])}
		while (i < len(prices)):
			while (prices[i][1] >= this_timestamp):
				t_dif = this_timestamp - prev_price['time']
				t_dif_2 = prices[i][1] - prev_price['time']
				dif = float(t_dif / t_dif_2)
				fixed = prev_price['price'] + ((float(prices[i][0]) - prev_price['price']) * dif)
				price = round(fixed, self.coin1_decimals)
				fixed_prices['prices'].append(price)
				if (not first_timestamp):
					first_timestamp = this_timestamp
					fixed_prices['first_timestamp'] = first_timestamp
				this_timestamp += timer_now
			prev_price = {'price': float(prices[i][0]), 'time' : float(prices[i][1])}
			i += 1
		if (first_timestamp and ((first_timestamp + (timer_now * (len(fixed_prices['prices']) - 1))) < self.init_timestamp)):
			return {'first_timestamp' : first_timestamp, 'prices' : []}
		return fixed_prices


	def set_strategy(self, row, v = None, change_comp = False):
		v.last_timestamp = row['last_timestamp']
		v.stop_loss = row['stop_loss']
		v.trade['type'] = row['trade_type']
		v.trade['prev_type'] = row['trade_type']
		v.trade['time'] = row['trade_timestamp']
		v.trade['prev_time'] = row['trade_prev_timestamp']
		v.trade['price'] = row['trade_price']
		v.trade['prev_price'] = row['trade_prev_price']
		v.leverage_s = row['leverage_s']
		v.leverage_l = row['leverage_l']
		if ('prev_pl' in row.keys()):
			v.pl = row['pl']
			v.prev_pl = row['prev_pl']
		v.l_l_ok = row['l_l_ok']
		v.l_s_ok = row['l_s_ok']
		v.l_l_no = row['l_l_no']
		v.l_s_no = row['l_s_no']
		v.zoom_s = row['zoom_s']
		v.zoom_l = row['zoom_l']
		v.far_price = row['far_price']
		v.set_config(row['initial_config'])
		v.derivatives = row['derivatives']
		if (change_comp):
			v.comp_initial_config = row['comp_initial_config']
			v.comp_last_timestamp = row['comp_last_timestamp']
			v.comp_prev_pl = row['comp_prev_pl']
			v.comp_pl = row['comp_pl']
		return v


	def get_strategy(self, timer, coin1, coin2, config = None, mode = 'backtesting', socket = None):#, m = None):
		if (mode != 'backtesting'):
			s, m = self.get_best_strategy(coin1, coin2, timer, config)
			return (s,m)
		else:
			s = self.get_next_strategy_to_test(coin1, coin2, timer, config)
			return s

	def get_next_strategy_to_test(self, coin1, coin2, timer, config2):
		v = None
		if (self.mode == 'backtesting'):
			self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_next_strategy_to_test', 'first_reply' : True}).encode())
			partial_msg_in = self.socket.recv(5000).decode()
			msg_in = partial_msg_in
			try:
				msg_in = json.JSONDecoder().decode(msg_in)
			except:
				pass
			while (type(msg_in) == type('')):
				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_next_strategy_to_test', 'first_reply' : False}).encode())
				partial_msg_in = self.socket.recv(5000).decode()
				msg_in += partial_msg_in
				try:
					msg_in = json.JSONDecoder().decode(msg_in)
				except:
					pass
			v = strategy.Strategy(timer, coin1, coin2, config = config2, name = 'bs_' + str(msg_in['initial_config']['sl_initial_dif_s']) + ',' + str(msg_in['initial_config']['sl_initial_dif_l']))
			self.set_strategy(msg_in, v, change_comp = True)
		else:
			v = strategy.Strategy(timer, coin1, coin2, config = config2, name = 'bs_' + str(config2[coin1 + '-' + coin2]['sl_initial_dif_s']) + ',' + str(config2[coin1 + '-' + coin2]['sl_initial_dif_l']))

			prev_status = {}
			try:
				f = open('strategies.json', 'r')
				prev_status = json.JSONDecoder().decode(f.read())
				prev_status[coin1 + '-' + coin2]
				f.close()
			except:
				0
			if (prev_status and prev_status[coin1 + '-' + coin2]['best_initial_config'] and (prev_status[coin1 + '-' + coin2]['timer'] == timer)):
				v.set_config(prev_status[coin1 + '-' + coin2]['best_initial_config'])
			try:
				f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'r')
			except:
				f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'w')
				f.close()
				f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'r')
			lst = f.read().strip().split('\n')
			f.close()
			rows = []
			r_or_d = False
			for row in lst:
				if (row):
					st = json.JSONDecoder().decode(row)
					if (st['ready_to_use']):
						rows.append(st)
						r_or_d = True
					if (st['initial_config'] == v.initial_config):
						r_or_d = True
			s = None
			btst = None
			if (r_or_d): # Significa que ya había una estrategia ready_to_use o con la configuración por defecto.
				d_comp = None
				# Busca la última estrategia ready_to_use y con mayor pl.
				try:
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'r')
				except:
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'w')
					f.close()
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'r')
				try:
					btst = json.JSONDecoder().decode(f.read().strip().split('\n')[-1])
				except:
					pass
				f.close()
				dif_initial_config = {'sl_s_dif' : 0, 'sl_l_dif' : 0, 'sl_reduced_dif_s' : 0, 'sl_reduced_dif_l' : 0, 'sl_initial_dif_s' : 0, 'sl_initial_dif_l' : 0, 'okno_inc_s' : 0, 'okno_inc_l' : 0, 'okno_dec_s' : 0, 'okno_dec_l' : 0, 'm_aprox_s' : 0, 'm_aprox_l' : 0, 'leverage_inc_s' : 0, 'leverage_inc_l' : 0, 'leverage_dec_s' : 0, 'leverage_dec_l' : 0, 'high_leverage_s' : 0, 'high_leverage_l' : 0, 'far_price_dif_s' : 0, 'far_price_dif_l' : 0}
				if (btst):
					v = strategy.Strategy(timer, coin1, coin2, config = config2, name = btst['name'])
					v.set_config(btst['initial_config'])

					d = btst['derivatives']
					max_d = (d[0]['coin2_balance'] - d[0]['total_investment'])
					for i in range(1, len(d)):
						if (d[i]['coin2_balance'] - d[i]['total_investment'] > max_d):
							max_d = (d[i]['coin2_balance'] - d[i]['total_investment'])

					for row in rows:
						if (row['initial_config'] == btst['comp_initial_config']):
							d_comp = row['derivatives']
					if (d_comp):
						max_d_comp = (d_comp[0]['coin2_balance'] - d_comp[0]['total_investment'])
						for i in range(1, len(d_comp)):
							if (d_comp[i]['coin2_balance'] - d_comp[i]['total_investment'] > max_d_comp):
								max_d_comp = (d_comp[i]['coin2_balance'] - d_comp[i]['total_investment'])

					if (btst['comp_initial_config']):
						dif_initial_config = {'sl_s_dif' : 0, 'sl_l_dif' : 0, 'sl_reduced_dif_s' : 0, 'sl_reduced_dif_l' : 0, 'sl_initial_dif_s' : 0, 'sl_initial_dif_l' : 0, 'okno_inc_s' : 0, 'okno_inc_l' : 0, 'okno_dec_s' : 0, 'okno_dec_l' : 0, 'm_aprox_s' : 0, 'm_aprox_l' : 0, 'leverage_inc_s' : 0, 'leverage_inc_l' : 0, 'leverage_dec_s' : 0, 'leverage_dec_l' : 0, 'high_leverage_s' : 0, 'high_leverage_l' : 0, 'far_price_dif_s' : 0, 'far_price_dif_l' : 0}
						if (d_comp):
							keys = list(dif_initial_config.keys())[1:]
							for k in keys:
								r = 0
								if (btst['initial_config'][k] < btst['comp_initial_config'][k]):
									r = -1
								if (btst['initial_config'][k] > btst['comp_initial_config'][k]):
									r = 1
								# Estas se calculan diferente debido a que es son variables que no influyen en 'pl'.
								if (((k == 'far_price_dif_s') or (k == 'far_price_dif_l')) and (max_d < max_d_comp)):
									r = r * -1
								dif_initial_config[k] = r

				st_in_files = True
				while (st_in_files):
					st_in_files = False
					v.set_config(v.initial_config)

					v.sl_reduced_dif_s = self.random_var(v.sl_reduced_dif_s, config2[coin1 + '-' + coin2]['sl_reduced_dif_min'], config2[coin1 + '-' + coin2]['sl_reduced_dif_max'], config2[coin1 + '-' + coin2]['sl_reduced_dif_decimals'], dif_initial_config['sl_reduced_dif_s'])
					v.sl_reduced_dif_l = self.random_var(v.sl_reduced_dif_l, config2[coin1 + '-' + coin2]['sl_reduced_dif_min'], config2[coin1 + '-' + coin2]['sl_reduced_dif_max'], config2[coin1 + '-' + coin2]['sl_reduced_dif_decimals'], dif_initial_config['sl_reduced_dif_l'])
					v.sl_initial_dif_s = self.random_var(v.sl_initial_dif_s, config2[coin1 + '-' + coin2]['sl_initial_dif_min'], config2[coin1 + '-' + coin2]['sl_initial_dif_max'], config2[coin1 + '-' + coin2]['sl_initial_dif_decimals'], dif_initial_config['sl_initial_dif_s'])
					v.sl_initial_dif_l = self.random_var(v.sl_initial_dif_l, config2[coin1 + '-' + coin2]['sl_initial_dif_min'], config2[coin1 + '-' + coin2]['sl_initial_dif_max'], config2[coin1 + '-' + coin2]['sl_initial_dif_decimals'], dif_initial_config['sl_initial_dif_l'])

					v.okno_dec_s = self.random_var(v.okno_dec_s, config2[coin1 + '-' + coin2]['okno_dec_min'], config2[coin1 + '-' + coin2]['okno_dec_max'], config2[coin1 + '-' + coin2]['okno_dec_decimals'], dif_initial_config['okno_dec_s'])
					v.okno_inc_s = self.random_var(v.okno_inc_s, config2[coin1 + '-' + coin2]['okno_inc_min'], config2[coin1 + '-' + coin2]['okno_inc_max'], config2[coin1 + '-' + coin2]['okno_inc_decimals'], dif_initial_config['okno_inc_s'])
					v.okno_dec_l = self.random_var(v.okno_dec_l, config2[coin1 + '-' + coin2]['okno_dec_min'], config2[coin1 + '-' + coin2]['okno_dec_max'], config2[coin1 + '-' + coin2]['okno_dec_decimals'], dif_initial_config['okno_dec_l'])
					v.okno_inc_l = self.random_var(v.okno_inc_l, config2[coin1 + '-' + coin2]['okno_inc_min'], config2[coin1 + '-' + coin2]['okno_inc_max'], config2[coin1 + '-' + coin2]['okno_inc_decimals'], dif_initial_config['okno_inc_l'])

					v.m_aprox_s = self.random_var(v.m_aprox_s, config2[coin1 + '-' + coin2]['m_aprox_min'], config2[coin1 + '-' + coin2]['m_aprox_max'], config2[coin1 + '-' + coin2]['m_aprox_decimals'], dif_initial_config['m_aprox_s'])
					v.m_aprox_l = self.random_var(v.m_aprox_l, config2[coin1 + '-' + coin2]['m_aprox_min'], config2[coin1 + '-' + coin2]['m_aprox_max'], config2[coin1 + '-' + coin2]['m_aprox_decimals'], dif_initial_config['m_aprox_l'])

					v.sl_s_dif = self.random_var(v.sl_s_dif, config2[coin1 + '-' + coin2]['sl_dif_min'], config2[coin1 + '-' + coin2]['sl_dif_max'], config2[coin1 + '-' + coin2]['sl_dif_decimals'], dif_initial_config['sl_s_dif'])
					v.sl_l_dif = self.random_var(v.sl_l_dif, config2[coin1 + '-' + coin2]['sl_dif_min'], config2[coin1 + '-' + coin2]['sl_dif_max'], config2[coin1 + '-' + coin2]['sl_dif_decimals'], dif_initial_config['sl_l_dif'])

					v.high_leverage_s = int(self.random_var(v.high_leverage_s, config2[coin1 + '-' + coin2]['high_leverage_min'], config2[coin1 + '-' + coin2]['high_leverage_max'], config2[coin1 + '-' + coin2]['high_leverage_decimals'], dif_initial_config['high_leverage_s']))
					v.high_leverage_l = int(self.random_var(v.high_leverage_l, config2[coin1 + '-' + coin2]['high_leverage_min'], config2[coin1 + '-' + coin2]['high_leverage_max'], config2[coin1 + '-' + coin2]['high_leverage_decimals'], dif_initial_config['high_leverage_l']))

					v.far_price_dif_s = self.random_var(v.far_price_dif_s, config2[coin1 + '-' + coin2]['far_price_dif_min'], config2[coin1 + '-' + coin2]['far_price_dif_max'], config2[coin1 + '-' + coin2]['far_price_dif_decimals'], dif_initial_config['far_price_dif_s'])
					v.far_price_dif_l = self.random_var(v.far_price_dif_l, config2[coin1 + '-' + coin2]['far_price_dif_min'], config2[coin1 + '-' + coin2]['far_price_dif_max'], config2[coin1 + '-' + coin2]['far_price_dif_decimals'], dif_initial_config['far_price_dif_l'])

					v.leverage_inc_s = self.random_var(v.leverage_inc_s, config2[coin1 + '-' + coin2]['leverage_inc_min'], config2[coin1 + '-' + coin2]['leverage_inc_max'], config2[coin1 + '-' + coin2]['leverage_inc_decimals'], dif_initial_config['leverage_inc_s'])
					v.leverage_dec_s = self.random_var(v.leverage_dec_s, config2[coin1 + '-' + coin2]['leverage_dec_min'], config2[coin1 + '-' + coin2]['leverage_dec_max'], config2[coin1 + '-' + coin2]['leverage_dec_decimals'], dif_initial_config['leverage_dec_s'])
					v.leverage_inc_l = self.random_var(v.leverage_inc_l, config2[coin1 + '-' + coin2]['leverage_inc_min'], config2[coin1 + '-' + coin2]['leverage_inc_max'], config2[coin1 + '-' + coin2]['leverage_inc_decimals'], dif_initial_config['leverage_inc_l'])
					v.leverage_dec_l = self.random_var(v.leverage_dec_l, config2[coin1 + '-' + coin2]['leverage_dec_min'], config2[coin1 + '-' + coin2]['leverage_dec_max'], config2[coin1 + '-' + coin2]['leverage_dec_decimals'], dif_initial_config['leverage_dec_l'])

					v.NAME = 'bs,' + str(v.sl_initial_dif_s) + ',' + str(v.sl_initial_dif_l)

					v.change_initial_config()
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'r')
					lst = f.read().strip().split('\n')
					f.close()
					for row in lst:
						if (row):
							st = json.JSONDecoder().decode(row)
							if (st['initial_config'] == v.initial_config):
								st_in_files = True
							if (st['ready_to_use']):
								s = st
			# Busca la última estrategia ready_to_use y con mayor pl, para comparar con la estrategia nueva.
			if (btst):
				prev_comp_initial_config = s['comp_initial_config']
				if (btst['initial_config'] != s['initial_config']):
					# Ver si esa estrategia es mejor que la anterior.
					if (btst['comp_pl'] >= btst['comp_prev_pl']):
						v.comp_initial_config = btst['initial_config']
						v.comp_last_timestamp = btst['last_timestamp']
						v.comp_prev_pl = btst['pl']
					else:
						v.comp_initial_config = prev_comp_initial_config
						v.comp_last_timestamp = s['comp_last_timestamp']
						v.comp_prev_pl = s['comp_prev_pl']
				else: # No había otras estrategias.
					v.comp_initial_config = s['initial_config']
					v.comp_last_timestamp = s['last_timestamp']
					v.comp_prev_pl = s['pl']
			if (v.comp_initial_config and (v.comp_initial_config != '{}')):
				ok = False
				for l in rows:
					if (l['initial_config'] == v.comp_initial_config):
						ok = True
				if (not ok):
					v.set_config(v.comp_initial_config)
			print(datetime.now().isoformat())
			print('Se usará una estrategia con: ' + json.JSONEncoder().encode(v.initial_config))
		return v


	def random_var(self, var, min_value, max_value, decimals, change_random):
		r = []
		config = self.config[self.coin1 + '-' + self.coin2]
		items = ['random_var_default_less_priority' , 'random_var_equal_priority', 'random_var_default_more_priority']
		for i in range(len(items)):
			for j in range(config[items[i]]):
				r.append(i - 1)
		if (change_random):
			if (change_random > 0):
				for i in range(config['random_var_add_more_priority']):
					r.append(1)
			else:
				for i in range(config['random_var_add_less_priority']):
					r.append(-1)
		d = random.choice(r)
		if (d):
			ok = False
			while (not ok):
				p = random.random()
				r = random.random()
				if (r >= p): # Si p es mayor, es menos probable que sea seleccionado.
					if (d > 0): # Incrementar variable.
						dif = max_value - var
						var += dif * p
					else:
						dif = var - min_value
						var -= dif * p
					ok = True
		if (var > max_value):
			var = max_value
		if (var < min_value):
			var = min_value
		return round(var, decimals)


	def get_best_strategy(self, coin1, coin2, timer, config2):
		v = None
		m = None
		real_time_initial_config = ''
		try:
			f = open(f'strategies/real_time/{timer}/{coin1}-{coin2}/list.txt', 'r')
		except:
			f = open(f'strategies/real_time/{timer}/{coin1}-{coin2}/list.txt', 'w')
			f.close()
			f = open(f'strategies/real_time/{timer}/{coin1}-{coin2}/list.txt', 'r')
		lst = f.read().strip().split('\n')
		f.close()
		st = ''
		btst = ''
		for row in lst:
			if (row):
				st = json.JSONDecoder().decode(row)
				real_time_initial_config = st['initial_config']

		new_initial_config = ''
		# Busca la última estrategia ready_to_use y con mayor pl.
		try:
			f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'r')
		except:
			f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'w')
			f.close()
			f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'r')
		try:
			btst = json.JSONDecoder().decode(f.read().strip().split('\n')[-1])
			new_initial_config = btst['initial_config']
		except:
			pass
		f.close()

		if (real_time_initial_config and (not new_initial_config)):
			new_initial_config = real_time_initial_config

		if (new_initial_config):
			t = 'backtesting'
			if (real_time_initial_config == new_initial_config):
				t = 'real_time'
			f = open(f'traders/{t}/{timer}/{coin1}-{coin2}/list.txt', 'r')
			lst = f.read().strip().split('\n')
			f.close()
			rows = []
			if (lst and lst[0]):
				for row in lst:
					tr = json.JSONDecoder().decode(row)
					if (tr['initial_config'] == new_initial_config):
						rows.append(tr)
			else: # Cargar desde backtesting porque no se encontró el trader en real_time
				t = 'backtesting'
				f = open(f'traders/{t}/{timer}/{coin1}-{coin2}/list.txt', 'r')
				lst = f.read().strip().split('\n')
				f.close()
				rows = []
				if (lst and lst[0]):
					for row in lst:
						tr = json.JSONDecoder().decode(row)
						if (tr['initial_config'] == new_initial_config):
							rows.append(tr)
			if (((real_time_initial_config != new_initial_config) or (not m)) and rows):
				m = rows[-1]
			t = btst
			if (real_time_initial_config == new_initial_config):
				t = st
			v = self.set_strategy(t, strategy.Strategy(timer, coin1, coin2, config = self.config, name = t['name']))
		if (v and (real_time_initial_config != new_initial_config)):
			self.save_strategy(v, 'real_time')
		return (v, m)


	def save_trader(self, m, mode = 'backtesting', st = None):
		statement = ''
		if (st):
			f = open(f"traders/backtesting/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'a')
			f.write(json.JSONEncoder().encode(st) + '\n')
			f.close()
		else:
			statement = {'timer' : m.timer, 'coin1' : m.coin1, 'coin2' : m.coin2, 'p_s_u' : m.p_s_u, 'p_c_u' : m.p_c_u, 'p_s_d' : m.p_s_d, 'p_c_d' : m.p_c_d, 'e_p_u' : m.e_p_u, 'e_p_d' : m.e_p_d, 'initial_config' : m.initial_config}
			self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_trader', 'data' : statement}).encode())
			self.socket.recv(5000)


	def update_trader(self, m, mode = 'backtesting', st = None):
		statement = ''
		if (m):
			statement = {'mode' : mode, 'timer' : m.timer, 'coin1' : m.coin1, 'coin2' : m.coin2, 'p_s_u' : m.p_s_u, 'p_c_u' : m.p_c_u, 'p_s_d' : m.p_s_d, 'p_c_d' : m.p_c_d, 'e_p_u' : m.e_p_u, 'e_p_d' : m.e_p_d, 'initial_config' : m.initial_config, 'last_timestamp' : m.last_timestamp}
			statement = json.JSONEncoder().encode(statement)
		if (st or (mode == 'real_time')):
			if (not st):
				st = json.JSONDecoder().decode(statement)
			else:
				st = json.JSONDecoder().decode(st)
			txt = ''
			try:
				f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'r')
			except:
				f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'w')
				f.close()
				f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'r')
			lst = f.read().strip().split('\n')
			f.close()
			for row in lst:
				if (row):
					tr = json.JSONDecoder().decode(row)
					if (tr['initial_config'] != st['initial_config']):
						txt += row + '\n'
					else:
						txt += json.JSONEncoder().encode(st) + '\n'
			if (not txt):
				txt = json.JSONEncoder().encode(st)
			f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'w')
			f.write(txt)
			f.close()
		else:
			self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'update_trader', 'data' : statement}).encode())
			self.socket.recv(5000).decode()


	def save_strategy(self, v, mode = 'backtesting', st = None):
		statement = ''
		if (v):
			statement = {'mode' : mode, 'name' : v.NAME, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'derivatives' : v.derivatives, 'initial_config' : v.initial_config}
			if (mode == 'backtesting'):
				statement['comp_initial_config'] = v.comp_initial_config
				statement['comp_last_timestamp'] = v.comp_last_timestamp
				statement['comp_prev_pl'] = v.comp_prev_pl
				statement['comp_pl'] = v.comp_pl
			statement = json.JSONEncoder().encode(statement)

		if (mode == 'backtesting'):
			if (st):
				st = json.JSONDecoder().decode(st)
				st['ready_to_use'] = False
				print('Guardando estrategia ...')
				f = open(f"strategies/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'a')
				f.write(json.JSONEncoder().encode(st) + '\n')
				f.close()
			else:
				r = None
				st2 = ''
				while (len(statement)):
					statement = list(statement)
					st2 = ''
					while ((len(st2) <= 800) and len(statement)):
						st2 += statement.pop(0)
					self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_strategy', 'data' : st2, 'ready' : False}).encode())
					self.socket.recv(5000)
				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_strategy', 'ready' : True}).encode())
				r = self.socket.recv(5000).decode()
		else:
			st = json.JSONDecoder().decode(statement)
			try:
				f = open(f"strategies/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'w')
				f.write(json.JSONEncoder().encode(st))
				f.close()
			except:
				print('No se pudo guardar la estrategia en tiempo real.')
				f = open(f"strategies/real_time/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'w')
				f.write()
				f.close()


	def update_strategy(self, v, mode = 'backtesting', st = None, timer = None, coin1 = None, coin2 = None, update_comp = True):
		statement = ''
		if (v):
			statement = {'mode' : mode, 'name' : v.NAME, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'derivatives' : v.derivatives, 'initial_config' : v.initial_config, 'stop_loss' : v.stop_loss, 'trade_type' : v.trade['type'], 'trade_timestamp' : v.trade['time'], 'trade_price' : v.trade['price'], 'trade_prev_price' : v.trade['prev_price'], 'trade_prev_timestamp' : float(v.trade['prev_time']), 'last_timestamp' : v.last_timestamp, 'pl' : v.pl, 'leverage_s' : v.leverage_s, 'leverage_l' : v.leverage_l, 'l_l_ok' : v.l_l_ok, 'l_s_ok' : v.l_s_ok, 'l_l_no' : v.l_l_no, 'l_s_no' : v.l_s_no, 'zoom_s' : v.zoom_s, 'zoom_l' : v.zoom_l, 'far_price' : v.far_price}
			if (mode == 'backtesting'):
				statement['comp_initial_config'] = v.comp_initial_config
				statement['comp_last_timestamp'] = v.comp_last_timestamp
				statement['comp_prev_pl'] = v.comp_prev_pl
				statement['comp_pl'] = v.comp_pl
				statement['ready_to_use'] = v.ready_to_use
			statement = json.JSONEncoder().encode(statement)
		if (mode == 'backtesting'):
			if (st):
				st = json.JSONDecoder().decode(st)
				new_initial_config = ''
				f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'r')
				lst = f.read().strip().split('\n')
				f.close()
				if (update_comp):
					comp = None
					# Busca la última estrategia ready_to_use y con mayor pl.
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'r')
					btst = None
					try:
						new_initial_config = json.JSONDecoder().decode(f.read().strip().split('\n')[-1])['initial_config']
					except:
						pass
					f.close()
					if (new_initial_config):
						# Busca la mejor estrategia para usarla como 'comp'.
						for row in lst:
							s = json.JSONDecoder().decode(row)
							if (s['initial_config'] == new_initial_config):
								comp = {'comp_initial_config' : new_initial_config, 'comp_last_timestamp' : float(s['last_timestamp']), 'comp_prev_pl' : s['pl']}
					return comp
				if (not new_initial_config):
					if (st['ready_to_use']):
						if (st['comp_pl'] >= st['comp_prev_pl']):
							f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'w')
							f.write(json.JSONEncoder().encode(st))
							f.close()
							print('Borrando estrategias anteriores.')
							txt = ''
							for row in lst:
								l = json.JSONDecoder().decode(row)
								if ((l['initial_config'] == st['initial_config']) or (l['initial_config'] == st['comp_initial_config']) or (l['comp_initial_config'] == st['initial_config']) or (not l['ready_to_use'])):
									txt += json.JSONEncoder().encode(l) + '\n'
							f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'w')
							f.write(txt)
							f.close()
							f = open(f'traders/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'r')
							lst = f.read().strip().split('\n')
							f.close()
							for row in lst:
								tr = json.JSONDecoder().decode(row)
								if (tr['initial_config'] == st['initial_config']):
									f = open(f'traders/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'w')
									f.write(json.JSONEncoder().encode(tr) + '\n')
									f.close()
				txt = ''
				f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'r')
				lst = f.read().strip().split('\n')
				f.close()
				for row in lst:
					if (row):
						s = json.JSONDecoder().decode(row)
						if (s['initial_config'] != st['initial_config']):
							txt += row + '\n'
						else:
							txt += json.JSONEncoder().encode(st) + '\n'
				f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/list.txt', 'w')
				f.write(txt)
				f.close()
			else:
				r = None
				st = ''
				while (len(statement)):
					statement = list(statement)
					st = ''
					while ((len(st) <= 700) and len(statement)):
						st += statement.pop(0)
					self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'update_strategy', 'data' : st, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'ready' : False}).encode())
					self.socket.recv(5000)

				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'update_strategy', 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'update_comp' : update_comp, 'ready' : True}).encode())
				r = self.socket.recv(5000).decode()
				msg_in = json.JSONDecoder().decode(r)
				return msg_in['comp']
		else:
			if (v):
				st = json.JSONDecoder().decode(statement)
				try:
					f = open(f"strategies/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'w')
					f.write(json.JSONEncoder().encode(st))
					f.close()
				except:
					print('No se pudo actualizar la estrategia en tiempo real.')
					f = open(f"strategies/real_time/{st['timer']}/{st['coin1']}-{st['coin2']}/list.txt", 'w')
					f.write('')
					f.close()
