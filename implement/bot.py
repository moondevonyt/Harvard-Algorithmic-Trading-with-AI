'''
🌙 Moon Dev's BB Squeeze ADX Trading Bot 🚀
🎯 Trading strategy: Bollinger Bands squeeze with ADX confirmation
🔍 Detects when volatility contracts (BB squeeze) and then trades breakouts
💥 Uses ADX to confirm strong trend direction after squeeze releases

Built with love by Moon Dev 🌙 ✨
disclaimer: this is not financial advice and there is no guarantee of any kind. use at your own risk.
'''

import sys
import os
import time
import schedule
import json
import requests
import pandas as pd
import numpy as np
import traceback
import talib
from termcolor import colored
import colorama
from colorama import Fore, Back, Style
import nice_funcs as n
from datetime import datetime, timedelta
import pytz
from eth_account.signers.local import LocalAccount
import eth_account
from dotenv import load_dotenv

# Add the parent directory to the Python path so we can import modules from there
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

# Import local modules
import nice_funcs as n

# Initialize colorama for terminal colors
colorama.init(autoreset=True)

# Load environment variables from .env file
load_dotenv()

# Get the Hyperliquid key from environment variables
HYPER_LIQUID_KEY = os.getenv('HYPER_LIQUID_KEY')

# Moon Dev ASCII Art Banner
MOON_DEV_BANNER = f"""{Fore.CYAN}
   __  ___                    ____           
  /  |/  /___  ____  ____    / __ \___  _  __
 / /|_/ / __ \/ __ \/ __ \  / / / / _ \| |/_/
/ /  / / /_/ / /_/ / / / / / /_/ /  __/>  <  
/_/  /_/\____/\____/_/ /_(_)____/\___/_/|_|  
                                             
{Fore.MAGENTA}🚀 BB Squeeze ADX Trading Bot 🌙{Fore.RESET}
"""

# ===== CONFIGURATION =====
# Symbol to trade
SYMBOL = 'BTC'  # Default symbol, can be changed as needed
LEVERAGE = 5     # Leverage to use for trading
POSITION_SIZE_USD = 10  # Position size in USD (small to ensure it performs like backtest)

# Strategy parameters (from backtest optimization)
BB_WINDOW = 20
BB_STD = 2.0
KELTNER_WINDOW = 20
KELTNER_ATR_MULT = 1.5
ADX_PERIOD = 14
ADX_THRESHOLD = 25

# Take profit and stop loss settings
TAKE_PROFIT_PERCENT = 5.0  # 5% - from backtest
STOP_LOSS_PERCENT = -3.0   # 3% - from backtest

# Market order type
USE_MARKET_ORDERS = False  # False for limit orders, True for market orders

# Initialize account
account = LocalAccount = eth_account.Account.from_key(HYPER_LIQUID_KEY)

# Trading state
squeeze_flag = False  # Tracks if we're in a squeeze
squeeze_released = False  # Tracks if a squeeze was just released
last_candle_time = None  # Tracks when we last processed a candle

def print_banner():
    """Print Moon Dev banner with a random quote"""
    print(MOON_DEV_BANNER)
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.YELLOW}🚀 Moon Dev BB Squeeze ADX Bot is starting up! 🎯")
    print(f"{Fore.YELLOW}💰 Trading {SYMBOL} with {LEVERAGE}x leverage")
    print(f"{Fore.YELLOW}💵 Position size: ${POSITION_SIZE_USD} USD")
    print(f"{Fore.CYAN}{'='*80}\n")

def fetch_klines(symbol, interval='4h', limit=100):
    """
    Fetch candlestick data for the given symbol
    """
    print(f"{Fore.YELLOW}🔍 Moon Dev is fetching {interval} candles for {symbol}... 🕯️")
    try:
        # This function would be implemented in nice_funcs
        ohlcv = n.get_ohlcv2(symbol, interval, limit)
        
        if ohlcv is None or len(ohlcv) == 0:
            print(f"{Fore.RED}❌ Failed to fetch candle data!")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        print(f"{Fore.GREEN}✅ Successfully fetched {len(df)} candles for {symbol}")
        return df
        
    except Exception as e:
        print(f"{Fore.RED}❌ Error fetching candles: {str(e)}")
        print(f"{Fore.RED}📋 Stack trace:\n{traceback.format_exc()}")
        return None

