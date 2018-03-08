import sys
import time
import datetime
from binance.client import Client

import numpy
import talib
from binance.websockets import BinanceSocketManager
from scipy.stats import linregress

balance = 10.0
gain = 0.0

buy_count = 0
sell_count = 0


def process_m_message(msg):
    global balance, gain, buy_count, sell_count
    #print("stream: {} data: {}".format(msg['stream'], msg['data']))
    symbol = msg["stream"].split('@')[0].upper()
    stream = msg["stream"].split('@')[1]
    if stream == "trade":
        #print("trade")
        price = float(msg["data"]["p"])
        profit = price - float(recent_purchases_dict[symbol])
        if profit / float(prices_dict[symbol]) > 0.03:  # SELL?
            print("SELLING " + key + " at gain/loss price " + str(profit))
            bought_amount = float(wallets[symbol])
            btc_gain = bought_amount * price
            btc_gain -= (0.0005 * btc_gain)  # fee
            balance += btc_gain
            gain += (btc_gain - (bought_amount * float(recent_purchases_dict[symbol])))
            wallets[key] = 0.0
            del recent_purchases_dict[symbol]
            bm_dict[symbol].close()
            sell_count += 1
    #elif stream == "kline_1m":
    #    print("kline")


BINANCE_KEY = sys.argv[1]
BINANCE_SECRET = sys.argv[2]

blacklist = ["BTCUSDT", "TRXBTC", "NCASHBTC"]


wallets = {}

BTC_symbols = []
kline_dict = {}
volume_dict = {}
vol_delta_dict = {}
close_delta_dict = {}
prices_dict = {}
recent_purchases_dict = {}
bm_dict = {}

sar_dict = {}
ema_dict = {}
rsi_dict = {}

client = Client(BINANCE_KEY, BINANCE_SECRET)

info = client.get_exchange_info()
for d in info["symbols"]:
    if "BTC" in d["symbol"]:
        BTC_symbols.append(d["symbol"])


while True:
    print("\nBTC BALANCE: " + str(balance))
    print("GAIN: " + str(gain))
    print("BUYS: " + str(buy_count))
    print("SELLS: " + str(sell_count))
    print("RECENT PURCHASES: ")
    for key, value in recent_purchases_dict.items():
        print(key + " " + value)
    tickers = client.get_ticker()
    for sym in tickers:
        volume_dict[sym["symbol"]] = sym["quoteVolume"]
    prices = client.get_all_tickers()
    for price in prices:
        prices_dict[price["symbol"]] = price["price"]
    print("UPDATING " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    for symbol in BTC_symbols:
        if symbol in blacklist or float(volume_dict[symbol]) < 100:
            continue
        kline_dict[symbol] = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_5MINUTE, limit='15')

        o = []
        h = []
        l = []
        c = []
        v = []
        for interval in kline_dict[symbol]:
            o.append(float(interval[1]))
            h.append(float(interval[2]))
            l.append(float(interval[3]))
            c.append(float(interval[4]))
            v.append(float(interval[5]))

        inputs = {
            'open': numpy.asarray(o),
            'high': numpy.asarray(h),
            'low': numpy.asarray(l),
            'close': numpy.asarray(c),
            'volume': numpy.asarray(v)
        }

        sar = talib.SAR(inputs["high"], inputs["low"])
        sar_dict[symbol] = sar
        ema = talib.EMA(inputs["close"], timeperiod=7)
        ema_dict[symbol] = ema
        rsi = talib.RSI(inputs["close"], timeperiod=14)
        rsi_dict[symbol] = rsi

        obv = talib.OBV(inputs["close"], inputs["volume"]).tolist()
        vol_delta = linregress(range(len(obv)), obv).slope
        vol_delta_dict[symbol] = vol_delta

        close_delta = float(kline_dict[symbol][-2][4])
        close_delta_dict[symbol] = close_delta

    sorted_vol_delta_list = sorted(vol_delta_dict, key=vol_delta_dict.get)[-10:]
    for sym in sorted_vol_delta_list:
        print("MAX VOL: " + sym + " (" + str(vol_delta_dict[sym]) + ") " + " PRICE: " + prices_dict[sym])
        last_sar = float(sar_dict[sym].item(-1))
        last_last_sar = float(sar_dict[sym].item(-2))
        last_ema = float(ema_dict[sym].item(-2))
        last_price = float(close_delta_dict[sym])
        if last_sar < last_price and last_last_sar > last_price and last_price > last_ema and sym not in recent_purchases_dict and len(
                recent_purchases_dict) < 5 and sym not in blacklist:  # BUY if we dont have it
            buy_amount_btc = 0.1 * balance
            wallets[sym] = buy_amount_btc / float(prices_dict[sym])
            wallets[sym] -= (0.0005 * float(wallets[sym]))  # binance fee
            balance -= buy_amount_btc
            recent_purchases_dict[sym] = prices_dict[sym]
            bm_dict[sym] = BinanceSocketManager(client)
            conn_key = bm_dict[sym].start_multiplex_socket([sym.lower()+'@trade', sym.lower()+'@kline_1m'], process_m_message)
            bm_dict[sym].start()
            print("buying " + str(wallets[sym]) + " " + sym + " at " + str(prices_dict[sym]))
            sar_diff = last_price - last_sar
            print("buying. last_sar: " + str(last_sar) + " last_last_sar: " + str(last_last_sar) + " last_price: " + str(last_price) + ". Diff: " + str(
                sar_diff))
            buy_count += 1
        else:
            sar_diff = last_price - last_sar
            print(
                "not buying. last_sar: " + str(last_sar) + " last_last_sar: " + str(last_last_sar) + " last_price: " + str(
                    last_price) + " last_ema: " + str(last_ema) +  ". Diff: " + str(
                    sar_diff))
            print("last_sar < last_price: " + str(last_sar < last_price))
            print("last_last_sar > last_price: " + str(last_last_sar > last_price))
            print("last_price > last_ema: " + str(last_price > last_ema))

    sells = []
    for key, value in recent_purchases_dict.items():
        profit = float(prices_dict[key]) - float(value)
        sar = sar_dict[key]
        last_sar = float(sar.item(-1))
        ema = ema_dict[key]
        last_ema = float(ema.item(-2))
        rsi = rsi_dict[key]
        last_rsi = float(rsi.item(-1))
        last_price = float(close_delta_dict[key])
        if (last_sar > last_price and last_price < last_ema) or last_rsi > 70:
            print("SELLING " + key + " at gain/loss price " + str(profit))
            bought_amount = float(wallets[key])
            curr_price = float(prices_dict[key])
            btc_gain = bought_amount * curr_price
            btc_gain -= (0.0005 * btc_gain)  # binance fee
            balance += btc_gain
            gain += (btc_gain - (bought_amount * float(value)))
            wallets[key] = 0.0
            bm_dict[key].close()
            sells.append(key)
            sell_count += 1
    for s in sells:
        del recent_purchases_dict[s]

    #time.sleep(38)
