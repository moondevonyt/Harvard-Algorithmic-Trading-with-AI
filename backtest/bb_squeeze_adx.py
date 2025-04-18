import pandas as pd
import numpy as np
import talib
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

# Load the filtered data
data_path = '/Users/md/Dropbox/dev/github/Harvard-Algorithmic-Trading-with-AI-/backtest/data/BTC-6h-1000wks-data.csv'
data = pd.read_csv(data_path, parse_dates=['datetime'], index_col='datetime')

# Bollinger Band Squeeze with ADX Strategy
class BBSqueezeADX(Strategy):
    # Parameters
    bb_window = 20
    bb_std = 2.0 
    keltner_window = 20
    keltner_atr_mult = 1.5
    adx_period = 14
    adx_threshold = 25
    take_profit = 0.05  # 5%
    stop_loss = 0.03    # 3%
    
    def init(self):
        # Calculate Bollinger Bands
        self.upper_bb, self.middle_bb, self.lower_bb = self.I(talib.BBANDS, 
                                                            self.data.Close, 
                                                            self.bb_window, 
                                                            self.bb_std, 
                                                            self.bb_std)
        
        # Calculate ATR for Keltner Channels
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, 
                          self.data.Close, self.keltner_window)
        
        # Calculate Keltner Channels
        self.keltner_middle = self.I(talib.SMA, self.data.Close, self.keltner_window)
        self.upper_kc = self.I(lambda: self.keltner_middle + self.keltner_atr_mult * self.atr)
        self.lower_kc = self.I(lambda: self.keltner_middle - self.keltner_atr_mult * self.atr)
        
        # Detect Bollinger Band Squeeze
        self.squeeze = self.I(lambda: (self.upper_bb < self.upper_kc) & 
                                     (self.lower_bb > self.lower_kc))
        
        # Calculate ADX
        self.adx = self.I(talib.ADX, self.data.High, self.data.Low, 
                          self.data.Close, self.adx_period)
        
        # For tracking squeeze releases
        self.squeeze_released = False
        
    def next(self):
        # Wait for enough data
        if len(self.data) < max(self.bb_window, self.keltner_window, self.adx_period):
            return
        
        # Check if we were in a squeeze condition and now it's released
        squeeze_now = self.squeeze[-1]
        squeeze_prev = self.squeeze[-2] if len(self.data) > (max(self.bb_window, self.keltner_window) + 1) else True
        
        # Squeeze is ending (was True, now False)
        if squeeze_prev and not squeeze_now:
            self.squeeze_released = True
        
        # Trading logic - if we had a squeeze release and ADX confirms trend strength
        if self.squeeze_released and self.adx[-1] > self.adx_threshold:
            # Determine breakout direction
            if self.data.Close[-1] > self.upper_bb[-1] and not self.position:
                # Long position for upward breakout
                self.buy(sl=self.data.Close[-1] * (1 - self.stop_loss),
                        tp=self.data.Close[-1] * (1 + self.take_profit))
                self.squeeze_released = False  # Reset flag
                
            elif self.data.Close[-1] < self.lower_bb[-1] and not self.position:
                # Short position for downward breakout
                self.sell(sl=self.data.Close[-1] * (1 + self.stop_loss),
                         tp=self.data.Close[-1] * (1 - self.take_profit))
                self.squeeze_released = False  # Reset flag

# Rename columns to match the backtesting library's expected format
# Based on the CSV headers: datetime,open,high,low,close,volume
data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

# Create and configure the backtest
bt = Backtest(data, BBSqueezeADX, cash=100000, commission=0.002) # .001 

# Run the backtest with default parameters and print the results
print("🌟 MOON DEV BACKTEST STARTING - Default Parameters 🌟")
stats_default = bt.run()
print("\n📊 MOON DEV DEFAULT PARAMETERS RESULTS:")
print(stats_default)

# Now perform the optimization
print("\n🔍 MOON DEV OPTIMIZATION STARTING - This may take a while... 🔍")
optimization_results = bt.optimize(
    bb_window=range(10, 15, 5),
    bb_std=[round(i, 1) for i in np.arange(1.5, 2.1, 0.5)],
    keltner_window=range(10, 20, 5),
    keltner_atr_mult=[round(i, 1) for i in np.arange(1.0, 2, 0.5)],
    adx_period=range(10, 20, 2),
    adx_threshold=range(20, 30, 5),
    take_profit=[i / 100 for i in range(3, 4, 2)],
    stop_loss=[i / 100 for i in range(2, 4, 1)],
    maximize='Equity Final [$]',
    constraint=lambda param: param.bb_window > 0 and param.bb_std > 0 and param.keltner_window > 0  # Ensure valid parameters
)

# Print the optimization results
print("\n🏆 MOON DEV OPTIMIZATION COMPLETE - Results:")
print(optimization_results)

# Print the best optimized values
print("\n✨ MOON DEV BEST PARAMETERS:")
print(f"BB Window: {optimization_results._strategy.bb_window}")
print(f"BB Standard Deviations: {optimization_results._strategy.bb_std}")
print(f"Keltner Window: {optimization_results._strategy.keltner_window}")
print(f"Keltner ATR Multiplier: {optimization_results._strategy.keltner_atr_mult}")
print(f"ADX Period: {optimization_results._strategy.adx_period}")
print(f"ADX Threshold: {optimization_results._strategy.adx_threshold}")
print(f"Take Profit: {optimization_results._strategy.take_profit * 100:.1f}%")
print(f"Stop Loss: {optimization_results._strategy.stop_loss * 100:.1f}%")
