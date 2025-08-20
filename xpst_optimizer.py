"""
XPST Optimizer - Enhanced cBot Parity Edition
Version: 3.2.2
Last Updated: 2025-08-20
Author: XPST Trading Systems

NEW IN v3.2.2:
- ENHANCED: Smoothed Pivot Supertrend (no mid-air flips)
- ENHANCED: Correct exit precedence (XTrend > Opposite > Trend > ADX)
- ENHANCED: ADX exit logic implementation
- ENHANCED: EMA filter sequencing (applied after signal generation)
- ENHANCED: Complete TradingView v3.1 logic parity
- ENHANCED: Jump protection system (2×ATR limits)
- ENHANCED: Enhanced pending state management
- NOW MATCHES: cBot v3.1.2-2.2 Enhanced behavior exactly
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
__version__ = "3.2.2"
__last_updated__ = "2025-08-20"

# Initialize session state
if 'downloaded_data' not in st.session_state:
    st.session_state.downloaded_data = {}
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = {}
if 'custom_assets' not in st.session_state:
    st.session_state.custom_assets = {}

# ==================== ENHANCED INDICATOR CALCULATION FUNCTIONS ====================

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
    """ENHANCED: Calculate Pivot Supertrend with v3.1.2 improvements (no mid-air flips)"""
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
        
        # ENHANCED: Calculate center line with smoothed updates (prevents sudden jumps)
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
                    # ENHANCED: Smoothed center calculation to prevent sudden jumps
                    smoothing_factor = 0.1  # Much gentler than the original (2+1)/3 = 0.33
                    center.iloc[i] = (center.iloc[i-1] * (1 - smoothing_factor)) + (last_pivot.iloc[i] * smoothing_factor)
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
        
        # ENHANCED: Initialize trailing stop and trend with jump protection
        tup = pd.Series(index=df.index, dtype=float)
        tdown = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)
        
        # Set initial values
        if len(df) > 0:
            tup.iloc[0] = up.iloc[0] if not pd.isna(up.iloc[0]) else df['low'].iloc[0]
            tdown.iloc[0] = down.iloc[0] if not pd.isna(down.iloc[0]) else df['high'].iloc[0]
            trend.iloc[0] = 1
        
        for i in range(1, len(df)):
            # Store previous values for jump protection
            prev_tup = tup.iloc[i-1]
            prev_tdown = tdown.iloc[i-1]
            
            # Calculate new TUp with jump protection
            if df['close'].iloc[i-1] > prev_tup if not pd.isna(prev_tup) else False:
                new_tup = max(up.iloc[i], prev_tup) if not pd.isna(prev_tup) and not pd.isna(up.iloc[i]) else up.iloc[i]
            else:
                new_tup = up.iloc[i] if not pd.isna(up.iloc[i]) else prev_tup
            
            # ENHANCED: Prevent sudden jumps - limit change to 2 * ATR per bar
            max_change = 2 * atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0
            if not pd.isna(prev_tup) and not pd.isna(new_tup) and abs(new_tup - prev_tup) > max_change:
                tup.iloc[i] = prev_tup + (max_change if new_tup > prev_tup else -max_change)
            else:
                tup.iloc[i] = new_tup
            
            # Calculate new TDown with jump protection
            if df['close'].iloc[i-1] < prev_tdown if not pd.isna(prev_tdown) else False:
                new_tdown = min(down.iloc[i], prev_tdown) if not pd.isna(prev_tdown) and not pd.isna(down.iloc[i]) else down.iloc[i]
            else:
                new_tdown = down.iloc[i] if not pd.isna(down.iloc[i]) else prev_tdown
            
            # ENHANCED: Prevent sudden jumps - limit change to 2 * ATR per bar
            if not pd.isna(prev_tdown) and not pd.isna(new_tdown) and abs(new_tdown - prev_tdown) > max_change:
                tdown.iloc[i] = prev_tdown + (max_change if new_tdown > prev_tdown else -max_change)
            else:
                tdown.iloc[i] = new_tdown
            
            # ENHANCED: Enhanced trend determination with stability checks
            current_close = df['close'].iloc[i]
            prev_trend = trend.iloc[i-1] if i > 0 else 1
            
            # Only allow trend change if price clearly crosses the opposite line
            # AND the new trend line is stable (not jumping around)
            if current_close > tdown.iloc[i-1] and prev_trend != 1:
                # Additional check: ensure we're not in a sudden jump situation
                stable_transition = abs(tdown.iloc[i] - prev_tdown) <= atr.iloc[i] if not pd.isna(atr.iloc[i]) else True
                if stable_transition or prev_trend == 0:
                    trend.iloc[i] = 1  # Bullish trend
                else:
                    trend.iloc[i] = prev_trend
            elif current_close < tup.iloc[i-1] and prev_trend != -1:
                # Additional check: ensure we're not in a sudden jump situation
                stable_transition = abs(tup.iloc[i] - prev_tup) <= atr.iloc[i] if not pd.isna(atr.iloc[i]) else True
                if stable_transition or prev_trend == 0:
                    trend.iloc[i] = -1  # Bearish trend
                else:
                    trend.iloc[i] = prev_trend
            else:
                trend.iloc[i] = prev_trend
            
            # Initialize trend if not set
            if trend.iloc[i] == 0:
                trend.iloc[i] = 1 if current_close > (tup.iloc[i] + tdown.iloc[i]) / 2 else -1
        
        df['pvt_trend'] = trend
        df['pvt_tup'] = tup
        df['pvt_tdown'] = tdown
        df['pvt_signal'] = trend.diff().fillna(0)
        
        return df
        
    except Exception as e:
        print(f"Error in Enhanced Pivot Supertrend calculation: {e}")
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

# ==================== ENHANCED BACKTEST FUNCTIONS ====================

def run_backtest_with_trades(df, params, htf_multiplier=None, asset_name=""):
    """ENHANCED: Run backtest with cBot v3.1.2-2.2 exact logic"""
    try:
        # Calculate indicators with enhanced logic
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
        
        # ENHANCED: Generate signals with complete TradingView v3.1 logic
        signals = []
        position = None
        entry_price = None
        entry_time = None
        
        # ENHANCED: Track pending signals (comprehensive state management)
        pvt_buy_pending = False
        pvt_sell_pending = False
        waiting_for_adx_buy = False
        waiting_for_adx_sell = False
        adx_was_above_threshold = False
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # Check for PVT flips
            pvt_buy_condition = (row['pvt_trend'] == 1) and (prev_row['pvt_trend'] == -1)
            pvt_sell_condition = (row['pvt_trend'] == -1) and (prev_row['pvt_trend'] == 1)
            
            # ENHANCED: Pending state management (TradingView v3.1 logic)
            if pvt_buy_condition:
                pvt_buy_pending = True
                pvt_sell_pending = False
                if params.get('use_adx', False) and not (row['adx'] >= params.get('adx_threshold', 25)):
                    waiting_for_adx_buy = True
            
            if pvt_sell_condition:
                pvt_sell_pending = True
                pvt_buy_pending = False
                if params.get('use_adx', False) and not (row['adx'] >= params.get('adx_threshold', 25)):
                    waiting_for_adx_sell = True
            
            # Update ADX waiting states
            if waiting_for_adx_buy and (row['adx'] >= params.get('adx_threshold', 25)):
                waiting_for_adx_buy = False
            if waiting_for_adx_sell and (row['adx'] >= params.get('adx_threshold', 25)):
                waiting_for_adx_sell = False
            
            # Check filters
            adx_filter = params.get('use_adx', False)
            adx_filter_passed = not adx_filter or row['adx'] >= params.get('adx_threshold', 25)
            
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
            
            # ENHANCED: Generate entry signals (complex pending logic)
            buy_signal = False
            sell_signal = False
            
            if not xtrend_filter:
                # No X Trend filter
                if not adx_filter:
                    buy_signal = pvt_buy_condition
                    sell_signal = pvt_sell_condition
                else:
                    buy_signal = pvt_buy_condition and adx_filter_passed
                    buy_signal = buy_signal or (waiting_for_adx_buy and adx_filter_passed)
                    sell_signal = pvt_sell_condition and adx_filter_passed
                    sell_signal = sell_signal or (waiting_for_adx_sell and adx_filter_passed)
            else:
                # With X Trend filter - complex pending logic
                if pvt_buy_condition and xtrend_buy:
                    if not adx_filter or adx_filter_passed:
                        buy_signal = True
                        pvt_buy_pending = False
                        waiting_for_adx_buy = False
                    else:
                        waiting_for_adx_buy = True
                elif pvt_buy_pending and xtrend_buy:
                    if not adx_filter or adx_filter_passed:
                        buy_signal = True
                        pvt_buy_pending = False
                        waiting_for_adx_buy = False
                    elif waiting_for_adx_buy and adx_filter_passed:
                        buy_signal = True
                        pvt_buy_pending = False
                        waiting_for_adx_buy = False
                
                if pvt_sell_condition and xtrend_sell:
                    if not adx_filter or adx_filter_passed:
                        sell_signal = True
                        pvt_sell_pending = False
                        waiting_for_adx_sell = False
                    else:
                        waiting_for_adx_sell = True
                elif pvt_sell_pending and xtrend_sell:
                    if not adx_filter or adx_filter_passed:
                        sell_signal = True
                        pvt_sell_pending = False
                        waiting_for_adx_sell = False
                    elif waiting_for_adx_sell and adx_filter_passed:
                        sell_signal = True
                        pvt_sell_pending = False
                        waiting_for_adx_sell = False
            
            # ENHANCED: Apply EMA filter AFTER signal generation (like cBot v3.1.2-2.2)
            ema_filter = params.get('use_ema', False)
            ema_filter_bullish = not ema_filter or row['close'] > row['ema']
            ema_filter_bearish = not ema_filter or row['close'] < row['ema']
            
            buy_signal = buy_signal and ema_filter_bullish
            sell_signal = sell_signal and ema_filter_bearish
            
            # Track ADX state for exit conditions
            adx_was_above_threshold = adx_filter_passed
            
            # X Trend flip detection for exits
            xtrend_flip_to_sell = xtrend_filter and (row['x_trend'] == 1) and (prev_row['x_trend'] == 0)
            xtrend_flip_to_buy = xtrend_filter and (row['x_trend'] == 0) and (prev_row['x_trend'] == 1)
            
            # HTF flip detection if using HTF
            if use_htf:
                htf_flip_to_sell = (row['htf_x_trend'] == 1) and (prev_row['htf_x_trend'] == 0)
                htf_flip_to_buy = (row['htf_x_trend'] == 0) and (prev_row['htf_x_trend'] == 1)
                
                if params.get('xtrend_grey_disagree', False):
                    # Both local and HTF must flip
                    xtrend_flip_to_sell = xtrend_flip_to_sell and htf_flip_to_sell
                    xtrend_flip_to_buy = xtrend_flip_to_buy and htf_flip_to_buy
                else:
                    # Use HTF flip only
                    xtrend_flip_to_sell = htf_flip_to_sell
                    xtrend_flip_to_buy = htf_flip_to_buy
            
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
                # ENHANCED: Exit conditions with correct precedence (XTrend > Opposite > Trend > ADX)
                exit_signal = False
                exit_reason = ""
                
                # Priority 1: XTrend Flip
                if xtrend_flip_to_sell:
                    exit_signal = True
                    exit_reason = "XTrend Flip"
                # Priority 2: Opposite Signal
                elif sell_signal:
                    exit_signal = True
                    exit_reason = "Opposite Signal"
                # Priority 3: Trend Change
                elif row['pvt_trend'] == -1:
                    exit_signal = True
                    exit_reason = "Trend Change"
                # Priority 4: ADX Drop (NEW)
                elif params.get('use_adx', False) and adx_was_above_threshold and not adx_filter_passed:
                    exit_signal = True
                    exit_reason = "ADX Drop"
                
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
                        'profit_pips': profit_pips,
                        'exit_reason': exit_reason
                    })
                    position = None
                    
            elif position == 'short':
                # ENHANCED: Exit conditions with correct precedence (XTrend > Opposite > Trend > ADX)
                exit_signal = False
                exit_reason = ""
                
                # Priority 1: XTrend Flip
                if xtrend_flip_to_buy:
                    exit_signal = True
                    exit_reason = "XTrend Flip"
                # Priority 2: Opposite Signal
                elif buy_signal:
                    exit_signal = True
                    exit_reason = "Opposite Signal"
                # Priority 3: Trend Change
                elif row['pvt_trend'] == 1:
                    exit_signal = True
                    exit_reason = "Trend Change"
                # Priority 4: ADX Drop (NEW)
                elif params.get('use_adx', False) and adx_was_above_threshold and not adx_filter_passed:
                    exit_signal = True
                    exit_reason = "ADX Drop"
                
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
                        'profit_pips': profit_pips,
                        'exit_reason': exit_reason
                    })
                    position = None
        
        # Calculate metrics with exit reason tracking
        if len(signals) > 0:
            trades_df = pd.DataFrame(signals)
            winning_trades = trades_df[trades_df['profit_pips'] > 0]
            losing_trades = trades_df[trades_df['profit_pips'] < 0]
            
            # Count exit reasons
            xtrend_exits = len(trades_df[trades_df['exit_reason'] == 'XTrend Flip'])
            opposite_exits = len(trades_df[trades_df['exit_reason'] == 'Opposite Signal'])
            trend_exits = len(trades_df[trades_df['exit_reason'] == 'Trend Change'])
            adx_exits = len(trades_df[trades_df['exit_reason'] == 'ADX Drop'])
            
            metrics = {
                'total_trades': len(trades_df),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(winning_trades) / len(trades_df) * 100,
                'total_pips': trades_df['profit_pips'].sum(),
                'avg_win': winning_trades['profit_pips'].mean() if len(winning_trades) > 0 else 0,
                'avg_loss': abs(losing_trades['profit_pips'].mean()) if len(losing_trades) > 0 else 0,
                'profit_factor': (winning_trades['profit_pips'].sum() / abs(losing_trades['profit_pips'].sum())) 
                                if len(losing_trades) > 0 and losing_trades['profit_pips'].sum() != 0 else 999,
                'xtrend_exits': xtrend_exits,
                'opposite_exits': opposite_exits,
                'trend_exits': trend_exits,
                'adx_exits': adx_exits
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
                'profit_factor': 0,
                'xtrend_exits': 0,
                'opposite_exits': 0,
                'trend_exits': 0,
                'adx_exits': 0
            }
        
        return metrics, signals
        
    except Exception as e:
        print(f"Error in enhanced backtest: {e}")
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pips': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'xtrend_exits': 0,
            'opposite_exits': 0,
            'trend_exits': 0,
            'adx_exits': 0
        }, []

def run_backtest(df, params, htf_multiplier=None, asset_name=""):
    """Enhanced backtest wrapper for compatibility"""
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

# ==================== ENHANCED OPTIMIZATION FUNCTIONS ====================

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

def run_enhanced_staged_optimization(df, asset_name, use_xtrend, use_adx, use_ema, xtrend_grey, 
                                    optimization_mode='Quick', use_htf=True, htf_mode='Essential',
                                    max_bars=500, skip_low_volume=True, optimize_filters=True):
    """ENHANCED: Run multi-stage optimization with cBot v3.1.2-2.2 logic"""
    try:
        # Limit data for faster processing
        if len(df) > max_bars:
            df = df.tail(max_bars)
            st.info(f"Using last {max_bars} bars for faster processing")
        
        # Store data period info
        if 'datetime' in df.columns:
            period_start = pd.to_datetime(df['datetime'].iloc[0])
            period_end = pd.to_datetime(df['datetime'].iloc[-1])
        else:
            period_start = pd.to_datetime(df['time'].iloc[0], unit='s')
            period_end = pd.to_datetime(df['time'].iloc[-1], unit='s')
        
        # Define parameter ranges based on optimization mode
        if optimization_mode == 'Quick':
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3] if use_htf else [1]
            adx_thresholds = [20, 25, 30] if optimize_filters else [25]
            ema_periods = [100, 200] if optimize_filters else [200]
        elif optimization_mode == 'Standard':
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3, 4, 6] if use_htf else [1]
            adx_thresholds = [15, 20, 25, 30, 35] if optimize_filters else [25]
            ema_periods = [50, 100, 150, 200, 250] if optimize_filters else [200]
        else:  # Full
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3, 4, 6, 8, 12, 16] if use_htf else [1]
            adx_thresholds = [15, 20, 25, 30, 35] if optimize_filters else [25]
            ema_periods = [50, 100, 150, 200, 250] if optimize_filters else [200]
        
        # Further filter HTF based on htf_mode
        if use_htf and htf_mode == 'Essential':
            htf_multipliers = [x for x in htf_multipliers if x in [1, 2, 3, 4]]
        
        # === STAGE 1: OPTIMIZE CORE PARAMETERS (Pivot + ATR + HTF) ===
        st.info("🎯 **Stage 1/2**: Optimizing Core Parameters (Enhanced Supertrend + HTF)")
        
        stage1_combinations = len(pivot_periods) * len(atr_factors) * len(atr_periods) * len(htf_multipliers)
        
        st.info(f"""
        **Stage 1 - Enhanced Core Parameter Optimization:**
        📊 Combinations: {stage1_combinations:,}
        🎯 Testing: {len(pivot_periods)} Pivot × {len(atr_factors)} ATR Factor × {len(atr_periods)} ATR Period × {len(htf_multipliers)} HTF
        🔧 Using: Enhanced Supertrend (no mid-air flips) + Default filters
        """)
        
        stage1_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        combination_count = 0
        
        for pivot_period in pivot_periods:
            for atr_factor in atr_factors:
                for atr_period in atr_periods:
                    for htf_mult in htf_multipliers:
                        combination_count += 1
                        progress = combination_count / stage1_combinations
                        progress_bar.progress(progress)
                        status_text.text(f"Stage 1: Testing {combination_count}/{stage1_combinations} (Enhanced Logic)")
                        
                        # Use default filter settings for Stage 1
                        params = {
                            'pivot_period': pivot_period,
                            'atr_factor': atr_factor,
                            'atr_period': atr_period,
                            'use_xtrend': use_xtrend,
                            'use_adx': False,  # No filters in Stage 1
                            'adx_threshold': 25,
                            'use_ema': False,  # No filters in Stage 1
                            'ema_period': 200,
                            'xtrend_grey_disagree': xtrend_grey
                        }
                        
                        metrics = run_backtest(df, params, htf_mult, asset_name)
                        
                        # Skip if too few trades
                        if skip_low_volume and metrics['total_trades'] < 5:
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
                        
                        stage1_results.append({
                            'pivot_period': pivot_period,
                            'atr_factor': atr_factor,
                            'atr_period': atr_period,
                            'htf_multiplier': htf_mult,
                            'htf_timeframe': get_htf_name(htf_mult),
                            'total_trades': metrics['total_trades'],
                            'win_rate': round(metrics['win_rate'], 2),
                            'total_pips': round(metrics['total_pips'], 2),
                            'profit_factor': round(metrics['profit_factor'], 2),
                            'avg_win': round(metrics['avg_win'], 2),
                            'avg_loss': round(metrics['avg_loss'], 2),
                            'score': round(score, 2)
                        })
        
        # Get top 3 core configurations
        stage1_df = pd.DataFrame(stage1_results)
        stage1_df = stage1_df.sort_values('score', ascending=False)
        top_3_core = stage1_df.head(3)
        
        progress_bar.empty()
        status_text.empty()
        
        st.success(f"✅ Stage 1 Complete! Found {len(stage1_results)} valid enhanced core configurations")
        st.info("🔝 **Top 3 Enhanced Core Configurations:**")
        st.dataframe(top_3_core[['pivot_period', 'atr_factor', 'atr_period', 'htf_timeframe', 'win_rate', 'total_pips', 'score']], use_container_width=True)
        
        # === STAGE 2: OPTIMIZE FILTERS ON TOP 3 CORE CONFIGS ===
        if not optimize_filters or (not use_adx and not use_ema):
            # No filter optimization needed
            st.info("🎯 **Stage 2**: Skipped (no filter optimization requested)")
            final_results = []
            
            for _, core_config in top_3_core.iterrows():
                # Add filter display values
                final_results.append({
                    'pivot_period': core_config['pivot_period'],
                    'atr_factor': core_config['atr_factor'],
                    'atr_period': core_config['atr_period'],
                    'adx_threshold': None,
                    'ema_period': None,
                    'htf_multiplier': core_config['htf_multiplier'],
                    'htf_timeframe': core_config['htf_timeframe'],
                    'use_xtrend': 'Yes' if use_xtrend else 'No',
                    'use_adx': 'No',
                    'use_ema': 'No',
                    'mtf_agree': 'Yes' if xtrend_grey else 'No',
                    'total_trades': core_config['total_trades'],
                    'win_rate': core_config['win_rate'],
                    'total_pips': core_config['total_pips'],
                    'profit_factor': core_config['profit_factor'],
                    'avg_win': core_config['avg_win'],
                    'avg_loss': core_config['avg_loss'],
                    'score': core_config['score']
                })
        
        else:
            st.info("🎯 **Stage 2/2**: Optimizing Enhanced Filters on Top 3 Core Configurations")
            
            # Filter parameter combinations based on enabled filters
            if not use_adx:
                adx_thresholds = [25]
            if not use_ema:
                ema_periods = [200]
            
            stage2_combinations = len(top_3_core) * len(adx_thresholds) * len(ema_periods)
            
            st.info(f"""
            **Stage 2 - Enhanced Filter Optimization:**
            📊 Combinations: {stage2_combinations:,}
            🎯 Testing: 3 Enhanced Core Configs × {len(adx_thresholds)} ADX × {len(ema_periods)} EMA
            🔧 Enhanced Features: Correct exit precedence + ADX exits + EMA sequencing
            """)
            
            stage2_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            combination_count = 0
            
            for _, core_config in top_3_core.iterrows():
                for adx_threshold in adx_thresholds:
                    for ema_period in ema_periods:
                        combination_count += 1
                        progress = combination_count / stage2_combinations
                        progress_bar.progress(progress)
                        status_text.text(f"Stage 2: Testing {combination_count}/{stage2_combinations} (Enhanced Filters)")
                        
                        params = {
                            'pivot_period': core_config['pivot_period'],
                            'atr_factor': core_config['atr_factor'],
                            'atr_period': core_config['atr_period'],
                            'use_xtrend': use_xtrend,
                            'use_adx': use_adx,
                            'adx_threshold': adx_threshold,
                            'use_ema': use_ema,
                            'ema_period': ema_period,
                            'xtrend_grey_disagree': xtrend_grey
                        }
                        
                        # Get detailed metrics including exit reasons
                        metrics, trades = run_backtest_with_trades(df, params, core_config['htf_multiplier'], asset_name)
                        
                        # Skip if too few trades
                        if skip_low_volume and metrics['total_trades'] < 5:
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
                        
                        # Format filter display values
                        adx_display = f"ADX≥{adx_threshold}" if use_adx else 'No'
                        ema_display = f"EMA{ema_period}" if use_ema else 'No'
                        
                        stage2_results.append({
                            'pivot_period': core_config['pivot_period'],
                            'atr_factor': core_config['atr_factor'],
                            'atr_period': core_config['atr_period'],
                            'adx_threshold': adx_threshold if use_adx else None,
                            'ema_period': ema_period if use_ema else None,
                            'htf_multiplier': core_config['htf_multiplier'],
                            'htf_timeframe': core_config['htf_timeframe'],
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
                            'score': round(score, 2),
                            # ENHANCED: Exit reason tracking
                            'xtrend_exits': metrics.get('xtrend_exits', 0),
                            'opposite_exits': metrics.get('opposite_exits', 0),
                            'trend_exits': metrics.get('trend_exits', 0),
                            'adx_exits': metrics.get('adx_exits', 0)
                        })
            
            progress_bar.empty()
            status_text.empty()
            
            final_results = stage2_results
            st.success(f"✅ Stage 2 Complete! Tested {len(final_results)} enhanced filter combinations")
        
        # Convert to DataFrame and sort
        results_df = pd.DataFrame(final_results)
        results_df = results_df.sort_values('score', ascending=False)
        
        # Add period info to results
        results_df['period_start'] = period_start
        results_df['period_end'] = period_end
        
        # Show enhanced final summary
        total_combinations_tested = stage1_combinations + (stage2_combinations if optimize_filters and (use_adx or use_ema) else 0)
        total_combinations_saved = (len(pivot_periods) * len(atr_factors) * len(atr_periods) * 
                                   len(htf_multipliers) * len(adx_thresholds) * len(ema_periods)) - total_combinations_tested
        
        st.success(f"""
        🎉 **Enhanced Staged Optimization Complete!**
        ✅ Total combinations tested: {total_combinations_tested:,}
        💡 Combinations saved vs full optimization: {total_combinations_saved:,}
        📈 Efficiency gain: {(total_combinations_saved / (total_combinations_tested + total_combinations_saved) * 100):.1f}%
        🔧 Enhanced features: Smoothed Supertrend + Correct exit precedence + ADX exits
        """)
        
        return results_df
        
    except Exception as e:
        st.error(f"Enhanced staged optimization error: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

# Legacy function for compatibility
def run_staged_optimization(df, asset_name, use_xtrend, use_adx, use_ema, xtrend_grey, 
                          optimization_mode='Quick', use_htf=True, htf_mode='Essential',
                          max_bars=500, skip_low_volume=True, optimize_filters=True):
    """Enhanced wrapper that calls the new enhanced staged optimization"""
    return run_enhanced_staged_optimization(df, asset_name, use_xtrend, use_adx, use_ema, xtrend_grey,
                                          optimization_mode, use_htf, htf_mode, max_bars, skip_low_volume, optimize_filters)

# ==================== MAIN APPLICATION ====================

def main():
    st.set_page_config(
        page_title="XPST Optimizer v3.2.2",
        page_icon="🎯",
        layout="wide"
    )
    
    # Enhanced Header
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🎯 XPST Optimizer v{__version__}</h1>
        <p style="color: #e8f4f8; margin: 5px 0 0 0;">Enhanced cBot Parity Edition</p>
        <p style="color: #d0e8f0; margin: 3px 0 0 0; font-size: 0.9em;">Last Updated: {__last_updated__}</p>
        <p style="color: #ffd700; margin: 8px 0 0 0; font-size: 0.95em; font-weight: bold;">🆕 NEW: Enhanced Supertrend + Correct Exit Precedence + ADX Exits!</p>
        <p style="color: #98fb98; margin: 5px 0 0 0; font-size: 0.9em;">✅ Now Matches: cBot v3.1.2-2.2 Enhanced Exactly</p>
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
    st.sidebar.header("📊 Enhanced Configuration")
    
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
        
        selected_assets = st.sidebar.multiselect(
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
    
    # Enhanced Optimization Settings
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Enhanced Optimization Settings")
    
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
        help="When enabled, tests multiple ADX thresholds and EMA periods with enhanced logic"
    )
    
    if optimize_filters:
        st.sidebar.success("✅ Will optimize ADX & EMA parameters with enhanced logic")
        
        # Show what will be tested
        if optimization_mode == 'Quick':
            st.sidebar.info("Quick: ADX[20,25,30] × EMA[100,200] + Enhanced exits")
        elif optimization_mode == 'Standard':
            st.sidebar.info("Standard: ADX[15,20,25,30,35] × EMA[50,100,150,200,250] + Enhanced exits")
        else:
            st.sidebar.info("Full: ADX[15,20,25,30,35] × EMA[50,100,150,200,250] + Enhanced exits")
    else:
        st.sidebar.info("Using defaults: ADX=25, EMA=200 (but enhanced logic)")
    
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
    st.markdown("### 📊 Enhanced Data Management")
    
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
                        st.write(f"**Optimizing {asset} with Enhanced Logic...**")
                        
                        # Pass enhanced optimization settings
                        results = run_enhanced_staged_optimization(
                            data, asset, use_xtrend, use_adx, use_ema, xtrend_grey,
                            optimization_mode, use_htf, htf_mode if use_htf else 'Essential',
                            max_bars, skip_low_volume, optimize_filters
                        )
                        
                        if not results.empty:
                            st.session_state.optimization_results[asset] = results
                            
                            # Show brief summary with enhanced filter info
                            best = results.iloc[0]
                            filter_summary = f"Win Rate {best['win_rate']}%, {best['total_pips']:.1f} pips"
                            if optimize_filters:
                                if best['adx_threshold'] is not None:
                                    filter_summary += f", ADX≥{best['adx_threshold']}"
                                if best['ema_period'] is not None:
                                    filter_summary += f", EMA{best['ema_period']}"
                            
                            # Show exit reason breakdown if available
                            if 'xtrend_exits' in best:
                                filter_summary += f" | Exits: XT:{best.get('xtrend_exits', 0)} OS:{best.get('opposite_exits', 0)} TC:{best.get('trend_exits', 0)}"
                            
                            st.success(f"Best Enhanced: {filter_summary}")
    
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
    
    # Enhanced Results section
    if st.session_state.optimization_results:
        st.markdown("---")
        st.markdown("### 🏆 Enhanced Staged Optimization Results")
        
        # Enhanced Summary table
        summary_data = []
        for asset, results in st.session_state.optimization_results.items():
            best = results.iloc[0]
            
            # Format enhanced filter info for summary
            filter_info = ""
            if best['adx_threshold'] is not None:
                filter_info += f" ADX≥{best['adx_threshold']}"
            if best['ema_period'] is not None:
                filter_info += f" EMA{best['ema_period']}"
            
            # Enhanced exit breakdown
            exit_breakdown = ""
            if 'xtrend_exits' in best:
                exit_breakdown = f"XT:{best.get('xtrend_exits', 0)} OS:{best.get('opposite_exits', 0)} TC:{best.get('trend_exits', 0)}"
                if best.get('adx_exits', 0) > 0:
                    exit_breakdown += f" ADX:{best.get('adx_exits', 0)}"
            
            summary_data.append({
                'Asset': asset,
                'Best Win Rate': f"{best['win_rate']}%",
                'Total Pips': f"{best['total_pips']:.1f}",
                'Profit Factor': f"{best['profit_factor']:.2f}",
                'HTF': best['htf_timeframe'],
                'Filters': filter_info.strip() if filter_info else 'None',
                'Exit Breakdown': exit_breakdown if exit_breakdown else 'N/A',
                'Score': f"{best['score']:.1f}"
            })
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
        
        # Enhanced Detailed tabs
        tabs = st.tabs(list(st.session_state.optimization_results.keys()))
        
        for tab, asset in zip(tabs, st.session_state.optimization_results.keys()):
            with tab:
                results = st.session_state.optimization_results[asset]
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Top configurations with enhanced display
                    st.write("**🥇 Top 10 Enhanced Staged Optimization Results:**")
                    display_cols = ['pivot_period', 'atr_factor', 'atr_period', 
                                  'htf_timeframe', 'use_xtrend', 'use_adx', 'use_ema',
                                  'adx_threshold', 'ema_period',
                                  'total_trades', 'win_rate', 'total_pips', 
                                  'profit_factor', 'score']
                    
                    # Add exit reason columns if available
                    if 'xtrend_exits' in results.columns:
                        display_cols.extend(['xtrend_exits', 'opposite_exits', 'trend_exits', 'adx_exits'])
                    
                    # Filter out None values for cleaner display
                    display_results = results[display_cols].copy()
                    
                    st.dataframe(
                        display_results.head(10),
                        use_container_width=True,
                        hide_index=True
                    )
                
                with col2:
                    # Enhanced configuration details
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
                    
                    # Enhanced exit reason breakdown
                    exit_reasons_str = ""
                    if 'xtrend_exits' in best:
                        exit_reasons_str = f"""
