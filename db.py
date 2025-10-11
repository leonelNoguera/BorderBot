from datetime import datetime
import random
import mariadb
import json
import time
import strategy
class Db(object):
	def __init__(self, config = None, mode = None, coin1 = None, coin2 = None, socket = None):
		super(Db, self).__init__()
		self.MAX_TEXT_LEN = 550000
		self.coin1 = coin1
		self.coin2 = coin2
		if (config):
			self.coin1_decimals = config[self.coin1 + '-' + self.coin2]['decimals']
			self.timer = config['timer']
		self.mode = mode
		self.socket = socket
		if (self.mode != 'backtesting'):
			print('Conectando a la db.')
			self.conn = mariadb.connect(user=config['db_user'], password=config['db_password'], host=config['db_host'], port=config['db_port'], database=config['db_database'])
			self.cur = self.conn.cursor()
		self.init_timestamp = 0
		self.last_price_in_list = None
		self.config = config


	def delete_prices(self, pair, timestamp, confirm = False):
		pair = pair.split('-')
		if (len(pair)):
			statement = "DELETE FROM prices WHERE (coin1 = '" + pair[0] + "' AND coin2 = '" + pair[1] + "' AND init_timestamp >= " + str(timestamp) + ");"
			if (confirm):
				try:
					cur = self.conn.cursor()
					cur.execute(statement)
					self.conn.commit()
					print('Precios borrados')
					return True
				except:
					print('Hubo un error')
			else:
				return statement

	def reset_strategies(self, pair, timer, cs, confirm = False):
		pair = pair.split('-')
		if (len(pair)):
			tables = ['strategies', 'traders', 'real_time_traders', 'real_time_strategies']
			if (confirm):
				best_initial_config = '{}'
				if (cs == 'y'):
					# Busca la última estrategia ready_to_use y con mayor pl.
					statement = 'SELECT last_timestamp, pl, initial_config, comp_initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + pair[0] + '" && coin2 = "' + pair[1] + '" AND ready_to_use) ORDER BY comp_last_timestamp DESC, last_timestamp DESC, pl DESC LIMIT 1;'
					cur = self.conn.cursor()
					cur.execute(statement)
					rows = cur.fetchall()
					if (rows):
						for (last_timestamp, pl, initial_config, comp_initial_config) in rows:
							# Seleccionar la mejor dentro de esa lista.
							statement = 'SELECT last_timestamp, pl, comp_pl, comp_prev_pl, initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + pair[0] + '" && coin2 = "' + pair[1] + '" AND comp_initial_config = \'' + comp_initial_config + '\' AND ready_to_use) ORDER BY comp_pl DESC, last_timestamp DESC, pl DESC LIMIT 1;'
							cur.execute(statement)
							rows2 = cur.fetchall()
							if (rows2):
								for (last_timestamp, pl, comp_pl, comp_prev_pl, initial_config) in rows2:
									# Ver si esa estrategia es mejor que la anterior.
									if (comp_pl >= comp_prev_pl):
										best_initial_config = initial_config
									else:
										best_initial_config = comp_initial_config

				prev_status = {}
				try:
					f = open('strategies.json', 'r')
					prev_status = json.JSONDecoder().decode(f.read())
					f.close()
				except:
					0
				prev_status[pair[0] + '-' + pair[1]] = {'best_initial_config' : json.JSONDecoder().decode(best_initial_config), 'timer' : timer}
				f = open('strategies.json', 'w')
				f.write(json.JSONEncoder().encode(prev_status))
				f.close()

				for t in tables:
					statement = "DELETE FROM " + t + " WHERE (coin1 = '" + pair[0] + "' AND coin2 = '" + pair[1] + "' AND timer = " + str(timer) + ");"
					try:
						cur = self.conn.cursor()
						cur.execute(statement)
						self.conn.commit()
						print('Las estrategias de la tabla \'' + t + '\' fueron borradas')
					except:
						print('Hubo un error')
				return True
			else:
				statement = ''
				for t in tables:
					statement += "DELETE FROM " + t + " WHERE (coin1 = '" + pair[0] + "' AND coin2 = '" + pair[1] + "' AND timer = " + str(timer) + ");"
				return statement

	def get_prices(self, coin1, coin2, timer_now, st = None, last_timestamp = 0, prices_gap_tolerance_seconds = None):
		self.init_timestamp = last_timestamp
		prices_joined = []
		need_more_prices = True
		fixed_time_prices = []
		statement = ''
		if (not st):
			statement = 'SELECT init_timestamp, timer, prices FROM prices WHERE (prices AND init_timestamp > ' + str(self.init_timestamp) + ' && coin1 = "' + str(coin1) + '" && coin2 = "' + str(coin2) + '") ORDER BY init_timestamp LIMIT 1;'
			if (not self.init_timestamp):
				statement = 'SELECT init_timestamp, timer, prices FROM prices WHERE (prices && coin1 = "' + str(coin1) + '" && coin2 = "' + str(coin2) + '") ORDER BY init_timestamp LIMIT 1;'
		if (self.mode == 'backtesting'):
			more_data = True
			self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_prices', 'data' : statement, 'last_timestamp' : last_timestamp}).encode())
			msg_in = json.JSONDecoder().decode(self.socket.recv(5000).decode())
			if (not msg_in['prices']):
				more_data = False
			prices_joined = []
			p = 0
			if (self.last_price_in_list):
				if ((msg_in['first_timestamp'] - self.last_price_in_list[1]) <= prices_gap_tolerance_seconds):
					prices_joined.append(self.last_price_in_list)
					p = 1
			while (len(msg_in['prices'])):
				for i in range(len(msg_in['prices'])):
					prices_joined.append([float(msg_in['prices'][i]), float(msg_in['first_timestamp'] + ((len(prices_joined) - p) * msg_in['timer']))])
				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'get_prices', 'data' : ''}).encode())
				msg_in = json.JSONDecoder().decode(self.socket.recv(5000).decode())
			fixed_prices = self.fix_prices(prices_joined, timer_now)

			self.last_price_in_list = prices_joined[-1]
			for p in fixed_prices['prices']:
				fixed_time_prices.append({'price': p, 'time' : float(fixed_prices['first_timestamp'] + (timer_now * len(fixed_time_prices)))})
			return (fixed_time_prices, more_data)
		else:
			values = {'first_timestamp' : 0, 'prices' : '', 'timer' : self.timer}
			if (st):
				statement = st
			while (need_more_prices):
				need_more_prices = False
				cur = self.conn.cursor()
				cur.execute(statement)
				rows = cur.fetchall()
				if (rows):
					for (init_timestamp, timer, prices) in rows:
						values['first_timestamp'] = float(init_timestamp)
						values['prices'] = prices.split('-')
						values['timer'] = timer
			return values


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


	def set_psc(self, m, row):
		if (type(m) == type({})):
			if (type(row) == type(())):
				p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d = row
				m['p_s_u'] = p_s_u
				m['p_c_u'] = p_c_u
				m['p_s_d'] = p_s_d
				m['p_c_d'] = p_c_d
				m['e_p_u'] = e_p_u
				m['e_p_d'] = e_p_d
			else:
				m['p_s_u'] = row['p_s_u']
				m['p_c_u'] = row['p_c_u']
				m['p_s_d'] = row['p_s_d']
				m['p_c_d'] = row['p_c_d']
				m['e_p_u'] = row['e_p_u']
				m['e_p_d'] = row['e_p_d']
		else:
			if (type(row) == type(())):
				p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d = row
				m.p_s_u = p_s_u
				m.p_c_u = p_c_u
				m.p_s_d = p_s_d
				m.p_c_d = p_c_d
				m.e_p_u = e_p_u
				m.e_p_d = e_p_d
			else:
				m.p_s_u = row['p_s_u']
				m.p_c_u = row['p_c_u']
				m.p_s_d = row['p_s_d']
				m.p_c_d = row['p_c_d']
				m.e_p_u = row['e_p_u']
				m.e_p_d = row['e_p_d']
		return m

	def set_strategy(self, row, v = None, change_comp = False):
		if (type(row) == type(())):
			init_timestamp, name, timer, derivatives, stop_loss, trade_type, trade_timestamp, trade_prev_timestamp, trade_price, trade_prev_price, aprox_s, aprox_r, last_timestamp, leverage_s, leverage_l, pl, pl_c, prev_pl, l_l_ok, l_s_ok, l_l_no, l_s_no, zoom_s, zoom_l, far_price, initial_config = row
			if (change_comp):
				init_timestamp, name, timer, derivatives, stop_loss, trade_type, trade_timestamp, trade_prev_timestamp, trade_price, trade_prev_price, aprox_s, aprox_r, last_timestamp, leverage_s, leverage_l, pl, pl_c, prev_pl, l_l_ok, l_s_ok, l_l_no, l_s_no, zoom_s, zoom_l, far_price, initial_config, comp_pl, comp_initial_config, comp_last_timestamp, comp_prev_pl = row

			v = strategy.Strategy(self, timer, self.coin1, self.coin2, config = self.config, name = name, mode = 'real_time', socket = self.socket, save = False)

			v.init_timestamp = init_timestamp
			v.last_timestamp = last_timestamp
			v.stop_loss = stop_loss
			v.trade['type'] = trade_type
			v.trade['prev_type'] = trade_type
			v.trade['time'] = trade_timestamp
			v.trade['prev_time'] = trade_prev_timestamp
			v.trade['price'] = trade_price
			v.trade['prev_price'] = trade_prev_price
			v.leverage_s = leverage_s
			v.leverage_l = leverage_l
			v.aprox_s = aprox_s
			v.aprox_r = aprox_r
			v.pl = pl
			v.pl_c = pl_c
			v.prev_pl = prev_pl
			v.l_l_ok = l_l_ok
			v.l_s_ok = l_s_ok
			v.l_l_no = l_l_no
			v.l_s_no = l_s_no
			v.zoom_s = zoom_s
			v.zoom_l = zoom_l
			v.far_price = far_price
			v.set_config(json.JSONDecoder().decode(initial_config))
			if (derivatives):
				v.derivatives = json.JSONDecoder().decode(derivatives)
			if (change_comp):
				v.comp_initial_config = comp_initial_config
				v.comp_last_timestamp = comp_last_timestamp
				v.comp_prev_pl = comp_prev_pl
				v.comp_pl = comp_pl
		else:
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
			v.pl_c = row['pl_c']
			v.prev_pl = row['prev_pl']
			v.l_l_ok = row['l_l_ok']
			v.l_s_ok = row['l_s_ok']
			v.l_l_no = row['l_l_no']
			v.l_s_no = row['l_s_no']
			v.zoom_s = row['zoom_s']
			v.zoom_l = row['zoom_l']
			v.far_price = row['far_price']
			v.comp_initial_config = row['comp_initial_config']
			v.comp_last_timestamp = row['comp_last_timestamp']
			v.comp_prev_pl = row['comp_prev_pl']
			v.comp_pl = row['comp_pl']
			v.set_config(row['initial_config'])
			v.derivatives = row['derivatives']

		return v

	def get_trader(self, m):
		# Viene del server.
		txt = ''
		statement = 'SELECT p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d, timer FROM real_time_traders WHERE (timer = ' + str(m.timer) + ' && coin1 = "' + m.coin1 + '" && coin2 = "' + m.coin2 + '");'
		cur = None
		if (self.mode != 'backtesting'):
			cur = self.conn.cursor()
			cur.execute(statement)
			rows = cur.fetchall()
			if (rows):
				print('Restaurando estrategia principal.')
				m = self.set_psc(m, rows[0])
				return True
			else:
				self.save_trader(m)
		statement = 'SELECT p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d, timer FROM traders WHERE (timer = ' + str(m.timer) + ' && coin1 = "' + m.coin1 + '" && coin2 = "' + m.coin2 + '");'
		cur = self.conn.cursor()
		cur.execute(statement)
		rows = cur.fetchall()
		if (rows):
			print('Restaurando estrategia principal.')
			m = self.set_psc(m, rows[0])
			return True
		else:
			self.save_trader(m)


	def get_strategy(self, timer, coin1, coin2, config = None, mode = 'backtesting', socket = None, m = None):
		s = None
		if (mode != 'backtesting'):
			s = self.get_best_strategy(coin1, coin2, timer, config, m, mode, socket)
		else:
			s, m2 = self.get_next_strategy_to_test(coin1, coin2, timer, config, {'p_s_u' : 0, 'p_c_u' : 0, 'p_s_d' : 0, 'p_c_d' : 0, 'e_p_u' : 0, 'e_p_d' : 0})
			if (m2):
				m = self.set_psc(m, m2)
			m.initial_config = s.initial_config
		return s


	def get_next_strategy_to_test(self, coin1, coin2, timer, config2, m):
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
			msg_in['initial_config'] = json.JSONDecoder().decode(msg_in['initial_config'])

			v = strategy.Strategy(self, timer, coin1, coin2, config = config2, name = 'bs,' + str(msg_in['initial_config']['sl_s_dif']) + ',' + str(msg_in['initial_config']['m_aprox']) + ',asl', mode = self.mode, socket = self.socket, save = False)
			self.set_strategy(msg_in, v, change_comp = True)
			m = self.set_psc(m, msg_in)
		else:
			s = config2[coin1 + '-' + coin2]['sl_s_dif']
			m_aprox = config2[coin1 + '-' + coin2]['m_aprox']

			v = strategy.Strategy(self, timer, coin1, coin2, config = config2, name = 'bs,' + str(s) + ',' + str(m_aprox) + ',asl', mode = self.mode, socket = self.socket, save = False)

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

			statement = 'SELECT initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND initial_config = \'' + v.initial_config + '\');'
			cur = self.conn.cursor()
			cur.execute(statement)
			rows = cur.fetchall()
			if (rows): # Significa que ya había una estrategia con la configuración por defecto.
				new_initial_config = ''
				# Busca la última estrategia ready_to_use y con mayor pl.
				d_comp = None
				statement = 'SELECT last_timestamp, pl, initial_config, comp_initial_config, derivatives FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND ready_to_use) ORDER BY pl DESC LIMIT 1;'
				cur.execute(statement)
				rows = cur.fetchall()
				if (rows):
					for (last_timestamp, pl, initial_config, comp_initial_config, derivatives) in rows:
						d_comp = json.JSONDecoder().decode(derivatives)
						# Seleccionar la mejor dentro de esa lista.
						statement = 'SELECT last_timestamp, pl, comp_pl, comp_prev_pl, initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND comp_initial_config = \'' + comp_initial_config + '\' AND ready_to_use) ORDER BY comp_pl DESC, pl DESC LIMIT 1;'
						cur.execute(statement)
						rows2 = cur.fetchall()
						if (rows2):
							for (last_timestamp, pl, comp_pl, comp_prev_pl, initial_config) in rows2:
								# Ver si esa estrategia es mejor que la anterior.
								if (comp_pl >= comp_prev_pl):
									new_initial_config = initial_config
								else:
									new_initial_config = comp_initial_config
				dif_initial_config = {'sl_s_dif' : 0, 'sl_l_dif' : 0, 'sl_reduced_dif' : 0, 'sl_initial_dif' : 0, 'okno_inc' : 0, 'okno_dec' : 0, 'm_aprox' : 0, 'leverage_inc' : 0, 'leverage_dec' : 0, 'high_leverage' : 0, 'far_price_dif' : 0}
				if (new_initial_config):
					statement = 'SELECT name, initial_config, comp_initial_config, derivatives FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND ready_to_use AND initial_config = \'' + new_initial_config + '\') LIMIT 1;'
					cur = self.conn.cursor()
					cur.execute(statement)
					rows = cur.fetchall()
					for (name, initial_config, comp_initial_config, derivatives) in rows:
						v = strategy.Strategy(self, timer, coin1, coin2, config = config2, name = name, mode = self.mode, socket = self.socket, save = False)
						initial_config = json.JSONDecoder().decode(initial_config)
						comp_initial_config = json.JSONDecoder().decode(comp_initial_config)
						v.set_config(initial_config)

						d = json.JSONDecoder().decode(derivatives)
						max_d = (d[0]['coin2_balance'] - d[0]['total_investment'])
						for i in range(1, len(d)):
							if (d[i]['coin2_balance'] - d[i]['total_investment'] > max_d):
								max_d = (d[i]['coin2_balance'] - d[i]['total_investment'])
						max_d_comp = (d_comp[0]['coin2_balance'] - d_comp[0]['total_investment'])
						for i in range(1, len(d_comp)):
							if (d_comp[i]['coin2_balance'] - d_comp[i]['total_investment'] > max_d_comp):
								max_d_comp = (d_comp[i]['coin2_balance'] - d_comp[i]['total_investment'])

						if (comp_initial_config):
							dif_initial_config = {'sl_s_dif' : 0, 'sl_l_dif' : 0, 'sl_reduced_dif' : 0, 'sl_initial_dif' : 0, 'okno_inc' : 0, 'okno_dec' : 0, 'm_aprox' : 0, 'leverage_inc' : 0, 'leverage_dec' : 0, 'high_leverage' : 0, 'far_price_dif' : 0}
							keys = list(initial_config.keys())[1:]
							for k in keys:
								r = 0
								if (initial_config[k] < comp_initial_config[k]):
									r = -1
								if (initial_config[k] > comp_initial_config[k]):
									r = 1

								# Este se calcula diferente debido a que es una variable que no influye en 'pl', por lo cual no tendría una correlación.
								if ((k == 'far_price_dif') and (max_d < max_d_comp)):
									r = r * -1

								dif_initial_config[k] = r

				prev_leverage_inc = v.leverage_inc
				prev_leverage_dec = v.leverage_dec
				rows = True
				while (rows):
					v.set_config(json.JSONDecoder().decode(v.initial_config))
					v.sl_reduced_dif = self.random_var(v.sl_reduced_dif, config2[coin1 + '-' + coin2]['sl_reduced_dif_min'], config2[coin1 + '-' + coin2]['sl_reduced_dif_max'], config2[coin1 + '-' + coin2]['sl_reduced_dif_decimals'], dif_initial_config['sl_reduced_dif'])
					v.sl_initial_dif = self.random_var(v.sl_initial_dif, config2[coin1 + '-' + coin2]['sl_initial_dif_min'], config2[coin1 + '-' + coin2]['sl_initial_dif_max'], config2[coin1 + '-' + coin2]['sl_initial_dif_decimals'], dif_initial_config['sl_initial_dif'])
					v.okno_dec = self.random_var(v.okno_dec, config2[coin1 + '-' + coin2]['okno_dec_min'], config2[coin1 + '-' + coin2]['okno_dec_max'], config2[coin1 + '-' + coin2]['okno_dec_decimals'], dif_initial_config['okno_dec'])
					v.okno_inc = self.random_var(v.okno_inc, config2[coin1 + '-' + coin2]['okno_inc_min'], config2[coin1 + '-' + coin2]['okno_inc_max'], config2[coin1 + '-' + coin2]['okno_inc_decimals'], dif_initial_config['okno_inc'])
					v.m_aprox = self.random_var(v.m_aprox, config2[coin1 + '-' + coin2]['m_aprox_min'], config2[coin1 + '-' + coin2]['m_aprox_max'], config2[coin1 + '-' + coin2]['m_aprox_decimals'], dif_initial_config['m_aprox'])
					v.sl_s_dif = self.random_var(v.sl_s_dif, config2[coin1 + '-' + coin2]['sl_dif_min'], config2[coin1 + '-' + coin2]['sl_dif_max'], config2[coin1 + '-' + coin2]['sl_dif_decimals'], dif_initial_config['sl_s_dif'])
					v.sl_l_dif = v.sl_s_dif
					v.high_leverage = int(self.random_var(v.high_leverage, config2[coin1 + '-' + coin2]['high_leverage_min'], config2[coin1 + '-' + coin2]['high_leverage_max'], config2[coin1 + '-' + coin2]['high_leverage_decimals'], dif_initial_config['high_leverage']))
					#print(v.far_price_dif)
					v.far_price_dif = self.random_var(v.far_price_dif, config2[coin1 + '-' + coin2]['far_price_dif_min'], config2[coin1 + '-' + coin2]['far_price_dif_max'], config2[coin1 + '-' + coin2]['far_price_dif_decimals'], dif_initial_config['far_price_dif'])
					#input(v.far_price_dif)
					dif_ok = False
					while (not dif_ok):
						v.leverage_inc = prev_leverage_inc
						v.leverage_dec = prev_leverage_dec
						v.leverage_inc = self.random_var(v.leverage_inc, config2[coin1 + '-' + coin2]['leverage_inc_min'], config2[coin1 + '-' + coin2]['leverage_inc_max'], config2[coin1 + '-' + coin2]['leverage_inc_decimals'], dif_initial_config['leverage_inc'])
						v.leverage_dec = self.random_var(v.leverage_dec, config2[coin1 + '-' + coin2]['leverage_dec_min'], config2[coin1 + '-' + coin2]['leverage_dec_max'], config2[coin1 + '-' + coin2]['leverage_dec_decimals'], dif_initial_config['leverage_dec'])
						if (v.leverage_inc < v.leverage_dec):
							dif_ok = True

					v.NAME = 'bs,' + str(v.sl_s_dif) + ',' + str(v.m_aprox) + ',asl'

					v.change_initial_config()
					statement = 'SELECT initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND initial_config = \'' + v.initial_config + '\');'
					cur.execute(statement)
					rows = cur.fetchall()
			print('Se usará una estrategia con: ' + v.initial_config)
			# Busca la última estrategia ready_to_use y con mayor pl, para comparar con la estrategia nueva.
			statement = 'SELECT last_timestamp, pl, initial_config, comp_initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND ready_to_use) ORDER BY comp_last_timestamp DESC, last_timestamp DESC LIMIT 1;'
			cur.execute(statement)
			rows = cur.fetchall()
			if (rows):
				for (last_timestamp, pl, initial_config, comp_initial_config) in rows:
					# Seleccionar la mejor dentro de esa lista.
					statement = 'SELECT last_timestamp, comp_last_timestamp, pl, comp_pl, comp_prev_pl, initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND comp_initial_config = \'' + comp_initial_config + '\' AND ready_to_use) ORDER BY comp_pl DESC, last_timestamp DESC, pl DESC LIMIT 1;'
					cur.execute(statement)
					rows2 = cur.fetchall()
					if (rows2):
						for (last_timestamp, comp_last_timestamp, pl, comp_pl, comp_prev_pl, initial_config) in rows2:
							# Ver si esa estrategia es mejor que la anterior.
							if (comp_pl >= comp_prev_pl): # 0.0 0.0 (cuando es la estrategia original)
								v.comp_initial_config = initial_config
								v.comp_last_timestamp = last_timestamp
								v.comp_prev_pl = pl
							else:
								v.comp_initial_config = comp_initial_config
								v.comp_last_timestamp = comp_last_timestamp
								v.comp_prev_pl = comp_prev_pl
					else: # No había otras estrategias.
						v.comp_initial_config = initial_config
						v.comp_last_timestamp = last_timestamp
						v.comp_prev_pl = pl
		return (v, m)


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


	def get_best_strategy(self, coin1, coin2, timer, config2, m, mode, socket):
		v = None
		real_time_initial_config = ''
		statement = 'SELECT initial_config FROM real_time_strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '") ORDER BY last_timestamp DESC, pl DESC LIMIT 1;'
		cur = self.conn.cursor()
		cur.execute(statement)
		rows = cur.fetchall()
		if (rows):
			for (initial_config,) in rows:
				real_time_initial_config = initial_config

		new_initial_config = ''
		# Busca la última estrategia ready_to_use y con mayor pl.
		statement = 'SELECT last_timestamp, pl, initial_config, comp_initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND ready_to_use) ORDER BY comp_last_timestamp DESC, last_timestamp DESC, pl DESC LIMIT 1;'
		cur.execute(statement)
		rows = cur.fetchall()
		if (rows):
			for (last_timestamp, pl, initial_config, comp_initial_config) in rows:
				# Seleccionar la mejor dentro de esa lista.
				statement = 'SELECT last_timestamp, pl, comp_pl, comp_prev_pl, initial_config FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND comp_initial_config = \'' + comp_initial_config + '\' AND ready_to_use) ORDER BY comp_pl DESC, last_timestamp DESC, pl DESC LIMIT 1;'
				cur.execute(statement)
				rows2 = cur.fetchall()
				if (rows2):
					for (last_timestamp, pl, comp_pl, comp_prev_pl, initial_config) in rows2:
						# Ver si esa estrategia es mejor que la anterior.
						if (comp_pl >= comp_prev_pl):
							new_initial_config = initial_config
						else:
							new_initial_config = comp_initial_config
		if (real_time_initial_config and (not new_initial_config)):
			new_initial_config = real_time_initial_config

		if (new_initial_config):
			t = ''
			if (real_time_initial_config == new_initial_config):
				t = 'real_time_'
				if (m.initial_config != new_initial_config):
					statement = 'SELECT p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d FROM real_time_traders WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '") ORDER BY last_timestamp DESC LIMIT 1;'
					cur.execute(statement)
					rows = cur.fetchall()
					if (rows):
						m = self.set_psc(m, rows[0])
						m.initial_config = new_initial_config
			else:
				statement = 'DELETE FROM real_time_traders WHERE (coin1 = "' + coin1 + '" AND coin2 = "' + coin2 + '" AND timer = ' + str(timer) + ' AND initial_config != \'' + new_initial_config + '\');'
				cur.execute(statement)
				self.conn.commit()

				statement = 'SELECT p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d FROM traders WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '") ORDER BY last_timestamp DESC LIMIT 1;'
				cur.execute(statement)
				rows = cur.fetchall()
				if (rows):
					m = self.set_psc(m, rows[0])
					m.initial_config = new_initial_config
				statement = """INSERT INTO real_time_traders (coin1, coin2, p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d, timer, initial_config) VALUES ('{}', '{}', {}, {}, {}, {}, {}, {}, {}, '{}');""".format(m.coin1, m.coin2, m.p_s_u, m.p_c_u, m.p_s_d, m.p_c_d, m.e_p_u, m.e_p_d, m.timer, new_initial_config)
				cur.execute(statement)
				self.conn.commit()

				statement = 'DELETE FROM real_time_strategies WHERE (coin1 = "' + coin1 + '" AND coin2 = "' + coin2 + '" AND timer = ' + str(timer) + ' AND initial_config != \'' + new_initial_config + '\');'
				cur.execute(statement)
				self.conn.commit()

			statement = 'SELECT init_timestamp, name, timer, derivatives, stop_loss, trade_type, trade_timestamp, trade_prev_timestamp, trade_price, trade_prev_price, aprox_s, aprox_r, last_timestamp, leverage_s, leverage_l, pl, pl_c, prev_pl, l_l_ok, l_s_ok, l_l_no, l_s_no, zoom_s, zoom_l, far_price, initial_config FROM ' + t + 'strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND initial_config = \'' + new_initial_config + '\') ORDER BY last_timestamp DESC LIMIT 1;'
			cur.execute(statement)
			rows = cur.fetchall()
			if (rows):
				v = self.set_strategy(rows[0])
		if (v and (real_time_initial_config != new_initial_config)):
			self.save_strategy(v, 'real_time')
		return v


	def save_trader(self, m, mode = 'backtesting', st = None):
		txt = ''
		if (mode == 'real_time'):
			txt += 'real_time_'
		# Pendiente modificar initial_config para que admita varias variantes y tal vez optimizar el bot.
		statement = ''
		if (m):
			statement = """INSERT INTO {}traders (coin1, coin2, p_s_u, p_c_u, p_s_d, p_c_d, e_p_u, e_p_d, timer, initial_config) VALUES ('{}', '{}', {}, {}, {}, {}, {}, {}, {}, \'{}\');""".format(txt, m.coin1, m.coin2, m.p_s_u, m.p_c_u, m.p_s_d, m.p_c_d, m.e_p_u, m.e_p_d, m.timer, m.initial_config)
		cur = None
		if (self.mode != 'backtesting'):
			cur = self.conn.cursor()
		if (mode == 'backtesting'):
			if (st):
				cur.execute(st)
				self.conn.commit()
			else:
				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_trader', 'data' : statement}).encode())
				self.socket.recv(5000)
		else:
			cur.execute(statement)
			self.conn.commit()


	def update_trader(self, m, mode = 'backtesting', st = None):
		txt = ''
		if (mode == 'real_time'):
			txt += 'real_time_'
		statement = ''
		if (m):
			statement = 'UPDATE ' + txt + 'traders SET p_s_u = ' + str(m.p_s_u) + ', p_c_u = ' + str(m.p_c_u) + ', p_s_d = ' + str(m.p_s_d) + ', p_c_d = ' + str(m.p_c_d) + ', e_p_u = ' + str(m.e_p_u) + ', e_p_d = ' + str(m.e_p_d) +  ', last_timestamp = ' + str(m.last_timestamp) + ' WHERE (coin1 = "' + m.coin1 + '" && coin2 = "' + m.coin2 + '" && timer = ' + str(m.timer) + ' && initial_config = \'' + str(m.initial_config) + '\');'
		cur = None
		if (self.mode != 'backtesting'):
			cur = self.conn.cursor()
		if (mode == 'backtesting'):
			if (st):
				cur.execute(st)
				self.conn.commit()
			else:
				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'update_trader', 'data' : statement}).encode())
				self.socket.recv(5000).decode()
		else:
			cur.execute(statement)
			self.conn.commit()


	def save_strategy(self, v, mode = 'backtesting', st = None):
		txt = ''
		t = ''
		t2 = ''
		if (v):
			t = ', comp_initial_config, comp_last_timestamp, comp_prev_pl, comp_pl'
			t2 = ', \'' + v.comp_initial_config + '\', ' + str(v.comp_last_timestamp) + ', ' + str(v.comp_prev_pl) + ', ' + str(v.comp_pl)
		if (mode == 'real_time'):
			txt = 'real_time_'
			t = ''
			t2 = ''
		statement = ''
		if (v):
			statement = """INSERT INTO {}strategies (name, timer, coin1, coin2, derivatives, last_timestamp, pl, leverage_s, leverage_l, l_l_ok, l_s_ok, l_l_no, l_s_no, zoom_s, zoom_l, far_price, initial_config{}) VALUES ('{}', {}, '{}', '{}', '{}', {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, '{}'{});""".format(txt, t, v.NAME, v.timer, v.coin1, v.coin2, json.JSONEncoder().encode(v.derivatives), 0, v.pl, int(v.leverage_s), int(v.leverage_l), v.l_l_ok, v.l_s_ok, v.l_l_no, v.l_s_no, v.zoom_s, v.zoom_l, v.far_price, v.initial_config, t2)

		if (mode == 'backtesting'):
			if (st):
				cur = self.conn.cursor()
				cur.execute(st)
				self.conn.commit()
			else:
				r = None
				st2 = ''
				while (len(statement)):
					statement = list(statement)
					st2 = ''
					while ((len(st2) <= 1000) and len(statement)):
						st2 += statement.pop(0)
					self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_strategy', 'data' : st2, 'ready' : False}).encode())
					self.socket.recv(5000)
				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'save_strategy', 'ready' : True}).encode())
				r = self.socket.recv(5000).decode()
		else:
			cur = self.conn.cursor()
			cur.execute(statement)
			self.conn.commit()


	def update_strategy(self, v, mode = 'backtesting', st = None, timer = None, coin1 = None, coin2 = None, update_comp = True):
		if (v):
			txt = ''
			t = ', ready_to_use = ' + str(v.ready_to_use) + ', comp_initial_config = \'' + v.comp_initial_config + '\', comp_last_timestamp = ' + str(v.comp_last_timestamp) + ', comp_prev_pl = ' + str(v.comp_prev_pl) + ', comp_pl = ' + str(v.comp_pl)
			if (mode == 'real_time'):
				txt = 'real_time_'
				t = ''
			statement = 'UPDATE ' + txt + 'strategies SET derivatives = \'' + json.JSONEncoder().encode(v.derivatives) + '\', stop_loss = ' + str(v.stop_loss) + ', trade_type = "' + str(v.trade['type']) + '", trade_timestamp = ' + str(v.trade['time']) + ', trade_price = ' + str(v.trade['price']) + ', trade_prev_price = ' + str(v.trade['prev_price']) + ', last_timestamp = ' + str(v.last_timestamp) + ', pl = ' + str(v.pl) + ', leverage_s = ' + str(int(v.leverage_s)) + ', leverage_l = ' + str(int(v.leverage_l)) + ', l_l_ok = ' + str(v.l_l_ok) + ', l_s_ok = ' + str(v.l_s_ok) + ', l_l_no = ' + str(v.l_l_no) + ', l_s_no = ' + str(v.l_s_no) + ', zoom_s = ' + str(v.zoom_s) + ', zoom_l = ' + str(v.zoom_l) + ', far_price = ' + str(v.far_price) + t + ' WHERE (name = "' + v.NAME + '" && timer = ' + str(v.timer) + ' && coin1 = "' + v.coin1 + '" && coin2 = "' + v.coin2 + '" && initial_config = \'' + v.initial_config + '\');'
		if (mode == 'backtesting'):
			if (st):
				cur = self.conn.cursor()
				cur.execute(st)
				self.conn.commit()

				comp = None
				if (update_comp):
					# Busca la última estrategia que esté testeando para usar el mismo comp_initial_config.
					statement = 'SELECT comp_initial_config, comp_last_timestamp, comp_prev_pl FROM strategies WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND NOT ready_to_use AND comp_last_timestamp) ORDER BY comp_last_timestamp DESC LIMIT 1;'
					cur.execute(statement)
					rows = cur.fetchall()
					if (rows):
						for (comp_initial_config, comp_last_timestamp, comp_prev_pl) in rows:
							comp = {'comp_initial_config' : comp_initial_config, 'comp_last_timestamp' : comp_last_timestamp, 'comp_prev_pl' : comp_prev_pl}
				return comp
			else:
				r = None
				st = ''
				while (len(statement)):
					statement = list(statement)
					st = ''
					while ((len(st) <= 1000) and len(statement)):
						st += statement.pop(0)
					self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'update_strategy', 'data' : st, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'ready' : False}).encode())
					self.socket.recv(5000)

				self.socket.send(json.JSONEncoder().encode({'type' : 'SQL', 'sub-type' : 'update_strategy', 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'update_comp' : update_comp, 'ready' : True}).encode())
				r = self.socket.recv(5000).decode()
				msg_in = json.JSONDecoder().decode(r)
				return msg_in['comp']
		else:
			if (v):
				cur = self.conn.cursor()
				cur.execute(statement)
				self.conn.commit()
