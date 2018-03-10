import sys
import time
import datetime
from binance.client import Client

import numpy
import talib
from binance.websockets import BinanceSocketManager
from scipy.stats import linregress
import glob
import os
import json
import csv
import threading

TESTING_MODE = False
tick = 30

TRADE_LOGGING = True

balance = 0.2
gain = 0.0

buy_count = 0
sell_count = 0


def process_m_message(msg):
    global balance, gain, buy_count, sell_count
    #print("stream: {} data: {}".format(msg['stream'], msg['data']))
    symbol = msg["stream"].split('@')[0].upper()
    stream = msg["stream"].split('@')[1]
    if stream == "trade":
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

gain_list = []

BINANCE_KEY = sys.argv[1]
BINANCE_SECRET = sys.argv[2]

blacklist = ["BTCUSDT", "NCASHBTC", "TRXBTC"]

if TRADE_LOGGING:
    start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with open(start_time + '.csv', 'a', newline='') as trade_log:
        headers = ["Date", "Side", "Symbol", "Last EMA", "Price", "Amount", "Balance", "Gain"]
        writer = csv.writer(trade_log)
        writer.writerow(headers)


wallets = {}

BTC_symbols = []
kline_dict = {}
volume_dict = {}
vol_delta_dict = {}
prices_dict = {}
recent_purchases_dict = {}
bm_dict = {}

sar_dict = {}
ema_dict = {}
rsi_dict = {}

def update_klines(klines):
    while True:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        tickers = client.get_ticker()
        prices = client.get_all_tickers()
        for price in prices:
            prices_dict[price["symbol"]] = price["price"]
        for sym in tickers:
            volume_dict[sym["symbol"]] = sym["quoteVolume"]
        for symbol in BTC_symbols:
            if not TESTING_MODE:
                if symbol in blacklist or float(volume_dict[symbol]) < 100:
                    continue
                k = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_2HOUR, limit='30')
                klines[symbol] = k


client = Client(BINANCE_KEY, BINANCE_SECRET)
if TESTING_MODE:
    os.chdir("./training/DecMar-2hr")
    for file in glob.glob("*.json"):
        with open(file) as json_data:
            s = file.split('_')[1]
            d = json.load(json_data)
            kline_dict[s] = d
            if "BTC" in s:
                BTC_symbols.append(s)
    os.chdir("../..")
else:
    info = client.get_exchange_info()
    for d in info["symbols"]:
        if "BTC" in d["symbol"]:
            BTC_symbols.append(d["symbol"])

if not TESTING_MODE:
    t = threading.Thread(target=update_klines, args=(kline_dict,))
    t.start()
    print("Waiting for initial data to populate...")
    time.sleep(30)