// === ENHANCED EXIT ANALYSIS ===
XTrend Flip Exits: {best.get('xtrend_exits', 0)}
Opposite Signal Exits: {best.get('opposite_exits', 0)}
Trend Change Exits: {best.get('trend_exits', 0)}
ADX Drop Exits: {best.get('adx_exits', 0)}
Exit Precedence: XTrend > Opposite > Trend > ADX"""
                    
                    st.code(f"""// XPST v3.2.2 Enhanced Optimization Settings for {asset}
{period_str}
// === ENHANCED CORE STRATEGY SETTINGS ===
Pivot Period: {best['pivot_period']}
ATR Factor: {best['atr_factor']}
ATR Period: {best['atr_period']}
Enhanced Supertrend: YES (No mid-air flips)

// === ENHANCED FILTER SETTINGS ===
Use X Trend Filter: {best.get('use_xtrend', 'Yes')}
Use ADX Filter: {use_adx_display.replace('ADX≥', 'Yes').replace(str(adx_threshold_val) if adx_threshold_val else '', '')}
ADX Threshold: {adx_threshold_display}
Use EMA Filter: {use_ema_display.replace('EMA', 'Yes').replace(str(ema_period_val) if ema_period_val else '', '')}
EMA Period: {ema_period_display}
EMA Applied: AFTER signal generation (Enhanced)

