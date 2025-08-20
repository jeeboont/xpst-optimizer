"""
XPST Optimizer - Enhanced Filter Optimization Edition
Version: 3.2.0
Last Updated: 2025-08-20
Author: XPST Trading Systems

NEW IN v3.2.0:
- Added ADX threshold optimization (15, 20, 25, 30, 35)
- Added EMA period optimization (50, 100, 150, 200, 250)
- Smart optimization modes to manage increased combinations
- Enhanced results display with filter parameter details
- Improved performance tracking and analysis
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
__version__ = "3.2.0"
__last_updated__ = "2025-08-20"

# Initialize session state
if 'downloaded_data' not in st.session_state:
    st.session_state.downloaded_data = {}
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = {}
if 'custom_assets' not in st.session_state:
    st.session_state.custom_assets = {}

# ==================== INDICATOR CALCULATION FUNCTIONS ====================

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

# ==================== BACKTEST FUNCTIONS ====================

def run_backtest_with_trades(df, params, htf_multiplier=None, asset_name=""):
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
            if use_htf and params.get('xtrend_grey_disagree', False):
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
                    if params.get('xtrend_grey_disagree', False):
                        exit_signal = exit_signal or (xtrend_flip and htf_flip)
                    else:
                        exit_signal = exit_signal or htf_flip
                
                if exit_signal:
                    # Calculate profit based on asset type
                    if 'BTC' in asset_name.upper() or 'ETH' in asset_name.upper() or 'XAU' in asset_name.upper():
                        # For crypto and gold, use points/dollars
                        profit_pips = row['close'] - entry_price
                    else:
                        # For forex, use standard pip calculation
                        profit_pips = (row['close'] - entry_price) / 0.0001
                    
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
                    if params.get('xtrend_grey_disagree', False):
                        exit_signal = exit_signal or (xtrend_flip and htf_flip)
                    else:
                        exit_signal = exit_signal or htf_flip
                
                if exit_signal:
                    # Calculate profit based on asset type
                    if 'BTC' in asset_name.upper() or 'ETH' in asset_name.upper() or 'XAU' in asset_name.upper():
                        # For crypto and gold, use points/dollars
                        profit_pips = entry_price - row['close']
                    else:
                        # For forex, use standard pip calculation
                        profit_pips = (entry_price - row['close']) / 0.0001
                    
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

def run_backtest(df, params, htf_multiplier=None, asset_name=""):
    """Run backtest with exact XPST v3.1 logic (wrapper for compatibility)"""
    metrics, _ = run_backtest_with_trades(df, params, htf_multiplier, asset_name)
    return metrics

# ==================== DATA FUNCTIONS ====================

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

# ==================== OPTIMIZATION FUNCTIONS ====================

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

def run_optimization_with_filters(df, asset_name, use_xtrend, use_adx, use_ema, xtrend_grey, 
                                  optimization_mode='Quick', use_htf=True, htf_mode='Essential',
                                  max_bars=500, skip_low_volume=True, optimize_filters=True):
    """Run optimization with enhanced filter parameter optimization"""
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
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3] if use_htf else [1]
            # Quick mode: Limited filter params
            adx_thresholds = [20, 25, 30] if optimize_filters else [25]
            ema_periods = [100, 200] if optimize_filters else [200]
        elif optimization_mode == 'Standard':
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3, 4, 6] if use_htf else [1]
            # Standard mode: More filter params
            adx_thresholds = [15, 20, 25, 30, 35] if optimize_filters else [25]
            ema_periods = [50, 100, 150, 200, 250] if optimize_filters else [200]
        else:  # Full
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3, 4, 6, 8, 12, 16] if use_htf else [1]
            # Full mode: All filter params
            adx_thresholds = [15, 20, 25, 30, 35] if optimize_filters else [25]
            ema_periods = [50, 100, 150, 200, 250] if optimize_filters else [200]
        
        # Further filter HTF based on htf_mode
        if use_htf and htf_mode == 'Essential':
            htf_multipliers = [x for x in htf_multipliers if x in [1, 2, 3, 4]]
        
        # Filter parameter combinations based on enabled filters
        if not use_adx:
            adx_thresholds = [25]  # Default value when not used
        if not use_ema:
            ema_periods = [200]  # Default value when not used
        
        # Calculate total combinations
        total_combinations = (len(pivot_periods) * len(atr_factors) * len(atr_periods) * 
                            len(htf_multipliers) * len(adx_thresholds) * len(ema_periods))
        
        # Show optimization summary
        mode_desc = {
            'Quick': f'Limited filter optimization ({len(adx_thresholds)} ADX × {len(ema_periods)} EMA)',
            'Standard': f'Standard filter optimization ({len(adx_thresholds)} ADX × {len(ema_periods)} EMA)', 
            'Full': f'Complete filter optimization ({len(adx_thresholds)} ADX × {len(ema_periods)} EMA)'
        }
        
        filter_info = ""
        if optimize_filters:
            filter_info = f"\n🔧 ADX Thresholds: {adx_thresholds}\n🔧 EMA Periods: {ema_periods}"
        
        st.info(f"""
        **{mode_desc[optimization_mode]}**
        📊 Total combinations: {total_combinations:,}
        🎯 Core params: {len(pivot_periods)} Pivot × {len(atr_factors)} ATR Factor × {len(atr_periods)} ATR Period
        📈 HTF variations: {len(htf_multipliers)}
        {filter_info}
        """)
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        combination_count = 0
        skipped_count = 0
        
        # Early exit tracking for poor performers
        best_score = 0
        base_scores = {}
        
        for pivot_period in pivot_periods:
            for atr_factor in atr_factors:
                for atr_period in atr_periods:
                    for adx_threshold in adx_thresholds:
                        for ema_period in ema_periods:
                            base_key = f"{pivot_period}_{atr_factor}_{atr_period}_{adx_threshold}_{ema_period}"
                            
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
                                    'adx_threshold': adx_threshold,
                                    'use_ema': use_ema,
                                    'ema_period': ema_period,
                                    'xtrend_grey_disagree': xtrend_grey
                                }
                                
                                # Run backtest
                                metrics = run_backtest(df, params, htf_mult, asset_name)
                                
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
                                
                                # Format filter display values
                                adx_display = f"ADX≥{adx_threshold}" if use_adx else 'No'
                                ema_display = f"EMA{ema_period}" if use_ema else 'No'
                                
                                # Include all settings in results
                                results.append({
                                    'pivot_period': pivot_period,
                                    'atr_factor': atr_factor,
                                    'atr_period': atr_period,
                                    'adx_threshold': adx_threshold if use_adx else None,
                                    'ema_period': ema_period if use_ema else None,
                                    'htf_multiplier': htf_mult,
                                    'htf_timeframe': get_htf_name(htf_mult),
                                    'use_xtrend': 'Yes' if use_xtrend else 'No',
                                    'use_adx': adx_display,
                                    'use_ema': ema_display,
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

# ==================== MAIN APPLICATION ====================

def main():
    st.set_page_config(
        page_title="XPST Optimizer v3.2",
        page_icon="🎯",
        layout="wide"
    )
    
    # Header
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🎯 XPST Optimizer v{__version__}</h1>
        <p style="color: #e8f4f8; margin: 5px 0 0 0;">Enhanced Filter Optimization Edition</p>
        <p style="color: #d0e8f0; margin: 3px 0 0 0; font-size: 0.9em;">Last Updated: {__last_updated__}</p>
        <p style="color: #ffd700; margin: 8px 0 0 0; font-size: 0.95em; font-weight: bold;">🆕 NEW: ADX Threshold & EMA Period Optimization!</p>
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
    
    # Sidebar configuration
    st.sidebar.header("📊 Configuration")
    
    # Data Source Selection
    data_source = st.sidebar.radio(
        "Data Source",
        options=["Yahoo Finance", "Upload CSV", "Custom Date Range"],
        index=0
    )
    
    # Initialize variables
    selected_assets = []
    timeframe = '5m'
    period = '7d'
    uploaded_files = None
    start_date = None
    end_date = None
    
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
    
    elif data_source == "Custom Date Range":
        # Custom date range for TradingView matching
        st.sidebar.subheader("📅 Custom Date Range")
        st.sidebar.info("Use this to match exact TradingView data periods")
        
        selected_assets = st.sidebar.multiselbox(
            "Select Assets",
            options=list(assets.keys()),
            default=['EURUSD'],
            format_func=lambda x: f"{x} ({assets[x]['name']})"
        )
        
        timeframe = st.sidebar.selectbox(
            "Timeframe",
            options=['1m', '5m', '15m', '30m', '1h', '1d'],
            index=1
        )
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=30),
                max_value=datetime.now()
            )
        
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                max_value=datetime.now()
            )
        
        # Show exact period that will be used
        st.sidebar.success(f"Period: {start_date} to {end_date}")
    
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
        help="""
        Quick: Core params + Limited filters (3 ADX × 2 EMA)
        Standard: Core params + Standard filters (5 ADX × 5 EMA)  
        Full: Core params + All filters (5 ADX × 5 EMA + All HTF)
        """
    )
    
    # Enhanced Filter Optimization Toggle
    st.sidebar.markdown("### 🆕 Enhanced Filter Optimization")
    optimize_filters = st.sidebar.checkbox(
        "Optimize Filter Parameters", 
        value=True,
        help="When enabled, tests multiple ADX thresholds and EMA periods"
    )
    
    if optimize_filters:
        st.sidebar.success("✅ Will optimize ADX & EMA parameters")
        
        # Show what will be tested
        if optimization_mode == 'Quick':
            st.sidebar.info("Quick: ADX[20,25,30] × EMA[100,200]")
        elif optimization_mode == 'Standard':
            st.sidebar.info("Standard: ADX[15,20,25,30,35] × EMA[50,100,150,200,250]")
        else:
            st.sidebar.info("Full: ADX[15,20,25,30,35] × EMA[50,100,150,200,250]")
    else:
        st.sidebar.info("Using defaults: ADX=25, EMA=200")
    
    # Filter settings
    use_filters = st.sidebar.checkbox("Use Filters in Optimization", value=True)
    if use_filters:
        use_xtrend = st.sidebar.checkbox("Use X Trend Filter", value=True)
        use_adx = st.sidebar.checkbox("Use ADX Filter", value=False)
        use_ema = st.sidebar.checkbox("Use EMA Filter", value=False)
        xtrend_grey = st.sidebar.checkbox("Require MTF Agreement", value=False, 
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
    
    htf_mode = 'Essential'
    if use_htf:
        htf_mode = st.sidebar.radio(
            "HTF Testing",
            options=["Essential", "All"],
            index=0,
            help="Essential: Tests 1x, 2x, 3x, 4x\nAll: Tests all multipliers"
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
            if st.button("🚀 Run Enhanced Optimization", type="primary", use_container_width=True):
                st.session_state.optimization_results.clear()
                
                for asset, data in st.session_state.downloaded_data.items():
                    with st.container():
                        st.write(f"**Optimizing {asset} with Enhanced Filters...**")
                        
                        # Pass enhanced optimization settings
                        results = run_optimization_with_filters(
                            data, asset, use_xtrend, use_adx, use_ema, xtrend_grey,
                            optimization_mode, use_htf, htf_mode if use_htf else 'Essential',
                            max_bars, skip_low_volume, optimize_filters
                        )
                        
                        if not results.empty:
                            st.session_state.optimization_results[asset] = results
                            
                            # Show brief summary with filter info
                            best = results.iloc[0]
                            filter_summary = f"Win Rate {best['win_rate']}%, {best['total_pips']:.1f} pips"
                            if optimize_filters:
                                if best['adx_threshold'] is not None:
                                    filter_summary += f", ADX≥{best['adx_threshold']}"
                                if best['ema_period'] is not None:
                                    filter_summary += f", EMA{best['ema_period']}"
                            st.success(f"Best: {filter_summary}")
    
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
    
    # Results section
    if st.session_state.optimization_results:
        st.markdown("---")
        st.markdown("### 🏆 Enhanced Optimization Results")
        
        # Summary table
        summary_data = []
        for asset, results in st.session_state.optimization_results.items():
            best = results.iloc[0]
            
            # Format filter info for summary
            filter_info = ""
            if best['adx_threshold'] is not None:
                filter_info += f" ADX≥{best['adx_threshold']}"
            if best['ema_period'] is not None:
                filter_info += f" EMA{best['ema_period']}"
            
            summary_data.append({
                'Asset': asset,
                'Best Win Rate': f"{best['win_rate']}%",
                'Total Pips': f"{best['total_pips']:.1f}",
                'Profit Factor': f"{best['profit_factor']:.2f}",
                'HTF': best['htf_timeframe'],
                'Filters': filter_info.strip() if filter_info else 'None',
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
                    # Top configurations with enhanced filter display
                    st.write("**🥇 Top 10 Enhanced Configurations:**")
                    display_cols = ['pivot_period', 'atr_factor', 'atr_period', 
                                  'htf_timeframe', 'use_xtrend', 'use_adx', 'use_ema',
                                  'adx_threshold', 'ema_period',
                                  'total_trades', 'win_rate', 'total_pips', 
                                  'profit_factor', 'score']
                    
                    # Filter out None values for cleaner display
                    display_results = results[display_cols].copy()
                    
                    st.dataframe(
                        display_results.head(10),
                        use_container_width=True,
                        hide_index=True
                    )
                
                with col2:
                    # Best configuration details with complete enhanced settings
                    best = results.iloc[0]
                    
                    # Get period info
                    period_start = best['period_start'] if 'period_start' in best else None
                    period_end = best['period_end'] if 'period_end' in best else None
                    
                    st.write("**📍 Optimal Enhanced Settings:**")
                    
                    # Format period string
                    period_str = ""
                    if period_start and period_end:
                        period_str = f"\n// Data Period\nStart: {period_start.strftime('%H:%M:%S %d/%m/%Y')}\nEnd: {period_end.strftime('%H:%M:%S %d/%m/%Y')}\n"
                    
                    # Format enhanced filter values
                    adx_threshold_val = best.get('adx_threshold')
                    ema_period_val = best.get('ema_period')
                    
                    use_adx_display = best.get('use_adx', 'No')
                    adx_threshold_display = f"{adx_threshold_val}" if adx_threshold_val is not None else '-'
                    
                    use_ema_display = best.get('use_ema', 'No')
                    ema_period_display = f"{ema_period_val}" if ema_period_val is not None else '-'
                    
                    st.code(f"""// XPST v3.2 Enhanced Settings for {asset}
{period_str}
// === CORE STRATEGY SETTINGS ===
Pivot Period: {best['pivot_period']}
ATR Factor: {best['atr_factor']}
ATR Period: {best['atr_period']}

