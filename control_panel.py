import db
class ControlPanel(object):
    def __init__(self):
        print('Panel de control de la base de datos.')
        self.db = db.Db()
        self.wait_op()

    def reset_strategies(self):
        op = 0
        try:
            op = input('Escriba el par correspondiente seguido por el timer en segundos (por ejemplo: ETH-USDT 10) o "back" para volver al menú principal.\n')
        except:
            pass
        timer = int(op.split(' ')[1].strip())
        op = op.split(' ')[0].strip()
        if (op.lower().strip() != 'back'):
            op2 = 'n'
            try:
                op2 = input('¿Conservar configuración de la mejor estrategia hasta el momento? (y/n)\n')
            except:
                pass

            r = self.db.reset_strategies(pair = op.strip(), timer = timer, cs = op2.strip().lower())
            if (r):
                print('SQL:')
                print(r)
                c = input('¿Confirmar cambios? y/n\n')
                if (c.strip().lower() == 'y'):
                    self.db.reset_strategies(pair = op.strip(), timer = timer, cs = op2.strip().lower(), confirm = True)
            while (not r):
                self.reset_strategies()
        self.wait_op()

    def delete_prices(self):
        op = 0
        try:
            op = input('Escriba el par correspondiente (por ejemplo: ETH-USDT) o "back" para volver al menú principal.\n')
        except:
            pass
        if (op.lower().strip() != 'back'):
            op2 = input('Escriba el timestamp correspondiente a partir del cual se eleminarán precios (por ejemplo: 1755972286.291702)\n')
            r = self.db.delete_prices(pair = op.strip(), timestamp = op2.strip())
            if (r):
                print('SQL:')
                print(r)
                c = input('¿Confirmar cambios? y/n\n')
                if (c.strip().lower() == 'y'):
                    self.db.delete_prices(pair = op.strip(), timestamp = op2.strip(), confirm = True)
            while (not r):
                self.delete_prices()
        self.wait_op()

    def wait_op(self):
        t = '\n\t1) Resetear estrategias.\n'
        t += '\t2) Borrar precios.\n'
        op = 0
        try:
            op = int(input(t))
        except:
            pass
        while ((not op) or (op < 0) or (op > 3)):
            self.wait_op()
        if (op == 1):
            self.reset_strategies()
        if (op == 2):
            self.delete_prices()

ControlPanel()
