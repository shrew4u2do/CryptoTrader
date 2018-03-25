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
import collections
import pandas as pd

TRADE_LOGGING = True


TESTING_MODE = False
tick = 40

LIVE_MODE = False
precision = 5

VIRTUAL_MODE = True

if sum(map(bool, [TESTING_MODE,LIVE_MODE,VIRTUAL_MODE])) != 1:
    print("Enable only one of testing, live, or virtual modes")
    sys.exit(0)

if LIVE_MODE:
    live_confirm = input('Entering live trading mode...continue? [y/n]: ')
    if live_confirm != "y":
        print("Exiting")
        sys.exit(0)

wallets = {}
filters = {}

BINANCE_KEY = sys.argv[1]
BINANCE_SECRET = sys.argv[2]
client = Client(BINANCE_KEY, BINANCE_SECRET)

if TESTING_MODE or VIRTUAL_MODE:
    balance = 0.2
else:
    info = client.get_account()
    balances = info["balances"]
    btc = next((item for item in balances if item["asset"] == "BTC"))
    balance = float(btc["free"])
    start_balance = balance
    for w in balances:
        wallets[w["asset"]] = w["free"]
    ce = client.get_exchange_info()
    for l in ce["symbols"]:
        filters[l["symbol"]] = l["filters"]

gain = 0.0

buy_count = 0
sell_count = 0


def process_m_message(msg):
    global balance, gain, buy_count, sell_count, kline_dict
    print("stream: {} data: {}".format(msg['stream'], msg['data']))
    symbol = msg["stream"].split('@')[0].upper()
    stream = msg["stream"].split('@')[1]
    # if stream == "trade":
    #     price = float(msg["data"]["p"])
    #     profit = price - float(recent_purchases_dict[symbol])
    #     if profit / float(prices_dict[symbol]) > 0.03:  # SELL?
    #         print("SELLING " + key + " at gain/loss price " + str(profit))
    #         bought_amount = float(wallets[symbol])
    #         btc_gain = bought_amount * price
    #         btc_gain -= (0.0005 * btc_gain)  # fee
    #         balance += btc_gain
    #         gain += (btc_gain - (bought_amount * float(recent_purchases_dict[symbol])))
    #         wallets[key] = 0.0
    #         del recent_purchases_dict[symbol]
    #         bm_dict[symbol].close()
    #         sell_count += 1
    if stream == "kline_2h":
        k = [msg["data"]["k"]["t"], msg["data"]["k"]["o"], msg["data"]["k"]["h"], msg["data"]["k"]["l"], msg["data"]["k"]["c"], msg["data"]["k"]["v"], msg["data"]["k"]["T"], msg["data"]["k"]["q"], msg["data"]["k"]["n"], msg["data"]["k"]["V"], msg["data"]["k"]["Q"], msg["data"]["k"]["B"]]
        try:
            kline_dict[symbol][-1] = k
        except Exception:
            return

gain_list = []



blacklist = ["BTCUSDT"]

if TRADE_LOGGING:
    start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with open(start_time + '.csv', 'a', newline='') as trade_log:
        headers = ["Date", "Side", "Symbol", "CCI", "RSI", "EMA", "SAR", "Boll U", "Boll L", "Price", "Amount", "Balance", "Gain"]
        writer = csv.writer(trade_log)
        writer.writerow(headers)




BTC_symbols = []
kline_dict = {}
volume_dict = {}
vol_delta_dict = {}
prices_dict = {}
recent_purchases_dict = {}
bm_dict = {}
buy_cooldown_dict = {}
rsi_overbought = {}
cci_overbought = {}
cci_history_dict = {}

sar_dict = {}
ema_dict = {}
rsi_dict = {}
cci_dict = {}
boll_dict = {}

def BBANDS(real, timeperiod=5, nbdevup=2, nbdevdn=2):
    ma = pd.rolling_mean(real, timeperiod, min_periods=timeperiod)
    std = pd.rolling_std(real, timeperiod, min_periods=timeperiod)
    lo = ma - nbdevdn * std
    hi = ma + nbdevup * std
    return hi, ma, lo

