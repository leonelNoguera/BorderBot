from datetime import datetime
import mariadb
import time
import json
import sys
class PricesUpdater(object):
	def __init__(self, config, coin1, coin2):
		super(PricesUpdater, self).__init__()
		self.MAX_TEXT_LEN = 55000
		self.coin1 = coin1
		self.coin2 = coin2
		self.decimals = config[self.coin1 + '-' + self.coin2]['decimals']
		self.timer = config['timer']
		print('Conectando a la db.')
		self.conn = mariadb.connect(user=config['db_user'], password=config['db_password'], host=config['db_host'], port=config['db_port'], database=config['db_database'])
		self.cur = self.conn.cursor()
	def save_prices(self, files, read_timestamp = False):
		last = ''
		for file in files:
			init_timestamp = None
			coin1 = self.coin1
			coin2 = self.coin2
			timer = 5
			blocks = []
			this_timestamp = 0
			block_timestamp = 0
			prev_timestamp = 0
			str_prices = ''
			block_completed = False
			prices = []
			prices_fixed = []
			i = 0

			f = open(file, 'r')
			data = f.read().split('\n')[:-1]
			print(file)
			timer = int(file.split('_')[-1].split('.')[0])
			f.close()
			if (not init_timestamp):
				init_timestamp = float(data[0].split(',')[0])
				this_timestamp = init_timestamp
				block_timestamp = init_timestamp
			for d in data:
				price = d.split(',')[1]
				if (not [float(d.split(',')[0]), float(price)] in prices):
					prices.append([float(d.split(',')[0]), float(price)])
			while (i < (len(prices) - 1)):
				while (prices[i + 1][0] >= this_timestamp):
					if (prices[i][0] == this_timestamp):
						fixed = prices[i][1]
					else:
						t_dif = this_timestamp - prices[i][0]
						t_dif_2 = prices[i + 1][0] - prices[i][0]
						dif = t_dif / t_dif_2
						'''
						t_dif -> diferencia en segundos entre time inicial y el que se busca (a veces 10 segundos)
						t_dif_2 -> diferencia en segundos entre time inicial y el siguiente time registrado
						dif -> cuanto porcentaje representa el time buscado de la diferencia entre registrados (ejemplo: 100, 112 y se busca 110; es 10/12 = 0.83)
						'''
						fixed = prices[i][1] + ((prices[i + 1][1] - prices[i][1]) * dif)
					price = str(round(fixed, self.decimals))
					if (len(str_prices + price) <= self.MAX_TEXT_LEN):
						str_prices += price + '-'
						block_completed = False
					else:
						blocks.append([block_timestamp, prev_timestamp, str_prices[:-1]])
						prev_timestamp = block_timestamp
						block_timestamp = this_timestamp
						block_completed = True
						str_prices = price + '-'
					this_timestamp += timer
				i += 1
			if (not block_completed):
				blocks.append([block_timestamp, prev_timestamp, str_prices[:-1]])
				prev_timestamp = block_timestamp
				block_timestamp = this_timestamp
			this_timestamp = init_timestamp
			block_updated = True
			for b in blocks:
				cur = self.conn.cursor()
				statement = """INSERT INTO prices (init_timestamp, coin1, coin2, timer, prices) VALUES ({}, '{}', '{}', {}, '{}')""".format(b[0], coin1, coin2, timer, b[2])
				s = """INSERT INTO prices (init_timestamp, coin1, coin2, timer, prices) VALUES ({}, '{}', '{}', {}, '{}')""".format(b[0], coin1, coin2, timer, 'prices...')

				statement2 = 'SELECT prices FROM prices WHERE (init_timestamp = ' + str(b[0]) + ' && coin1 = "' + str(coin1) + '" && coin2 = "' + str(coin2) + '" AND timer = ' + str(timer) + ') LIMIT 1;'
				cur.execute(statement2)
				rows = cur.fetchall()
				if (rows):# Ya existía ese bloque. Se deben comparar las listas de precios.
					statement = 'UPDATE prices SET prices = "' + b[2] + '" WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND init_timestamp = ' + str(b[0]) + ');'
					s = 'UPDATE prices SET prices = "prices..." WHERE (timer = ' + str(timer) + ' && coin1 = "' + coin1 + '" && coin2 = "' + coin2 + '" AND init_timestamp = ' + str(b[0]) + ');'
				print(s)
				cur.execute(statement)
				self.conn.commit()

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
				price = round(fixed, self.decimals)
				fixed_prices['prices'].append(price)
				if (not first_timestamp):
					first_timestamp = this_timestamp
					fixed_prices['first_timestamp'] = first_timestamp
				this_timestamp += timer_now
			prev_price = {'price': float(prices[i][0]), 'time' : float(prices[i][1])}
			i += 1
		return fixed_prices

coin1 = 'DRIFT'
coin2 = 'USDT'
if (len(sys.argv) > 1):
	coin1 = sys.argv[1:][0].split('-')[0]
	coin2 = sys.argv[1:][0].split('-')[1]
updater = PricesUpdater(config = json.JSONDecoder().decode(open('config.json', 'r').read()), coin1 = coin1, coin2 = coin2)

cur = updater.conn.cursor()
last_list_file_path = ''
while (True):
    f = open('prices/' + updater.coin1 + '-' + updater.coin2 + '_prices_lists.txt', 'r')
    lists = f.read().split('\n')[:-1]
    f.close()
    if (not last_list_file_path):
        last_list_file_path = lists[0]
    j = -1
    if (last_list_file_path and (last_list_file_path in lists)):
        j = lists.index(last_list_file_path)
    try:
        if (j):
            updater.save_prices([
                lists[j - 1]
            ])
    except:
        0
    updater.save_prices([
        last_list_file_path
    ])
    if (len(lists) > (j + 1)):
        last_list_file_path = lists[j + 1]
    time.sleep(20)
