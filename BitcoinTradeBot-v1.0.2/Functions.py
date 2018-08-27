import time
def getTime(ts):
    time_str = int(ts) / 1000
    time_str = time.localtime(time_str)
    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time_str)
    return time_str