// === ENHANCED FILTER SETTINGS ===
Use X Trend Filter: {best.get('use_xtrend', 'Yes')}
Use ADX Filter: {use_adx_display.replace('ADX≥', 'Yes').replace(str(adx_threshold_val) if adx_threshold_val else '', '')}
ADX Threshold: {adx_threshold_display}
Use EMA Filter: {use_ema_display.replace('EMA', 'Yes').replace(str(ema_period_val) if ema_period_val else '', '')}
EMA Period: {ema_period_display}

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
                
                # Enhanced Filter Analysis
                if optimize_filters:
                    st.write("**🔧 Enhanced Filter Performance Analysis:**")
                    
                    # ADX threshold analysis
                    if best.get('adx_threshold') is not None:
                        adx_analysis = results[results['use_adx'] != 'No'].groupby('adx_threshold').agg({
                            'score': 'mean',
                            'win_rate': 'mean',
                            'total_pips': 'mean'
                        }).round(2).sort_values('score', ascending=False)
                        
                        st.write("**ADX Threshold Performance:**")
                        st.dataframe(adx_analysis, use_container_width=True)
                    
                    # EMA period analysis
                    if best.get('ema_period') is not None:
                        ema_analysis = results[results['use_ema'] != 'No'].groupby('ema_period').agg({
                            'score': 'mean',
                            'win_rate': 'mean',
                            'total_pips': 'mean'
                        }).round(2).sort_values('score', ascending=False)
                        
                        st.write("**EMA Period Performance:**")
                        st.dataframe(ema_analysis, use_container_width=True)
                
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
                        # Run backtest with best enhanced parameters
                        use_xtrend_bool = best.get('use_xtrend', 'Yes') == 'Yes'
                        use_adx_bool = best.get('use_adx', 'No') != 'No'
                        use_ema_bool = best.get('use_ema', 'No') != 'No'
                        
                        best_params = {
                            'pivot_period': best['pivot_period'],
                            'atr_factor': best['atr_factor'],
                            'atr_period': best['atr_period'],
                            'use_xtrend': use_xtrend_bool,
                            'use_adx': use_adx_bool,
                            'adx_threshold': best.get('adx_threshold', 25),
                            'use_ema': use_ema_bool,
                            'ema_period': best.get('ema_period', 200),
                            'xtrend_grey_disagree': best.get('mtf_agree', 'Yes') == 'Yes'
                        }
                        
                        # Get the data for this asset
                        asset_data = st.session_state.downloaded_data.get(asset)
                        if asset_data is not None:
                            # Run full backtest to get trade details
                            full_metrics, trade_list = run_backtest_with_trades(
                                asset_data, best_params, best['htf_multiplier'], asset
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
                
                # Download button with enhanced results
                csv = results.to_csv(index=False)
                st.download_button(
                    label=f"📥 Download {asset} Enhanced Results CSV",
                    data=csv,
                    file_name=f"xpst_enhanced_optimization_{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    else:
        if not st.session_state.downloaded_data:
            st.info("👈 Select assets and download data to begin enhanced optimization")
        else:
            st.info("✨ Data ready! Click 'Run Enhanced Optimization' to find the best XPST settings with optimized filters")
    
    # Enhanced Feature Info Box
    if not st.session_state.optimization_results:
        st.markdown("---")
        with st.expander("🆕 What's New in v3.2.0 - Enhanced Filter Optimization"):
            st.markdown("""
            ### 🚀 Major Enhancements:
            
            **1. ADX Threshold Optimization**
            - Previously: Fixed at 25
            - Now: Tests 15, 20, 25, 30, 35 (or subset based on mode)
            - Find optimal momentum threshold for each asset
            
            **2. EMA Period Optimization**
            - Previously: Fixed at 200
            - Now: Tests 50, 100, 150, 200, 250 (or subset based on mode)
            - Discover best trend filter period
            
            **3. Smart Optimization Modes**
            - **Quick**: Core params + Limited filters (faster)
            - **Standard**: Core params + Full filters (balanced) 
            - **Full**: Everything + All HTF variations (comprehensive)
            
            **4. Enhanced Results Display**
            - Shows optimal ADX threshold and EMA period
            - Performance analysis by filter parameter
            - Complete TradingView settings export
            
            ### 📊 Combination Count Examples:
            - **v3.1**: ~400 combinations (Standard mode)
            - **v3.2**: ~10,000 combinations (Standard mode with filters)
            - **Smart skipping** keeps optimization times reasonable
            
            ### 🎯 Expected Benefits:
            - Better asset-specific filter tuning
            - Higher win rates and profit factors
            - More robust performance across market conditions
            """)
    
    # Footer with enhanced verification tips
    st.markdown("---")
    with st.expander("🔍 How to Verify Enhanced Results with TradingView"):
        st.markdown("""
        ### Enhanced Verification Process:
        
        **Step 1: Apply Core Settings**
        - Set Pivot Period, ATR Factor, ATR Period from results
        - Enable/disable X Trend, ADX, EMA filters as shown
        
        **Step 2: Apply Enhanced Filter Settings**
        - Set **ADX Threshold** to optimized value (if ADX enabled)
        - Set **EMA Period** to optimized value (if EMA enabled) 
        - Enable **HTF multiplier** as specified
        
        **Step 3: Verify Key Metrics**
        - Win Rate should match within 2-3%
        - Total pips should be similar (±10%)
        - Profit factor should align (±0.2)
        
        ### 🆕 Enhanced Settings to Check:
        ```
        // Standard Settings
        Pivot Period: [from results]
        ATR Factor: [from results]
        ATR Period: [from results]
        
        // Enhanced Filter Settings  
        ADX Threshold: [optimized value, not default 25]
        EMA Period: [optimized value, not default 200]
        HTF Multiplier: [optimized HTF]
        ```
        
        ### 💡 Pro Tips:
        - Use the exact ADX threshold shown (e.g., 30 instead of 25)
        - Use the exact EMA period shown (e.g., 150 instead of 200)
        - Small differences are normal due to data feed variations
        - Focus on ratio-based metrics (win rate %, profit factor)
        """)
    
    st.markdown(
        f"""
        <div style="text-align: center; color: #666;">
            <small>
            XPST Optimizer v{__version__} | Enhanced Filter Optimization Edition<br>
            ADX Threshold & EMA Period Optimization | Data provided by Yahoo Finance
            </small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
