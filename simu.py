# Design a training evaluation program, using python ccxt gateio to fetch XRP/USDT daily K-line data
# Calculate bollinger bands, rsi13, rsi42 indicators, display daily K-line candlestick chart, volume candlestick chart, rsi chart
# Manually predict the next day's price trend, decide "hold", "buy", "sell" operations, and record log and sell profit/loss percentage
# Display the next actual data after each operation on the daily K-line
# Add a checkbox named "Three Elements of Limit Up", after a limit up, encountering such a pullback, a big yang limit up appears at the low position, the second does not break half of the big yang position in the following three days, the third appears to swallow the yang K and swallow the previous three K lines, then the main force pull-up strategy is established. Implement an automatic reminder function for buying points based on this model content, and mark the number 3 on the buying point.

import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
import matplotlib.dates as mdates
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QLabel, QSizePolicy, QComboBox, QListWidget, QCheckBox
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import random
from matplotlib.animation import FuncAnimation


# Initialize Gate.io exchange
exchange = ccxt.gateio()

def fetch_ohlcv_data(symbol, timeframe='1d', limit=200):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai')
    df.set_index('timestamp', inplace=True)
    return df

def calculate_indicators(df):
    # Calculate Bollinger Bands
    df['middle_band'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper_band'] = df['middle_band'] + (df['std'] * 2)
    df['lower_band'] = df['middle_band'] - (df['std'] * 2)

    # Calculate RSI-13 and RSI-42
    def calculate_rsi(data, periods):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    df['rsi_13'] = calculate_rsi(df['close'], 13)
    df['rsi_42'] = calculate_rsi(df['close'], 42)

    return df

class TradingSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crypto Trading Simulator")  # Update window title
        self.setGeometry(100, 100, 1600, 900)  # Increase window size

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)

        # Left chart area
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)

        # Add timeframe selection dropdown
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(['1d', '4h', '1h'])
        self.timeframe_combo.currentTextChanged.connect(self.change_timeframe)
        chart_layout.addWidget(self.timeframe_combo)

        self.figure, (self.ax1, self.ax2, self.ax3) = plt.subplots(3, 1, figsize=(12, 16), 
                                                                   gridspec_kw={'height_ratios': [2, 1, 1]},
                                                                   sharex=True)
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas)
        
        # Set size policy for the left area
        chart_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(chart_widget, 3)

        # Right information and button area
        info_button_widget = QWidget()
        info_button_layout = QVBoxLayout(info_button_widget)
        
        # Add currency pair list
        self.pair_list = QListWidget()
        self.pair_list.addItems([
            'DOGE/USDT', 'CGPU/USDT', 'BTC/USDT', 'SFT/USDT', 'WLD/USDT', 'ETH/USDT', 'TURBO/USDT', 'MAX/USDT', 'PEPE/USDT', 'BOME/USDT', 'SOL/USDT', 'POPCAT/USDT', 'BABYDOGE/USDT', 'TOMI/USDT', 'ENA/USDT', 'ZETA/USDT', 'SUNDOG/USDT', 'PEOPLE/USDT', 'ZBU/USDT', 'FTN/USDT'
        ])
        self.pair_list.setCurrentRow(0)  # Select the first currency pair by default
        self.pair_list.currentTextChanged.connect(self.change_trading_pair)
        self.pair_list.setMaximumHeight(150)  # Set maximum height to 150 pixels
        info_button_layout.addWidget(self.pair_list)
        
        self.info_label = QLabel()
        info_button_layout.addWidget(self.info_label)
        
        button_layout = QHBoxLayout()
        self.buy_button = QPushButton("Buy")
        self.sell_button = QPushButton("Sell")
        self.hold_button = QPushButton("Hold")
        self.end_button = QPushButton("End")  # Add End button
        button_layout.addWidget(self.buy_button)
        button_layout.addWidget(self.sell_button)
        button_layout.addWidget(self.hold_button)
        button_layout.addWidget(self.end_button)  # Add End button to layout
        info_button_layout.addLayout(button_layout)
        
        # Add a spacer to push buttons to the bottom
        info_button_layout.addStretch()
        
        # Add "Three Elements of Limit Up" checkbox
        self.three_elements_checkbox = QCheckBox("Three Elements of Limit Up")
        self.three_elements_checkbox.stateChanged.connect(self.update_chart)
        info_button_layout.addWidget(self.three_elements_checkbox)
        
        # Set size policy for the right area
        info_button_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        main_layout.addWidget(info_button_widget, 1)

        self.buy_button.clicked.connect(lambda: self.action_clicked('buy'))
        self.sell_button.clicked.connect(lambda: self.action_clicked('sell'))
        self.hold_button.clicked.connect(lambda: self.action_clicked('hold'))
        self.end_button.clicked.connect(self.end_simulation)  # Connect End button to new method

        self.symbol = 'BTC/USDT'  # Default trading pair
        self.timeframe = '1d'
        self.df = fetch_ohlcv_data(self.symbol, self.timeframe)
        self.df = calculate_indicators(self.df)
        
        # Ensure there's enough data to calculate RSI-42
        min_index = 42
        max_index = len(self.df) - 100
        
        if max_index > min_index:
            self.current_index = random.randint(min_index, max_index)
        else:
            self.current_index = min_index
        
        self.balance = 1000
        self.crypto_holdings = 0
        self.trade_log = []
        self.trade_marks = []

        self.update_chart()
        self.update_info()

    def end_simulation(self):
        self.show_final_results()
        self.disable_trading_buttons()

    def show_final_results(self):
        crypto_symbol = self.symbol.split('/')[0]
        current_price = self.df.iloc[self.current_index]['close']
        final_value = self.balance + (self.crypto_holdings * current_price)
        total_return = (final_value - 1000) / 1000 * 100
        result_text = (
            "Simulation ended.\n"
            f"Final portfolio value: {final_value:.2f} USDT\n"
            f"Total return: {total_return:.2f}%\n"
            f"Current {crypto_symbol} price: {current_price:.2f} USDT\n"
            f"Current {crypto_symbol} holdings: {self.crypto_holdings:.4f}\n"
            f"Current USDT balance: {self.balance:.2f}\n\n"
            "Trade Log:\n" + "\n".join(self.trade_log)
        )
        self.info_label.setText(result_text)

    def disable_trading_buttons(self):
        self.buy_button.setEnabled(False)
        self.sell_button.setEnabled(False)
        self.hold_button.setEnabled(False)
        self.end_button.setEnabled(False)

    def change_trading_pair(self, new_pair):
        self.symbol = new_pair
        self.df = fetch_ohlcv_data(self.symbol, self.timeframe)
        self.df = calculate_indicators(self.df)
        
        # Ensure there's enough data to calculate RSI-42
        min_index = 42
        max_index = len(self.df) - 100
        
        if max_index > min_index:
            self.current_index = random.randint(min_index, max_index)
        else:
            self.current_index = min_index
        
        self.balance = 1000
        self.crypto_holdings = 0
        self.trade_log = []
        self.trade_marks = []
        
        # Re-enable buttons
        self.enable_trading_buttons()
        
        self.update_chart()
        self.update_info()

    def enable_trading_buttons(self):
        self.buy_button.setEnabled(True)
        self.sell_button.setEnabled(True)
        self.hold_button.setEnabled(True)
        self.end_button.setEnabled(True)

    def action_clicked(self, action):
        current_data = self.df.iloc[self.current_index]
        crypto_symbol = self.symbol.split('/')[0]

        if action == 'buy' and self.balance > 0:
            crypto_bought = self.balance / current_data['close']
            self.crypto_holdings += crypto_bought
            self.balance = 0
            self.trade_log.append(f"Bought {crypto_bought:.2f} {crypto_symbol} at {current_data['close']}")
            self.trade_marks.append((self.current_index, 'B'))
        elif action == 'sell' and self.crypto_holdings > 0:
            self.balance = self.crypto_holdings * current_data['close']
            profit_loss = (self.balance - 1000) / 1000 * 100
            self.trade_log.append(f"Sold {self.crypto_holdings:.2f} {crypto_symbol} at {current_data['close']}. P/L: {profit_loss:.2f}%")
            self.crypto_holdings = 0
            self.trade_marks.append((self.current_index, 'S'))

        self.current_index += 1
        if self.current_index >= len(self.df) - 1:
            self.end_simulation()
        else:
            self.update_chart()
            self.update_info()

    def change_timeframe(self, timeframe):
        self.timeframe = timeframe
        self.df = fetch_ohlcv_data(self.symbol, self.timeframe)
        self.df = calculate_indicators(self.df)
        self.current_index = len(self.df) - 100
        self.trade_marks = []  # Clear trade marks
        self.update_chart()
        self.update_info()

    def update_chart(self):
        # Clear the current plot
        for ax in (self.ax1, self.ax2, self.ax3):
            ax.clear()

        # Set fixed display count of K lines
        display_count = 100
        start_index = max(0, self.current_index - display_count + 1)
        end_index = self.current_index + 1
        current_df = self.df.iloc[start_index:end_index]
        
        # Candlestick chart
        ohlc = current_df[['open', 'high', 'low', 'close']].reset_index()
        ohlc['timestamp'] = ohlc['timestamp'].map(mdates.date2num)
        
        # Adjust candle width based on time frame
        if self.timeframe == '1d':
            width = 0.6
        elif self.timeframe == '4h':
            width = 0.1
        elif self.timeframe == '1h':
            width = 0.03
        else:
            width = 0.6  # Default width
        
        candlestick_ohlc(self.ax1, ohlc.values, width=width, colorup='g', colordown='r')
        self.ax1.plot(current_df.index, current_df['upper_band'], 'y--', label='Upper BB')
        self.ax1.plot(current_df.index, current_df['middle_band'], 'b-', label='Middle BB')
        self.ax1.plot(current_df.index, current_df['lower_band'], 'b--', label='Lower BB')
        self.ax1.set_title(f'{self.symbol} {self.timeframe} Candlestick Chart with Bollinger Bands')
        self.ax1.legend()

        # Volume chart with color based on price movement and adjusted width
        colors = ['g' if close >= open else 'r' for open, close in zip(current_df['open'], current_df['close'])]
        self.ax2.bar(current_df.index, current_df['volume'], color=colors, width=width, align='center')
        self.ax2.set_title('Volume')

        # RSI chart
        self.ax3.plot(current_df.index, current_df['rsi_13'], label='RSI-13')
        self.ax3.plot(current_df.index, current_df['rsi_42'], label='RSI-42')
        self.ax3.axhline(y=70, color='r', linestyle='--')
        self.ax3.axhline(y=30, color='r', linestyle='--')
        self.ax3.set_title('RSI')
        self.ax3.legend()

        # Draw trade marks
        for index, mark in self.trade_marks:
            if start_index <= index <= end_index:
                x = current_df.index[index - start_index]
                open_price = current_df['open'].iloc[index - start_index]
                close_price = current_df['close'].iloc[index - start_index]
                color = 'g' if mark == 'B' else 'r'
                
                if close_price >= open_price:
                    y = close_price
                    xytext = (0, 5)  # Upward阳线，标记在上方
                    va = 'bottom'
                else:
                    y = close_price
                    xytext = (0, -5)  # Downward阴线，标记在下方
                    va = 'top'
                
                self.ax1.annotate(mark, (x, y), xytext=xytext, 
                                  textcoords='offset points', 
                                  color=color, fontweight='bold', 
                                  ha='center', va=va)

        if self.three_elements_checkbox.isChecked():
            buy_signals = self.find_three_elements_signals(current_df)
            for index, signal in buy_signals:
                self.ax1.annotate('3', (current_df.index[index], current_df['high'].iloc[index]),
                                  xytext=(0, 5), textcoords='offset points',
                                  ha='center', va='bottom', color='g', fontweight='bold')

        # Adjust x-axis date format based on time frame
        if self.timeframe == '1d':
            date_format = '%m-%d'
            locator = mdates.WeekdayLocator(byweekday=mdates.MO)
        elif self.timeframe == '4h':
            date_format = '%m-%d %H:%M'
            locator = mdates.DayLocator()
        elif self.timeframe == '1h':
            date_format = '%m-%d %H:%M'
            locator = mdates.HourLocator(interval=6)
        else:
            date_format = '%m-%d'
            locator = mdates.WeekdayLocator(byweekday=mdates.MO)

        # Set x-axis range, leaving a time unit's worth of space on both sides
        date_range = (current_df.index[-1] - current_df.index[0])
        if self.timeframe == '1d':
            time_unit = pd.Timedelta(days=1)
        elif self.timeframe == '4h':
            time_unit = pd.Timedelta(hours=4)
        elif self.timeframe == '1h':
            time_unit = pd.Timedelta(hours=1)
        else:
            time_unit = pd.Timedelta(days=1)

        x_min = current_df.index[0] - time_unit
        x_max = current_df.index[-1] + time_unit

        for ax in (self.ax1, self.ax2, self.ax3):
            ax.set_xlim(x_min, x_max)

        # Format x-axis date
        self.ax3.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
        self.ax3.xaxis.set_major_locator(locator)
        self.figure.autofmt_xdate()

        self.figure.tight_layout()
        self.canvas.draw()

    def update_info(self):
        current_data = self.df.iloc[self.current_index]
        crypto_symbol = self.symbol.split('/')[0]
        info_text = (
            f"Date: {current_data.name.date()}\n"
            f"Close: {current_data['close']}\n"
            f"RSI-13: {current_data['rsi_13']:.2f}\n"
            f"RSI-42: {current_data['rsi_42']:.2f}\n"
            f"Current balance: {self.balance:.2f} USDT\n"
            f"Current {crypto_symbol} holdings: {self.crypto_holdings}"
        )
        self.info_label.setText(info_text)

    def find_three_elements_signals(self, df):
        signals = []
        for i in range(4, len(df)):
            if self.is_three_elements_pattern(df.iloc[i-4:i+1]):
                signals.append((i, 'buy'))
        return signals

    def is_three_elements_pattern(self, window):
        # Check if the conditions for the Three Elements of Limit Up are met
        # 1. A big yang limit up appears at the low position
        if not (window.iloc[0]['close'] > window.iloc[0]['open'] * 1.09):  # Assume a 9% increase is a limit up
            return False

        # 2. The second does not break half of the big yang position in the following three days
        half_position = (window.iloc[0]['high'] + window.iloc[0]['low']) / 2
        if any(window.iloc[1:4]['low'] < half_position):
            return False

        # 3. The third appears to swallow the yang K and swallow the previous three K lines
        last_candle = window.iloc[-1]
        if not (last_candle['close'] > last_candle['open'] and
                last_candle['high'] > window.iloc[1:4]['high'].max() and
                last_candle['low'] < window.iloc[1:4]['low'].min()):
            return False

        return True

    def start_animation(self):
        # Use FuncAnimation for dynamic updates
        self.ani = FuncAnimation(self.figure, self.update_chart, interval=1000, blit=True)

if __name__ == "__main__":
    app = QApplication([])
    simulator = TradingSimulator()
    simulator.show()
    app.exec_()
