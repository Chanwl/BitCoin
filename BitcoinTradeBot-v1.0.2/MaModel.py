import pandas as pd
import numpy as np
from Functions import *
from decimal import *
import os

class Model:
    def __init__(self,coinbase,csv_price,csv_transactions):
        # pd.set_option('display.max_rows',None)
        # pd.set_option('display.max_colwidth',500)
        self.transaction_dataframe = pd.DataFrame(data={'huobi_id' : [], 'product_id' : [], 'datetime': [], 'balance' : [], 'buy/sell': [], 'price': [], 'quantity': [], 'status': []})
        self.ma_dataframe = pd.DataFrame(data={'datetime': [],'price': [], 'MA_st': [], 'MA_lt': [], 'RSI': [], 'RRSI': [], 'signal': []})
        self.csv_price = csv_price
        self.csv_transactions = csv_transactions
        self.CoinBase = coinbase
        csv_price_exists = os.path.isfile(self.csv_price)
        csv_transactions_exists = os.path.isfile(self.csv_transactions)
        if not csv_price_exists:
            self.logPrice(False)
        if not csv_transactions_exists:
            self.logTransactions(False)

        # Constants
        self.transaction_fee_ratio = 0.002 # 交易费用比率
        self.balance_leverage = 1.004012032 # 赚回手续费比率
        self.fee_leverage = 0.996004 # 手续费缩水比率

        '''Hyperparameters'''
        '''在这里调参'''
        self.ma1 = 9 # Short-term MA period，此处修改无效，请到TimeThread.py, line:45
        self.ma2 = 26 # Long-term MA period，修改同上
        self.RSIperiod = 14 # RSI period,，此处修改无效，请到TimeThread.py, line:46
        # self.profit_ratio_threshold = 1.0001 # 收益比率
        self.deficit_stop_ratio = 0.998         # 【动】止损比率，随止损动态变化
        self.shrunken_ratio = self.fee_leverage # 【动】买入时机top缩水比率，随买入动态变化
        self.shrunken_ratio_stride = 0.000001   # 买入时机top缩水比率增加步长
        self.RRSI_threshold = -30.0             # 【动】买入时机RRSI阈值，近三次累积RRSI变化，调低使买入更保守，买入时机更难遇到，务必是负数，随市价动态变化
        self.level_threshold = 0                # 【动】买入时机市价水平阈值，调低使买入条件更加严格，随止损动态变化
        self.clearance_threshold = 75           # 残币清仓RSI阈值，调高使清仓条件更严格，0~100
        self.RSI_threshold = 1 - self.clearance_threshold
        '''在这里调参'''
        '''Hyperparameters'''

        # Assistant variables
        self.last_id = None
        self.history = []
        self.target_price = 9999
        self.loss_limit = 0
        self.sell_first = 0
        self.state = 'tobuy' # wait观望，tobuy待买入，tosell待卖出

        self.checkLastBuy()

    def checkLastBuy(self):
        last_order=self.CoinBase.orders_matchresults(size=1)
        if last_order['status']== 'ok' and last_order['data'] :
            if last_order['data'][0]['type'] == 'buy-market':
                self.target_price = Decimal(last_order['data'][0]['price']) * Decimal(self.balance_leverage)
                self.loss_limit = Decimal(last_order['data'][0]['price']) * Decimal(self.deficit_stop_ratio)
                self.sell_first = 1
                self.state = 'wait'
                return True
            else:
                return None
        else:
            print(last_order)
            return False


    def calculateMA(self,short_term,long_term):
        # pd.set_option('display.max_rows',None)
        # pd.set_option('display.max_colwidth',500)
        print("> Calculating MA%d/%d ..." % (short_term, long_term))
        self.ma1 = short_term
        self.ma2 = long_term

        if self.last_id is None:
            kline = self.CoinBase.get_kline('1min', self.ma2+1)
            if kline['status'] == 'ok' and kline['data']:
                for i in range(self.ma2, 0, -1):
                    price = kline['data'][i]['close']
                    self.ma_dataframe = self.ma_dataframe.append(pd.DataFrame({'price': price}, index=[0]),ignore_index=True, sort=True)
                    self.history.append(price)
                market_value = np.median(self.history)
                self.last_id = kline['data'][i]['id']
            else:
                print("KLINE ERROR: ", kline)

        kline = self.CoinBase.get_kline('1min')
        if kline['status'] == 'ok' and kline['data']:
            new_id = kline['data'][0]['id']
            new_price = kline['data'][0]['close']
        else:
            print("KLINE ERROR: ", kline)

        if new_id == self.last_id:
            self.updateHistory(new_price, forward=False)
            length = self.ma_dataframe.shape[0]
            self.ma_dataframe.ix[length - 1, 'price'] = new_price # Only to update price
            # print(self.ma_dataframe)
        else:
            print(self.ma_dataframe)
            self.updateHistory(new_price, forward=True)
            self.ma_dataframe = self.ma_dataframe.append(pd.DataFrame({'datetime': getTime(kline['ts']), 'price': new_price}, index=[0]),ignore_index=True, sort=True)
            self.last_id = new_id
            length = self.ma_dataframe.shape[0]
        self.market_value = np.median(self.history)
        self.temp_top = np.max(self.history)
        self.shrunken_value = self.temp_top * self.shrunken_ratio
        if self.market_value < self.shrunken_value:
            self.shrunken_value = self.market_value
        self.level = new_price - self.shrunken_value
        self.RRSI_threshold = new_price * (1 - self.balance_leverage)
        # print("Record Length:", length)
        print("Market value: %s, shrunken(%.6f): %.2f, level(%s) %.2f" % (self.market_value, self.shrunken_ratio, self.shrunken_value, self.level_threshold, self.level))

        if length > self.ma1:
            # 指数均值
            # self.ma_dataframe['MA_st'] = self.ma_dataframe['price'].dropna().shift().fillna(self.ma_dataframe['MA_st']).ewm(com=self.ma1).mean()
            # 普通均值
            # self.ma_dataframe['MA_st'] =self.ma_dataframe['price'].fillna(self.ma_dataframe['MA_st']).rolling(self.ma1).mean()
            self.ma_dataframe.ix[length - 1, 'MA_st'] = self.ma_dataframe['price'].tail(self.ma1).mean()
        if length > self.ma2:
            # 指数均值
            # self.ma_dataframe['MA_lt'] = self.ma_dataframe['price'].dropna().shift().fillna(self.ma_dataframe['MA_lt']).ewm(com=self.ma2).mean()
            # 普通均值
            # self.ma_dataframe['MA_lt'] = self.ma_dataframe['price'].fillna(self.ma_dataframe['MA_lt']).rolling(self.ma2).mean()
            self.ma_dataframe.ix[length - 1, 'MA_lt'] = self.ma_dataframe['price'].tail(self.ma2).mean()

    def getHistoryMedian(self, latest_price, forward=False):
        self.updateHistory(latest_price, forward)
        return 
    def updateHistory(self, latest_price, forward=False):
        if forward:
            self.history.pop(0)
        else:
            self.history.pop()
        self.history.append(latest_price)



    def calculateRSI(self, period, RRSI=True):
        self.RSIperiod = period
        print("> Calculating RSI%d ..." % (self.RSIperiod))
        length = self.ma_dataframe.shape[0]
        if length > self.RSIperiod:
            delta = self.ma_dataframe['price'].dropna().apply(float).diff()
            dUp, dDown = delta.copy(), delta.copy()
            dUp[dUp < 0] = 0
            RollUp = dUp.rolling(window=self.RSIperiod).mean()
            dDown[dDown > 0] = 0
            RollDown = dDown.rolling(window=self.RSIperiod).mean().abs()
            # RSI = 100.0 * RollUp / (RollUp + RollDown)
            RSI = 4.0 * RollUp / (RollUp + RollDown)
            self.RRSI_threshold = self.RRSI_threshold * RSI.tail(1).item()
            RSI = 25.0 * RSI
            # RSI = 100.0 - (100.0 / (1.0 + RS))
            self.ma_dataframe['RSI'] = RSI

        if (RRSI) & (length>(self.RSIperiod+self.ma1)):
            # delta = self.ma_dataframe['RSI'].dropna().apply(float).diff() # 差分
            # RRSI = delta.rolling(window=self.ma1).mean() #再求平均，其实等于头尾相减平均，所以不用了
            RecentRSI = []
            for i in range(self.ma1, 1, -1):
                RecentRSI.append(self.ma_dataframe.ix[length-i, 'RSI'].item())
            self.ma_dataframe.ix[length-1, 'RRSI'] = self.ma_dataframe.ix[length-1, 'RSI'].item() - np.max(RecentRSI)
            self.RSI_median = np.median(RecentRSI)


    def tradeEvaluation(self, balance, quantity):
        print("> Start trade evaluation...")
        length = self.ma_dataframe.shape[0]
        if length > self.ma1:
            # 取出tail的两个数据，也就是最新的数据
            MA_st = self.ma_dataframe['MA_st'].tail(2).reset_index(drop=True)
            last_MA_st = MA_st[0]
            cur_MA_st = MA_st[1]
            MA_lt = self.ma_dataframe['MA_lt'].tail(2).reset_index(drop=True)
            last_MA_lt = MA_lt[0]
            cur_MA_lt = MA_lt[1]
            RSI = self.ma_dataframe['RSI'].tail(2).reset_index(drop=True) # 同样取出两个RSI数据
            last_RSI = RSI[0]
            cur_RSI = RSI[1]
            RRSI = self.ma_dataframe['RRSI'].tail(1).item()

            # 价格上轨
            # upper = MA_lt[1] + MA_lt[1] * self.profit_ratio_threshold
            # 价格下轨
            # lower = MA_lt[1] - MA_lt[1] * self.profit_ratio_threshold

            if self.sell_first == 0 and Decimal(balance) < Decimal('1.'):
                print("Too LITTLE to BUY!")
                self.state = 'tosell'
                self.sell_first = 1
            elif self.sell_first == 1 and Decimal(quantity) < Decimal('0.0001'):
                print("Too LITTLE to SELL")
                self.state = 'tobuy'
                self.sell_first = 0
            print('(sell_first = %d, state: %s)' % (self.sell_first, self.state))

            kline = self.CoinBase.get_kline('1min')
            if kline['status'] == 'ok' and kline['data']:
                print(getTime(kline['ts']))
                cur_price = kline['data'][0]['close']
                low = kline['data'][0]['low']
                high = kline['data'][0]['high']
            else:
                print("KLINE ERROR: ", kline)

            signal = None

            if self.sell_first == 0: # wait / tobuy
                print("MA DIF (Short-Long) %.2f -> %.2f" % (last_MA_st-last_MA_lt, cur_MA_st-cur_MA_lt))
                print("RSI %.2f -> %.2f, RRSI(%.3f) %.5f" % (last_RSI, cur_RSI, self.RRSI_threshold, RRSI))
                # State Machine (Sell)
                if cur_MA_st <= cur_MA_lt:
                    self.state = 'tobuy' # 行情下行，可以开始寻找买入时机了
                else:
                    self.state = 'wait' # 买入时机不成熟，继续观望，可考虑卖出
                # Action
                if self.state == 'tobuy':
                    if ((self.level < self.level_threshold) and (last_RSI <= cur_RSI) and (RRSI < self.RRSI_threshold or self.RSI_median < self.RSI_threshold)): # 买！
                        signal = {'signal': 'Long-position', 'direction': 'buy', 'confidence': ((100.0-cur_RSI)/100.0)}
                        self.target_price = cur_price * self.balance_leverage # 止盈
                        self.loss_limit = cur_price * self.deficit_stop_ratio # 止损
                        print("Confidence: %.2f%%, Target: %s, Limit: %s" % (100.0-cur_RSI, self.target_price, self.loss_limit))
                        self.state = 'tosell'
                        self.sell_first = 1 # 尽快卖出
                        self.shrunken_ratio = cur_price / self.temp_top
                    else:
                        if self.shrunken_value < self.market_value:
                            self.shrunken_ratio = self.shrunken_ratio + self.shrunken_ratio_stride
                elif self.state == 'wait':
                    if (Decimal(quantity) > Decimal('0.0001')) and (cur_RSI >= self.clearance_threshold) and RRSI > 0: # 清仓
                        signal = {'signal': 'Clearance-sale', 'direction': 'sell', 'confidence': (cur_RSI / 100.0)}
                        print("Clearance sale: %s * %.2f%%" % (Decimal(quantity).quantize(Decimal('0.0001'), rounding=ROUND_DOWN), cur_RSI))
                else:
                    print("Go to sell...")

            elif self.sell_first == 1: # wait / tosell
                print("Current price: %s, Target: %.2f, Limit(%.3f): %.2f" % (cur_price, self.target_price, self.deficit_stop_ratio, self.loss_limit))
                print("RSI %.2f -> %.2f, RRSI(%.3f) %s " % (last_RSI, cur_RSI, self.RRSI_threshold, RRSI))
                # State Machine (Sell)
                if (cur_price >= self.target_price):
                    self.state = 'tosell'
                else:
                    self.state = 'wait'
                # Action
                if self.state == 'tosell':
                    if (self.level > self.level_threshold) and (last_RSI >= cur_RSI) and RRSI >= 0:
                        signal = {'signal': 'Short-position', 'direction': 'sell', 'confidence': 1.0}
                        self.level_threshold = 0 # 重置市价水平阈值
                        self.state = 'tobuy'
                        self.sell_first = 0
                elif self.state == 'wait':
                    if (cur_price <= self.loss_limit and RRSI < 0): # 止损！！！
                        signal = {'signal': 'Loss-limit', 'direction': 'sell', 'confidence': 1.0}
                        self.deficit_stop_ratio = low / high
                        self.level_threshold = self.level - float(str(self.loss_limit)) * 1.0 * self.transaction_fee_ratio # 降低市价水平阈值，延缓再买入
                        self.state = 'wait'
                        self.sell_first = 0
                        print("My Godness!!!!!")
                else:
                    print("Go to buy...")
            if signal is not None:
                self.ma_dataframe.loc[self.ma_dataframe.index[length-1], 'signal'] = signal['direction']
            self.logPrice(True)
            # pd.set_option('display.max_rows',None)
            # pd.set_option('display.max_colwidth',500)
            print(self.ma_dataframe.tail(1))
            print('(sell_first = %d, state: %s)' % (self.sell_first, self.state))
            return signal
        else:
            self.logPrice(True)
            # pd.set_option('display.max_rows',None)
            # pd.set_option('display.max_colwidth',500)
            print(self.ma_dataframe.tail(1))



    def logPrice(self, append):
        #Log price to CSV
        if (append):
            columns = ['datetime','price', 'MA_st', 'MA_lt', 'RSI', 'RRSI', 'signal']
            self.ma_dataframe.tail(1).to_csv(self.csv_price, encoding='utf-8', mode='a',sep=',', index=False, header=False, columns=columns)
        else:
            self.ma_dataframe.tail(1).to_csv(self.csv_price, encoding='utf-8', sep=',',index=False, header=True)
    def logTransactions(self, append):
        #Log transactions to CSV
        if (append):
            columns = ['huobi_id' , 'product_id' , 'datetime', 'balance', 'buy/sell', 'price', 'quantity', 'status']
            self.transaction_dataframe.tail(1).to_csv(self.csv_transactions, encoding='utf-8', mode='a',sep=',', index=False, header=False,  columns=columns)
        else:
            self.transaction_dataframe.tail(1).to_csv(self.csv_transactions, encoding='utf-8', sep=',',index=False, header=True)




