"""
A trading strategy.
"""
from datetime import datetime
import json
class Strategy():
    def __init__(self, db, timer, coin1, coin2, config, name, mode, socket, save = True):
        super().__init__()
        self.db = db
        self.socket = socket
        self.NAME = name
        self.mode = mode
        self.last_timestamp = 0
        self.timer = timer
        self.coin1 = coin1
        self.coin2= coin2
        self.ready_to_use = 0

        self.trade = {'type': 'short', 'prev_type': '', 'time': 0,
                      'prev_time': 0, 'price': 0, 'prev_price': 0}
        self.price_source = config['price_source']
        self.pl = 0
        self.pl_c = 0
        self.prev_pl = 0
        self.leverage_s = 1
        self.leverage_l = 1
        self.high_leverage = 1
        self.l_l_ok = 0
        self.l_s_ok = 0
        self.l_l_no = 0
        self.l_s_no = 0
        self.stage = 0
        self.zoom_s = 0 # 0 - 1
        self.zoom_l = 0
        self.omit_aprox_count = 0
        self.sl_s_dif = None
        self.sl_l_dif = None

        self.sl_reduced_dif = config[self.coin1 + '-' + self.coin2]['sl_reduced_dif']
        self.sl_initial_dif = config[self.coin1 + '-' + self.coin2]['sl_initial_dif']
        self.okno_inc = config[self.coin1 + '-' + self.coin2]['okno_inc']
        self.okno_dec = config[self.coin1 + '-' + self.coin2]['okno_dec']

        self.m_aprox = config[self.coin1 + '-' + self.coin2]['m_aprox']
        self.high_leverage = config[self.coin1 + '-' + self.coin2]['high_leverage']
        self.leverage_inc = config[self.coin1 + '-' + self.coin2]['leverage_inc']
        self.leverage_dec = config[self.coin1 + '-' + self.coin2]['leverage_dec']
        self.far_price_dif = config[self.coin1 + '-' + self.coin2]['far_price_dif']

        self.last_pl_priority = config[self.coin1 + '-' + self.coin2]['last_pl_priority']

        self.omit = False
        self.far_price = 0
        self.stop_loss = 0

        self.comp_pl = 0
        self.comp_prev_pl = 0
        self.comp_initial_config = '{}'
        self.comp_last_timestamp = 0

        self.derivatives = None
        self.change_initial_config()


    def set_config(self, initial_config):
        self.sl_reduced_dif = initial_config['sl_reduced_dif']
        self.sl_initial_dif = initial_config['sl_initial_dif']
        self.okno_dec = initial_config['okno_dec']
        self.okno_inc = initial_config['okno_inc']
        self.m_aprox = initial_config['m_aprox']
        self.sl_s_dif = initial_config['sl_s_dif']
        self.sl_l_dif = self.sl_s_dif
        self.NAME = 'bs,' + str(self.sl_s_dif) + ',' + str(self.m_aprox) + ',asl'
        self.m_aprox = initial_config['m_aprox']
        self.high_leverage = initial_config['high_leverage']
        self.leverage_inc = initial_config['leverage_inc']
        self.leverage_dec = initial_config['leverage_dec']
        self.far_price_dif = initial_config['far_price_dif']
        self.change_initial_config()

    def change_initial_config(self):
        self.initial_config = json.JSONEncoder().encode({'type' : self.NAME.split(',')[0], 'sl_s_dif' : float(self.NAME.split(',')[1]), 'sl_l_dif' : float(self.NAME.split(',')[1]), 'sl_reduced_dif' : self.sl_reduced_dif, 'sl_initial_dif' : self.sl_initial_dif, 'okno_inc' : self.okno_inc, 'okno_dec' : self.okno_dec, 'm_aprox' : self.m_aprox, 'leverage_inc' : self.leverage_inc, 'leverage_dec' : self.leverage_dec, 'high_leverage' : self.high_leverage, 'far_price_dif' : self.far_price_dif})

        self.derivatives = [
            {'position' : 'close', 'coin2_balance' : 1, 'leverage' : 1, 'wait_zoom' : False, 'wait_far_price_dif' : True, 'far_price_dif' : self.far_price_dif, 'total_investment' : 1, 'open_price' : None},
            {'position' : 'close', 'coin2_balance' : 1, 'leverage' : 1, 'wait_zoom' : False, 'wait_far_price_dif' : True, 'far_price_dif' : 0, 'total_investment' : 1, 'open_price' : None}
        ]

    def change_status(self, values, i, fee_short, fee_long):
        """
        Aplica la estrategia de trading y cambia el trade de ser necesario.
        """
        omit_prev = False
        if (self.omit):
            omit_prev = True
        self.omit = False

        if (not self.trade['price']):
            self.trade['price'] = values[i]['price']

        self.last_timestamp = values[i]['time']
        prev_price = values[i]['price']
        j = i - 1
        while ((j >= 0) and (prev_price == values[i]['price'])):
            prev_price = values[j]['price']
            j -= 1
        prev = self.trade['type']
        sl = None

        if ((not self.omit) and ((self.trade['type'] != prev) or (not self.stop_loss))):
            if (self.trade['type'] == 'short'):
                self.stop_loss = values[i]['price'] * (1 + (self.sl_initial_dif))
            if (self.trade['type'] == 'long'):
                self.stop_loss = values[i]['price'] * (1 - (self.sl_initial_dif))
        if (not self.omit):
            if (self.trade['prev_type'] != self.trade['type']):
                self.trade['time'] = float(values[i]['time'])
                p = self.trade['price']
                self.trade['price'] = values[i]['price']
                leverage_dif = 0
                for j in range(2):
                    trade_type = 'long'
                    fee = fee_long
                    fee2 = fee_short
                    leverage = self.leverage_l
                    leverage2 = self.leverage_s
                    dividend = self.trade['prev_price']
                    divisor = self.trade['price']
                    l_no = self.l_s_no
                    l_ok = self.l_s_ok
                    zoom = self.zoom_l
                    zoom2 = self.zoom_s
                    sl_p = self.sl_l_dif
                    if (j):
                        trade_type = 'short'
                        fee = fee_short
                        fee2 = fee_long
                        leverage = self.leverage_s
                        leverage2 = self.leverage_l
                        dividend = self.trade['price']
                        divisor = self.trade['prev_price']
                        l_no = self.l_l_no
                        l_ok = self.l_l_ok
                        zoom = self.zoom_s
                        zoom2 = self.zoom_l
                    if (self.trade['type'] == trade_type):
                        dif = ((dividend / (divisor * (1 + (fee2 * 0.5)))) - 1) * int(leverage2)
                        dif2 = ((dividend / (divisor * (1 + fee2))) - 1) * int(leverage2)

                        if (self.trade['prev_type'] != self.trade['type']):
                            if ((type(self.prev_pl) == type(1)) or (type(self.prev_pl) == type(1.1))):
                                self.pl_c += 1
                                self.pl = (self.prev_pl + (dif2 * self.last_pl_priority)) / (self.last_pl_priority + 1)
                                self.prev_pl = ((self.prev_pl * self.pl_c) + dif2) / (self.pl_c + 1)

                            if (
                                ((self.trade['type'] == 'long') and (self.trade['price'] < (self.trade['prev_price'] * (1 - fee_short)))) or
                                ((self.trade['type'] == 'short') and (self.trade['price'] > (self.trade['prev_price'] * (1 + fee_long))))
                            ):
                                l_no -= self.okno_dec
                                if (l_no < 0):
                                    l_no = 0
                                l_ok += self.okno_inc
                                stage = (((dividend / divisor) - 1) / fee2) - 1
                                inc = self.leverage_inc * stage * (1.01 ** (1 + l_ok))
                                leverage2 += inc
                                if (leverage2 > self.high_leverage):
                                    leverage2 = self.high_leverage
                                zoom2 += (inc / 100)
                                if (zoom2 > 1):
                                    zoom2 = 1
                            else:
                                l_ok -= self.okno_dec
                                if (l_ok < 0):
                                    l_ok = 0
                                l_no += self.okno_inc
                                stage = ((divisor / (dividend * (1 - fee2))) - 1) / fee2
                                dec = self.leverage_dec * stage * (1.01 ** (1 + l_no))

                                leverage2 -= dec
                                if (int(leverage2) <= 0):
                                    leverage2 = 1
                                zoom2 -= (dec / 100)
                                if (zoom2 < 0):
                                    zoom2 = 0

                            if (self.trade['type'] == 'long'):
                                self.leverage_l = leverage
                                self.leverage_s = leverage2
                                self.l_s_no = l_no
                                self.l_s_ok = l_ok
                                self.zoom_l = zoom
                                self.zoom_s = zoom2
                            else:
                                self.leverage_l = leverage2
                                self.leverage_s = leverage
                                self.l_l_no = l_no
                                self.l_l_ok = l_ok
                                self.zoom_l = zoom2
                                self.zoom_s = zoom
                self.trade['prev_type'] = self.trade['type']
                self.omit_aprox_count = 0

            if (self.stop_loss and (((self.trade['type'] == 'long') and (values[i]['price'] <= self.stop_loss)) or ((self.trade['type'] == 'short') and (values[i]['price'] >= self.stop_loss)))):
                self.far_price = values[i]['price']
                self.trade['prev_price'] = self.trade['price']
                self.trade['price'] = values[i]['price']
                if (self.trade['type'] == 'long'):
                    self.trade['type'] = 'short'
                else:
                    self.trade['type'] = 'long'

            if (not self.far_price):
                self.far_price = values[i]['price']
            zoom_p = (self.zoom_l + self.zoom_s) * 0.5
            aprox = None
            for j in range(2):
                trade_type = 'long'
                fee = fee_long
                fee2 = fee_short
                leverage = self.leverage_l
                leverage2 = self.leverage_s
                dividend = self.stop_loss
                divisor = self.trade['price']
                m = self.stop_loss
                l = self.trade['price'] * (1 + fee_long)
                m2 = values[i]['price']
                l2 = self.far_price
                l_no = self.l_l_no
                l_ok = self.l_l_ok
                zoom = self.zoom_l
                zoom2 = self.zoom_s
                sl_p = self.sl_l_dif
                if (j):
                    trade_type = 'short'
                    fee = fee_short
                    fee2 = fee_long
                    leverage = self.leverage_s
                    leverage2 = self.leverage_l
                    dividend = self.trade['price']
                    divisor = self.stop_loss
                    m = self.trade['price'] * (1 - fee_short)
                    l = self.stop_loss
                    m2 = self.far_price
                    l2 = values[i]['price']
                    l_no = self.l_s_no
                    l_ok = self.l_s_ok
                    zoom = self.zoom_s
                    zoom2 = self.zoom_l
                    sl_p = self.sl_s_dif

                if (self.trade['type'] == trade_type):
                    tmp_zoom = 0
                    tmp_l_no = 0
                    tmp_l_ok = 0
                    if (self.trade['price'] and self.stop_loss):
                        dif = ((dividend / (divisor * (1 + fee))) - 1) * int(leverage)
                        for d in self.derivatives:
                            dividend2 = d['open_price']
                            divisor2 = values[i]['price']
                            if (self.trade['type'] == 'short'):
                                dividend2 = values[i]['price']
                                divisor2 = d['open_price']
                            dif2 = None
                            if (dividend2 and divisor2):
                                dif2 = ((dividend2 / (divisor2 * (1 + (fee2 * 0.5)))) - 1) * int(d['leverage'])
                            c = None
                            n = None
                            if (d['wait_zoom']):
                                c = d['min_zoom']['c']
                                n = d['min_zoom']['n']
                            if ((not d['wait_zoom']) or (((c == '>') and (zoom > n)) or ((c == '>=') and (zoom >= n)))):
                                fd = self.far_price / self.trade['price']
                                if (self.trade['type'] == 'short'):
                                    fd = self.trade['price'] / self.far_price
                                if ((not d['wait_far_price_dif']) or (fd >= (1 + d['far_price_dif']))):
                                    if (d['position'] != self.trade['type']):
                                        if (d['position'] != 'close'):
                                            d['coin2_balance'] = d['coin2_balance'] * (1 + dif2) * (1 - (fee * 0.5 * int(leverage)))
                                        else:
                                            d['coin2_balance'] = d['coin2_balance'] * (1 - (fee * 0.5 * int(leverage)))
                                        d['leverage'] = leverage
                                        d['position'] = self.trade['type']
                                        d['open_price'] = values[i]['price']
                                        t2 = ''
                                        if (d['wait_far_price_dif']):
                                            t2 += ', far_price_dif: ' + str(d['far_price_dif'])
                                        if (d['wait_zoom']):
                                            t2 += ', zoom ' + str(d['min_zoom']['c']) + ' ' + str(d['min_zoom']['n'])
                                        print('strategy derivatives, ' + d['position'] + t2 + ', ' + str(d['coin2_balance']) + ' USD, investment: ' + str(d['total_investment']) + ', ' + datetime.fromtimestamp(values[i]['time']).isoformat() + ', open price: ' + str(d['open_price']) + ', leverage: ' + str(d['leverage']))
                            else:
                                if (d['position'] != 'close'):
                                    d['coin2_balance'] = d['coin2_balance'] * (1 + dif2)
                                    d['position'] = 'close'

                            if (d['coin2_balance'] >= 0):
                                if (d['coin2_balance'] <= 0.01):
                                    d['coin2_balance'] += 1
                                    d['total_investment'] += 1
                            else:
                                d['coin2_balance'] = 1
                                d['total_investment'] += 1

                        if ((type(self.prev_pl) == type(1)) or (type(self.prev_pl) == type(1.1))):
                            self.pl = (self.prev_pl + (dif * self.last_pl_priority)) / (self.last_pl_priority + 1)

                        if (m > l): # Tendría ganancia con ese stop loss.
                            tmp_l_no -= self.okno_dec
                            if ((l_no + tmp_l_no) < 0):
                                tmp_l_no = 0
                            tmp_l_ok += self.okno_inc
                            stage = (((dividend / divisor) - 1) / fee) - 1
                            inc = self.leverage_inc * stage * (1.01 ** (1 + ((l_ok + tmp_l_ok) * 0.255)))

                            tmp_zoom += (inc / 100)
                            if ((zoom + tmp_zoom) > 1):
                                tmp_zoom = 1 - zoom
                        else:
                            tmp_l_ok -= self.okno_dec
                            if ((l_ok + tmp_l_ok) < 0):
                                tmp_l_ok = 0
                            tmp_l_no += self.okno_inc
                            stage = ((divisor / (dividend * (1 - fee))) - 1) / fee
                            dec = self.leverage_dec * stage * (1.01 ** (1 + ((l_no + tmp_l_no) * 0.255)))
                            tmp_zoom -= (dec / 100)
                            if ((zoom + tmp_zoom) < 0):
                                tmp_zoom = 0
                    zoom_p = ((zoom + tmp_zoom) + zoom2) * 0.5
                    aprox = self.m_aprox * zoom_p
                    if (
                        (
                            (trade_type == 'long') and
                            (
                                (values[i]['price'] > (self.trade['price'] * (1 + fee))) or
                                (
                                    values[i]['price'] < (self.trade['price'] * (1 - (self.sl_initial_dif * 0.5)))
                                )
                            )
                        ) or

                        ((trade_type == 'short') and ((values[i]['price'] < (self.trade['price'] * (1 - fee))) or (values[i]['price'] < (self.trade['price'] * (1 + (self.sl_initial_dif * 0.5))))))
                    ):
                        aprox = self.m_aprox * zoom_p * (((values[i]['time'] - float(self.trade['time'])) / self.timer) - self.omit_aprox_count)
                    else:
                        self.omit_aprox_count += (values[i]['time'] - values[i - 1]['time']) / self.timer

                    if ((not self.far_price) or (self.far_price and (m2 > l2))):
                        self.far_price = values[i]['price']
                    sl = self.stop_loss

                    sl2 = self.trade['price'] * (1 - self.sl_initial_dif + self.sl_reduced_dif)
                    if (trade_type == 'short'):
                        sl2 = self.trade['price'] * (1 + self.sl_initial_dif - self.sl_reduced_dif)

                    if (((trade_type == 'long') and (sl < sl2)) or ((trade_type == 'short') and (sl > sl2))): #No está en la zona de break even o mejor.
                        sl_p = self.sl_initial_dif

                    sl2 = self.far_price * (1 - sl_p + aprox)
                    if (trade_type == 'short'):
                        sl2 = self.far_price * (1 + sl_p - aprox)

                    if (
                        (
                            (trade_type == 'long') and
                            ((sl2 < values[i]['price']) or ((sl2 > values[i]['price']) and (values[i]['price'] < prev_price)))
                        ) or
                        (
                            (trade_type == 'short') and
                            ((sl2 > values[i]['price']) or ((sl2 < values[i]['price']) and (values[i]['price'] > prev_price)))
                        )
                    ):
                        sl = sl2
                    if (((trade_type == 'long') and sl and (sl > self.stop_loss)) or ((trade_type == 'short') and sl and (sl < self.stop_loss))):
                        self.stop_loss = sl
        else:
            self.last_s_s = 0
            self.last_s_l = 0