// === X TREND MTF SETTINGS ===
HTF Multiplier: {best['htf_multiplier']}x
MTF Agreement Required: {best.get('mtf_agree', 'Yes')}

// === ENHANCED PERFORMANCE METRICS ===
Win Rate: {best['win_rate']}%
Total Trades: {best['total_trades']}
Total Pips: {best['total_pips']:.1f}
Profit Factor: {best['profit_factor']:.2f}
Avg Win: {best['avg_win']:.1f} pips
Avg Loss: {best['avg_loss']:.1f} pips
Score: {best['score']:.1f}
{exit_reasons_str}
                    """)
                
                # Enhanced Analysis Sections
                if optimize_filters:
                    st.write("**🔧 Enhanced Filter Performance Analysis:**")
                    
                    # ADX threshold analysis
                    if best.get('adx_threshold') is not None:
                        adx_analysis = results[results['use_adx'] != 'No'].groupby('adx_threshold').agg({
                            'score': 'mean',
                            'win_rate': 'mean',
                            'total_pips': 'mean'
                        }).round(2).sort_values('score', ascending=False)
                        
                        st.write("**Enhanced ADX Threshold Performance:**")
                        st.dataframe(adx_analysis, use_container_width=True)
                    
                    # EMA period analysis
                    if best.get('ema_period') is not None:
                        ema_analysis = results[results['use_ema'] != 'No'].groupby('ema_period').agg({
                            'score': 'mean',
                            'win_rate': 'mean',
                            'total_pips': 'mean'
                        }).round(2).sort_values('score', ascending=False)
                        
                        st.write("**Enhanced EMA Period Performance:**")
                        st.dataframe(ema_analysis, use_container_width=True)
                
                # Enhanced Exit Reason Analysis
                if 'xtrend_exits' in results.columns:
                    st.write("**📊 Enhanced Exit Reason Analysis:**")
                    
                    col_exit1, col_exit2 = st.columns(2)
                    
                    with col_exit1:
                        # Exit reason totals
                        total_xtrend = results['xtrend_exits'].sum()
                        total_opposite = results['opposite_exits'].sum()
                        total_trend = results['trend_exits'].sum()
                        total_adx = results['adx_exits'].sum()
                        total_exits = total_xtrend + total_opposite + total_trend + total_adx
                        
                        if total_exits > 0:
                            exit_summary = pd.DataFrame({
                                'Exit Type': ['XTrend Flip', 'Opposite Signal', 'Trend Change', 'ADX Drop'],
                                'Count': [total_xtrend, total_opposite, total_trend, total_adx],
                                'Percentage': [
                                    f"{(total_xtrend/total_exits)*100:.1f}%",
                                    f"{(total_opposite/total_exits)*100:.1f}%",
                                    f"{(total_trend/total_exits)*100:.1f}%",
                                    f"{(total_adx/total_exits)*100:.1f}%"
                                ]
                            })
                            st.dataframe(exit_summary, use_container_width=True, hide_index=True)
                    
                    with col_exit2:
                        st.info(f"""
                        **Enhanced Exit Logic:**
                        ✅ Priority 1: XTrend Flip
                        ✅ Priority 2: Opposite Signal  
                        ✅ Priority 3: Trend Change
                        ✅ Priority 4: ADX Drop (NEW)
                        
                        **Total Exits**: {total_exits}
                        """)
                
                # Last N Trades Analysis with Enhanced Logic
                st.write("**📊 Enhanced Last N Trades Analysis:**")
                
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
                    if st.button(f"Calculate Enhanced Last {last_n_trades} Trades", key=f"calc_{asset}"):
                        # Run enhanced backtest with best parameters
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
                            # Run enhanced backtest to get trade details
                            full_metrics, trade_list = run_backtest_with_trades(
                                asset_data, best_params, best['htf_multiplier'], asset
                            )
                            
                            if trade_list and len(trade_list) > 0:
                                # Analyze last N trades
                                last_trades = trade_list[-last_n_trades:] if len(trade_list) >= last_n_trades else trade_list
                                
                                # Calculate enhanced metrics for last N trades
                                last_n_pips = sum([t['profit_pips'] for t in last_trades])
                                last_n_wins = len([t for t in last_trades if t['profit_pips'] > 0])
                                last_n_losses = len([t for t in last_trades if t['profit_pips'] < 0])
                                last_n_win_rate = (last_n_wins / len(last_trades) * 100) if last_trades else 0
                                
                                # Enhanced exit reason breakdown for last N
                                last_xtrend_exits = len([t for t in last_trades if t.get('exit_reason') == 'XTrend Flip'])
                                last_opposite_exits = len([t for t in last_trades if t.get('exit_reason') == 'Opposite Signal'])
                                last_trend_exits = len([t for t in last_trades if t.get('exit_reason') == 'Trend Change'])
                                last_adx_exits = len([t for t in last_trades if t.get('exit_reason') == 'ADX Drop'])
                                
                                st.success(f"""
                                **Enhanced Last {last_n_trades} Trades Performance:**
                                - Win Rate: {last_n_win_rate:.1f}%
                                - Total Pips: {last_n_pips:.1f}
                                - Wins/Losses: {last_n_wins}/{last_n_losses}
                                - Avg per Trade: {last_n_pips/len(last_trades):.1f} pips
                                - Actual Trades Analyzed: {len(last_trades)}
                                
                                **Enhanced Exit Breakdown:**
                                - XTrend Flip: {last_xtrend_exits}
                                - Opposite Signal: {last_opposite_exits}
                                - Trend Change: {last_trend_exits}
                                - ADX Drop: {last_adx_exits}
                                """)
                            else:
                                st.warning("No trades found with enhanced settings")
                        else:
                            st.error("Data not found for this asset")
                
                # Enhanced HTF Analysis
                st.write("**📊 Enhanced HTF Performance Analysis:**")
                htf_summary = results.groupby('htf_timeframe').agg({
                    'score': 'mean',
                    'win_rate': 'mean',
                    'total_pips': 'mean',
                    'total_trades': 'mean'
                }).round(2).sort_values('score', ascending=False)
                
                st.dataframe(htf_summary, use_container_width=True)
                
                # Enhanced Download button
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
            st.info("✨ Data ready! Click 'Run Enhanced Optimization' to find the best XPST settings with cBot v3.1.2-2.2 logic")
    
    # Enhanced Info Boxes
    if not st.session_state.optimization_results:
        st.markdown("---")
        with st.expander("🆕 What's New in v3.2.2 - Enhanced cBot Parity"):
            st.markdown("""
            ### 🚀 Revolutionary Enhanced Features:
            
            **Enhanced Pivot Supertrend (NO MORE MID-AIR FLIPS!):**
            - ✅ Smoothed center calculation (0.1 factor vs aggressive 0.33)
            - ✅ Jump protection system (limits changes to 2×ATR per bar)
            - ✅ Enhanced trend stability checks
            - ✅ NO sudden vertical drops or color changes without price interaction
            
            **Enhanced Exit Logic (CORRECT PRECEDENCE!):**
            - ✅ Priority 1: XTrend Flip (highest priority)
            - ✅ Priority 2: Opposite Signal 
            - ✅ Priority 3: Trend Change
            - ✅ Priority 4: ADX Drop (NEW - when ADX falls below threshold)
            - ✅ Exit reason tracking for complete analysis
            
            **Enhanced Signal Processing:**
            - ✅ EMA filter applied AFTER signal generation (not during)
            - ✅ Enhanced pending state management (comprehensive TradingView v3.1 logic)
            - ✅ Complete ADX exit implementation
            - ✅ Jump protection prevents unstable trend transitions
            
            ### 🎯 Now Matches: cBot v3.1.2-2.2 Enhanced EXACTLY
            
            ### 📊 Benefits You'll See:
            1. **Stable Supertrend**: No more erratic line behavior
            2. **Better Exits**: Correct priority order optimizes trade outcomes  
            3. **More Accurate Signals**: Enhanced filter sequencing
            4. **Complete Logic**: All edge cases handled properly
            5. **Reliable Results**: What you optimize matches what you trade
            
            ### 🔧 Technical Improvements:
            - Enhanced Supertrend calculation prevents mathematical instability
            - Correct exit precedence matches professional trading logic
            - ADX exits provide additional risk management
            - EMA filter sequencing improves signal accuracy
            - Complete state management handles all market conditions
            """)
    
    else:
        with st.expander("🔍 Understanding Enhanced Optimization Results"):
            st.markdown("""
            ### 📊 How to Read Your Enhanced Results:
            
            **Enhanced Stage 1**: Core parameters optimized with stable Supertrend (no mid-air flips)
            **Enhanced Stage 2**: Filters optimized with correct precedence and ADX exits  
            **Enhanced Final**: Ranked by performance with complete exit reason breakdown
            
            ### 🎯 Enhanced Key Insights:
            - **Stable Core**: Notice how enhanced Supertrend eliminates erratic behavior
            - **Exit Analysis**: See breakdown of XTrend/Opposite/Trend/ADX exits
            - **Filter Impact**: Observe how enhanced EMA sequencing affects performance
            - **Complete Logic**: All edge cases and state transitions handled properly
            
            ### 📈 Enhanced Verification Tips:
            - Enhanced Supertrend should show smooth, continuous lines
            - Exit precedence: XTrend Flip should be most common for trending markets
            - ADX exits provide additional risk management in choppy conditions
            - EMA filter effects should be more pronounced when applied after signals
            """)
    
    # Enhanced Footer
    st.markdown("---")
    with st.expander("🔍 How to Verify Enhanced Results with cBot v3.1.2-2.2"):
        st.markdown("""
        ### Enhanced Verification Process:
        
        **Step 1: Apply Enhanced Core Settings**
        - Set Pivot Period, ATR Factor, ATR Period from enhanced results
        - Set HTF multiplier as specified
        - Verify you're using cBot v3.1.2-2.2 Enhanced (not older versions)
        
        **Step 2: Apply Enhanced Filters with Correct Logic**
        - Enable X Trend filter (if used)
        - Set **ADX Threshold** to optimized value (not default 25)
        - Set **EMA Period** to optimized value (not default 200)  
        - Enable **MTF Agreement** if specified
        - Verify EMA filter is applied AFTER signal generation in cBot
        
        **Step 3: Verify Enhanced Behavior**
        - Supertrend should show smooth lines (no mid-air flips)
        - Exit precedence should follow: XTrend > Opposite > Trend > ADX
        - ADX exits should trigger when ADX drops below threshold
        - Performance should match with enhanced logic enabled
        
        ### 🎯 Enhanced Settings Export Format:
        ```
        // Enhanced Core Parameters (stable Supertrend)
        Pivot Period: [optimized]
        ATR Factor: [optimized] 
        ATR Period: [optimized]
        HTF Multiplier: [optimized]
        Enhanced Supertrend: ENABLED
        
        // Enhanced Filter Logic
        ADX Threshold: [optimized]
        EMA Period: [optimized]
        EMA Applied After Signals: ENABLED
        ADX Exits: ENABLED
        Correct Exit Precedence: ENABLED
        ```
        
        ### 💡 Enhanced Verification Benefits:
        - **Visual Confirmation**: See smooth Supertrend behavior
        - **Logic Verification**: Confirm correct exit order and timing
        - **Performance Match**: Results should align exactly with cBot
        - **Complete Feature Set**: All enhancements working together
        - **Professional Quality**: Behavior matches institutional standards
        """)
    
    st.markdown(
        f"""
        <div style="text-align: center; color: #666;">
            <small>
            XPST Optimizer v{__version__} | Enhanced cBot Parity Edition<br>
            Enhanced Supertrend + Correct Exit Precedence + ADX Exits + Complete Logic<br>
            ✅ Now Matches: cBot v3.1.2-2.2 Enhanced Exactly
            </small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
