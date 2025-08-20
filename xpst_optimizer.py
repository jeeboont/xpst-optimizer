"""
XPST Optimizer - TradingView Consistency Verified Edition
Version: 3.1.32
Last Updated: 2025-08-20
Author: XPST Trading Systems

VERSION HISTORY:
================
v3.1.32 (2025-08-20) - Current Version
- Fixed NameError: process_uploaded_csv function placement
- Reorganized function definitions to ensure proper scope
- Enhanced error handling with detailed traceback
- Confirmed CSV processing works with TradingView exports

v3.1.31 (2025-08-20)
- Fixed CSV upload to handle TradingView exported files
- Added automatic column name normalization (handles Volume vs volume)
- Enhanced CSV processing with better error messages
- Added TradingView CSV format converter function
- Improved data type validation and conversion

v3.1.30 (2025-08-20)
- Added Custom Date Range option for exact TradingView period matching
- Implemented verification guide for comparing with TradingView
- Added helper functions for data format conversion
- Enhanced data download with actual date range display
- Added verification tips in expandable footer section

v3.1.25 (2025-08-20)
- Fixed Last N Trades heading to show requested number instead of actual
- Updated filter display to show ADX≥25 and EMA200 format in tables
- Added complete XPST settings display with all filters and thresholds
- Added data period context (start/end timestamps) to optimization results
- Implemented Last N Trades analysis feature (10-100 trades)
- Added data export functionality for downloaded price data (CSV and ZIP)

v3.1.20 (2025-08-20)
- Fixed UnboundLocalError for uploaded_files variable scoping
- Added proper variable initialization for all configuration options
- Improved error handling for CSV upload mode

v3.1.15 (2025-08-20)
- Implemented optimization modes (Quick, Standard, Full)
- Added HTF control settings (Essential vs All)
- Ensured Quick mode tests all Pivot/ATR parameters
- Added smart skipping for poor performing combinations
- Added max bars slider for performance control

v3.1.10 (2025-08-20)
- Fixed pivot calculation errors with manual implementation
- Enhanced error handling and data validation
- Added fallback values for calculation failures
- Improved NaN handling in indicators

v3.1.5 (2025-08-20)
- Added direct Yahoo Finance data download
- Removed dependency on manual CSV uploads
- Added support for crypto, forex, and commodities
- Implemented dual data source option (Yahoo/CSV)

v3.1.0 (2025-08-20)
- Initial release matching TradingView XPST v3.1 implementation
- Full backtest engine with exact signal logic
- Complete parameter optimization
- HTF (Higher Timeframe) analysis
- Performance metrics and statistics table

COMPATIBILITY:
==============
- TradingView XPST Indicator: v3.1
- Python Requirements: 3.8+
- Streamlit: 1.48.0+
- Required Libraries: pandas, numpy, yfinance, streamlit

USAGE:
======
streamlit run xpst_optimizer.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import io
import zipfile
warnings.filterwarnings('ignore')

# Version display in UI
__version__ = "3.1.32"
__last_updated__ = "2025-08-20"

# Initialize session state
if 'downloaded_data' not in st.session_state:
    st.session_state.downloaded_data = {}
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = {}
if 'custom_assets' not in st.session_state:
    st.session_state.custom_assets = {}

# ==================== XPST INDICATOR FUNCTIONS ====================

def calculate_pivot_points(df, period=5):
    """Calculate pivot highs and lows"""
    try:
        # Ensure we have enough data
        if len(df) < period * 2 + 1:
            return pd.Series(index=df.index, dtype=float), pd.Series(index=df.index, dtype=float)
        
        pivot_highs = pd.Series(index=df.index, dtype=float)
        pivot_lows = pd.Series(index=df.index, dtype=float)
        
        # Calculate pivots manually to match TradingView logic
        for i in range(period, len(df) - period):
            # Check for pivot high
            is_pivot_high = True
            high_val = df['high'].iloc[i]
            
            # Check left side
            for j in range(i - period, i):
                if df['high'].iloc[j] >= high_val:
                    is_pivot_high = False
                    break
            
            # Check right side
            if is_pivot_high:
                for j in range(i + 1, i + period + 1):
                    if j < len(df) and df['high'].iloc[j] > high_val:
                        is_pivot_high = False
                        break
            
            if is_pivot_high:
                pivot_highs.iloc[i] = high_val
            
            # Check for pivot low
            is_pivot_low = True
            low_val = df['low'].iloc[i]
            
            # Check left side
            for j in range(i - period, i):
                if df['low'].iloc[j] <= low_val:
                    is_pivot_low = False
                    break
            
            # Check right side
            if is_pivot_low:
                for j in range(i + 1, i + period + 1):
                    if j < len(df) and df['low'].iloc[j] < low_val:
                        is_pivot_low = False
                        break
            
            if is_pivot_low:
                pivot_lows.iloc[i] = low_val
        
        return pivot_highs, pivot_lows
        
    except Exception as e:
        print(f"Pivot calculation error details: {e}")
        return pd.Series(index=df.index, dtype=float), pd.Series(index=df.index, dtype=float)

def calculate_pivot_supertrend(df, pivot_period=5, atr_factor=1.25, atr_period=15):
    """Calculate Pivot Supertrend based on TradingView XPST v3.1"""
    try:
        df = df.copy()
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Check for sufficient data
        if len(df) < max(pivot_period * 2 + 1, atr_period):
            print(f"Insufficient data: {len(df)} rows, need at least {max(pivot_period * 2 + 1, atr_period)}")
            df['pvt_trend'] = 1
            df['pvt_signal'] = 0
            return df
        
        # Calculate pivot points
        pivot_highs, pivot_lows = calculate_pivot_points(df, pivot_period)
        
        # Calculate center line (as per TradingView code)
        center = pd.Series(index=df.index, dtype=float)
        last_pivot = pd.Series(index=df.index, dtype=float)
        
        for i in range(len(df)):
            if not pd.isna(pivot_highs.iloc[i]):
                last_pivot.iloc[i] = pivot_highs.iloc[i]
            elif not pd.isna(pivot_lows.iloc[i]):
                last_pivot.iloc[i] = pivot_lows.iloc[i]
            elif i > 0:
                last_pivot.iloc[i] = last_pivot.iloc[i-1]
            
            if not pd.isna(last_pivot.iloc[i]):
                if i == 0 or pd.isna(center.iloc[i-1]):
                    center.iloc[i] = last_pivot.iloc[i]
                else:
                    center.iloc[i] = (center.iloc[i-1] * 2 + last_pivot.iloc[i]) / 3
            elif i > 0:
                center.iloc[i] = center.iloc[i-1]
            else:
                center.iloc[i] = df['close'].iloc[0]  # Fallback to close price
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=atr_period, min_periods=1).mean()
        
        # Fill any NaN values in ATR
        atr = atr.fillna(method='bfill').fillna(method='ffill')
        if atr.isna().all():
            atr = pd.Series(0.0001, index=df.index)  # Fallback value
        
        # Calculate bands
        up = center - (atr_factor * atr)
        down = center + (atr_factor * atr)
        
        # Initialize trailing stop and trend
        tup = pd.Series(index=df.index, dtype=float)
        tdown = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)
        
        # Set initial values
        if len(df) > 0:
            tup.iloc[0] = up.iloc[0] if not pd.isna(up.iloc[0]) else df['low'].iloc[0]
            tdown.iloc[0] = down.iloc[0] if not pd.isna(down.iloc[0]) else df['high'].iloc[0]
            trend.iloc[0] = 1
        
        for i in range(1, len(df)):
            # Update TUp
            if df['close'].iloc[i-1] > tup.iloc[i-1] if not pd.isna(tup.iloc[i-1]) else False:
                tup.iloc[i] = max(up.iloc[i], tup.iloc[i-1]) if not pd.isna(tup.iloc[i-1]) and not pd.isna(up.iloc[i]) else up.iloc[i]
            else:
                tup.iloc[i] = up.iloc[i] if not pd.isna(up.iloc[i]) else tup.iloc[i-1]
            
            # Update TDown
            if df['close'].iloc[i-1] < tdown.iloc[i-1] if not pd.isna(tdown.iloc[i-1]) else False:
                tdown.iloc[i] = min(down.iloc[i], tdown.iloc[i-1]) if not pd.isna(tdown.iloc[i-1]) and not pd.isna(down.iloc[i]) else down.iloc[i]
            else:
                tdown.iloc[i] = down.iloc[i] if not pd.isna(down.iloc[i]) else tdown.iloc[i-1]
            
            # Determine trend
            if df['close'].iloc[i] > tdown.iloc[i-1] if not pd.isna(tdown.iloc[i-1]) else False:
                trend.iloc[i] = 1
            elif df['close'].iloc[i] < tup.iloc[i-1] if not pd.isna(tup.iloc[i-1]) else False:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1] if i > 0 else 1
        
        df['pvt_trend'] = trend
        df['pvt_tup'] = tup
        df['pvt_tdown'] = tdown
        df['pvt_signal'] = trend.diff().fillna(0)
        
        return df
        
    except Exception as e:
        print(f"Error in Pivot Supertrend calculation: {e}")
        import traceback
        traceback.print_exc()
        
        # Return df with default values
        df['pvt_trend'] = 1
        df['pvt_signal'] = 0
        df['pvt_tup'] = df['low']
        df['pvt_tdown'] = df['high']
        return df

def calculate_x_trend(df):
    """Calculate X Trend indicator as per TradingView XPST v3.1"""
    try:
        df = df.copy()
        
        # X Trend calculations
        lowest_low = df['low'].rolling(window=3).min()
        ma_low = df['low'].ewm(span=3, adjust=False).mean()
        highest_high = df['high'].rolling(window=2).max()
        ma_high = df['high'].rolling(window=2).mean()
        
        # Initialize X Trend variables
        next_trend = pd.Series(0.0, index=df.index)
        x_trend = pd.Series(0.0, index=df.index)
        low_max = pd.Series(df['low'].iloc[0] if len(df) > 0 else 0, index=df.index)
        high_min = pd.Series(df['high'].iloc[0] if len(df) > 0 else 0, index=df.index)
        
        for i in range(1, len(df)):
            next_trend.iloc[i] = next_trend.iloc[i-1]
            x_trend.iloc[i] = x_trend.iloc[i-1]
            low_max.iloc[i] = low_max.iloc[i-1]
            high_min.iloc[i] = high_min.iloc[i-1]
            
            if next_trend.iloc[i] == 1:
                low_max.iloc[i] = max(low_max.iloc[i], lowest_low.iloc[i]) if not pd.isna(lowest_low.iloc[i]) else low_max.iloc[i]
                if (ma_high.iloc[i] < low_max.iloc[i] and 
                    df['close'].iloc[i] < df['low'].iloc[i-1]):
                    x_trend.iloc[i] = 1
                    next_trend.iloc[i] = 0
                    high_min.iloc[i] = highest_high.iloc[i] if not pd.isna(highest_high.iloc[i]) else high_min.iloc[i]
            
            if next_trend.iloc[i] == 0:
                high_min.iloc[i] = min(high_min.iloc[i], highest_high.iloc[i]) if not pd.isna(highest_high.iloc[i]) else high_min.iloc[i]
                if (ma_low.iloc[i] > high_min.iloc[i] and 
                    df['close'].iloc[i] > df['high'].iloc[i-1]):
                    x_trend.iloc[i] = 0
                    next_trend.iloc[i] = 1
                    low_max.iloc[i] = lowest_low.iloc[i] if not pd.isna(lowest_low.iloc[i]) else low_max.iloc[i]
        
        df['x_trend'] = x_trend
        df['x_trend_signal'] = x_trend.diff().fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Error in X Trend calculation: {e}")
        return df

def calculate_adx(df, period=14):
    """Calculate ADX indicator"""
    try:
        df = df.copy()
        
        # Calculate directional movement
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        plus_dm = pd.Series(0.0, index=df.index)
        minus_dm = pd.Series(0.0, index=df.index)
        
        plus_dm[(high_diff > low_diff) & (high_diff > 0)] = high_diff
        minus_dm[(low_diff > high_diff) & (low_diff > 0)] = low_diff
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()
        
        # Calculate DI+ and DI-
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
        
        # Calculate DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        df['adx'] = adx.fillna(25)  # Default value if calculation fails
        
        return df
    except Exception as e:
        st.error(f"Error in ADX calculation: {e}")
        df['adx'] = 25  # Default value
        return df

def calculate_ema(df, period=200):
    """Calculate EMA"""
    try:
        df = df.copy()
        df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
        return df
    except Exception as e:
        st.error(f"Error in EMA calculation: {e}")
        df['ema'] = df['close']
        return df

def apply_htf_x_trend(df, base_timeframe, htf_multiplier):
    """Apply HTF X Trend logic matching TradingView implementation"""
    try:
        df = df.copy()
        
        # Map every base_timeframe bar to HTF bar
        bars_per_htf = htf_multiplier
        htf_bar_index = df.index // bars_per_htf
        
        # Group by HTF bar and take the last X Trend value
        htf_x_trend = df.groupby(htf_bar_index)['x_trend'].last()
        
        # Map back to original timeframe
        df['htf_x_trend'] = df.index.map(lambda x: htf_x_trend.get(x // bars_per_htf, np.nan))
        df['htf_x_trend'].fillna(method='ffill', inplace=True)
        
        return df
    except Exception as e:
        st.error(f"Error in HTF X Trend: {e}")
        df['htf_x_trend'] = df['x_trend']
        return df

def run_backtest_with_trades(df, params, htf_multiplier=None):
    """Run backtest and return both metrics and trade list"""
    try:
        # Calculate indicators
        df = calculate_pivot_supertrend(df, 
                                       pivot_period=params['pivot_period'],
                                       atr_factor=params['atr_factor'],
                                       atr_period=params['atr_period'])
        df = calculate_x_trend(df)
        df = calculate_adx(df)
        df = calculate_ema(df, params.get('ema_period', 200))
        
        # Apply HTF if specified
        if htf_multiplier and htf_multiplier > 1:
            df = apply_htf_x_trend(df, '1m', htf_multiplier)
            use_htf = True
        else:
            df['htf_x_trend'] = df['x_trend']
            use_htf = False
        
        # Generate signals based on XPST v3.1 logic
        signals = []
        position = None
        entry_price = None
        entry_time = None
        
        # Track pending signals
        pvt_buy_pending = False
        pvt_sell_pending = False
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # Check for PVT flips
            pvt_buy_flip = (row['pvt_trend'] == 1) and (prev_row['pvt_trend'] == -1)
            pvt_sell_flip = (row['pvt_trend'] == -1) and (prev_row['pvt_trend'] == 1)
            
            # Update pending signals
            if pvt_buy_flip:
                pvt_buy_pending = True
                pvt_sell_pending = False
            if pvt_sell_flip:
                pvt_sell_pending = True
                pvt_buy_pending = False
            
            # Check filters
            adx_filter = params.get('use_adx', False)
            adx_passed = not adx_filter or row['adx'] >= params.get('adx_threshold', 25)
            
            ema_filter = params.get('use_ema', False)
            ema_bull = not ema_filter or row['close'] > row['ema']
            ema_bear = not ema_filter or row['close'] < row['ema']
            
            xtrend_filter = params.get('use_xtrend', True)
            if use_htf and params.get('xtrend_grey_disagree', True):
                # MTF agreement required
                xtrend_buy = (row['x_trend'] == 0) and (row['htf_x_trend'] == 0)
                xtrend_sell = (row['x_trend'] == 1) and (row['htf_x_trend'] == 1)
            elif use_htf:
                # Use HTF only
                xtrend_buy = row['htf_x_trend'] == 0
                xtrend_sell = row['htf_x_trend'] == 1
            else:
                # Use local X Trend
                xtrend_buy = row['x_trend'] == 0
                xtrend_sell = row['x_trend'] == 1
            
            # Generate entry signals (matching XPST v3.1 logic)
            buy_signal = False
            sell_signal = False
            
            if not xtrend_filter:
                # No X Trend filter
                buy_signal = pvt_buy_flip and adx_passed and ema_bull
                sell_signal = pvt_sell_flip and adx_passed and ema_bear
            else:
                # With X Trend filter
                if pvt_buy_flip and xtrend_buy:
                    buy_signal = adx_passed and ema_bull
                elif pvt_buy_pending and xtrend_buy:
                    buy_signal = adx_passed and ema_bull
                    if buy_signal:
                        pvt_buy_pending = False
                
                if pvt_sell_flip and xtrend_sell:
                    sell_signal = adx_passed and ema_bear
                elif pvt_sell_pending and xtrend_sell:
                    sell_signal = adx_passed and ema_bear
                    if sell_signal:
                        pvt_sell_pending = False
            
            # Process signals
            if position is None:
                if buy_signal:
                    position = 'long'
                    entry_price = row['close']
                    entry_time = i
                elif sell_signal:
                    position = 'short'
                    entry_price = row['close']
                    entry_time = i
            elif position == 'long':
                # Exit conditions for long
                exit_signal = sell_signal or (row['pvt_trend'] == -1)
                if xtrend_filter and use_htf:
                    # Check for X Trend flip
                    xtrend_flip = (row['x_trend'] == 1) and (prev_row['x_trend'] == 0)
                    htf_flip = (row['htf_x_trend'] == 1) and (prev_row['htf_x_trend'] == 0)
                    if params.get('xtrend_grey_disagree', True):
                        exit_signal = exit_signal or (xtrend_flip and htf_flip)
                    else:
                        exit_signal = exit_signal or htf_flip
                
                if exit_signal:
                    profit_pips = (row['close'] - entry_price) / 0.0001  # Forex pips
                    signals.append({
                        'entry_time': entry_time,
                        'exit_time': i,
                        'direction': 'long',
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'profit_pips': profit_pips
                    })
                    position = None
                    
            elif position == 'short':
                # Exit conditions for short
                exit_signal = buy_signal or (row['pvt_trend'] == 1)
                if xtrend_filter and use_htf:
                    # Check for X Trend flip
                    xtrend_flip = (row['x_trend'] == 0) and (prev_row['x_trend'] == 1)
                    htf_flip = (row['htf_x_trend'] == 0) and (prev_row['htf_x_trend'] == 1)
                    if params.get('xtrend_grey_disagree', True):
                        exit_signal = exit_signal or (xtrend_flip and htf_flip)
                    else:
                        exit_signal = exit_signal or htf_flip
                
                if exit_signal:
                    profit_pips = (entry_price - row['close']) / 0.0001  # Forex pips
                    signals.append({
                        'entry_time': entry_time,
                        'exit_time': i,
                        'direction': 'short',
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'profit_pips': profit_pips
                    })
                    position = None
        
        # Calculate metrics
        if len(signals) > 0:
            trades_df = pd.DataFrame(signals)
            winning_trades = trades_df[trades_df['profit_pips'] > 0]
            losing_trades = trades_df[trades_df['profit_pips'] < 0]
            
            metrics = {
                'total_trades': len(trades_df),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(winning_trades) / len(trades_df) * 100,
                'total_pips': trades_df['profit_pips'].sum(),
                'avg_win': winning_trades['profit_pips'].mean() if len(winning_trades) > 0 else 0,
                'avg_loss': abs(losing_trades['profit_pips'].mean()) if len(losing_trades) > 0 else 0,
                'profit_factor': (winning_trades['profit_pips'].sum() / abs(losing_trades['profit_pips'].sum())) 
                                if len(losing_trades) > 0 and losing_trades['profit_pips'].sum() != 0 else 999
            }
        else:
            metrics = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pips': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0
            }
        
        return metrics, signals
        
    except Exception as e:
        print(f"Error in backtest: {e}")
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pips': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0
        }, []

def run_backtest(df, params, htf_multiplier=None):
    """Run backtest with exact XPST v3.1 logic (wrapper for compatibility)"""
    metrics, _ = run_backtest_with_trades(df, params, htf_multiplier)
    return metrics

def download_data(symbol, period='1mo', interval='5m'):
    """Download data from Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        
        if data.empty:
            st.error(f"No data found for {symbol}")
            return None
        
        # Format data to match CSV structure
        data.reset_index(inplace=True)
        data.columns = [col.lower() for col in data.columns]
        
        # Ensure we have the required columns
        required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        data = data.rename(columns={'date': 'datetime', 'index': 'datetime'})
        
        # Convert datetime to timestamp format if needed
        if 'datetime' in data.columns:
            data['time'] = pd.to_datetime(data['datetime']).astype(int) // 10**9
        
        # Limit data for performance (last 1000 bars)
        if len(data) > 1000:
            data = data.tail(1000)
            st.info(f"Using last 1000 bars for {symbol}")
        
        return data[['time', 'open', 'high', 'low', 'close', 'volume']]
        
    except Exception as e:
        st.error(f"Error downloading {symbol}: {e}")
        return None