def calculate_indicators(df):
    """
    Calculate all strategy indicators:
    - Bollinger Bands
    - Keltner Channels
    - ADX
    """
    try:
        print(f"{Fore.YELLOW}🧮 Moon Dev calculating indicators... 🧠")
        
        # Calculate Bollinger Bands
        df['upper_bb'], df['middle_bb'], df['lower_bb'] = talib.BBANDS(
            df['close'], 
            timeperiod=BB_WINDOW, 
            nbdevup=BB_STD, 
            nbdevdn=BB_STD
        )
        
        # Calculate ATR for Keltner Channels
        df['atr'] = talib.ATR(
            df['high'], 
            df['low'], 
            df['close'], 
            timeperiod=KELTNER_WINDOW
        )
        
        # Calculate Keltner Channels
        df['keltner_middle'] = talib.SMA(df['close'], timeperiod=KELTNER_WINDOW)
        df['upper_kc'] = df['keltner_middle'] + KELTNER_ATR_MULT * df['atr']
        df['lower_kc'] = df['keltner_middle'] - KELTNER_ATR_MULT * df['atr']
        
        # Calculate ADX
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=ADX_PERIOD)
        
        # Detect Bollinger Band Squeeze
        df['squeeze'] = (df['upper_bb'] < df['upper_kc']) & (df['lower_bb'] > df['lower_kc'])
        
        print(f"{Fore.GREEN}✅ Moon Dev finished calculating indicators! 🧙‍♂️")
        
        return df
    
    except Exception as e:
        print(f"{Fore.RED}❌ Error calculating indicators: {str(e)}")
        print(f"{Fore.RED}📋 Stack trace:\n{traceback.format_exc()}")
        return None

def analyze_market():
    """
    Analyze market conditions and detect BB squeeze patterns
    """
    global squeeze_flag, squeeze_released
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}{'='*25} 🔍 MARKET ANALYSIS 🔍 {'='*25}")
    print(f"{Fore.CYAN}{'='*80}")
    
    try:
        # Fetch candle data
        df = fetch_klines(SYMBOL, interval='6h', limit=100)
        if df is None:
            return False
        
        # Calculate indicators
        df = calculate_indicators(df)
        if df is None:
            return False
        
        # Get the most recent data points
        current_candle = df.iloc[-1]
        previous_candle = df.iloc[-2]
        
        # Print current price and indicator values
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}{'='*25} 📊 CURRENT MARKET STATUS 📊 {'='*25}")
        print(f"{Fore.CYAN}{'='*80}")
        print(f"{Fore.GREEN}🕯️ Current Close: ${current_candle['close']:.2f}")
        print(f"{Fore.GREEN}📈 ADX Value: {current_candle['adx']:.2f} (Threshold: {ADX_THRESHOLD})")
        print(f"{Fore.GREEN}📏 Bollinger Bands: Upper ${current_candle['upper_bb']:.2f} | Middle ${current_candle['middle_bb']:.2f} | Lower ${current_candle['lower_bb']:.2f}")
        print(f"{Fore.GREEN}📏 Keltner Channels: Upper ${current_candle['upper_kc']:.2f} | Middle ${current_candle['keltner_middle']:.2f} | Lower ${current_candle['lower_kc']:.2f}")
        
        # Check if we're in a squeeze
        squeeze_now = current_candle['squeeze']
        squeeze_prev = previous_candle['squeeze']
        
        # Check for squeeze ending (was True, now False)
        if squeeze_prev and not squeeze_now:
            print(f"\n{Fore.MAGENTA}🚨 MOON DEV ALERT: BB SQUEEZE JUST RELEASED! 🚨")
            squeeze_released = True
            squeeze_flag = False
        elif squeeze_now:
            print(f"\n{Fore.YELLOW}⚠️ MOON DEV ALERT: Currently in BB Squeeze! Volatility contraction in progress...")
            squeeze_flag = True
            squeeze_released = False
        else:
            print(f"\n{Fore.BLUE}ℹ️ MOON DEV INFO: No squeeze detected. Normal volatility.")
            squeeze_flag = False
        
        # Display ADX trend strength
        if current_candle['adx'] > ADX_THRESHOLD:
            print(f"{Fore.GREEN}💪 ADX: {current_candle['adx']:.2f} - Strong trend detected! (Threshold: {ADX_THRESHOLD})")
        else:
            print(f"{Fore.YELLOW}👀 ADX: {current_candle['adx']:.2f} - Weak/no trend (Threshold: {ADX_THRESHOLD})")
        
        # Check for potential breakout direction
        if squeeze_released:
            if current_candle['close'] > current_candle['upper_bb']:
                print(f"{Fore.GREEN}🚀 POTENTIAL UPWARD BREAKOUT - Close (${current_candle['close']:.2f}) above upper BB (${current_candle['upper_bb']:.2f})")
            elif current_candle['close'] < current_candle['lower_bb']:
                print(f"{Fore.RED}📉 POTENTIAL DOWNWARD BREAKOUT - Close (${current_candle['close']:.2f}) below lower BB (${current_candle['lower_bb']:.2f})")
        
        return True
        
    except Exception as e:
        print(f"{Fore.RED}❌ Error during market analysis: {str(e)}")
        print(f"{Fore.RED}📋 Stack trace:\n{traceback.format_exc()}")
        return False

