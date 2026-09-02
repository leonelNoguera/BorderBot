from datetime import datetime
import random
import json
import strategy
class Db(object):
	def __init__(self, config = None, coin1 = None, coin2 = None, socket = None):
		super(Db, self).__init__()
		self.coin1 = coin1
		self.coin2 = coin2
		if (config and coin1 and coin2):
			self.coin1_decimals = config[self.coin1 + '-' + self.coin2]['decimals']
			self.timer = config['timer']
		self.mode = 'backtesting'
		self.socket = socket
		self.last_check = datetime.now().timestamp()
		self.config = config
		self.values_dict = {}
		self.reset_values()

	def reset_values(self):
		self.init_timestamp = 0
		self.last_price_in_list = None
		self.db_update_timestamp = 0
		self.init_timestamps = []

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
		f = None
		if (len(self.init_timestamps) < 2):
			#self.times('get_init_timestamps')
			# Obtener también todos los init_timestamp de las listas y que sean posteriores al 'last_timestamp'. Luego se buscarán los archivos de texto que tengan dichos timestamps en el nombre.
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
				if (file_exists):#Los precios de esa lista ya estaban almacenados locálmente y se actualizaron antes del último backtesting.
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

	def get_prices(self, last_timestamp = 0, prices_gap_tolerance_seconds = None):
		self.init_timestamp = last_timestamp
		# Verificar si la lista correspondiente está almacenada en archivos locales.
		fixed_time_prices, more_data = self.get_prices_local(prices_gap_tolerance_seconds, last_timestamp)
		return (fixed_time_prices, more_data)


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


	def get_next_strategy_to_test(self, coin1, coin2, timer, config2):
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
		return v


	def save_trader(self, m):
		statement = {'timer' : m.timer, 'coin1' : m.coin1, 'coin2' : m.coin2, 'p_s_u' : m.p_s_u, 'p_c_u' : m.p_c_u, 'p_s_d' : m.p_s_d, 'p_c_d' : m.p_c_d, 'e_p_u' : m.e_p_u, 'e_p_d' : m.e_p_d, 'initial_config' : m.initial_config}
		self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_trader', 'data' : statement}).encode())
		self.socket.recv(5000)


	def update_trader(self, m):
		statement = {'mode' : 'backtesting', 'timer' : m.timer, 'coin1' : m.coin1, 'coin2' : m.coin2, 'p_s_u' : m.p_s_u, 'p_c_u' : m.p_c_u, 'p_s_d' : m.p_s_d, 'p_c_d' : m.p_c_d, 'e_p_u' : m.e_p_u, 'e_p_d' : m.e_p_d, 'initial_config' : m.initial_config, 'last_timestamp' : m.last_timestamp}
		statement = json.JSONEncoder().encode(statement)
		self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'update_trader', 'data' : statement}).encode())
		self.socket.recv(5000).decode()


	def save_strategy(self, v):
		statement = {'mode' : 'backtesting', 'name' : v.NAME, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'derivatives' : v.derivatives, 'initial_config' : v.initial_config}
		statement['comp_initial_config'] = v.comp_initial_config
		statement['comp_last_timestamp'] = v.comp_last_timestamp
		statement['comp_prev_pl'] = v.comp_prev_pl
		statement['comp_pl'] = v.comp_pl
		statement = json.JSONEncoder().encode(statement)
		st2 = ''
		while (len(statement)):
			statement = list(statement)
			st2 = ''
			while ((len(st2) <= 800) and len(statement)):
				st2 += statement.pop(0)
			self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_strategy', 'data' : st2, 'ready' : False}).encode())
			self.socket.recv(5000)
		self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_strategy', 'ready' : True}).encode())
		self.socket.recv(5000).decode()


	def update_strategy(self, v, update_comp = True):
		statement = {'mode' : 'backtesting', 'name' : v.NAME, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'derivatives' : v.derivatives, 'initial_config' : v.initial_config, 'stop_loss' : v.stop_loss, 'trade_type' : v.trade['type'], 'trade_timestamp' : v.trade['time'], 'trade_price' : v.trade['price'], 'trade_prev_price' : v.trade['prev_price'], 'trade_prev_timestamp' : float(v.trade['prev_time']), 'last_timestamp' : v.last_timestamp, 'pl' : v.pl, 'leverage_s' : v.leverage_s, 'leverage_l' : v.leverage_l, 'l_l_ok' : v.l_l_ok, 'l_s_ok' : v.l_s_ok, 'l_l_no' : v.l_l_no, 'l_s_no' : v.l_s_no, 'zoom_s' : v.zoom_s, 'zoom_l' : v.zoom_l, 'far_price' : v.far_price}
		statement['comp_initial_config'] = v.comp_initial_config
		statement['comp_last_timestamp'] = v.comp_last_timestamp
		statement['comp_prev_pl'] = v.comp_prev_pl
		statement['comp_pl'] = v.comp_pl
		statement['ready_to_use'] = v.ready_to_use
		statement = json.JSONEncoder().encode(statement)

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