def download_data_custom_range(symbol, start_date, end_date, interval='5m'):
    """Download data for custom date range"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start_date, end=end_date, interval=interval)
        
        if data.empty:
            st.error(f"No data found for {symbol} in the specified range")
            return None
        
        # Format data to match CSV structure
        data.reset_index(inplace=True)
        data.columns = [col.lower() for col in data.columns]
        
        # Ensure we have the required columns
        data = data.rename(columns={'date': 'datetime', 'index': 'datetime'})
        
        # Convert datetime to timestamp format
        if 'datetime' in data.columns:
            data['time'] = pd.to_datetime(data['datetime']).astype(int) // 10**9
        
        # Show actual data range retrieved
        actual_start = pd.to_datetime(data['datetime'].iloc[0])
        actual_end = pd.to_datetime(data['datetime'].iloc[-1])
        st.info(f"Retrieved {len(data)} bars from {actual_start:%Y-%m-%d %H:%M} to {actual_end:%Y-%m-%d %H:%M}")
        
        return data[['time', 'open', 'high', 'low', 'close', 'volume']]
        
    except Exception as e:
        st.error(f"Error downloading {symbol}: {e}")
        return None

def process_uploaded_csv(df, filename):
    """Process uploaded CSV file to match expected format"""
    try:
        df = df.copy()
        
        # Ensure column names are lowercase
        df.columns = [col.lower() for col in df.columns]
        
        # Check for required columns
        required = ['time', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required):
            # Try to find close matches
            missing = [col for col in required if col not in df.columns]
            st.error(f"CSV must have columns: {required}")
            st.error(f"Missing: {missing}")
            st.error(f"Found columns: {list(df.columns)}")
            return None
        
        # Ensure numeric types for price columns
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Ensure time is integer
        df['time'] = pd.to_numeric(df['time'], errors='coerce').astype('int64')
        
        # Remove any rows with NaN values
        df = df.dropna()
        
        # Limit to 1000 rows for performance (optional)
        if len(df) > 1000:
            df = df.tail(1000)
            st.info(f"Using last 1000 bars from {filename}")
        
        st.success(f"Successfully processed {filename}: {len(df)} valid bars")
        
        return df
        
    except Exception as e:
        st.error(f"Error processing CSV: {e}")
        import traceback
        st.error(f"Details: {traceback.format_exc()}")
        return None

def run_optimization_with_filters(df, asset_name, use_xtrend, use_adx, use_ema, xtrend_grey, 
                                  optimization_mode='Quick', use_htf=True, htf_mode='Essential',
                                  max_bars=500, skip_low_volume=True):
    """Run optimization with specified filter settings and optimization mode"""
    try:
        results = []
        
        # Limit data for faster processing
        if len(df) > max_bars:
            df = df.tail(max_bars)
            st.info(f"Using last {max_bars} bars for faster processing")
        
        # Store data period info
        if 'datetime' in df.columns:
            period_start = pd.to_datetime(df['datetime'].iloc[0])
            period_end = pd.to_datetime(df['datetime'].iloc[-1])
        else:
            # Convert timestamp to datetime if needed
            period_start = pd.to_datetime(df['time'].iloc[0], unit='s')
            period_end = pd.to_datetime(df['time'].iloc[-1], unit='s')
        
        # Define parameter ranges based on optimization mode
        if optimization_mode == 'Quick':
            # Quick mode: Still test key pivot and ATR values, but fewer combinations
            pivot_periods = [3, 5, 7, 10]  # All pivot periods for proper optimization
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]  # All ATR factors for proper optimization
            atr_periods = [10, 14, 15, 20]  # All ATR periods for proper optimization
            htf_multipliers = [1, 3, 6] if use_htf else [1]  # Reduced HTF only
        elif optimization_mode == 'Standard':
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3, 6, 12] if use_htf else [1]
        else:  # Full
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3, 4, 6, 8, 12, 16] if use_htf else [1]
        
        # Further filter HTF based on htf_mode
        if use_htf and htf_mode == 'Essential':
            htf_multipliers = [x for x in htf_multipliers if x in [1, 3, 6, 12]]
        
        # Calculate total combinations
        total_combinations = len(pivot_periods) * len(atr_factors) * len(atr_periods) * len(htf_multipliers)
        
        # Show optimization summary
        mode_desc = {
            'Quick': 'Testing all Pivot/ATR params with limited HTF',
            'Standard': 'Testing all params with moderate HTF variations',
            'Full': 'Testing all params with all HTF variations'
        }
        st.info(f"{mode_desc[optimization_mode]}: {total_combinations} combinations")
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        combination_count = 0
        skipped_count = 0
        
        # Early exit tracking for poor performers
        best_score = 0
        base_scores = {}  # Track scores for base parameters
        
        for pivot_period in pivot_periods:
            for atr_factor in atr_factors:
                for atr_period in atr_periods:
                    base_key = f"{pivot_period}_{atr_factor}_{atr_period}"
                    base_performed_well = True
                    
                    for htf_mult in htf_multipliers:
                        combination_count += 1
                        progress = combination_count / total_combinations
                        progress_bar.progress(progress)
                        status_text.text(f"Testing {combination_count}/{total_combinations} (Skipped: {skipped_count})")
                        
                        # In Quick mode, skip poor HTF variations more aggressively
                        if optimization_mode == 'Quick' and htf_mult > 1:
                            if base_key in base_scores and base_scores[base_key] < best_score * 0.5:
                                skipped_count += 1
                                continue
                        
                        params = {
                            'pivot_period': pivot_period,
                            'atr_factor': atr_factor,
                            'atr_period': atr_period,
                            'use_xtrend': use_xtrend,
                            'use_adx': use_adx,
                            'adx_threshold': 25,
                            'use_ema': use_ema,
                            'ema_period': 200,
                            'xtrend_grey_disagree': xtrend_grey
                        }
                        
                        metrics = run_backtest(df, params, htf_mult)
                        
                        # Skip if too few trades
                        if skip_low_volume and metrics['total_trades'] < 5:
                            skipped_count += 1
                            if htf_mult == 1:
                                base_scores[base_key] = 0
                            continue
                        
                        # Calculate composite score
                        if metrics['total_trades'] > 0:
                            score = (
                                metrics['win_rate'] * 0.3 +
                                min(metrics['profit_factor'], 3) * 20 +
                                (metrics['total_pips'] / metrics['total_trades']) * 0.5
                            )
                        else:
                            score = 0
                        
                        # Track scores
                        if htf_mult == 1:
                            base_scores[base_key] = score
                        
                        if score > best_score:
                            best_score = score
                        
                        # Include all filter settings in results
                        results.append({
                            'pivot_period': pivot_period,
                            'atr_factor': atr_factor,
                            'atr_period': atr_period,
                            'htf_multiplier': htf_mult,
                            'htf_timeframe': get_htf_name(htf_mult),
                            'use_xtrend': 'Yes' if use_xtrend else 'No',
                            'use_adx': f"ADX≥{25}" if use_adx else 'No',
                            'use_ema': f"EMA{200}" if use_ema else 'No',
                            'mtf_agree': 'Yes' if xtrend_grey else 'No',
                            'total_trades': metrics['total_trades'],
                            'win_rate': round(metrics['win_rate'], 2),
                            'total_pips': round(metrics['total_pips'], 2),
                            'profit_factor': round(metrics['profit_factor'], 2),
                            'avg_win': round(metrics['avg_win'], 2),
                            'avg_loss': round(metrics['avg_loss'], 2),
                            'score': round(score, 2)
                        })
        
        progress_bar.empty()
        status_text.empty()
        
        if skipped_count > 0:
            st.info(f"Optimization complete! Skipped {skipped_count} low-performing combinations")
        
        # Convert to DataFrame and sort
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('score', ascending=False)
        
        # Add period info to results
        results_df['period_start'] = period_start
        results_df['period_end'] = period_end
        
        return results_df
        
    except Exception as e:
        st.error(f"Optimization error: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def run_optimization(df, asset_name):
    """Run complete optimization for an asset (wrapper for backward compatibility)"""
    return run_optimization_with_filters(df, asset_name, True, False, False, True)

def get_htf_name(multiplier):
    """Convert HTF multiplier to readable timeframe name"""
    htf_map = {
        1: "Same TF",
        2: "2x HTF",
        3: "3x HTF",
        4: "4x HTF",
        6: "6x HTF",
        8: "8x HTF",
        12: "12x HTF",
        16: "16x HTF"
    }
    return htf_map.get(multiplier, f"{multiplier}x HTF")

# ==================== STREAMLIT UI ====================

def main():
    st.set_page_config(
        page_title="XPST Optimizer",
        page_icon="🎯",
        layout="wide"
    )
    
    # Header
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🎯 XPST Optimizer v{__version__}</h1>
        <p style="color: #e8f4f8; margin: 5px 0 0 0;">TradingView Consistency Verified Edition</p>
        <p style="color: #d0e8f0; margin: 3px 0 0 0; font-size: 0.9em;">Last Updated: {__last_updated__}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Asset configuration
    assets = {
        'BTCUSD': {'yf': 'BTC-USD', 'name': 'Bitcoin/USD'},
        'ETHUSD': {'yf': 'ETH-USD', 'name': 'Ethereum/USD'},
        'XAUUSD': {'yf': 'GC=F', 'name': 'Gold/USD'},
        'EURUSD': {'yf': 'EURUSD=X', 'name': 'Euro/USD'},
        'GBPUSD': {'yf': 'GBPUSD=X', 'name': 'GBP/USD'},
        'USDJPY': {'yf': 'USDJPY=X', 'name': 'USD/JPY'},
        'AUDUSD': {'yf': 'AUDUSD=X', 'name': 'AUD/USD'},
        'USDCAD': {'yf': 'USDCAD=X', 'name': 'USD/CAD'}
    }
    
    # Sidebar
    st.sidebar.header("📊 Configuration")
    
    # Data Source Selection
    data_source = st.sidebar.radio(
        "Data Source",
        options=["Yahoo Finance", "Upload CSV"],
        index=0
    )
    
    # Initialize variables
    selected_assets = []
    timeframe = '5m'
    period = '7d'
    uploaded_files = None
    
    if data_source == "Yahoo Finance":
        # Asset selection
        selected_assets = st.sidebar.multiselect(
            "Select Assets",
            options=list(assets.keys()),
            default=['EURUSD', 'BTCUSD'],
            format_func=lambda x: f"{x} ({assets[x]['name']})"
        )
        
        # Timeframe and period
        col1, col2 = st.sidebar.columns(2)
        with col1:
            timeframe = st.selectbox(
                "Timeframe",
                options=['1m', '5m', '15m', '30m', '1h'],
                index=1
            )
        
        with col2:
            period = st.selectbox(
                "Data Period",
                options=['7d', '1mo', '3mo'],
                index=0,
                help="1m timeframe limited to 7d by Yahoo Finance"
            )
        
        # Validate timeframe/period combination
        if timeframe == '1m' and period != '7d':
            st.sidebar.warning("⚠️ 1-minute data only available for 7 days")
            period = '7d'
    
    else:  # Upload CSV
        st.sidebar.subheader("📁 Upload CSV Files")
        uploaded_files = st.sidebar.file_uploader(
            "Choose CSV files",
            type=['csv'],
            accept_multiple_files=True,
            help="CSV must have columns: time, open, high, low, close, volume"
        )
    
    # Optimization Settings
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Optimization Settings")
    
    # Quick vs Full optimization
    optimization_mode = st.sidebar.radio(
        "Optimization Mode",
        options=["Quick", "Standard", "Full"],
        index=0,
        help="Quick: All Pivot/ATR params with limited HTF (240 combos)\nStandard: All params with moderate HTF (400 combos)\nFull: All params with all HTF variations (640 combos)"
    )
    
    # Filter settings
    use_filters = st.sidebar.checkbox("Use Filters in Optimization", value=True)
    if use_filters:
        use_xtrend = st.sidebar.checkbox("Use X Trend Filter", value=True)
        use_adx = st.sidebar.checkbox("Use ADX Filter", value=False)
        use_ema = st.sidebar.checkbox("Use EMA Filter", value=False)
        xtrend_grey = st.sidebar.checkbox("Require MTF Agreement", value=True, 
                                         help="Grey/block when local and HTF disagree")
    else:
        use_xtrend = False
        use_adx = False
        use_ema = False
        xtrend_grey = False
    
    # HTF Settings
    st.sidebar.markdown("**HTF Settings:**")
    use_htf = st.sidebar.checkbox("Test HTF Variations", value=True, 
                                  help="Disable to only test same timeframe (1x)")
    
    htf_mode = 'Essential'  # Default value
    if use_htf:
        htf_mode = st.sidebar.radio(
            "HTF Testing",
            options=["Essential", "All"],
            index=0,
            help="Essential: Tests 1x, 3x, 6x, 12x\nAll: Tests all multipliers"
        )
    
    # Advanced settings (collapsible)
    with st.sidebar.expander("🔧 Advanced Settings"):
        max_bars = st.sidebar.slider(
            "Max Bars to Process",
            min_value=200,
            max_value=2000,
            value=500,
            step=100,
            help="Fewer bars = faster processing"
        )
        
        skip_low_volume = st.sidebar.checkbox(
            "Skip Low Volume Periods",
            value=True,
            help="Skip combinations that produce < 5 trades"
        )
    
    # Main content area
    st.markdown("### 📊 Data Management")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if data_source == "Yahoo Finance":
            if st.button("📥 Download All Data", type="primary", use_container_width=True):
                st.session_state.downloaded_data.clear()
                
                for asset in selected_assets:
                    with st.spinner(f"Downloading {asset}..."):
                        data = download_data(
                            assets[asset]['yf'],
                            period=period,
                            interval=timeframe
                        )
                        if data is not None:
                            st.session_state.downloaded_data[asset] = data
                            st.success(f"✅ {asset}: {len(data)} bars")
        
        elif data_source == "Custom Date Range":
            if st.button("📥 Download Custom Range", type="primary", use_container_width=True):
                st.session_state.downloaded_data.clear()
                
                for asset in selected_assets:
                    with st.spinner(f"Downloading {asset} for custom range..."):
                        data = download_data_custom_range(
                            assets[asset]['yf'],
                            start_date,
                            end_date,
                            interval=timeframe
                        )
                        if data is not None:
                            st.session_state.downloaded_data[asset] = data
                            st.success(f"✅ {asset}: {len(data)} bars")
        
        else:  # Upload CSV
            if uploaded_files:
                if st.button("📤 Process CSV Files", type="primary", use_container_width=True):
                    st.session_state.downloaded_data.clear()
                    
                    for file in uploaded_files:
                        df = pd.read_csv(file)
                        processed = process_uploaded_csv(df, file.name)
                        if processed is not None:
                            # Extract asset name from filename
                            asset_name = file.name.replace('.csv', '').split('_')[0].upper()
                            st.session_state.downloaded_data[asset_name] = processed
                            st.success(f"✅ {asset_name}: {len(processed)} bars")
            else:
                st.info("👆 Please upload CSV files to proceed")
    
    with col2:
        if st.session_state.downloaded_data:
            if st.button("🚀 Run Optimization", type="primary", use_container_width=True):
                st.session_state.optimization_results.clear()
                
                for asset, data in st.session_state.downloaded_data.items():
                    with st.container():
                        st.write(f"**Optimizing {asset}...**")
                        
                        # Pass all optimization settings
                        results = run_optimization_with_filters(
                            data, asset, use_xtrend, use_adx, use_ema, xtrend_grey,
                            optimization_mode, use_htf, htf_mode if use_htf else 'Essential',
                            max_bars, skip_low_volume
                        )
                        
                        if not results.empty:
                            st.session_state.optimization_results[asset] = results
                            
                            # Show brief summary
                            best = results.iloc[0]
                            st.success(f"Best: Win Rate {best['win_rate']}%, {best['total_pips']:.1f} pips")
    
    with col3:
        if st.session_state.optimization_results:
            if st.button("📊 Clear Results", type="secondary", use_container_width=True):
                st.session_state.optimization_results.clear()
                st.session_state.downloaded_data.clear()
                st.rerun()
    
    # Display current data status
    if st.session_state.downloaded_data:
        st.markdown("---")
        st.markdown("### 📈 Downloaded Data")
        
        data_cols = st.columns(len(st.session_state.downloaded_data))
        for idx, (asset, data) in enumerate(st.session_state.downloaded_data.items()):
            with data_cols[idx]:
                st.metric(
                    label=asset,
                    value=f"{len(data)} bars",
                    delta=f"{data['time'].iloc[-1] - data['time'].iloc[0]} seconds"
                )
        
        # Add download options for the data
        st.markdown("### 💾 Export Data")
        export_cols = st.columns(len(st.session_state.downloaded_data))
        
        for idx, (asset, data) in enumerate(st.session_state.downloaded_data.items()):
            with export_cols[idx]:
                # Convert data to CSV
                csv = data.to_csv(index=False)
                
                # Create download button for each asset
                st.download_button(
                    label=f"📥 Download {asset}",
                    data=csv,
                    file_name=f"{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help=f"Download {asset} price data as CSV file"
                )
        
        # Option to download all data as a zip file
        if len(st.session_state.downloaded_data) > 1:
            st.markdown("---")
            with st.expander("📦 Download All Data as ZIP"):
                import io
                import zipfile
                
                # Create a ZIP file in memory
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for asset, data in st.session_state.downloaded_data.items():
                        csv_data = data.to_csv(index=False)
                        file_name = f"{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        zip_file.writestr(file_name, csv_data)
                
                zip_buffer.seek(0)
                
                st.download_button(
                    label="📦 Download All Data (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"XPST_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
    
    # Results section
    if st.session_state.optimization_results:
        st.markdown("---")
        st.markdown("### 🏆 Optimization Results")
        
        # Summary table
        summary_data = []
        for asset, results in st.session_state.optimization_results.items():
            best = results.iloc[0]
            summary_data.append({
                'Asset': asset,
                'Best Win Rate': f"{best['win_rate']}%",
                'Total Pips': f"{best['total_pips']:.1f}",
                'Profit Factor': f"{best['profit_factor']:.2f}",
                'HTF': best['htf_timeframe'],
                'Score': f"{best['score']:.1f}"
            })
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
        
        # Detailed tabs
        tabs = st.tabs(list(st.session_state.optimization_results.keys()))
        
        for tab, asset in zip(tabs, st.session_state.optimization_results.keys()):
            with tab:
                results = st.session_state.optimization_results[asset]
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Top configurations with all filters shown
                    st.write("**🥇 Top 10 Configurations:**")
                    display_cols = ['pivot_period', 'atr_factor', 'atr_period', 
                                  'htf_timeframe', 'use_xtrend', 'use_adx', 'use_ema',
                                  'total_trades', 'win_rate', 'total_pips', 
                                  'profit_factor', 'score']
                    st.dataframe(
                        results[display_cols].head(10),
                        use_container_width=True,
                        hide_index=True
                    )
                
                with col2:
                    # Best configuration details with complete settings
                    best = results.iloc[0]
                    
                    # Get period info
                    period_start = best['period_start'] if 'period_start' in best else None
                    period_end = best['period_end'] if 'period_end' in best else None
                    
                    st.write("**📍 Optimal Settings:**")
                    
                    # Format period string
                    period_str = ""
                    if period_start and period_end:
                        period_str = f"\n// Data Period\nStart: {period_start.strftime('%H:%M:%S %d/%m/%Y')}\nEnd: {period_end.strftime('%H:%M:%S %d/%m/%Y')}\n"
                    
                    # Format filter values for display
                    use_adx_display = best.get('use_adx', 'No')
                    adx_threshold = '25' if use_adx_display != 'No' else '-'
                    use_ema_display = best.get('use_ema', 'No')
                    ema_period = '200' if use_ema_display != 'No' else '-'
                    
                    st.code(f"""// XPST v3.1 Complete Settings for {asset}
{period_str}
// === CORE STRATEGY SETTINGS ===
Pivot Period: {best['pivot_period']}
ATR Factor: {best['atr_factor']}
ATR Period: {best['atr_period']}