def check_for_entry_signals(df):
    """
    Check for trade entry signals based on BB squeeze and ADX
    """
    try:
        # Get last two candles
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Initialize signal variables
        long_signal = False
        short_signal = False
        
        # Check if squeeze just ended (was in squeeze and now it's not)
        squeeze_just_released = previous['squeeze'] and not current['squeeze']
        
        # If squeeze just released and ADX confirms trend strength
        if squeeze_just_released and current['adx'] > ADX_THRESHOLD:
            print(f"{Fore.MAGENTA}🔎 MOON DEV SIGNAL ANALYSIS: Squeeze just released with ADX: {current['adx']:.2f} > {ADX_THRESHOLD} 💪")
            
            # Determine breakout direction
            if current['close'] > current['upper_bb']:
                long_signal = True
                print(f"{Fore.GREEN}🚀 LONG SIGNAL TRIGGERED! Price broke above upper BB (${current['upper_bb']:.2f})")
                
            elif current['close'] < current['lower_bb']:
                short_signal = True
                print(f"{Fore.RED}📉 SHORT SIGNAL TRIGGERED! Price broke below lower BB (${current['lower_bb']:.2f})")
        
        return long_signal, short_signal
        
    except Exception as e:
        print(f"{Fore.RED}❌ Error checking entry signals: {str(e)}")
        print(f"{Fore.RED}📋 Stack trace:\n{traceback.format_exc()}")
        return False, False

