import json, requests, datetime
from Utils import *

ACCOUNT_ID = 0

class CoinbaseExchange(CoinbaseExchangeAuth):
    #Class used to perform different actions on the GDAX API
    def __init__(self, symbol,access_key, secret_key, market_url, trade_url):
        super(CoinbaseExchange,self).__init__(access_key, secret_key, market_url, trade_url)
        self.symbol = symbol

    def get_kline(self,period='1min', size=1):
        """
        :param symbol
        :param period: 可选值：{1min, 5min, 15min, 30min, 60min, 1day, 1mon, 1week, 1year }
        :param size: 可选值： [1,2000]
        """
        url = self.market_url + '/history/kline'
        params = {'symbol': self.symbol,
                  'period': period,
                  'size': size}
        return self.http_get_request(params, url)

    def get_accounts(self):
        """
        :return id: account-id
        :return state: 账户状态：{working：正常, lock：账户被锁定}
        :return type: 账户类型：{spot：现货账户， margin：杠杆账户，otc：OTC账户，point：点卡账户}
        """
        path = "/account/accounts"
        params = {}
        return self.api_key_get(params, path)

    def send_order(self,amount, source, _type, price=0):
        """
        :param amount:
        :param source: 如果使用借贷资产交易，请在下单接口,请求参数source中填写'margin-api'
        :param symbol:
        :param _type: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
        :param price:
        :return:
        """
        try:
            accounts = self.get_accounts()
            acct_id = accounts['data'][0]['id']
        except BaseException as e:
            print('get acct_id error.%s' % e)
            acct_id = ACCOUNT_ID

        params = {"account-id": acct_id,
                  "amount": amount,
                  "symbol": self.symbol,
                  "type": _type,
                  "source": source}
        if price:
            params["price"] = price

        url = '/order/orders/place'
        return self.api_key_post(params, url)

    def get_balance(self,acct_id=None):
        """
        :param acct_id
        :return:
        """
        global ACCOUNT_ID

        if not acct_id:
            accounts = self.get_accounts()
            acct_id = accounts['data'][0]['id'];
        url = "/account/accounts/{0}/balance".format(acct_id)
        params = {"account-id": acct_id}
        return self.api_key_get(params, url)

    def get_timestamp(self):
        url = self.trade_url + '/common/timestamp'
        return self.http_get_url(url)

    def orders_matchresults(self,symbol=None, types='buy-market,sell-market', start_date="2018-08-15", end_date=None, oid_from=None, direct='prev', size=None):
        """
        :param symbol:
        :param types: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
        :param start_date:
        :param end_date:
        :param oid_from:
        :param direct: 可选值{prev 向前，next 向后}
        :param size:
        :return:
        """
        params = {'symbol': self.symbol}

        if types:
            params['types'] = types
        if start_date:
            params['start-date'] = start_date
        if end_date:
            params['end-date'] = end_date
        if oid_from:
            params['from'] = oid_from
        if direct:
            params['direct'] = direct
        if size:
            params['size'] = size
        url = '/order/matchresults'
        return self.api_key_get(params, url)

    def get_orders(self,symbol=None, types='buy-market,sell-market', start_date="2018-08-15", end_date=None, states='submitted,partial-filled,partial-canceled', oid_from=None, direct='prev', size=None):
        """
        :param symbol: 交易对，btcusdt, bchbtc, rcneth ...
        :param types:  查询的订单类型组合，使用','分割: buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖, buy-ioc：IOC买单, sell-ioc：IOC卖单
        :start-date:   查询开始日期, 日期格式yyyy-mm-dd      
        :end-date:     查询结束日期, 日期格式yyyy-mm-dd      
        :states:       查询的订单状态组合，使用','分割：submitted 已提交, partial-filled 部分成交, partial-canceled 部分成交撤销, filled 完全成交, canceled 已撤销
        :from:         查询起始 ID     
        :direct:       查询方向：prev 向前，next 向后
        :size:         查询记录大小
        """
        params = {'symbol': self.symbol,
                  'states': states}

        if types:
            params['types'] = types
        if start_date:
            params['start-date'] = start_date
        if end_date:
            params['end-date'] = end_date
        if oid_from:
            params['from'] = oid_from
        if direct:
            params['direct'] = direct
        if size:
            params['size'] = size
        url = '/order/orders'
        return self.api_key_get(params, url)