while True:
    print("\nBTC BALANCE: " + f"{balance:.8f}")
    print("GAIN: " + f"{gain:.8f}")
    print("BUYS: " + str(buy_count))
    print("SELLS: " + str(sell_count))
    print("RECENT PURCHASES: ")
    for key, value in recent_purchases_dict.items():
        print(key + " " + value)
    if not TESTING_MODE:
        print("UPDATING " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print("UPDATING " + str(tick))
    for symbol in BTC_symbols:
        if not TESTING_MODE:
            if symbol in blacklist or float(volume_dict[symbol]) < 100:
                continue
        o = []
        h = []
        l = []
        c = []
        v = []
        if TESTING_MODE:
            test_window = kline_dict[symbol][tick-30:tick]
            for interval in test_window:
                o.append(float(interval[1]))
                h.append(float(interval[2]))
                l.append(float(interval[3]))
                c.append(float(interval[4]))
                v.append(float(interval[5]))
            prices_dict[symbol] = test_window[-1][4]
        else:
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
        ema = talib.EMA(inputs["close"], timeperiod=14)
        ema_dict[symbol] = ema
        rsi = talib.RSI(inputs["close"], timeperiod=14)
        rsi_dict[symbol] = rsi

        obv = talib.OBV(inputs["close"], inputs["volume"]).tolist()
        vol_delta = linregress(range(len(obv)), obv).slope
        vol_delta_dict[symbol] = vol_delta

    sorted_vol_delta_list = sorted(vol_delta_dict, key=vol_delta_dict.get)[-10:]
    for sym in sorted_vol_delta_list:
        if not TESTING_MODE:
            print("MAX VOL: " + sym + " (" + str(vol_delta_dict[sym]) + ") " + " PRICE: " + prices_dict[sym])
        last_sar = float(sar_dict[sym].item(-1))
        last_last_sar = float(sar_dict[sym].item(-2))
        last_ema = float(ema_dict[sym].item(-1))
        if TESTING_MODE:
            last_price = float(prices_dict[sym])
        else:
            last_price = float(kline_dict[sym][-1][4])
        if last_sar < last_price and last_last_sar > last_price and last_price > last_ema and sym not in recent_purchases_dict and len(
                recent_purchases_dict) < 20 and sym not in blacklist and balance > 0.01:  # BUY if we dont have it
            buy_amount_btc = 0.3 * balance
            wallets[sym] = buy_amount_btc / float(prices_dict[sym])
            wallets[sym] -= (0.0005 * float(wallets[sym]))  # binance fee
            balance -= buy_amount_btc
            recent_purchases_dict[sym] = prices_dict[sym]
            #if not TESTING_MODE:
                #bm_dict[sym] = BinanceSocketManager(client)
                #conn_key = bm_dict[sym].start_multiplex_socket([sym.lower()+'@trade', sym.lower()+'@kline_1m'], process_m_message)
                #bm_dict[sym].start()
            if TRADE_LOGGING:
                if TESTING_MODE:
                    t = datetime.datetime.utcfromtimestamp(
                        float(kline_dict[symbol][tick - 30:tick][-1][6]) / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    t = datetime.datetime.utcfromtimestamp(
                        float(kline_dict[symbol][-1][6]) / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                trade = [t, "BUY", sym, f"{last_ema:.8f}", prices_dict[sym], wallets[sym], f"{balance:.8f}", f"{gain:.8f}"]
                with open(start_time + '.csv', 'a', newline='') as trade_log:
                    writer = csv.writer(trade_log)
                    a = writer.writerow(trade)
            buy_count += 1

    sells = []
    for key, value in recent_purchases_dict.items():
        profit = float(prices_dict[key]) - float(value)
        sar = sar_dict[key]
        last_sar = float(sar.item(-1))
        ema = ema_dict[key]
        last_ema = float(ema.item(-1))
        rsi = rsi_dict[key]
        last_rsi = float(rsi.item(-1))
        if TESTING_MODE:
            last_price = float(prices_dict[key])
        else:
            last_price = float(kline_dict[key][-1][4])
        if (last_sar > last_price and last_price < last_ema) or last_rsi > 70:
            print("SELLING " + key + " at gain/loss price " + str(profit))
            bought_amount = float(wallets[key])
            curr_price = float(prices_dict[key])
            btc_gain = bought_amount * curr_price
            btc_gain -= (0.0005 * btc_gain)  # binance fee
            balance += btc_gain
            gain += (btc_gain - (bought_amount * float(value)))
            wallets[key] = 0.0
            #if not TESTING_MODE:
                #bm_dict[key].close()
            if TRADE_LOGGING:
                if TESTING_MODE:
                    t = datetime.datetime.utcfromtimestamp(
                        float(kline_dict[symbol][tick - 30:tick][-1][6]) / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    t = datetime.datetime.utcfromtimestamp(
                        float(kline_dict[symbol][-1][6]) / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                trade = [t, "SELL", key, f"{last_ema:.8f}", prices_dict[key], bought_amount, f"{balance:.8f}", f"{gain:.8f}"]
                with open(start_time + '.csv', 'a', newline='') as trade_log:
                    writer = csv.writer(trade_log)
                    a = writer.writerow(trade)
            sells.append(key)
            sell_count += 1
    for s in sells:
        del recent_purchases_dict[s]
        sells.remove(s)

    if TESTING_MODE:
        tick += 1
