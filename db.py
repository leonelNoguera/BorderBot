from datetime import datetime
import random
import json
import time
import strategy
class Db(object):
	def __init__(self):
		super(Db, self).__init__()

	def set_config(self, config = None, mode = None, coin1 = None, coin2 = None, client_name = None):
		self.coin1 = coin1
		self.coin2 = coin2
		if (config and coin1 and coin2):
			self.coin1_decimals = config[self.coin1 + '-' + self.coin2]['decimals']
			self.timer = config['timer']
		self.mode = mode
		self.last_check = datetime.now().timestamp()
		if (self.mode != 'backtesting'):
			print('Conectando a la db.')
		self.config = config
		self.values_dict = {}
		self.config_cpu_temp = None
		self.init_timestamp = 0
		self.last_price_in_list = None
		self.db_update_timestamp = 0
		self.init_timestamps = []
		self.prev_far_price_dif_l = None
		self.prev_far_price_dif_s = None
		self.client_name = client_name
		self.retest_btst_time = config[self.coin1 + '-' + self.coin2]['retest_btst_time']
		self.prom_st = None

	def get_init_timestamps(self, st_last_timestamp, last_t = False):
		c1 = self.coin1
		c2 = self.coin2
		ts = []
		lists_ok = False
		while (not lists_ok):
			lists_ok = True
			f = open(f'prices/{c1}-{c2}/lists.txt', 'r')
			lists = f.read().strip().split('\n')#['1769427124.441381_jupiter', '1769431333.370391_jupiter', ...]
			f.close()
			if (not lists):
				lists_ok = False
			if (not last_t):
				for l in lists:
					it = None
					try:
						it = float(l.split('_')[0])
					except:
						lists_ok = False
					src = ''
					try:
						src = '_' + l.split('_')[1]
					except:
						0
					if (it):
						#prices/JUP-USDT/JUP-USDT_1771508156.480666_jupiter.txt
						f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{l}.txt', 'r')
						first_t = float(f.read().split('\n')[0].split(',')[0])#['1769427124.441381_jupiter', '1769431333.370391_jupiter', ...]
						f.close()
						if (first_t > st_last_timestamp):
							updated_ok = False
							while (not updated_ok):
								updated_ok = True
								try:
									f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{l}_updated.txt', 'r')
									ts.append({'init_timestamp' : it, 'update_timestamp' : float(f.read().strip()), 'source' : src, 'first_t' : first_t})
									f.close()
								except:
									updated_ok = False
			if (last_t and lists_ok):
				f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{lists[-1]}_updated.txt', 'r')
				t = f.read().strip()
				try:
					last_t = float(t)
				except:
					0
				f.close()
				return last_t

		return ts


	def get_prices(self, coin1, coin2, st = None, last_timestamp = 0):
		self.init_timestamp = last_timestamp
		f = open(f'prices/{coin1}-{coin2}/{coin1}-{coin2}_{st}.txt', 'r')
		prices = f.read().strip()
		f.close()
		return prices


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


	def get_strategy(self, timer, coin1, coin2, config = None):
		s, m = self.get_best_strategy(coin1, coin2, timer, config)
		return (s,m)

	def get_next_strategy_to_test(self, coin1, coin2, timer):
		config2 = self.config
		v = strategy.Strategy(timer, coin1, coin2, config = self.config, name = 'bs,' + str(self.config[coin1 + '-' + coin2]['sl_initial_dif_s']) + ',' + str(self.config[coin1 + '-' + coin2]['sl_initial_dif_l']))
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

		# Generar un archivo con la lista de clientes.
		path = f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/clients_list.txt'
		clients = []
		try:
			f = open(path, 'r')
			clients = f.read().strip().split('\n')
			f.close()
		except:
			0

		if (not self.client_name in clients):
			f = open(path, 'a')
			f.write(self.client_name + '\n')
			f.close()
			clients.append(self.client_name)
		lst = []
		for c in clients:
			path = f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt'
			try:
				f = open(path, 'r')
			except:
				f = open(path, 'w')
				f.close()
				f = open(path, 'r')
			lst.extend(f.read().strip().split('\n'))
			f.close()
		
		s = None
		btst = None
		# Busca la última estrategia 'ready_to_use' y con mayor 'pl'.
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

		last_t = self.get_init_timestamps(None, True)
		rows = []
		r_or_d = False
		retest_btst = False
		for row in lst:
			if (row):
				st = None
				try:
					st = json.JSONDecoder().decode(row)
				except:
					0
				if (st):
					if (btst and (st['initial_config'] == btst['initial_config'])):
						if ((st['ready_to_use']) and ((last_t - st['last_timestamp']) > self.retest_btst_time)):
							retest_btst = True
						else:
							retest_btst = False

					if (st['ready_to_use']):
						rows.append(st)
						r_or_d = True
					if (st['initial_config'] == v.initial_config):
						r_or_d = True
		
		dif_initial_config = {'sl_s_dif' : 0, 'sl_l_dif' : 0, 'sl_reduced_dif_s' : 0, 'sl_reduced_dif_l' : 0, 'sl_initial_dif_s' : 0, 'sl_initial_dif_l' : 0, 'okno_inc_s' : 0, 'okno_inc_l' : 0, 'okno_dec_s' : 0, 'okno_dec_l' : 0, 'm_aprox_s' : 0, 'm_aprox_l' : 0, 'leverage_inc_s' : 0, 'leverage_inc_l' : 0, 'leverage_dec_s' : 0, 'leverage_dec_l' : 0, 'high_leverage_s' : 0, 'high_leverage_l' : 0, 'far_price_dif_s' : 0, 'far_price_dif_l' : 0}
		if (btst):
			v = strategy.Strategy(timer, coin1, coin2, config = config2, name = btst['name'])
			v.set_config(btst['initial_config'])
			if (not retest_btst):
				d = btst['derivatives']
				max_d = (d[0]['coin2_balance'] - d[0]['total_investment'])
				for i in range(1, len(d)):
					if (d[i]['coin2_balance'] - d[i]['total_investment'] > max_d):
						max_d = (d[i]['coin2_balance'] - d[i]['total_investment'])
				d_comp = None
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
		if (self.prom_st):
			for k in (list(self.prom_st.keys())):
				best_d = None
				d_dec = None
				d_eq = None
				d_inc = None
				if (dif_initial_config[k] == 1): # Se priorizaba incremento.
					d = self.prom_st[k]
					if (d['inc'][1] and (d['eq'][1] or d['dec'][1])): # Hay datos de alguna de las otras direcciones como para comparar.
						d_inc = d['inc'][2] / d['inc'][1]
						if (not d['eq'][1]):
							d['eq'] = None
						if (not d['dec'][1]):
							d['dec'] = None
						best_d = 1
						if (d['eq']):
							d_eq = d['eq'][2] / d['eq'][1]
							if (d_eq > d_inc):
								best_d = 0
						if (d['dec'] and (d_eq != None)):
							d_dec = d['dec'][2] / d['dec'][1]
							if (d_dec > d_eq):
								best_d = -1
				if (dif_initial_config[k] == 0):
					d = self.prom_st[k]
					if (d['eq'][1] and (d['inc'][1] or d['dec'][1])):
						d_eq = d['eq'][2] / d['eq'][1]
						if (not d['inc'][1]):
							d['inc'] = None
						if (not d['dec'][1]):
							d['dec'] = None
						best_d = 0
						if (d['inc']):
							d_inc = d['inc'][2] / d['inc'][1]
							if (d_inc > d_eq):
								best_d = 1
						if (d['dec'] and (d_inc != None)):
							d_dec = d['dec'][2] / d['dec'][1]
							if (d_dec > d_inc):
								best_d = -1

				if (dif_initial_config[k] == -1):
					d = self.prom_st[k]
					if (d['dec'][1] and (d['eq'][1] or d['inc'][1])):
						d_dec = d['dec'][2] / d['dec'][1]
						if (not d['eq'][1]):
							d['eq'] = None
						if (not d['inc'][1]):
							d['inc'] = None
						best_d = -1
						if (d['eq']):
							d_eq = d['eq'][2] / d['eq'][1]
							if (d_eq > d_dec):
								best_d = 0
						if (d['inc'] and (d_dec != None)):
							d_inc = d['inc'][2] / d['inc'][1]
							if (d_inc > d_dec):
								best_d = 1
				if (best_d != None):
					dif_initial_config[k] = best_d

		if (not retest_btst):
			st_in_files = True
			while (st_in_files):
				st_in_files = False
				v.set_config(v.initial_config)
				if (not self.prev_far_price_dif_l):
					v.sl_reduced_dif_s = self.random_var(v.sl_reduced_dif_s, config2[coin1 + '-' + coin2]['sl_reduced_dif_min'], config2[coin1 + '-' + coin2]['sl_reduced_dif_max'], config2[coin1 + '-' + coin2]['sl_reduced_dif_decimals'], dif_initial_config['sl_reduced_dif_s'])
					v.sl_reduced_dif_l = self.random_var(v.sl_reduced_dif_l, config2[coin1 + '-' + coin2]['sl_reduced_dif_min'], config2[coin1 + '-' + coin2]['sl_reduced_dif_max'], config2[coin1 + '-' + coin2]['sl_reduced_dif_decimals'], dif_initial_config['sl_reduced_dif_l'])

					v.okno_dec_s = self.random_var(v.okno_dec_s, config2[coin1 + '-' + coin2]['okno_dec_min'], config2[coin1 + '-' + coin2]['okno_dec_max'], config2[coin1 + '-' + coin2]['okno_dec_decimals'], dif_initial_config['okno_dec_s'])
					v.okno_inc_s = self.random_var(v.okno_inc_s, config2[coin1 + '-' + coin2]['okno_inc_min'], config2[coin1 + '-' + coin2]['okno_inc_max'], config2[coin1 + '-' + coin2]['okno_inc_decimals'], dif_initial_config['okno_inc_s'])
					v.okno_dec_l = self.random_var(v.okno_dec_l, config2[coin1 + '-' + coin2]['okno_dec_min'], config2[coin1 + '-' + coin2]['okno_dec_max'], config2[coin1 + '-' + coin2]['okno_dec_decimals'], dif_initial_config['okno_dec_l'])
					v.okno_inc_l = self.random_var(v.okno_inc_l, config2[coin1 + '-' + coin2]['okno_inc_min'], config2[coin1 + '-' + coin2]['okno_inc_max'], config2[coin1 + '-' + coin2]['okno_inc_decimals'], dif_initial_config['okno_inc_l'])

					v.m_aprox_s = self.random_var(v.m_aprox_s, config2[coin1 + '-' + coin2]['m_aprox_min'], config2[coin1 + '-' + coin2]['m_aprox_max'], config2[coin1 + '-' + coin2]['m_aprox_decimals'], dif_initial_config['m_aprox_s'])
					v.m_aprox_l = self.random_var(v.m_aprox_l, config2[coin1 + '-' + coin2]['m_aprox_min'], config2[coin1 + '-' + coin2]['m_aprox_max'], config2[coin1 + '-' + coin2]['m_aprox_decimals'], dif_initial_config['m_aprox_l'])

					v.sl_s_dif = self.random_var(v.sl_s_dif, config2[coin1 + '-' + coin2]['sl_dif_min'], config2[coin1 + '-' + coin2]['sl_dif_max'], config2[coin1 + '-' + coin2]['sl_dif_decimals'], dif_initial_config['sl_s_dif'])
					v.sl_l_dif = self.random_var(v.sl_l_dif, config2[coin1 + '-' + coin2]['sl_dif_min'], config2[coin1 + '-' + coin2]['sl_dif_max'], config2[coin1 + '-' + coin2]['sl_dif_decimals'], dif_initial_config['sl_l_dif'])

					v.sl_initial_dif_s = self.random_var(v.sl_initial_dif_s, config2[coin1 + '-' + coin2]['sl_initial_dif_min'], config2[coin1 + '-' + coin2]['sl_initial_dif_max'], config2[coin1 + '-' + coin2]['sl_initial_dif_decimals'], dif_initial_config['sl_initial_dif_s'])
					v.high_leverage_s = int(self.random_var(v.high_leverage_s, config2[coin1 + '-' + coin2]['high_leverage_min'], config2[coin1 + '-' + coin2]['high_leverage_max'], config2[coin1 + '-' + coin2]['high_leverage_decimals'], dif_initial_config['high_leverage_s']))
					v.far_price_dif_s = self.random_var(v.far_price_dif_s, config2[coin1 + '-' + coin2]['far_price_dif_min'], config2[coin1 + '-' + coin2]['far_price_dif_max'], config2[coin1 + '-' + coin2]['far_price_dif_decimals'], dif_initial_config['far_price_dif_s'])
				else:
					v.far_price_dif_l = self.prev_far_price_dif_l
					v.far_price_dif_s = self.prev_far_price_dif_s
					print('Se utilizaran los \'far_price_dif\' anteriores')
					self.prev_far_price_dif_l = None
					self.prev_far_price_dif_s = None

				v.sl_initial_dif_l = self.random_var(v.sl_initial_dif_l, config2[coin1 + '-' + coin2]['sl_initial_dif_min'], config2[coin1 + '-' + coin2]['sl_initial_dif_max'], config2[coin1 + '-' + coin2]['sl_initial_dif_decimals'], dif_initial_config['sl_initial_dif_l'])
				v.high_leverage_l = int(self.random_var(v.high_leverage_l, config2[coin1 + '-' + coin2]['high_leverage_min'], config2[coin1 + '-' + coin2]['high_leverage_max'], config2[coin1 + '-' + coin2]['high_leverage_decimals'], dif_initial_config['high_leverage_l']))
				v.far_price_dif_l = self.random_var(v.far_price_dif_l, config2[coin1 + '-' + coin2]['far_price_dif_min'], config2[coin1 + '-' + coin2]['far_price_dif_max'], config2[coin1 + '-' + coin2]['far_price_dif_decimals'], dif_initial_config['far_price_dif_l'])

				v.leverage_inc_s = self.random_var(v.leverage_inc_s, config2[coin1 + '-' + coin2]['leverage_inc_min'], config2[coin1 + '-' + coin2]['leverage_inc_max'], config2[coin1 + '-' + coin2]['leverage_inc_decimals'], dif_initial_config['leverage_inc_s'])
				v.leverage_dec_s = self.random_var(v.leverage_dec_s, config2[coin1 + '-' + coin2]['leverage_dec_min'], config2[coin1 + '-' + coin2]['leverage_dec_max'], config2[coin1 + '-' + coin2]['leverage_dec_decimals'], dif_initial_config['leverage_dec_s'])
				v.leverage_inc_l = self.random_var(v.leverage_inc_l, config2[coin1 + '-' + coin2]['leverage_inc_min'], config2[coin1 + '-' + coin2]['leverage_inc_max'], config2[coin1 + '-' + coin2]['leverage_inc_decimals'], dif_initial_config['leverage_inc_l'])
				v.leverage_dec_l = self.random_var(v.leverage_dec_l, config2[coin1 + '-' + coin2]['leverage_dec_min'], config2[coin1 + '-' + coin2]['leverage_dec_max'], config2[coin1 + '-' + coin2]['leverage_dec_decimals'], dif_initial_config['leverage_dec_l'])

				v.NAME = 'bs,' + str(v.sl_initial_dif_s) + ',' + str(v.sl_initial_dif_l)

				v.change_initial_config()

				lst = []
				for c in clients:
					path = f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt'
					f = open(path, 'r')
					lst.extend(f.read().strip().split('\n'))
					f.close()

				for row in lst:
					if (row):
						st = None
						try:
							st = json.JSONDecoder().decode(row)
						except:
							0
						if (st):
							if (st['initial_config'] == v.initial_config):
								st_in_files = True
							if (st['ready_to_use']):
								s = st

			# Busca la última estrategia ready_to_use y con mayor pl, para comparar con la estrategia nueva.
			if (btst and s):
				prev_comp_initial_config = s['comp_initial_config']
				if (btst['initial_config'] != s['initial_config']):
					# Ver si esa estrategia es mejor que la anterior.
					if (btst['comp_pl'] >= btst['comp_prev_pl']): # 0.0 0.0 (cuando es la estrategia original)
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
			if (btst and (not r_or_d)):
				v.set_config(btst['initial_config'])
		print(datetime.now().isoformat())
		print('Se usará una estrategia con: ' + json.JSONEncoder().encode(v.initial_config))
		if (retest_btst):
			print('retest_btst')
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
					r2 = random.randint(0,1)
					if (d > 0): # Incrementar variable.
						if (r2):
							dif = max_value - var
							var += dif * p
						else: # Incrementar lo menos posible.
							var += 1 / (1 * (10 ** decimals))
							if (not decimals):
								var += 1
					else:
						if (r2):
							dif = var - min_value
							var -= dif * p
						else: # Decrementar lo menos posible.
							var -= 1 / (1 * (10 ** decimals))
							if (not decimals):
								var -= 1

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

			clients = []
			path = f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/clients_list.txt'
			try:
				f = open(path, 'r')
				clients = f.read().strip().split('\n')
				f.close()
			except:
				0

			lst = []
			for c in clients:
				path = f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt'
				f = open(path, 'r')
				lst.extend(f.read().strip().split('\n'))
				f.close()

			lst = None
			if (t == 'real_time'):
				f = open(f'traders/{t}/{timer}/{coin1}-{coin2}/list.txt', 'r')
				lst = f.read().strip().split('\n')
				f.close()
			rows = []
			if (lst and lst[0]):
				for row in lst:
					tr = None
					try:
						tr = json.JSONDecoder().decode(row)
					except:
						0
					if (tr and (tr['initial_config'] == new_initial_config)):
						rows.append(tr)
			else: # Cargar desde backtesting porque no se encontró el trader en real_time
				t = 'backtesting'
				lst = []
				for c in clients:
					path = f'traders/{t}/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt'
					f = open(path, 'r')
					lst.extend(f.read().strip().split('\n'))
					f.close()
				rows = []
				if (lst and lst[0]):
					for row in lst:
						tr = None
						try:
							tr = json.JSONDecoder().decode(row)
						except:
							0
						if (tr and (tr['initial_config'] == new_initial_config)):
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


	def save_trader(self, st):
		f = open(f"traders/backtesting/{st['timer']}/{st['coin1']}-{st['coin2']}/clients_list/{self.client_name}_list.txt", 'a')
		f.write(json.JSONEncoder().encode(st) + '\n')
		f.close()


	def update_trader(self, mode = 'backtesting', st = None, m = None):
		if (m):
			st = {'mode' : mode, 'timer' : m.timer, 'coin1' : m.coin1, 'coin2' : m.coin2, 'p_s_u' : m.p_s_u, 'p_c_u' : m.p_c_u, 'p_s_d' : m.p_s_d, 'p_c_d' : m.p_c_d, 'e_p_u' : m.e_p_u, 'e_p_d' : m.e_p_d, 'initial_config' : m.initial_config, 'last_timestamp' : m.last_timestamp}
		else:
			st = json.JSONDecoder().decode(st)
		t = f"clients_list/{self.client_name}_"
		if (st['mode'] == 'real_time'):
			t = ''
		strategies_ok = False
		while (not strategies_ok):
			strategies_ok = True
			txt = ''
			try:
				f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/{t}list.txt", 'r')
			except:
				f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/{t}list.txt", 'w')
				f.close()
				f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/{t}list.txt", 'r')
			lst = f.read().strip().split('\n')
			f.close()
			for row in lst:
				if (row):
					tr = None
					try:
						tr = json.JSONDecoder().decode(row)
					except:
						parseable = False
						time.sleep(1)
					if (tr):
						if (tr['initial_config'] != st['initial_config']):
							txt += row + '\n'
						else:
							txt += json.JSONEncoder().encode(st) + '\n'
			if (not txt):
				txt = json.JSONEncoder().encode(st)
		f = open(f"traders/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/{t}list.txt", 'w')
		f.write(txt)
		f.close()


	def save_strategy(self, v, mode = 'backtesting', st = None):
		if (mode == 'backtesting'):
			st = json.JSONDecoder().decode(st)
			st['ready_to_use'] = False
			print('Guardando estrategia ...')
			f = open(f"strategies/{st['mode']}/{st['timer']}/{st['coin1']}-{st['coin2']}/clients_list/{self.client_name}_list.txt", 'a')
			f.write(json.JSONEncoder().encode(st) + '\n')
			f.close()
		else:#Guardando desde real_time
			statement = {'mode' : mode, 'name' : v.NAME, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'derivatives' : v.derivatives, 'initial_config' : v.initial_config}
			try:
				f = open(f"strategies/{statement['mode']}/{statement['timer']}/{statement['coin1']}-{statement['coin2']}/list.txt", 'w')
				f.write(json.JSONEncoder().encode(statement))
				f.close()
			except:
				print('No se pudo guardar la estrategia en tiempo real.')
				f = open(f"strategies/real_time/{statement['timer']}/{statement['coin1']}-{statement['coin2']}/list.txt", 'w')
				f.write()
				f.close()


	def update_strategy(self, v, mode = 'backtesting', st = None, timer = None, coin1 = None, coin2 = None, update_comp = True):
		retest_btst = False
		if (mode == 'backtesting'):
			best = None
			st = json.JSONDecoder().decode(st)
			comp = None
			# Busca la mejor estrategia para usarla como 'comp'.
			f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'r')
			best = None
			try:
				best = json.JSONDecoder().decode(f.read().strip().split('\n')[-1])
			except:
				0
			f.close()
			if (update_comp):
				if (best):
					comp = {'comp_initial_config' : best['initial_config'], 'comp_last_timestamp' : float(best['last_timestamp']), 'comp_prev_pl' : best['pl']}
				return comp
			else:
				if (best and st['ready_to_use'] and (st['initial_config'] == best['initial_config'])):
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'w')
					f.write(json.JSONEncoder().encode(st))
					f.close()
					retest_btst = True

			st_failed = False
			if (st['ready_to_use']):
				if ((st['comp_pl'] >= st['comp_prev_pl']) or retest_btst):
					path = f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/clients_list.txt'
					f = open(path, 'r')
					clients = f.read().strip().split('\n')
					f.close()

					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/best_update.txt', 'w')
					f.write(json.JSONEncoder().encode(st))
					f.close()
					print('Borrando estrategias anteriores.')
					txt = ''
					for c in clients:
						txt = ''
						f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt', 'r')
						lst = f.read().strip().split('\n')
						f.close()
						for row in lst:
							l = None
							try:
								l = json.JSONDecoder().decode(row)
							except:
								0
							if (l):
								if ((st['comp_pl'] == st['comp_prev_pl']) and (l['initial_config'] == st['comp_initial_config'])):
									best = -1
									best_prev = -1
									for d in l['derivatives']:
										if ((d['coin2_balance'] - d['total_investment']) > best_prev):
											best_prev = (d['coin2_balance'] - d['total_investment'])
									for d in st['derivatives']:
										if ((d['coin2_balance'] - d['total_investment']) > best):
											best = (d['coin2_balance'] - d['total_investment'])
									if (best_prev >= best):
										self.prev_far_price_dif_l = st['comp_initial_config']['far_price_dif_l']
										self.prev_far_price_dif_s = st['comp_initial_config']['far_price_dif_s']
								if (
									(l['initial_config'] == st['initial_config']) or 
									(l['initial_config'] == st['comp_initial_config']) or 
									(l['comp_initial_config'] == st['initial_config']) or 
									((not l['ready_to_use']) and (l['comp_last_timestamp'] >= st['last_timestamp']))
								):
									txt += json.JSONEncoder().encode(l) + '\n'
						f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt', 'w')
						f.write(txt)
						f.close()
						f = open(f'traders/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt', 'r')
						lst = f.read().strip().split('\n')
						f.close()
						for row in lst:
							tr = None
							try:
								tr = json.JSONDecoder().decode(row)
							except:
								0
							if (tr and (tr['initial_config'] == st['initial_config'])):
								f = open(f'traders/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt', 'w')
								f.write(json.JSONEncoder().encode(tr) + '\n')
								f.close()
				else:
					if (not retest_btst):
						st_failed = True
				self.prom_st = st['initial_config'].copy()
				self.prom_st.pop('type')
				self.prom_st.pop('far_price_dif_s')
				self.prom_st.pop('far_price_dif_l')
			strategies_ok = False
			while (not strategies_ok):
				path = f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/clients_list.txt'
				clients = []
				try:
					f = open(path, 'r')
					clients = f.read().strip().split('\n')
					f.close()
				except:
					0
				for k in list(self.prom_st.keys()):
					self.prom_st[k] = {'dec' : [0,0,0], 'eq' : [0,0,0], 'inc' : [0,0,0]}
				for c in clients:
					txt = ''
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt', 'r')
					lst = f.read().strip().split('\n')
					f.close()
					for row in lst:
						if (row):
							s = None
							try:
								s = json.JSONDecoder().decode(row)
								strategies_ok = True
							except:
								0
							if (s):
								if (s['initial_config'] != st['initial_config']):
									if (st_failed):
										if (s['comp_initial_config'] == st['comp_initial_config']):
											for k in list(self.prom_st.keys()):
												side = 'eq'
												if (s['initial_config'][k] > st['comp_initial_config'][k]):
													side = 'inc'
												if (s['initial_config'][k] < st['comp_initial_config'][k]):
													side = 'dec'
												self.prom_st[k][side][0] += s['initial_config'][k]
												self.prom_st[k][side][1] += 1
												self.prom_st[k][side][2] += s['comp_pl']
									txt += row + '\n'
					txt += json.JSONEncoder().encode(st) + '\n'
					f = open(f'strategies/backtesting/{timer}/{coin1}-{coin2}/clients_list/{c}_list.txt', 'w')
					f.write(txt)
					f.close()
				if (not strategies_ok):
					time.sleep(1)
		else:
			statement = {'mode' : mode, 'name' : v.NAME, 'timer' : v.timer, 'coin1' : v.coin1, 'coin2' : v.coin2, 'derivatives' : v.derivatives, 'initial_config' : v.initial_config, 'stop_loss' : v.stop_loss, 'trade_type' : v.trade['type'], 'trade_timestamp' : v.trade['time'], 'trade_price' : v.trade['price'], 'trade_prev_price' : v.trade['prev_price'], 'trade_prev_timestamp' : float(v.trade['prev_time']), 'last_timestamp' : v.last_timestamp, 'pl' : v.pl, 'leverage_s' : v.leverage_s, 'leverage_l' : v.leverage_l, 'l_l_ok' : v.l_l_ok, 'l_s_ok' : v.l_s_ok, 'l_l_no' : v.l_l_no, 'l_s_no' : v.l_s_no, 'zoom_s' : v.zoom_s, 'zoom_l' : v.zoom_l, 'far_price' : v.far_price}
			try:
				f = open(f"strategies/{statement['mode']}/{statement['timer']}/{statement['coin1']}-{statement['coin2']}/list.txt", 'w')
				f.write(json.JSONEncoder().encode(statement))
				f.close()
			except:
				print('No se pudo actualizar la estrategia en tiempo real.')
				f = open(f"strategies/real_time/{statement['timer']}/{statement['coin1']}-{statement['coin2']}/list.txt", 'w')
				f.write('')
				f.close()