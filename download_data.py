import json
from binance.client import Client
from binance.helpers import date_to_milliseconds
import time
import os.path

start = "1 Dec, 2017"
end = "1 Jan, 2018"
interval = Client.KLINE_INTERVAL_5MINUTE

client = Client("", "")

info = client.get_exchange_info()
for d in info["symbols"]:
    if "BTC" in d["symbol"]:
        if os.path.exists("Binance_{}_{}_{}-{}.json".format(
                d["symbol"],
                interval,
                date_to_milliseconds(start),
                date_to_milliseconds(end)
            )):
            continue
        print(d["symbol"])
        klines = client.get_historical_klines(d["symbol"], interval, start, end)

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
        time.sleep(10)