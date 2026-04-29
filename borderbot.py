from datetime import datetime
import time
import json
import sys
import db_client

class BorderBot(object):
	"""docstring for BorderBot"""
	def __init__(self, args, socket = None, config = None):
		super(BorderBot, self).__init__()
		self.socket = socket
		self.config = config
		self.timer = config['timer']
		self.sleep_timer = config['timer']

		if (len(args)):
			self.coin1 = args[0].split('-')[0]
			self.coin2 = args[0].split('-')[1]
		else:
			self.coin1 = self.config['pair'].split('-')[0]
			self.coin2 = self.config['pair'].split('-')[1]
		self.dt = self.config[self.coin1 + '-' + self.coin2]['dif_tolerance'] # La tolerancia de diferencia de precios entre cada periodo (10 segundos por defecto). Si la diferencia es mayor a dicha variable, no simulará operaciones con ese precio.

		# Esta variable contiene el timestamp a partir del cual se tendrán en cuenta las diferencias de precios por encima de la tolerancia establecida.
		# Se asigna manuálmente por el usuario, en casos de haber alta volatilidad (pero realista) en los precios guardados.
		self.last_dif_t = self.config[self.coin1 + '-' + self.coin2]['last_dif_timestamp']

		self.derivatives = [{'position' : 'close', 'coin2_balance' : 1, 'min_zoom' : {'c' : '>=', 'n' : 0}, 'total_investment' : 1}]

		self.price_source = 'db'
		self.prev_price = 0
		self.p_s_u = 0
		self.e_p_u = 0
		self.p_c_u = 0
		self.p_s_d = 0
		self.e_p_d = 0
		self.p_c_d = 0
		self.last_timestamp = 0
		self.fee_p_c = 0
		self.fee_p_a = 0
		#if (self.simulate_trading):
		self.db = db_client.Db(self.config, self.coin1, self.coin2, self.socket)
		self.strategy = None
		self.last_up_down_priority = self.config[self.coin1 + '-' + self.coin2]['last_up_down_priority'] # Cuanta prioridad se le dará a la última diferencia de precios respecto al promedio general.
		self.min_fee = self.config[self.coin1 + '-' + self.coin2]['min_fee']
		self.fee_multiplier = self.config[self.coin1 + '-' + self.coin2]['fee_multiplier']
		self.fee_long = self.min_fee
		self.fee_short = self.min_fee
		self.prices_gap_tolerance_seconds = self.config['prices_gap_tolerance_seconds']
		self.min_balance = self.config['min_balance']


	def start(self):
		"""Se inicia el bot, en tiempo real o en backtesting"""
		self.values = []
		self.trade_type = None
		if (self.db):
			self.derivatives = [{'position' : 'close', 'coin2_balance' : 1, 'min_zoom' : {'c' : '>=', 'n' : 0}, 'total_investment' : 1}]
			self.db.reset_values()
		self.analyze()


	def validate_dif(self, j, prev_omitted):
		"""
			Calcula la diferencia promedio entre un precio y el anterior.
			También revisa la diferencia entre el precio actual y el anterior. Si la diferencia parece realista (no es demasiada), el precio se toma como válido.
			En caso de detectar precios inválidos, se almacenan los timestamp en archivos (por ejemplo: 'prices/dif_DRIFT-USDT_10_real_time.txt') por si el usuario quire revisarlos luego.
		"""
		omit = False
		last_price = self.values[j]['price']
		prev_price = self.values[j - 1]['price']
		c = (self.values[j]['time'] - self.values[j - 1]['time']) / self.timer

		for i in range(2):
			dif = (last_price / prev_price) - 1
			p_c = self.p_c_u
			p_s = self.p_s_u
			p_s_e = self.e_p_u
			if (i):
				dif = (prev_price / last_price) - 1
				p_c = self.p_c_d
				p_s = self.p_s_d
				p_s_e = self.e_p_d
			prev_m = None
			if (p_c):
				prev_m = p_s / p_c
			else:
				p_s_e = dif
			if (((i == 0) and (last_price > prev_price)) or ((i == 1) and (last_price < prev_price))):
				p_c += c
				p_s += dif
				k = j - 2
				prev = None
				while (k >= 0):
					if (self.values[k]['price'] != prev_price):
						prev = self.values[k + 1]
						k = -1
					k -= 1
				if (prev):
					# La cantidad de periodos desde que comenzó el precio anterior.
					# 101 100 100 100 99
					#	 este
					c = (self.values[j]['time'] - prev['time']) / self.timer
					dif = dif / c
				p_s_e = (((p_s / p_c) * self.last_up_down_priority) + dif) / (self.last_up_down_priority + 1)
			if (last_price == prev_price):
				p_c += c
			if (p_c):
				p = p_s / p_c
				if (dif >= (p + self.dt)):
					omit = True
					if (self.values[j]['time'] > self.last_dif_t):
						t = 'La diferencia es: ' + str(dif) + ' en ' + str(self.values[j]['time'])
						print(t)
						f = open('prices/dif_' + self.coin1 + '-' + self.coin2 + '_' + str(self.timer) + '_backtesting.txt', 'a')
						f.write(t + '\n')
						f.close()
				else:
					if (prev_omitted and (last_price == prev_price)):
						omit = True
				if (prev_m):
					if (i):
						self.fee_long = (p_s_e / self.timer * self.fee_multiplier) + self.min_fee
					else:
						self.fee_short = (p_s_e / self.timer * self.fee_multiplier) + self.min_fee

			if (i):
				self.p_c_d = p_c
				self.p_s_d = p_s
				self.e_p_d = p_s_e
			else:
				self.p_c_u = p_c
				self.p_s_u = p_s
				self.e_p_u = p_s_e
		return omit


	def change_trade(self, leverage_s, leverage_l, zoom_s, zoom_l, j):
		"""
			Cierra una posición y abre otra.
		"""
		for i in range(2):
			trade_type = 'long'
			zoom = zoom_l
			fee = self.fee_short
			fee2 = self.fee_long
			leverage = leverage_l
			leverage2 = leverage_s
			if (i):
				trade_type = 'short'
				zoom = zoom_s
				fee = self.fee_long
				fee2 = self.fee_short
				leverage = leverage_s
				leverage2 = leverage_l
			if (self.trade_type == trade_type):
				leverage_dif = 0
				if (self.prev_price):
					leverage_dif = ((self.prev_price / (self.values[j]['price'] * (1 + (fee * 0.5)))) - 1) * int(leverage2)
					if (trade_type == 'short'):
						leverage_dif = ((self.values[j]['price'] / (self.prev_price * (1 + (fee * 0.5)))) - 1) * int(leverage2)
				for d in self.derivatives:
					c = d['min_zoom']['c']
					n = d['min_zoom']['n']
					if (d['position'] != 'close'):# El short/long anterior estaba abierto.
						if (((c == '>') and (zoom > n)) or ((c == '>=') and (zoom >= n))): # Hay zoom para el short/long.
							c2 = d['coin2_balance'] * (1 + leverage_dif)
							if (c2 < 0):
								c2 = self.min_balance
								d['total_investment'] += 1
							else:
								if (c2 < self.min_balance):
									c2 += 1
									d['total_investment'] += 1
							d['coin2_balance'] = c2 * (1 - (fee2 * 0.5 * int(leverage)))
							d['position'] = trade_type
						else:
							d['coin2_balance'] = d['coin2_balance'] * (1 + leverage_dif)
							d['position'] = 'close'
					else:
						if (((c == '>') and (zoom > n)) or ((c == '>=') and (zoom >= n))):
							if (d['coin2_balance'] < 0):
								d['coin2_balance'] = self.min_balance
								d['total_investment'] += 1
							else:
								if (d['coin2_balance'] < self.min_balance):
									d['coin2_balance'] += 1
									d['total_investment'] += 1
							d['coin2_balance'] = d['coin2_balance'] * (1 - (fee2 * 0.5 * int(leverage)))
							d['position'] = trade_type

					if (d['coin2_balance'] >= 0):
						if (d['coin2_balance'] <= 0.4):
							d['coin2_balance'] += 1
							d['total_investment'] += 1
					else:
						d['coin2_balance'] = 1
						d['total_investment'] += 1


	def analyze(self):
		"""
			Asigna al trader la que es, teóricamante, la mejor estrategia hasta el momento.
			Muestra cierta información al abrir una posición.
		"""
		leverage_s = 1
		leverage_l = 1
		zoom_s = 0
		zoom_l = 0
		c1 = self.coin1
		c2 = self.coin2
		print('Obteniendo precios de la db.')
		omit = False
		more_data = True
		self.strategy = self.db.get_next_strategy_to_test(self.coin1, self.coin2, self.timer, self.config)
		self.initial_config = self.strategy.initial_config
		self.db.save_strategy(self.strategy)
		self.db.save_trader(self)
		aux_pl = None
		prev_time = None
		while (more_data):
			prev_omitted = False
			if (omit):
				prev_omitted = True
			omit = False
			more_data = False
			prev_value = -1
			self.values, more_data = self.db.get_prices(self.strategy.last_timestamp, self.prices_gap_tolerance_seconds)
			if (self.values and len(self.values)):
				j = 0
				initial = 1
				while ((self.values[j]['time'] <= self.db.init_timestamp) and ((j + 1) < len(self.values))):
					j += 1
				initial = j
				if (initial < 1):
					initial = 1
				zoom_s = self.strategy.zoom_s
				zoom_l = self.strategy.zoom_l
				leverage_s = int(self.strategy.leverage_s)
				leverage_l = int(self.strategy.leverage_l)
				for j in range(initial, len(self.values)):
					self.last_timestamp = self.values[j]['time']
					omit = self.validate_dif(j, prev_omitted)
					if ((self.values[j]['price'] != prev_value) and (not omit)):
						if (self.strategy.last_timestamp < self.values[j]['time']):
							self.strategy.change_status(self.values, j, self.fee_short, self.fee_long)
							if (self.values[j]['time'] <= self.strategy.comp_last_timestamp): # Está en el last_timestamp de la estrategia anterior.
								self.strategy.comp_pl = self.strategy.pl
						if (self.strategy.trade['type'] and (self.strategy.trade['type'] != self.trade_type)):
							self.trade_type = self.strategy.trade['type']
							if (self.trade_type == 'short'):
								zoom_s = self.strategy.zoom_s
								leverage_s = int(self.strategy.leverage_s)
							else:
								zoom_l = self.strategy.zoom_l
								leverage_l = int(self.strategy.leverage_l)
							self.change_trade(leverage_s, leverage_l, zoom_s, zoom_l, j)

							t = '\tSiguiendo a la estrategia: ' + self.strategy.NAME + ', ' + self.strategy.trade['type'] + ', ' + datetime.fromtimestamp(self.values[j]['time']).isoformat() + ', ' + str(self.values[j]['price']) + '\n\tleverage_s: ' + str(leverage_s) + '\n\tleverage_l: ' + str(leverage_l) + '\n\tzoom_s: ' + str(self.strategy.zoom_s) + '\n\tzoom_l: ' + str(self.strategy.zoom_l) + '\n\tfee short: ' + str(self.fee_short) + '\n\tfee long: ' + str(self.fee_long)
							self.fee_p_a += (self.fee_short + self.fee_long) * 0.5
							self.fee_p_c += 1

							for d in self.strategy.derivatives:
								t2 = ''
								if (d['wait_far_price_dif']):
									t2 += 'far_price_dif >= ' + str(d['far_price_dif_s']) + ',' + str(d['far_price_dif_l'])
								if (d['wait_zoom']):
									t2 += 'zoom ' + str(d['min_zoom']['c']) + ' ' + str(d['min_zoom']['n'])
								t += '\n\tstrategy derivatives, ' + d['position'] + ', ' + t2 + ', ' + str(d['coin2_balance']) + ' USD, investment: ' + str(d['total_investment']) + ', leverage: ' + str(int(d['leverage']))
							for d in self.derivatives:
								t += '\n\tderivatives, zoom ' + str(d['min_zoom']['c']) + ' ' + str(d['min_zoom']['n']) + ', ' + str(d['coin2_balance']) + ' USD, investment: ' + str(d['total_investment'])

							t += '\n\tfee promedio: ' + str(self.fee_p_a / self.fee_p_c)
							t += '\n\tleverage_l_ok: ' + str(self.strategy.l_l_ok) + ', leverage_l_no: ' + str(self.strategy.l_l_no)
							t += '\n\tleverage_s_ok: ' + str(self.strategy.l_s_ok) + ', leverage_s_no: ' + str(self.strategy.l_s_no)
							print(t)
							self.prev_price = self.values[j]['price']
						prev_value = self.values[j]['price']
					# Cuando volvió a la normalidad. Se asigna el último 'pl'.
					if (prev_time and ((self.values[j]['time'] - prev_time) >= self.prices_gap_tolerance_seconds)):
						self.strategy.prev_pl -= (self.strategy.pl - aux_pl)
					prev_time = self.values[j]['time']
				# Antes del corte. Se toma el último 'pl'.
				aux_pl = self.strategy.pl
				aux_price = self.values[-1]['price']
				if ((self.values[-1]['time'] + (self.timer * 10)) >= self.strategy.comp_last_timestamp):
					print("Se habilita la actualización por si hay un nuevo 'comp'.")
					self.db.update_trader(self)
				self.strategy.last_timestamp = self.db.last_price_in_list['time']
				if ((self.values[-1]['time'] + (self.timer * 10)) >= self.strategy.comp_last_timestamp):
					comp = self.db.update_strategy(self.strategy)
					if (comp and (self.strategy.comp_initial_config != comp['comp_initial_config'])):
						self.strategy.comp_initial_config = comp['comp_initial_config']
						self.strategy.comp_last_timestamp = float(comp['comp_last_timestamp'])
						self.strategy.comp_prev_pl = comp['comp_prev_pl']
			self.strategy.last_timestamp = self.db.last_price_in_list['time']
		# Cuando no hay más precios para testear.
		if (self.db.last_price_in_list):
			self.db.update_trader(self)
			self.strategy.ready_to_use = True
			self.strategy.last_timestamp = self.db.last_price_in_list['time']
			self.db.update_strategy(self.strategy, update_comp = False)
		print('No hay más precios para testear.')
