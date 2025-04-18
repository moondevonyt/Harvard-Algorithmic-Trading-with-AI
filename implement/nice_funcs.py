

from eth_account.signers.local import LocalAccount
import eth_account
import json
import time 
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import ccxt
import pandas as pd
import datetime
import schedule 
import requests 
from datetime import datetime, timedelta
import pandas_ta as ta
import ccxt 
print('sup dawg')
from termcolor import colored


def ask_bid(symbol):
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}

    data = {
        'type': 'l2Book',
        'coin': symbol
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    l2_data = response.json()
    l2_data = l2_data['levels']

    # get bid and ask 
    bid = float(l2_data[0][0]['px'])
    ask = float(l2_data[1][0]['px'])

    return ask, bid, l2_data


    
def get_sz_px_decimals(symbol):

    '''
    this is succesfully returns Size decimals and Price decimals

    this outputs the size decimals for a given symbol
    which is - the SIZE you can buy or sell at
    ex. if sz decimal == 1 then you can buy/sell 1.4
    if sz decimal == 2 then you can buy/sell 1.45
    if sz decimal == 3 then you can buy/sell 1.456

    if size isnt right, we get this error. to avoid it use the sz decimal func
    {'error': 'Invalid order size'}
    '''
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}
    data = {'type': 'meta'}

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        # Success
        data = response.json()
        #print(data)
        symbols = data['universe']
        symbol_info = next((s for s in symbols if s['name'] == symbol), None)
        if symbol_info:
            sz_decimals = symbol_info['szDecimals']
            
        else:
            print('Symbol not found')
    else:
        # Error
        print('Error:', response.status_code)

    ask = ask_bid(symbol)[0]
    # print(f'this is the ask {ask}')

    # Compute the number of decimal points in the ask price
    ask_str = str(ask)
    print(f'this is the ask str {ask_str}')
    if '.' in ask_str:
        px_decimals = len(ask_str.split('.')[1])
    else:
        px_decimals = 0

    print(f'{symbol} this is the price: {ask}  sz decimal(s) {sz_decimals}, px decimal(s) {px_decimals}')

    return sz_decimals, px_decimals

def adjust_leverage_usd_size(symbol, usd_size, leverage, account):

        '''
        this calculates size based off a specific USD dollar amount
        '''

        print('leverage:', leverage)

        #account: LocalAccount = eth_account.Account.from_key(key)
        exchange = Exchange(account, constants.MAINNET_API_URL)
        info = Info(constants.MAINNET_API_URL, skip_ws=True)

        # Get the user state and print out leverage information for ETH
        user_state = info.user_state(account.address)
        acct_value = user_state["marginSummary"]["accountValue"]
        acct_value = float(acct_value)

        print(exchange.update_leverage(leverage, symbol, is_cross=False))

        price = ask_bid(symbol)[0]

        # size == balance / price * leverage
        # INJ 6.95 ... at 10x lev... 10 INJ == $cost 6.95
        size = (usd_size / price) * leverage
        size = float(size)
        rounding = get_sz_px_decimals(symbol)[0]
        size = round(size, rounding)
        print(f'this is the size of crypto we will be using {size}')
    
        user_state = info.user_state(account.address)
            
        return leverage, size


def get_ohlcv2(symbol, interval, lookback_days):
    end_time = datetime.now()
    start_time = end_time - timedelta(days=lookback_days)
    
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type': 'application/json'}
    data = {
        "type": "candleSnapshot",
        "req": {
            "coin": symbol,
            "interval": interval,
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000)
        }
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        snapshot_data = response.json()
        return snapshot_data
    else:
        print(f"Error fetching data for {symbol}: {response.status_code}")
        return None
    

def get_position(symbol, account):

    '''
    gets the current position info, like size etc. 
    '''

    # account = LocalAccount = eth_account.Account.from_key(key)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    user_state = info.user_state(account.address)
    print(f'this is current account value: {user_state["marginSummary"]["accountValue"]}')
    positions = []
    print(f'this is the symbol {symbol}')
    print(user_state["assetPositions"])
    for position in user_state["assetPositions"]:
        if (position["position"]["coin"] == symbol) and float(position["position"]["szi"]) != 0:
            positions.append(position["position"])
            in_pos = True 
            size = float(position["position"]["szi"])
            pos_sym = position["position"]["coin"]
            entry_px = float(position["position"]["entryPx"])
            pnl_perc = float(position["position"]["returnOnEquity"])*100
            print(f'this is the pnl perc {pnl_perc}')
            break 
    else:
        in_pos = False 
        size = 0 
        pos_sym = None 
        entry_px = 0 
        pnl_perc = 0

    if size > 0:
        long = True 
    elif size < 0:
        long = False 
    else:
        long = None 

    return positions, in_pos, size, pos_sym, entry_px, pnl_perc, long


def limit_order(coin, is_buy, sz, limit_px, reduce_only, account):
    exchange = Exchange(account, constants.MAINNET_API_URL)
    
    rounding = get_sz_px_decimals(coin)[0]
    sz = round(sz,rounding)
    print(f"🌙 Moon Dev placing order:")
    print(f"Symbol: {coin}")
    print(f"Side: {'BUY' if is_buy else 'SELL'}")
    print(f"Size: {sz}")
    print(f"Price: ${limit_px}")
    print(f"Reduce Only: {reduce_only}")

    order_result = exchange.order(coin, is_buy, sz, limit_px, {"limit": {"tif": "Gtc"}}, reduce_only=reduce_only)
    print(f"🔍 Raw order result (type {type(order_result)}): {order_result}")

    if isinstance(order_result, dict) and 'response' in order_result:
        print(f"✅ Order placed with status: {order_result['response']['data']['statuses'][0]}")
    else:
        print(f"✅ Order placed (raw response)")

    return order_result


