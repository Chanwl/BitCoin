import time
from TimeThread import *

# 换账户仅修改下面ACCESS_KEY和SECRET_KEY
# 调参请到MaModel.py, line:25

''' Time settings '''
LOOP_DURATION = 1# Time period (in seconds)
MAX_LOOP_TIME = 120 * 60 * 60 # Max duration to run (in seconds)


''' Use REST API '''
SYMBOL = "btcusdt"

# ''' TEST Keys'''
# ACCESS_KEY = "204e335a-3208ae52-75d34260-1068a"
# SECRET_KEY = "51e0753d-23e60931-1f60f52c-4fa9b"

# '''WORK Keys'''
# ACCESS_KEY = "075aae5e-8bea2755-71253241-738d8"
# SECRET_KEY = "89040928-6f1d2fb8-347f74f2-71893"

# '''FINAL Keys'''
ACCESS_KEY = "9ec0c479-8a25992c-bc3260f5-e3989"
SECRET_KEY = "4436c80a-010aa1aa-1fec5c26-ab0dc"

# API 请求地址
MARKET_URL = "https://api.hadax.com/market"
TRADE_URL = "https://api.hadax.com/v1"
# CSV Records
CSV_PRICE = "./price.csv" # Price CSV name
CSV_TRANSACTIONS = "./transactions.csv" # Transaction CSV name

''' Set proxy '''
os.environ['HTTP_PROXY'] = 'http://web-proxy.tencent.com:8080'
os.environ['HTTPS_PROXY'] = 'http://web-proxy.tencent.com:8080'

''' Start thread '''
stopFlag = Event()
thread = TimedThread(stopFlag, LOOP_DURATION,SYMBOL,ACCESS_KEY,SECRET_KEY,MARKET_URL,TRADE_URL, CSV_PRICE, CSV_TRANSACTIONS)
thread.daemon = True
thread.start()
time.sleep(MAX_LOOP_TIME)
stopFlag.set() # Stop
