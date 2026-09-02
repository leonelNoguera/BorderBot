from datetime import datetime
from bs4 import BeautifulSoup
import time
import requests
import json
import sys
import db

class BorderBot(object):
	"""docstring for BorderBot"""
	def __init__(self, args, mode = 'backtesting', socket = None, config = None):
		super(BorderBot, self).__init__()
		self.mode = mode
		self.socket = socket
		f = open('config.json', 'r')
		self.config = json.JSONDecoder().decode(f.read())
		f.close()
		self.timer = self.config['timer']
		if (config): # Sucede cuando es un cliente que recibe la configuración desde el servidor.
			self.config = config
			self.timer = config['timer']
			self.sleep_timer = config['timer']

		self.price_source = self.config['price_source']
		self.simulate_trading = self.config['simulate_trading']
		if (len(args)):
			self.coin1 = args[0].split('-')[0]
			self.coin2 = args[0].split('-')[1]
			if (len(args) > 1):
				self.simulate_trading = int(args[1])
			if (len(args) > 2):
				self.price_source = args[2]
		else:
			self.coin1 = self.config['pair'].split('-')[0]
			self.coin2 = self.config['pair'].split('-')[1]
		self.dt = self.config[self.coin1 + '-' + self.coin2]['dif_tolerance'] # La tolerancia de diferencia de precios entre cada periodo (10 segundos por defecto). Si la diferencia es mayor a dicha variable, no simulará operaciones con ese precio.

		# Esta variable contiene el timestamp a partir del cual se tendrán en cuenta las diferencias de precios por encima de la tolerancia establecida.
		# Se asigna manuálmente por el usuario, en casos de haber alta volatilidad (pero realista) en los precios guardados.
		self.last_dif_t = self.config[self.coin1 + '-' + self.coin2]['last_dif_timestamp']

		self.derivatives = [{'position' : 'close', 'coin2_balance' : 1, 'min_zoom' : {'c' : '>=', 'n' : 0}, 'total_investment' : 1}]

		if (self.mode == 'backtesting'):
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
		self.initial_config = '{}'
		self.db = None
		if (self.simulate_trading):
			self.db = db.Db()
			self.db.set_config(self.config, self.mode, self.coin1, self.coin2)
		# Representa la mayor cantidad de periodos del timing seleccionado (por defecto 10 segundos) que puede haber en una lista de precios dentro de un mismo archivo. Es necesario para no tener que procesar archivos demasiado grandes (en caso de dejar en bot funcionando por mucho tiempo sin detenerse).
		# DRIFT
		self.max_periods = 25920 # con timer de 10 segundos, son 3 días
		self.strategy = None
		self.last_up_down_priority = self.config[self.coin1 + '-' + self.coin2]['last_up_down_priority'] # Cuanta prioridad se le dará a la última diferencia de precios respecto al promedio general.
		self.min_fee = self.config[self.coin1 + '-' + self.coin2]['min_fee']
		self.fee_multiplier = self.config[self.coin1 + '-' + self.coin2]['fee_multiplier']
		self.fee_long = self.min_fee
		self.fee_short = self.min_fee
		self.prices_gap_tolerance_seconds = self.config['prices_gap_tolerance_seconds']
		self.min_balance = self.config['min_balance']
		self.link = None

	def get_price(self):
		"""Se obtienen los precios de Jupiter y los guarda en el array self.values"""
		try:
			soup = BeautifulSoup(requests.get(self.link, headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout = 5).content.decode(), 'html.parser')
			html = soup.decode()
			if (self.price_source == 'jupiter'):
				try:
					price = float(json.JSONDecoder().decode(html)[self.config[self.coin1 + '-' + self.coin2]['id']]['usdPrice'])
					new = {'time' : datetime.now().timestamp(), 'price' : price}
					self.values.append(new)
					if (not self.strategy):
						print(datetime.fromtimestamp(new['time']).isoformat() + ', ' + str(new['price']))
				except:
					0
				return new
		except:
			print('Falló la obtención del precio.')
		if (len(self.values) >= 1500):
			self.values = self.values[-1000:]


	def start(self):
		"""Se inicia el bot, en tiempo real o en backtesting"""
		self.values = []
		self.trade_type = None
		if (self.price_source == 'jupiter'):
			self.link = 'https://lite-api.jup.ag/price/v3?ids=' + self.config[self.coin1 + '-' + self.coin2]['id']
		if (self.db):
			self.derivatives = [{'position' : 'close', 'coin2_balance' : 1, 'min_zoom' : {'c' : '>=', 'n' : 0}, 'total_investment' : 1}]
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
						f = open('prices/dif_' + self.coin1 + '-' + self.coin2 + '_' + str(self.timer) + '_' + self.mode + '.txt', 'a')
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
						if (d['coin2_balance'] <= self.config['min_balance']):
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
		self.log_file_path = str(datetime.now().timestamp()) + '_' + self.config['price_source']
		leverage_s = 1
		leverage_l = 1
		zoom_s = 0
		zoom_l = 0
		c1 = self.coin1
		c2 = self.coin2
		print('Obteniendo precios...')
		omit = False
		first_timestamp_in_list = None
		if (self.simulate_trading):
			trader_log_file_path = 'logs/' + self.coin1 + '-' + self.coin2 + '_' + str(self.timer) + '_' + datetime.now().isoformat() + '.txt'
			prev_position_best_derivative = 'close' # Cambiar si es necesario al reiniciar el bot en tiempo real.
			prev_position_best_spot = None
			while (True):
				txt = ''
				prev_omitted = False
				if (omit):
					prev_omitted = True
				omit = False
				l = len(self.values)
				new = self.get_price()
				while (not new):
					new = self.get_price()
					time.sleep(1)
				j = len(self.values) - 1
				if (len(self.values) > 1):
					omit = self.validate_dif(j, prev_omitted)

				if (not first_timestamp_in_list):
					f = open(f'prices/{c1}-{c2}/lists.txt', 'a')
					f.write(self.log_file_path + '\n')
					f.close()
					first_timestamp_in_list = new['time']

				if ((((new['time'] - first_timestamp_in_list) / self.timer) > self.max_periods) or ((len(self.values) > 1) and ((new['time'] - self.values[-2]['time']) > self.prices_gap_tolerance_seconds))):
					self.log_file_path = str(datetime.now().timestamp()) + '_' + self.config['price_source']

					f = open(f'prices/{c1}-{c2}/lists.txt', 'a')
					f.write(self.log_file_path + '\n')
					f.close()

					first_timestamp_in_list = new['time']

				f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{self.log_file_path}.txt', 'a')
				f.write(str(new['time']) + ',' + str(new['price']) + '\n')
				f.close()
				f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{self.log_file_path}_updated.txt', 'w')
				f.write(str(datetime.now().timestamp()))
				f.close()

				self.last_timestamp = self.values[-1]['time']
				if (l != len(self.values)):
					if (not self.strategy):
						f = open('config.json', 'r')
						self.config = json.JSONDecoder().decode(f.read())
						f.close()
						self.price_source = self.config['price_source']
						self.strategy, m = self.db.get_strategy(
							self.timer,
							self.coin1,
							self.coin2,
							config = self.config
						)
						if (self.strategy):
							if (m):
								self.p_s_u = m['p_s_u']
								self.p_c_u = m['p_c_u']
								self.p_s_d = m['p_s_d']
								self.p_c_d = m['p_c_d']
								self.e_p_u = m['e_p_u']
								self.e_p_d = m['e_p_d']
							self.initial_config = self.strategy.initial_config
					else: # Ya se estaba utilizando un trader.
						new_strategy, m = self.db.get_strategy(
							self.timer,
							self.coin1,
							self.coin2,
							config = self.config
						)
						if (not self.strategy.trade['type']):
							self.strategy.initial_config = ''
							print(new_strategy.trade['type'])
						if (new_strategy and (new_strategy.initial_config != self.strategy.initial_config)): # Nuevo trader.
							t = datetime.fromtimestamp(self.values[j]['time']).isoformat() + ' cambio de estrategia: '
							t += json.JSONEncoder().encode(new_strategy.initial_config) + '\n'
							txt += t + '\n'
							print(t)

							self.strategy = new_strategy
							if (m):
								self.p_s_u = m['p_s_u']
								self.p_c_u = m['p_c_u']
								self.p_s_d = m['p_s_d']
								self.p_c_d = m['p_c_d']
								self.e_p_u = m['e_p_u']
								self.e_p_d = m['e_p_d']
							self.initial_config = self.strategy.initial_config
					if (self.strategy):
						if (not omit):
							self.strategy.change_status(self.values, j, self.fee_short, self.fee_long)
							self.db.update_strategy(self.strategy, self.mode)
							if (self.strategy.trade['type'] and (self.strategy.trade['type'] != self.trade_type)):
								self.trade_type = self.strategy.trade['type']

								if (self.trade_type == 'short'):
									zoom_s = self.strategy.zoom_s
									leverage_s = int(self.strategy.leverage_s)
								else:
									zoom_l = self.strategy.zoom_l
									leverage_l = int(self.strategy.leverage_l)

								self.change_trade(leverage_s, leverage_l, zoom_s, zoom_l, j)
								t = '\tSiguiendo a la estrategia: ' + self.strategy.NAME + ', ' + self.strategy.trade['type'] + ', ' + str(datetime.fromtimestamp(self.values[j]['time']).isoformat()) + ', ' + str(self.values[j]['price'])
								txt += t + '\n'
								for d in self.strategy.derivatives:
									t2 = ''
									if (d['wait_far_price_dif']):
										t2 += 'far_price_dif >= ' + str(d['far_price_dif_s']) + ',' + str(d['far_price_dif_l'])
									if (d['wait_zoom']):
										t2 += 'zoom ' + str(d['min_zoom']['c']) + ' ' + str(d['min_zoom']['n'])
									t += '\n\tstrategy derivatives, ' + d['position'] + ', ' + t2 + ', ' + str(d['coin2_balance']) + ' USD, investment: ' + str(d['total_investment']) + ', leverage: ' + str(int(d['leverage']))
									txt += t + '\n'
								for d in self.derivatives:
									t += '\n\tderivatives, zoom ' + str(d['min_zoom']['c']) + ' ' + str(d['min_zoom']['n']) + ', ' + str(d['coin2_balance']) + ' USD, investment: ' + str(d['total_investment'])
									txt += t + '\n'

								t += '\n\tleverage_s: ' + str(leverage_s) + '\n'
								t += '\tleverage_l: ' + str(leverage_l) + '\n'
								t += '\tzoom_s: ' + str(self.strategy.zoom_s) + '\n'
								t += '\tzoom_l: ' + str(self.strategy.zoom_l) + '\n'
								t += '\tfee short: ' + str(self.fee_short) + '\n\tfee long: ' + str(self.fee_long) + '\n'
								t += '\tleverage_l_ok: ' + str(self.strategy.l_l_ok) + ', leverage_l_no: ' + str(self.strategy.l_l_no) + '\n'
								t += '\tleverage_s_ok: ' + str(self.strategy.l_s_ok) + ', leverage_s_no: ' + str(self.strategy.l_s_no) + '\n'

								txt += t + '\n'
								print(t)

							prev_status = {}
							try:
								f = open('status.json', 'r')
								prev_status = json.JSONDecoder().decode(f.read())
								f.close()
							except:
								0

							max_d = 0
							max_d_spot = -1
							ds = self.strategy.derivatives

							if (prev_status and ((self.coin1 + '-' + self.coin2) in prev_status.keys()) and ('derivatives' in prev_status[self.coin1 + '-' + self.coin2].keys())):
								ds = prev_status[self.coin1 + '-' + self.coin2]['derivatives']

							for i in range(len(ds)):
								if ((ds[i]['coin2_balance'] - ds[i]['total_investment']) > (ds[max_d]['coin2_balance'] - ds[max_d]['total_investment'])):
									max_d = i
								if ((not ds[i]['close_on_close']) and ((max_d_spot == -1) or ((ds[i]['coin2_balance'] - ds[i]['total_investment']) > (ds[max_d_spot]['coin2_balance'] - ds[max_d_spot]['total_investment'])))):
									max_d_spot = i

							max_l = self.config[self.coin1 + '-' + self.coin2]['high_leverage_max']
							if (ds[max_d_spot]['position'] != prev_position_best_spot):
								pos = 'buy'
								if (ds[max_d_spot]['position'] != 'long'):
									pos = 'sell'
								p_sell = 0

								p_sell = 50 + (self.strategy.leverage_s / max_l * 50)
								if (pos == 'buy'):
									p_sell = 100 - (50 + (self.strategy.leverage_l / max_l * 50))

								if (ds[max_d]['position'] == 'close'):
									p_sell = 50

								prev_position_best_spot = ds[max_d_spot]['position']
								f = open('trades_spot_' + self.coin1 + '-' + self.coin2 + '.json', 'a')
								f.write(datetime.fromtimestamp(self.values[j]['time']).isoformat() + ',' + str(round((100 - p_sell), 2)) + ',' + str(round(p_sell, 2)) + ',' + pos + ',' + str(self.values[j]['price']) + ',' + str(self.strategy.stop_loss) + '\n')
								f.close()
							if (ds[max_d]['position'] != prev_position_best_derivative):
								prev_position_best_derivative = ds[max_d]['position']
								f = open('trades_' + self.coin1 + '-' + self.coin2 + '.json', 'a')
								f.write(datetime.fromtimestamp(self.values[j]['time']).isoformat() + ',' + ds[max_d]['position'] + ',' + str(self.values[j]['price']) + ',' + str(int(ds[max_d]['leverage'])) + ',' + str(self.strategy.stop_loss) + '\n')
								f.close()

							prev_status[self.coin1 + '-' + self.coin2] = {'trade_type' : self.trade_type, 'leverage_s' : leverage_s, 'leverage_l' : leverage_l, 'zoom_s' : self.strategy.zoom_s, 'zoom_l' : self.strategy.zoom_l, 'derivatives' : self.strategy.derivatives, 'high_leverage_max' : max_l, 'stop_loss' : self.strategy.stop_loss}
							f = open('status.json', 'w')
							f.write(json.JSONEncoder().encode(prev_status))
							f.close()
				self.db.update_trader(self.mode, None, self)

				f = open(trader_log_file_path, 'a')
				f.write(txt)
				f.close()

				time.sleep(self.timer)
		else:
			print('Obteniendo precios...')
			while (True):
				new = self.get_price()
				while (not new):
					new = self.get_price()
					time.sleep(1)
				j = len(self.values) - 1

				if (not first_timestamp_in_list):
					f = open(f'prices/{c1}-{c2}/lists.txt', 'a')
					f.write(self.log_file_path + '\n')
					f.close()
					first_timestamp_in_list = new['time']

				if ((((new['time'] - first_timestamp_in_list) / self.timer) > self.max_periods) or ((len(self.values) > 1) and ((new['time'] - self.values[-2]['time']) > self.prices_gap_tolerance_seconds))):
					self.log_file_path = str(datetime.now().timestamp()) + '_' + self.config['price_source']
					f = open(f'prices/{c1}-{c2}/lists.txt', 'a')
					f.write(self.log_file_path + '\n')
					f.close()

					first_timestamp_in_list = new['time']

				f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{self.log_file_path}.txt', 'a')
				f.write(str(new['time']) + ',' + str(new['price']) + '\n')
				f.close()
				f = open(f'prices/{c1}-{c2}/{c1}-{c2}_{self.log_file_path}_updated.txt', 'w')
				f.write(str(datetime.now().timestamp()))
				f.close()
				time.sleep(self.timer)

bot = BorderBot(sys.argv[1:], 'real_time')
bot.start()