def bot():
    """
    Main bot function that runs on each cycle
    """
    try:
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.YELLOW}🌙 Moon Dev's BB Squeeze ADX Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 🚀")
        print(f"{Fore.CYAN}{'='*80}")
        
        # First check for existing positions and handle them
        print(f"\n{Fore.CYAN}🔍 Checking for existing positions...")
        positions, im_in_pos, mypos_size, pos_sym, entry_px, pnl_perc, is_long = n.get_position(SYMBOL, account)
        print(f"{Fore.CYAN}📊 Current positions: {positions}")
        
        if im_in_pos:
            print(f"{Fore.GREEN}📈 In position, checking PnL for close conditions...")
            print(f"{Fore.YELLOW}💰 Current PnL: {pnl_perc:.2f}% | Take Profit: {TAKE_PROFIT_PERCENT}% | Stop Loss: {STOP_LOSS_PERCENT}%")
            # Check if we need to close based on profit/loss targets
            n.pnl_close(SYMBOL, TAKE_PROFIT_PERCENT, STOP_LOSS_PERCENT, account)
            
            # After pnl_close may have closed the position, check again if we're still in position
            positions, im_in_pos, mypos_size, pos_sym, entry_px, pnl_perc, is_long = n.get_position(SYMBOL, account)
            
            if im_in_pos:
                print(f"{Fore.GREEN}✅ Current position maintained: {SYMBOL} {'LONG' if is_long else 'SHORT'} {mypos_size} @ ${entry_px} (PnL: {pnl_perc}%)")
                return  # Exit early since we're already in a position
        else:
            print(f"{Fore.YELLOW}📉 Not in position, looking for entry opportunities...")
            # Cancel any pending orders before analyzing for new entries
            n.cancel_all_orders(account)
            print(f"{Fore.YELLOW}🚫 Canceled all existing orders")
        
        # Fetch and analyze market data
        df = fetch_klines(SYMBOL, interval='6h', limit=100)
        if df is None:
            return
            
        # Calculate indicators
        df = calculate_indicators(df)
        if df is None:
            return
        
        # Check for entry signals
        long_signal, short_signal = check_for_entry_signals(df)
        
        # If we have a signal and we're not in a position, enter a trade
        if (long_signal or short_signal) and not im_in_pos:
            # Get orderbook data
            print(f"\n{Fore.CYAN}📚 Fetching orderbook data...")
            ask, bid, l2_data = n.ask_bid(SYMBOL)
            print(f"{Fore.GREEN}💰 Current price - Ask: ${ask:.2f}, Bid: ${bid:.2f}")
            
            # Adjust leverage and position size
            lev, pos_size = n.adjust_leverage_usd_size(SYMBOL, POSITION_SIZE_USD, LEVERAGE, account)
            print(f"{Fore.YELLOW}📊 Leverage: {lev}x | Position size: {pos_size}")
            
            if long_signal:
                n.limit_order(SYMBOL, True, pos_size, bid, False, account)
                print(f"{Fore.GREEN}🎯 Entry reason: BB Squeeze breakout with ADX confirmation")
                
            elif short_signal:
                print(f"{Fore.RED}📉 Placing LIMIT SELL order at ${ask}...")
                n.limit_order(SYMBOL, False, pos_size, ask, False, account)
                print(f"{Fore.RED}🎯 Entry reason: BB Squeeze breakdown with ADX confirmation")
                
            print(f"{Fore.YELLOW}⏳ Order placed, waiting for fill...")
        else:
            if im_in_pos:
                print(f"{Fore.YELLOW}⏳ Already in position, no new orders placed")
            elif long_signal or short_signal:
                print(f"{Fore.YELLOW}⏳ Signal detected but position exists, skipping entry")
            else:
                print(f"{Fore.YELLOW}⏳ No entry signals detected, continuing to monitor...")
        
        # Easter egg
        print(f"\n{Fore.MAGENTA}🌕 Moon Dev says: Patience is key with squeeze strategies! 🤖")
        
    except Exception as e:
        print(f"{Fore.RED}❌ Error in bot execution: {str(e)}")
        print(f"{Fore.RED}📋 Stack trace:\n{traceback.format_exc()}")

def main():
    """Main entry point for the bot"""
    # Display banner
    print_banner()
    
    # Initial market analysis
    print(f"{Fore.YELLOW}🔍 Moon Dev performing initial market analysis...")
    analyze_market()
    
    # Initial bot run
    print(f"{Fore.YELLOW}🚀 Starting first Moon Dev bot cycle...")
    bot()
    
    # Schedule the bot to run every minute
    schedule.every(1).minutes.do(bot)
    
    # Schedule market analysis to run hourly
    schedule.every(1).hours.do(analyze_market)
    
    print(f"{Fore.GREEN}✅ Bot scheduled to run every minute")
    print(f"{Fore.GREEN}✅ Market analysis scheduled to run every hour")
    
    while True:
        try:
            # Run pending scheduled tasks
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print(f"{Fore.YELLOW}⚠️ Bot stopped by user")
            break
        except Exception as e:
            print(f"{Fore.RED}❌ Encountered an error: {e}")
            print(f"{Fore.RED}📋 Stack trace:\n{traceback.format_exc()}")
            # Wait before retrying to avoid rapid error logging
            time.sleep(10)

if __name__ == "__main__":
    main()