def update_klines(klines):
    while True:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        tickers = client.get_ticker()
        prices = client.get_all_tickers()
        for price in prices:
            prices_dict[price["symbol"]] = price["price"]
        for sym in tickers:
            volume_dict[sym["symbol"]] = sym["quoteVolume"]
        if LIVE_MODE:
            info = client.get_account()
            balances = info["balances"]
            for w in balances:
                wallets[w["asset"]] = w["free"]
                if w["asset"] == "BTC":
                    global balance
                    balance = float(w["free"])
        for symbol in BTC_symbols:
            if not TESTING_MODE:
                if symbol in blacklist or float(volume_dict[symbol]) < 100:
                    continue
                k = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR, limit='40')
                klines[symbol] = k
                o = []
                h = []
                l = []
                c = []
                v = []
                try:
                    for interval in klines[symbol]:
                        o.append(float(interval[1]))
                        h.append(float(interval[2]))
                        l.append(float(interval[3]))
                        c.append(float(interval[4]))
                        v.append(float(interval[5]))
                except KeyError as e:
                    print("Key error: {0}".format(e))
                    continue

                inputs = {
                    'open': numpy.asarray(o),
                    'high': numpy.asarray(h),
                    'low': numpy.asarray(l),
                    'close': numpy.asarray(c),
                    'volume': numpy.asarray(v)
                }
                cci = talib.CCI(inputs["high"], inputs["low"], inputs["close"], timeperiod=20)
                #if symbol not in cci_history_dict:
                 #   cci_history_dict[symbol] = collections.deque(maxlen=8)
                #cci_history_dict[symbol].append(cci.item(-1))



if TESTING_MODE:
    os.chdir("./training/test")
    for file in glob.glob("*ETH*.json"):  # assumes ETH will exist the whole period
        with open(file) as json_data:
            s = file.split('_')[1]
            d = json.load(json_data)
            sim_start = int(d[0][0])
            sim_end = int(d[-1][6])

    for file in glob.glob("*.json"):
        with open(file) as json_data:
            s = file.split('_')[1]
            d = json.load(json_data)
            first_appeared = int(d[0][0])
            diff = first_appeared - sim_start
            TWOHOURS_MS = 7200000
            FIVEMIN_MS = 300000
            zero_ints_needed = int(diff / TWOHOURS_MS)  # change when running a different interval.
            if diff > 0:
                empty_kline = [0, "0.0", "0.0", "0.0", "0.0", "0.0", 0, "0.0", 0, "0.0", "0.0", "0.0"]  # pad time before coin existed with empty kline
                for x in range(0, zero_ints_needed):
                    d.insert(0, empty_kline)
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
    th = threading.Thread(target=update_klines, args=(kline_dict,))
    th.start()
    print("Waiting for initial data to populate...")
    time.sleep(25)
