from datetime import datetime
import json
class Strategy():
    def __init__(self, db, timer, coin1, coin2, config, name, mode, socket, save = True):
        super().__init__()
        self.db = db
        self.config = config
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
        self.prev_pl = 0
        self.leverage_s = 1
        self.leverage_l = 1
        self.high_leverage_s = 1
        self.high_leverage_l = 1
        self.l_l_ok = 0
        self.l_s_ok = 0
        self.l_l_no = 0
        self.l_s_no = 0
        self.stage = 0
        self.zoom_s = 0 # 0 - 1
        self.zoom_l = 0
        self.omit_aprox_count = 0
        self.sl_s_dif = config[self.coin1 + '-' + self.coin2]['sl_s_dif']
        self.sl_l_dif = config[self.coin1 + '-' + self.coin2]['sl_l_dif']

        self.sl_reduced_dif_s = config[self.coin1 + '-' + self.coin2]['sl_reduced_dif_s']
        self.sl_reduced_dif_l = config[self.coin1 + '-' + self.coin2]['sl_reduced_dif_l']
        self.sl_initial_dif_s = config[self.coin1 + '-' + self.coin2]['sl_initial_dif_s']
        self.sl_initial_dif_l = config[self.coin1 + '-' + self.coin2]['sl_initial_dif_l']
        self.okno_inc_s = config[self.coin1 + '-' + self.coin2]['okno_inc_s']
        self.okno_dec_s = config[self.coin1 + '-' + self.coin2]['okno_dec_s']
        self.okno_inc_l = config[self.coin1 + '-' + self.coin2]['okno_inc_l']
        self.okno_dec_l = config[self.coin1 + '-' + self.coin2]['okno_dec_l']

        self.m_aprox_s = config[self.coin1 + '-' + self.coin2]['m_aprox_s']
        self.m_aprox_l = config[self.coin1 + '-' + self.coin2]['m_aprox_l']
        self.high_leverage_s = config[self.coin1 + '-' + self.coin2]['high_leverage_s']
        self.high_leverage_l = config[self.coin1 + '-' + self.coin2]['high_leverage_l']
        self.leverage_inc_s = config[self.coin1 + '-' + self.coin2]['leverage_inc_s']
        self.leverage_dec_s = config[self.coin1 + '-' + self.coin2]['leverage_dec_s']
        self.leverage_inc_l = config[self.coin1 + '-' + self.coin2]['leverage_inc_l']
        self.leverage_dec_l = config[self.coin1 + '-' + self.coin2]['leverage_dec_l']
        self.far_price_dif_s = config[self.coin1 + '-' + self.coin2]['far_price_dif_s']
        self.far_price_dif_l = config[self.coin1 + '-' + self.coin2]['far_price_dif_l']
        self.min_balance = config['min_balance']

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
        self.sl_reduced_dif_s = initial_config['sl_reduced_dif_s']
        self.sl_reduced_dif_l = initial_config['sl_reduced_dif_l']
        self.sl_initial_dif_s = initial_config['sl_initial_dif_s']
        self.sl_initial_dif_l = initial_config['sl_initial_dif_l']

        self.okno_inc_s = initial_config['okno_inc_s']
        self.okno_dec_s = initial_config['okno_dec_s']
        self.okno_inc_l = initial_config['okno_inc_l']
        self.okno_dec_l = initial_config['okno_dec_l']

        self.m_aprox_s = initial_config['m_aprox_s']
        self.m_aprox_l = initial_config['m_aprox_l']
        self.sl_s_dif = initial_config['sl_s_dif']
        self.sl_l_dif = initial_config['sl_l_dif']
        self.NAME = 'bs,' + str(self.sl_initial_dif_s) + ',' + str(self.sl_initial_dif_l)
        self.high_leverage_s = initial_config['high_leverage_s']
        self.high_leverage_l = initial_config['high_leverage_l']
        self.leverage_inc_s = initial_config['leverage_inc_s']
        self.leverage_dec_s = initial_config['leverage_dec_s']
        self.leverage_inc_l = initial_config['leverage_inc_l']
        self.leverage_dec_l = initial_config['leverage_dec_l']
        self.far_price_dif_s = initial_config['far_price_dif_s']
        self.far_price_dif_l = initial_config['far_price_dif_l']
        self.change_initial_config()

    def change_initial_config(self):
        self.initial_config = json.JSONEncoder().encode({
            'type' : self.NAME.split(',')[0],
            'sl_s_dif' : self.sl_s_dif,
            'sl_l_dif' : self.sl_l_dif,
            'sl_reduced_dif_s' : self.sl_reduced_dif_s,
            'sl_reduced_dif_l' : self.sl_reduced_dif_l,
            'sl_initial_dif_s' : self.sl_initial_dif_s,
            'sl_initial_dif_l' : self.sl_initial_dif_l,
            'okno_inc_s' : self.okno_inc_s,
            'okno_dec_s' : self.okno_dec_s,
            'okno_inc_l' : self.okno_inc_l,
            'okno_dec_l' : self.okno_dec_l,
            'm_aprox_s' : self.m_aprox_s,
            'm_aprox_l' : self.m_aprox_l,
            'leverage_inc_s' : self.leverage_inc_s,
            'leverage_dec_s' : self.leverage_dec_s,
            'leverage_inc_l' : self.leverage_inc_l,
            'leverage_dec_l' : self.leverage_dec_l,
            'high_leverage_s' : self.high_leverage_s,
            'high_leverage_l' : self.high_leverage_l,
            'far_price_dif_s' : self.far_price_dif_s,
            'far_price_dif_l' : self.far_price_dif_l
        })
        self.derivatives = self.config[self.coin1 + '-' + self.coin2]['derivatives']
        for i in range(len(self.derivatives)):
            if (self.derivatives[i]['wait_far_price_dif']):
                self.derivatives[i]['far_price_dif_s'] = self.far_price_dif_s
                self.derivatives[i]['far_price_dif_l'] = self.far_price_dif_l

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
        sl = None

        if ((not self.omit) and ((not self.stop_loss) or (self.stop_loss < 0))):
            if (self.trade['type'] == 'short'):
                self.stop_loss = values[i]['price'] * (1 + (self.sl_initial_dif_s))
            if (self.trade['type'] == 'long'):
                self.stop_loss = values[i]['price'] * (1 - (self.sl_initial_dif_l))
        if (not self.omit):
            prev_pl_updated = False
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
                                self.prev_pl = self.prev_pl + (dif2 * self.last_pl_priority)
                                self.pl = self.prev_pl
                                prev_pl_updated = True
                            if (
                                ((self.trade['type'] == 'long') and (self.trade['price'] < (self.trade['prev_price'] * (1 - fee_short)))) or
                                ((self.trade['type'] == 'short') and (self.trade['price'] > (self.trade['prev_price'] * (1 + fee_long))))
                            ):
                                if (self.trade['type'] == 'short'):
                                    l_no -= self.okno_dec_l
                                    l_ok += self.okno_inc_l
                                else:
                                    l_no -= self.okno_dec_s
                                    l_ok += self.okno_inc_s
                                if (l_no < 0):
                                    l_no = 0
                                stage = (((dividend / divisor) - 1) / fee2) - 1
                                li = self.leverage_inc_s
                                if (self.trade['type'] == 'short'):
                                    li = self.leverage_inc_l
                                inc = li * stage * (1.01 ** (1 + l_ok))
                                leverage2 += inc
                                high_leverage = self.high_leverage_l
                                if (self.trade['type'] == 'long'):
                                    high_leverage = self.high_leverage_s
                                if (leverage2 > high_leverage):
                                    leverage2 = high_leverage
                                zoom2 += (inc / 100)
                                if (zoom2 > 1):
                                    zoom2 = 1
                            else:
                                if (self.trade['type'] == 'long'):
                                    l_ok -= self.okno_dec_s
                                    l_no += self.okno_inc_s
                                else:
                                    l_ok -= self.okno_dec_l
                                    l_no += self.okno_inc_l
                                if (l_ok < 0):
                                    l_ok = 0

                                stage = ((divisor / (dividend * (1 - fee2))) - 1) / fee2
                                ld = self.leverage_dec_s
                                if (self.trade['type'] == 'short'):
                                    ld = self.leverage_dec_l
                                dec = ld * stage * (1.01 ** (1 + l_no))

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

            # Cambio de trade, de ser necesario.
            if (self.stop_loss and (((self.trade['type'] == 'long') and (values[i]['price'] <= self.stop_loss)) or ((self.trade['type'] == 'short') and (values[i]['price'] >= self.stop_loss)))):
                self.far_price = values[i]['price']
                self.trade['prev_price'] = self.trade['price']
                self.trade['price'] = values[i]['price']
                if (self.trade['type'] == 'long'):
                    self.trade['type'] = 'short'
                    self.stop_loss = values[i]['price'] * (1 + (self.sl_initial_dif_s))
                else:
                    self.trade['type'] = 'long'
                    self.stop_loss = values[i]['price'] * (1 - (self.sl_initial_dif_l))

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
                            close_position = False
                            if ((d['position'] != 'close') and (d['position'] != self.trade['type'])):
                                coin2_balance = d['coin2_balance'] * (1 + dif2) * (1 - (fee * 0.5 * int(leverage)))
                                if (coin2_balance  <= 0.01):
                                    close_position = True
                                    print('Se cerrará la posición por liquidación.')
                                else:
                                    if (d['close_on_close']):
                                        close_position = True
                            fpd = None
                            if (d['wait_far_price_dif']):
                                fpd = d['far_price_dif_l']
                                if (self.trade['type'] == 'short'):
                                    fpd = d['far_price_dif_s']
                            if (((not d['wait_zoom']) or (((c == '>') and (zoom > n)) or ((c == '>=') and (zoom >= n)))) and not close_position):
                                fd = self.far_price / self.trade['price']
                                if (self.trade['type'] == 'short'):
                                    fd = self.trade['price'] / self.far_price
                                if ((not d['wait_far_price_dif']) or (fd >= (1 + fpd))):
                                    if (d['position'] != self.trade['type']):
                                        if (d['position'] != 'close'):
                                            c2 = d['coin2_balance'] * (1 + dif2)
                                            if (c2 < 0):
                                                c2 = self.min_balance
                                                d['total_investment'] += 1
                                            else:
                                                if (c2 < self.min_balance):
                                                    c2 += 1
                                                    d['total_investment'] += 1
                                            d['coin2_balance'] = c2 * (1 - (fee * 0.5 * int(leverage)))
                                        else:
                                            if (d['coin2_balance'] < 0):
                                                d['coin2_balance'] = self.min_balance
                                                d['total_investment'] += 1
                                            else:
                                                if (d['coin2_balance'] < self.min_balance):
                                                    d['coin2_balance'] += 1
                                                    d['total_investment'] += 1
                                            d['coin2_balance'] = d['coin2_balance'] * (1 - (fee * 0.5 * int(leverage)))
                                        d['leverage'] = leverage
                                        d['position'] = self.trade['type']
                                        d['open_price'] = values[i]['price']
                                        t2 = ''
                                        if (d['wait_far_price_dif']):
                                            t2 += ', far_price_dif: ' + str(fpd)
                                        if (d['close_on_close']):
                                            t2 += ', close_on_close'
                                        if (d['wait_zoom']):
                                            t2 += ', zoom ' + str(d['min_zoom']['c']) + ' ' + str(d['min_zoom']['n'])
                                        print('strategy derivatives, ' + d['position'] + t2 + ', ' + str(d['coin2_balance']) + ' USD, investment: ' + str(d['total_investment']) + ', ' + datetime.fromtimestamp(values[i]['time']).isoformat() + ', open price: ' + str(d['open_price']) + ', leverage: ' + str(d['leverage']))
                            else:
                                if (d['position'] != 'close'):
                                    d['coin2_balance'] = d['coin2_balance'] * (1 + dif2)
                                    d['position'] = 'close'
                                    t2 = ''
                                    if (d['wait_far_price_dif']):
                                        t2 += ', far_price_dif: ' + str(fpd)
                                    if (d['close_on_close']):
                                        t2 += ', close_on_close'
                                    if (d['wait_zoom']):
                                        t2 += ', zoom ' + str(d['min_zoom']['c']) + ' ' + str(d['min_zoom']['n'])
                                    print('strategy derivatives, ' + d['position'] + t2 + ', ' + str(d['coin2_balance']) + ' USD, investment: ' + str(d['total_investment']) + ', ' + datetime.fromtimestamp(values[i]['time']).isoformat() + ', open price: ' + str(d['open_price']) + ', leverage: ' + str(int(d['leverage'])))

                            if (d['coin2_balance'] >= 0):
                                if (d['coin2_balance'] <= 0.01):
                                    d['coin2_balance'] += 1
                                    d['total_investment'] += 1
                            else:
                                d['coin2_balance'] = 1
                                d['total_investment'] += 1

                        if ((type(self.prev_pl) == type(1)) or (type(self.prev_pl) == type(1.1))):
                            if (not prev_pl_updated):
                                self.pl = self.prev_pl + (dif * self.last_pl_priority)

                        if (m > l): # Tendría ganancia con ese stop loss.
                            if (self.trade['type'] == 'short'):
                                tmp_l_no -= self.okno_dec_s
                            else:
                                tmp_l_no -= self.okno_dec_l
                            if ((l_no + tmp_l_no) < 0):
                                tmp_l_no = 0
                            if (self.trade['type'] == 'short'):
                                tmp_l_ok += self.okno_inc_s
                            else:
                                tmp_l_ok += self.okno_inc_l
                            stage = (((dividend / divisor) - 1) / fee) - 1
                            li = self.leverage_inc_s
                            if (self.trade['type'] == 'short'):
                                li = self.leverage_inc_l
                            inc = li * stage * (1.01 ** (1 + l_ok + tmp_l_ok))

                            tmp_zoom += (inc / 100)
                            if ((zoom + tmp_zoom) > 1):
                                tmp_zoom = 1 - zoom
                        else:
                            if (self.trade['type'] == 'short'):
                                tmp_l_ok -= self.okno_dec_s
                            else:
                                tmp_l_ok -= self.okno_dec_l
                            if ((l_ok + tmp_l_ok) < 0):
                                tmp_l_ok = 0
                            if (self.trade['type'] == 'short'):
                                tmp_l_no += self.okno_inc_s
                            else:
                                tmp_l_no += self.okno_inc_l
                            stage = ((divisor / (dividend * (1 - fee))) - 1) / fee
                            ld = self.leverage_dec_l
                            if (self.trade['type'] == 'short'):
                                ld = self.leverage_dec_s
                            dec = ld * stage * (1.01 ** (1 + l_no + tmp_l_no))
                            tmp_zoom -= (dec / 100)
                            if ((zoom + tmp_zoom) < 0):
                                tmp_zoom = 0
                    zoom_p = ((zoom + tmp_zoom) + zoom2) * 0.5
                    a = self.m_aprox_s
                    if (self.trade['type'] == 'long'):
                        a = self.m_aprox_l
                    aprox = 0
                    if (
                        (
                            (trade_type == 'long') and
                            (
                                (values[i]['price'] > (self.trade['price'] * (1 + fee))) or
                                (
                                    values[i]['price'] < (self.trade['price'] * (1 - (self.sl_initial_dif_l * 0.25)))
                                )
                            )
                        ) or

                        ((trade_type == 'short') and ((values[i]['price'] < (self.trade['price'] * (1 - fee))) or (values[i]['price'] > (self.trade['price'] * (1 + (self.sl_initial_dif_s * 0.25))))))
                    ):
                        aprox = a * zoom_p * (((values[i]['time'] - float(self.trade['time'])) / self.timer) - self.omit_aprox_count)
                    else:
                        self.omit_aprox_count += (values[i]['time'] - values[i - 1]['time']) / self.timer

                    if ((not self.far_price) or (self.far_price and (m2 > l2))):
                        self.far_price = values[i]['price']
                    sl = self.stop_loss

                    sl2 = self.trade['price'] * (1 - self.sl_initial_dif_l + self.sl_reduced_dif_l)
                    if (trade_type == 'short'):
                        sl2 = self.trade['price'] * (1 + self.sl_initial_dif_s - self.sl_reduced_dif_s)

                    if (((trade_type == 'long') and (sl < sl2)) or ((trade_type == 'short') and (sl > sl2))): #No está en la zona de break even o mejor.
                        sl_p = self.sl_initial_dif_s
                        if (trade_type == 'long'):
                            sl_p = self.sl_initial_dif_l

                    sl2 = self.far_price * (1 - sl_p + aprox)
                    if (trade_type == 'short'):
                        sl2 = self.far_price * (1 + sl_p - aprox)
                    if (sl2 < 0):
                        sl2 = self.far_price * (1 - sl_p)
                        if (trade_type == 'short'):
                            sl2 = self.far_price * (1 + sl_p)

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
