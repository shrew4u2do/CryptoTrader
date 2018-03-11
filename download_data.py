import json
from binance.client import Client
from binance.helpers import date_to_milliseconds
import time
import os.path

#start = "14 hours ago UTC"
start = "1 Dec, 2017"
end = "now"
interval = Client.KLINE_INTERVAL_2HOUR
s = date_to_milliseconds(start)
e = date_to_milliseconds(end)

client = Client("", "")

info = client.get_exchange_info()
for d in info["symbols"]:
    if "BTC" in d["symbol"]:
        if os.path.exists("Binance_{}_{}_{}-{}.json".format(
                d["symbol"],
                interval,
                s,
                e
            )):
            print("Data for " + d["symbol"] + " exists. Skipping...")
            continue
        print(d["symbol"])
        klines = client.get_historical_klines(d["symbol"], interval, start, end)
        if len(klines) == 0:
            print("Data for " + d["symbol"] + " doesn't exist for this period. Skipping...")
            continue
        # open a file with filename including symbol, interval and start and end converted to milliseconds
        with open(
            "Binance_{}_{}_{}-{}.json".format(
                d["symbol"],
                interval,
                date_to_milliseconds(start),
                date_to_milliseconds(end)
            ),
            'w' # set file write mode
        ) as f:
            f.write(json.dumps(klines))
