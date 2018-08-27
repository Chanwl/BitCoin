import time
from threading import Event, Thread
from CoinApi import *
from MaModel import *
from Functions import *
from decimal import *

class TimedThread(Thread):
    def __init__(self, event, wait_time, symbol,access_key,secret_key,market_url,trade_url, csv_price, csv_transactions):
        Thread.__init__(self)
        self.stopped = event
        self.wait_time = wait_time
        # Trade variable
        self.symbol = symbol
        self.access_key = access_key
        self.secret_key = secret_key
        self.market_url = market_url
        self.trade_url = trade_url
        # API
        self.CoinBase = CoinbaseExchange(self.symbol,self.access_key, self.secret_key, self.market_url, self.trade_url)
        # Account id
        accounts = self.CoinBase.get_accounts()
        if accounts['status'] == 'ok' and accounts['data']:
            self.acct_id = accounts['data'][0]['id']
        else:
            print("ID ERROR: ", accounts)
	    # Create model
        self.model = Model(self.CoinBase, csv_price, csv_transactions)
        print('Thread initiated...')

    def run(self):
        '''Trade by hand'''
        # self.checkBalance()
        # self.order('buy', 1) # BUY
        # self.order('sell', allin=True) # SELL
        # self.checkBalance()
        # time.sleep(1024)
        # self.stopped.set()
        '''Trade by hand'''

        '''Start point'''
        # start_flag = 9999
        # while not self.stopped.wait(self.wait_time) and start_flag > 6340:
        #     kline = self.CoinBase.get_kline('1min', size=1)
        #     if kline['status'] == 'ok' and kline['data']:
        #         datetime = getTime(kline['ts']) # 获得当前时间
        #         start_flag = kline['data'][0]['close'] # 获得当前价格
        #         print(datetime, start_flag)
        #     else:
        #         print("KLINE ERROR: ", kline)
        '''Start point'''
        
        print("**************************Thread start**************************")
        while not self.stopped.wait(self.wait_time): # Run thread until stopped by 'stopFlag' Event, waiting at set intervals
            order_state = self.CoinBase.get_orders()
            if order_state['status'] == 'ok':
                if order_state['data']:
                    print("PAUSE: There are unfilled orders...")
                    for orders in order_state['data']:
                        if orders['type'] == 'buy-market':
                            print("%s %s  %.8f of %s %s"% (getTime(orders['created-at']), orders['type'], float(orders['field-cash-amount']), orders['amount'], orders['state']))
                        else:
                            print("%s %s %.4f BTC of %s %s"% (getTime(orders['created-at']), orders['type'], float(orders['field-amount']), orders['amount'], orders['state']))
                else:
                    self.checkBalance()
                    if (Decimal(self.balance_f) >= Decimal('1.')) and (Decimal(self.quantity_f) >= Decimal('0.0001')):
                        print("PAUSE: There are frozen settlements")
                    else:
                        self.EMA_RSI_Strategy()
                        if self.model.sell_first == 0 and Decimal(self.quantity) < Decimal('0.0001') and self.model.level >= 10:
                            if self.wait_time <= 15:
                                self.wait_time = self.wait_time + 1
                        else:
                            self.wait_time = 1
            else:
                print("ORDERS STATE ERROR: ", order_state)
            print("****************************************************************")

    def EMA_RSI_Strategy(self):
        self.model.calculateMA(9, 26)
        self.model.calculateRSI(14)
        signal = self.model.tradeEvaluation(self.balance, self.quantity)
        if signal is not None:
            if signal['direction'] == 'buy':
                howmuch = Decimal(self.balance) * Decimal(signal['confidence'])
                if howmuch >= Decimal('1.'): # min 1
                    self.order('buy', howmuch, signal['signal'])
            elif signal['direction'] == 'sell':
                howmuch = Decimal(self.quantity) * Decimal(signal['confidence'])
                if howmuch >= Decimal('0.0001'): # min 0.0001
                    self.order('sell', howmuch, signal['signal'])
        if self.model.transaction_dataframe.shape[0]:
            print("> Local transaction record")
            print(self.model.transaction_dataframe)
            print("> Server transaction record")
            self.checkResults(self.model.transaction_dataframe.shape[0])

    def order(self, type, number=0, signal_status=0, allin=False):
        print("> Ordering...")
        kline = self.CoinBase.get_kline('1min', size=1)
        if kline['status'] == 'ok' and kline['data']:
            datetime = getTime(kline['ts']) # 获得当前时间
            latest_price = kline['data'][0]['close'] # 获得当前价格
        else:
            print("KLINE ERROR: ", kline)
        if (type == 'sell'):
            if Decimal(self.quantity) < Decimal('0.0001'):
                print("Too LITTLE to SELL")
                self.model.state = 'tobuy'
                self.model.sell_first = 0
                return
            if allin:
                sell_amount = Decimal(self.quantity).quantize(Decimal('0.0001'), rounding=ROUND_DOWN) # all sell!
            else:
                sell_amount = Decimal(number).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            #sell_gain = sell_amount * latest_price * (1 - self.model.transaction_fee_ratio)
            print('Sell %s BTC...' % (sell_amount))
            '''CSV Record'''
            data = {'huobi_id': self.acct_id, 'product_id': self.symbol, 'datetime': datetime, 'balance': self.balance, 'buy/sell': 'sell', 'price': latest_price, 'quantity': sell_amount, 'status': signal_status}
            self.model.transaction_dataframe = self.model.transaction_dataframe.append(pd.DataFrame(data, index=[0]),ignore_index=True, sort=True)
            self.model.logTransactions(True)
            print(self.model.transaction_dataframe)
            '''API Sell'''
            order = self.CoinBase.send_order(str(sell_amount),'api','sell-market') # min 0.0001
            print("%s! (order-id: %s)" % (order['status'].upper(), order['data']))
            if 'err-msg' in order:
                print(order['err-msg'])
        elif (type == 'buy'):
            if Decimal(self.balance) < Decimal('1.'):
                print("Too LITTLE to BUY!")
                self.state = 'tosell'
                self.model.sell_first = 1
                return
            if allin:
                buy_payment = Decimal(self.balance).quantize(Decimal('1.00000000'), rounding=ROUND_DOWN) # all buy!
            else:
                buy_payment = Decimal(number).quantize(Decimal('1.00000000'), rounding=ROUND_DOWN)
            #buy_gain = (self.balance * (1 - self.model.transaction_fee_ratio)) / latest_price
            print('Spend %s USDT...' % (buy_payment))
            '''CSV Record'''
            data = {'huobi_id': self.acct_id, 'product_id': self.symbol, 'datetime': datetime, 'balance': self.balance, 'buy/sell': 'buy', 'price': latest_price, 'quantity': buy_payment, 'status': signal_status}
            self.model.transaction_dataframe = self.model.transaction_dataframe.append(pd.DataFrame(data, index=[0]),ignore_index=True, sort=True)
            self.model.logTransactions(True)
            print(self.model.transaction_dataframe)
            '''API Buy'''
            order = self.CoinBase.send_order(str(buy_payment),'api','buy-market') # min 1.00000000
            print("%s! (order-id: %s)" % (order['status'].upper(), order['data']))
            if 'err-msg' in order:
                print(order['err-msg'])
            while self.model.checkLastBuy() is not True:
                pass
        else:
            print("Wrong order type!")
            return

    def checkBalance(self):
        print("> Checking balance (id: %s)..." % (self.acct_id))
        account=self.CoinBase.get_balance(self.acct_id)
        if account['status'] == 'ok' and account['data']:
            flag = 0
            for line in account['data']['list']:
                if line['currency'] == 'usdt' and line['type'] == 'trade':
                    self.balance = line['balance'] # 获得当前balance
                    flag = flag+1
                elif line['currency'] == 'btc' and line['type'] == 'trade':
                    self.quantity = line['balance'] # 获得当前币的数量
                    flag = flag+1
                elif line['currency'] == 'usdt' and line['type'] == 'frozen':
                    self.balance_f = line['balance'] # 获得当前balance
                    flag = flag+1
                elif line['currency'] == 'btc' and line['type'] == 'frozen':
                    self.quantity_f = line['balance'] # 获得当前币的数量
                    flag = flag+1
                elif flag == 4:
                    break
            print("USDT: %s (Besides, %s frozen)" % (self.balance, self.balance_f))
            print(" BTC:  %s (Besides, %s frozen)" % (self.quantity, self.quantity_f))
        else:
            print("BALANCE ERROR:", account)

    def checkResults(self, size):
        ret=self.CoinBase.orders_matchresults(size=size)
        if ret['status'] == 'ok' and ret['data']:
            for orders in ret['data']:
                print("%s %s %s %s %s"% (getTime(orders['created-at']), orders['type'], orders['price'], orders['filled-amount'], orders['filled-fees']))
        else:
            print("RESULTS ERROR: ", ret)