while True:
    if not TESTING_MODE and th.isAlive() is False:
        print("RESTARTING UPDATE")
        th = threading.Thread(target=update_klines, args=(kline_dict,))
        th.start()

    if LIVE_MODE:
        gain = float(wallets["BTC"]) - float(start_balance)
    print("\nBTC BALANCE: " + f"{balance:.8f}")
    print("GAIN: " + f"{gain:.8f}")
    print("BUYS: " + str(buy_count))
    print("SELLS: " + str(sell_count))
    print("RECENT PURCHASES: ")
    for key, value in recent_purchases_dict.items():
        #cci_slope = linregress(range(len(cci_history_dict[key])), cci_history_dict[key]).slope
        print(key + " Purchased Price: " + f"{value:.8f}" + " Current Price: " + f"{float(prices_dict[key]):.8f}" + " EMA: " + f"{ema_dict[key].item(-1):.8f}" +
              " SAR: " + f"{sar_dict[key].item(-1):.8f}" + " CCI: " + f"{cci_dict[key].item(-1):.8f}" + " RSI: " + f"{rsi_dict[key].item(-1):.8f}")
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
            test_window = kline_dict[symbol][tick-40:tick]
            if len(test_window) == 0:
                sys.exit(0)  # test window is empty. the sim is probably done...
            for interval in test_window:
                o.append(float(interval[1]))
                h.append(float(interval[2]))
                l.append(float(interval[3]))
                c.append(float(interval[4]))
                v.append(float(interval[5]))
            prices_dict[symbol] = test_window[-1][4]
        else:
            try:
                for interval in kline_dict[symbol]:
                    o.append(float(interval[1]))
                    h.append(float(interval[2]))
                    l.append(float(interval[3]))
                    c.append(float(interval[4]))
                    v.append(float(interval[5]))
            except KeyError as e:
                print("Key error: {0}".format(e))
                continue

        inputs = {
            'open': numpy.asarray(o),
            'high': numpy.asarray(h),
            'low': numpy.asarray(l),
            'close': numpy.asarray(c),
            'volume': numpy.asarray(v)
        }
        sar = talib.SAR(inputs["high"], inputs["low"])
        sar_dict[symbol] = sar
        ema = talib.TEMA(inputs["close"], timeperiod=9)
        ema_dict[symbol] = ema
        rsi = talib.RSI(inputs["close"]*100000, timeperiod=14)
        rsi_dict[symbol] = rsi
        cci = talib.CCI(inputs["high"], inputs["low"], inputs["close"], timeperiod=20)
        cci_dict[symbol] = cci
        if symbol not in cci_overbought:
            cci_overbought[symbol] = True
        upperband, middleband, lowerband = BBANDS(inputs["close"], timeperiod=10, nbdevup=2, nbdevdn=2)
        boll_dict[symbol] = [upperband, middleband, lowerband]

        obv = talib.OBV(inputs["close"], inputs["volume"]).tolist()
        vol_delta = linregress(range(len(obv)), obv).slope
        vol_delta_dict[symbol] = vol_delta

    sorted_vol_delta_list = sorted(vol_delta_dict, key=vol_delta_dict.get)
    for sym in sorted_vol_delta_list:
        #cci_slope = linregress(range(len(cci_history_dict[sym])), cci_history_dict[sym]).slope
        if not TESTING_MODE:
            print("MAX VOL: " + sym + " (" + str(vol_delta_dict[sym]) + ") " + " PRICE: " + prices_dict[sym] + " EMA: " + f"{ema_dict[sym].item(-1):.8f}" +
              " SAR: " + f"{sar_dict[sym].item(-1):.8f}" + " CCI: " + f"{cci_dict[sym].item(-1):.8f}" + " RSI: " + f"{rsi_dict[sym].item(-1):.8f}")
        last_sar = float(sar_dict[sym].item(-1))
        last_rsi = float(rsi_dict[sym].item(-1))
        last_last_rsi = float(rsi_dict[sym].item(-2))
        last_last_boll_l = float(boll_dict[sym][2].item(-2))
        last_boll_l = float(boll_dict[sym][2].item(-1))
        last_boll_h = float(boll_dict[sym][0].item(-1))
        try:
            last_cci = float(cci_dict[sym].item(-1))
        except IndexError:
            continue
        last_ema = float(ema_dict[sym].item(-1))
        last_last_price = float(kline_dict[sym][-2][4])
        if TESTING_MODE:
            last_price = float(prices_dict[sym])
        else:
            last_price = float(kline_dict[sym][-1][4])
        if last_last_price < last_last_boll_l and last_price > last_boll_l and last_last_rsi < 30 and last_rsi > 30 and sym not in recent_purchases_dict and len(
                recent_purchases_dict) < 10 and sym not in blacklist and balance > 0.001:  # BUY if the stars and moon align
        #if 100 < last_cci < 180 and last_price > last_ema and last_rsi < 70 and sym in cci_overbought and not cci_overbought[sym] and sym not in recent_purchases_dict and len(
        #        recent_purchases_dict) < 20 and sym not in blacklist and balance > 0.001:  # BUY if the stars and moon align
            if not TESTING_MODE:
                if sym in buy_cooldown_dict and datetime.datetime.now() < buy_cooldown_dict[sym]:
                    continue
            if VIRTUAL_MODE or TESTING_MODE:
                buy_amount_btc = 0.3 * balance
                wallets[sym.split("BTC")[0]] = buy_amount_btc / last_price
                wallets[sym.split("BTC")[0]] -= (0.0005 * float(wallets[sym.split("BTC")[0]]))  # binance fee
                balance -= buy_amount_btc
            elif LIVE_MODE:
                buy_amount_btc = 0.3 * float(wallets["BTC"])
                buy = buy_amount_btc / last_price
                step = float(filters[sym][1]["stepSize"])
                m = float(buy) % step
                a = float(buy) - m
                amt_str = "{:0.0{}f}".format(a, precision)
                order = client.order_market_buy(symbol=sym, quantity=amt_str)
                info = client.get_account()
                balances = info["balances"]
                for w in balances:
                    wallets[w["asset"]] = w["free"]

            recent_purchases_dict[sym] = last_price
            rsi_overbought[sym] = False
            if not TESTING_MODE:
                bm_dict[sym] = BinanceSocketManager(client)
                conn_key = bm_dict[sym].start_multiplex_socket([sym.lower()+'@trade', sym.lower()+'@kline_2h'], process_m_message)
                bm_dict[sym].start()
            if TRADE_LOGGING:
                if TESTING_MODE:
                    t = datetime.datetime.utcfromtimestamp(
                        float(kline_dict[symbol][tick - 40:tick][-1][6]) / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    t = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                trade = [t, "BUY", sym, f"{last_cci:.8f}", f"{last_rsi:.8f}", f"{last_ema:.8f}", f"{last_sar:.8f}", f"{last_boll_h:.8f}", f"{last_boll_l:.8f}", f"{last_price:.8f}", wallets[sym.split("BTC")[0]], f"{balance:.8f}", f"{gain:.8f}"]
                with open(start_time + '.csv', 'a', newline='') as trade_log:
                    writer = csv.writer(trade_log)
                    a = writer.writerow(trade)
            buy_count += 1
        cci_overbought[sym] = last_cci > 100

    sells = []
    for key, value in recent_purchases_dict.items():
        profit = float(prices_dict[key]) - float(value)
        sar = sar_dict[key]
        last_sar = float(sar.item(-1))
        ema = ema_dict[key]
        last_ema = float(ema.item(-1))
        rsi = rsi_dict[key]
        last_rsi = float(rsi.item(-1))
        cci = cci_dict[key]
        last_cci = float(cci.item(-1))
        #cci_slope = linregress(range(len(cci_history_dict[key])), cci_history_dict[key]).slope
        last_boll_l = float(boll_dict[key][2].item(-1))
        last_boll_h = float(boll_dict[key][0].item(-1))
        if TESTING_MODE:
            last_price = float(prices_dict[key])
        else:
            last_price = float(kline_dict[key][-1][4])
        if last_price > last_boll_h or last_price < (last_boll_l - 4e-8):
        #if (last_price < last_ema and last_cci < 95) or (key in rsi_overbought and rsi_overbought[key] and last_rsi < 70) or last_cci < -200 or last_cci > 200 or cci_slope < -0.2:
            print("SELLING " + key + " at gain/loss price " + str(profit))
            if last_rsi < 70:
                rsi_overbought[key] = False
            bought_amount = float(wallets[key.split("BTC")[0]])
            if VIRTUAL_MODE or TESTING_MODE:
                btc_gain = bought_amount * last_price
                btc_gain -= (0.0005 * btc_gain)  # binance fee
                balance += btc_gain
                gain += (btc_gain - (bought_amount * float(value)))
                wallets[key.split("BTC")[0]] = 0.0
            elif LIVE_MODE:
                step = float(filters[key][1]["stepSize"])
                m = float(bought_amount) % step
                a = float(bought_amount) - m
                amt_str = "{:0.0{}f}".format(a, precision)
                order = client.order_market_sell(symbol=key, quantity=amt_str)
                info = client.get_account()
                balances = info["balances"]
                for w in balances:
                    wallets[w["asset"]] = w["free"]
            if not TESTING_MODE:
                buy_cooldown_dict[key] = datetime.datetime.now() + datetime.timedelta(minutes=60)
                bm_dict[key].close()
            if TRADE_LOGGING:
                if TESTING_MODE:
                    t = datetime.datetime.utcfromtimestamp(
                        float(kline_dict[symbol][tick - 40:tick][-1][6]) / 1000
                    ).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    t = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                trade = [t, "SELL", key, f"{last_cci:.8f}", f"{last_rsi:.8f}", f"{last_ema:.8f}", f"{last_sar:.8f}", f"{last_boll_h:.8f}", f"{last_boll_l:.8f}", f"{last_price:.8f}", bought_amount, f"{balance:.8f}", f"{gain:.8f}"]
                with open(start_time + '.csv', 'a', newline='') as trade_log:
                    writer = csv.writer(trade_log)
                    a = writer.writerow(trade)
            sells.append(key)
            sell_count += 1
        if last_rsi > 70:
            rsi_overbought[key] = True
        cci_overbought[key] = last_cci > 100
    for s in sells:
        del recent_purchases_dict[s]

    if TESTING_MODE:
        tick += 1