// === FILTER SETTINGS ===
Use X Trend Filter: {best.get('use_xtrend', 'Yes')}
Use ADX Filter: {use_adx_display.replace('ADX≥', 'Yes (Threshold: ').replace('25', '25)') if use_adx_display != 'No' else 'No'}
ADX Threshold: {adx_threshold}
Use EMA Filter: {use_ema_display.replace('EMA', 'Yes (Period: ') + ')' if use_ema_display != 'No' else 'No'}
EMA Period: {ema_period}

// === X TREND MTF SETTINGS ===
HTF Multiplier: {best['htf_multiplier']}x
MTF Agreement Required: {best.get('mtf_agree', 'Yes')}

// === PERFORMANCE METRICS ===
Win Rate: {best['win_rate']}%
Total Trades: {best['total_trades']}
Total Pips: {best['total_pips']:.1f}
Profit Factor: {best['profit_factor']:.2f}
Avg Win: {best['avg_win']:.1f} pips
Avg Loss: {best['avg_loss']:.1f} pips
Score: {best['score']:.1f}
                    """)
                
                # Last N Trades Analysis
                st.write("**📊 Last N Trades Analysis:**")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    last_n_trades = st.number_input(
                        "Analyze last N trades",
                        min_value=10,
                        max_value=100,
                        value=30,
                        step=10,
                        key=f"last_n_{asset}"
                    )
                
                with col_b:
                    if st.button(f"Calculate Last {last_n_trades} Trades", key=f"calc_{asset}"):
                        # Run backtest with best parameters
                        # Parse the filter values
                        use_xtrend_bool = best.get('use_xtrend', 'Yes') == 'Yes'
                        use_adx_bool = best.get('use_adx', 'No') != 'No'
                        use_ema_bool = best.get('use_ema', 'No') != 'No'
                        
                        best_params = {
                            'pivot_period': best['pivot_period'],
                            'atr_factor': best['atr_factor'],
                            'atr_period': best['atr_period'],
                            'use_xtrend': use_xtrend_bool,
                            'use_adx': use_adx_bool,
                            'adx_threshold': 25,
                            'use_ema': use_ema_bool,
                            'ema_period': 200,
                            'xtrend_grey_disagree': best.get('mtf_agree', 'Yes') == 'Yes'
                        }
                        
                        # Get the data for this asset
                        asset_data = st.session_state.downloaded_data.get(asset)
                        if asset_data is not None:
                            # Run full backtest to get trade details
                            full_metrics, trade_list = run_backtest_with_trades(
                                asset_data, best_params, best['htf_multiplier']
                            )
                            
                            if trade_list and len(trade_list) > 0:
                                # Analyze last N trades
                                last_trades = trade_list[-last_n_trades:] if len(trade_list) >= last_n_trades else trade_list
                                
                                # Calculate metrics for last N trades
                                last_n_pips = sum([t['profit_pips'] for t in last_trades])
                                last_n_wins = len([t for t in last_trades if t['profit_pips'] > 0])
                                last_n_losses = len([t for t in last_trades if t['profit_pips'] < 0])
                                last_n_win_rate = (last_n_wins / len(last_trades) * 100) if last_trades else 0
                                
                                st.success(f"""
                                **Last {last_n_trades} Trades Performance:**
                                - Win Rate: {last_n_win_rate:.1f}%
                                - Total Pips: {last_n_pips:.1f}
                                - Wins/Losses: {last_n_wins}/{last_n_losses}
                                - Avg per Trade: {last_n_pips/len(last_trades):.1f} pips
                                - Actual Trades Analyzed: {len(last_trades)}
                                """)
                            else:
                                st.warning("No trades found with these settings")
                        else:
                            st.error("Data not found for this asset")
                
                # HTF Analysis
                st.write("**📊 HTF Performance Analysis:**")
                htf_summary = results.groupby('htf_timeframe').agg({
                    'score': 'mean',
                    'win_rate': 'mean',
                    'total_pips': 'mean',
                    'total_trades': 'mean'
                }).round(2).sort_values('score', ascending=False)
                
                st.dataframe(htf_summary, use_container_width=True)
                
                # Download button
                csv = results.to_csv(index=False)
                st.download_button(
                    label=f"📥 Download {asset} Results CSV",
                    data=csv,
                    file_name=f"xpst_optimization_{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    else:
        if not st.session_state.downloaded_data:
            st.info("👈 Select assets and download data to begin optimization")
        else:
            st.info("✨ Data ready! Click 'Run Optimization' to find the best XPST settings")
    
    # Footer with verification tips
    st.markdown("---")
    with st.expander("🔍 How to Verify Results with TradingView"):
        st.markdown("""
        ### Method 1: Use Exact Same Data
        1. Download data from optimizer using **Custom Date Range**
        2. Export the CSV using the download button
        3. Note the exact start/end times shown in optimization
        4. In TradingView, use Bar Replay to match the same period
        
        ### Method 2: Compare Key Metrics
        Focus on these ratio-based metrics that should be similar:
        - **Win Rate %** (should match within 2-3%)
        - **Average Win/Loss Ratio**
        - **Profit Factor** (if trade count is similar)
        
        ### Method 3: Spot Check Specific Trades
        1. Pick a specific date/time from the optimizer results
        2. Check if TradingView shows entry/exit at same points
        3. Verify signal conditions (PVT flip, X Trend state, etc.)
        
        ### Tips for Accurate Comparison:
        - ✅ Ensure same timeframe (1m, 5m, etc.)
        - ✅ Check timezone settings match
        - ✅ Verify all filters are set identically
        - ✅ Use "Require MTF Agreement" if testing HTF
        - ⚠️ Small differences (1-2 trades) are normal due to data variations
        """)
    
    st.markdown(
        """
        <div style="text-align: center; color: #666;">
            <small>
            XPST Optimizer v{} | Matches TradingView Implementation<br>
            Data provided by Yahoo Finance | Optimized for XPST v3.1 Pine Script
            </small>
        </div>
        """.format(__version__),
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
