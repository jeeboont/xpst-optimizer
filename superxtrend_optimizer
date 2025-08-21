"""
XPST Optimizer - Unified Version with cTrader v3.3.0 Logic
Version: 3.3.0
Last Updated: 2025-08-21
Author: XPST Trading Systems

UNIFIED v3.3.0 MAJOR UPDATE:
- FIXED: X-Trend now properly flips between bullish/bearish (removed nextTrend logic)
- FIXED: MTF X-Trend calculation with proper time alignment
- FIXED: Non-repainting Pivot Supertrend calculation with historical value storage
- NEW: Re-entry logic after X-Trend flip exits
- NEW: Historical center/TUp/TDown tracking to prevent repainting
- IMPROVED: MTF bar synchronization
- ENHANCED: Exit precedence with re-entry management
- All components now match cTrader v3.3.0 EXACTLY
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import io
import zipfile
from typing import Dict, List, Tuple, Optional
warnings.filterwarnings('ignore')

# Version display in UI
__version__ = "3.3.0"
__last_updated__ = "2025-08-21"

# Initialize session state
if 'downloaded_data' not in st.session_state:
    st.session_state.downloaded_data = {}
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = {}
if 'custom_assets' not in st.session_state:
    st.session_state.custom_assets = {}

# ==================== v3.3.0 ENHANCED INDICATOR CALCULATION FUNCTIONS ====================

class HistoricalValueTracker:
    """Track historical values to prevent repainting (v3.3.0 feature)"""
    def __init__(self):
        self.center_history = {}
        self.tup_history = {}
        self.tdown_history = {}
        
    def get_center(self, index: int) -> Optional[float]:
        """Get center value for specific bar"""
        if index in self.center_history:
            return self.center_history[index]
        elif self.center_history:
            # Use most recent center value
            keys = [k for k in self.center_history.keys() if k <= index]
            if keys:
                last_index = max(keys)
                return self.center_history[last_index]
        return None
    
    def update_center(self, index: int, last_pivot: float):
        """Update center value ONLY for current bar (non-repainting)"""
        if index not in self.center_history:
            prev_center = self.get_center(index - 1)
            if prev_center is None:
                self.center_history[index] = last_pivot
            else:
                # TradingView formula: (center * 2 + lastpp) / 3
                self.center_history[index] = (prev_center * 2 + last_pivot) / 3

def calculate_pivot_points(df, period=5):
    """Calculate pivot highs and lows - v3.3.0 enhanced"""
    try:
        if len(df) < period * 2 + 1:
            return pd.Series(index=df.index, dtype=float), pd.Series(index=df.index, dtype=float)
        
        pivot_highs = pd.Series(index=df.index, dtype=float)
        pivot_lows = pd.Series(index=df.index, dtype=float)
        
        # Calculate pivots with look-ahead and look-back
        for i in range(period, len(df) - period):
            # Check for pivot high
            is_pivot_high = True
            high_val = df['high'].iloc[i]
            
            # Check both sides
            for j in range(i - period, i + period + 1):
                if j != i and j < len(df):
                    if df['high'].iloc[j] >= high_val:
                        is_pivot_high = False
                        break
            
            if is_pivot_high:
                # Store pivot at detection bar (i + period) to match cTrader timing
                if i + period < len(df):
                    pivot_highs.iloc[i + period] = high_val
            
            # Check for pivot low
            is_pivot_low = True
            low_val = df['low'].iloc[i]
            
            for j in range(i - period, i + period + 1):
                if j != i and j < len(df):
                    if df['low'].iloc[j] <= low_val:
                        is_pivot_low = False
                        break
            
            if is_pivot_low:
                # Store pivot at detection bar (i + period) to match cTrader timing
                if i + period < len(df):
                    pivot_lows.iloc[i + period] = low_val
        
        return pivot_highs, pivot_lows
        
    except Exception as e:
        print(f"Pivot calculation error: {e}")
        return pd.Series(index=df.index, dtype=float), pd.Series(index=df.index, dtype=float)

def calculate_pivot_supertrend_v33(df, pivot_period=5, atr_factor=1.25, atr_period=15):
    """v3.3.0: Non-repainting Pivot Supertrend with historical value storage"""
    try:
        df = df.copy()
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Check for sufficient data
        if len(df) < max(pivot_period * 2 + 1, atr_period):
            print(f"Insufficient data: {len(df)} rows")
            df['pvt_trend'] = 1
            df['pvt_signal'] = 0
            return df
        
        # Initialize historical value tracker
        tracker = HistoricalValueTracker()
        
        # Calculate pivot points with v3.3.0 timing
        pivot_highs, pivot_lows = calculate_pivot_points(df, pivot_period)
        
        # Update center values at pivot detection bars (non-repainting)
        for i in range(len(df)):
            if not pd.isna(pivot_highs.iloc[i]):
                tracker.update_center(i, pivot_highs.iloc[i])
            elif not pd.isna(pivot_lows.iloc[i]):
                tracker.update_center(i, pivot_lows.iloc[i])
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=atr_period, min_periods=1).mean()
        
        # Initialize arrays
        tup = pd.Series(index=df.index, dtype=float)
        tdown = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)
        
        # Calculate Supertrend with historical tracking
        for i in range(len(df)):
            # Get center value for this bar (non-repainting)
            center = tracker.get_center(i)
            if center is None:
                center = df['close'].iloc[0]  # Fallback
                tracker.center_history[i] = center
            
            # Calculate bands
            up = center - (atr_factor * atr.iloc[i])
            down = center + (atr_factor * atr.iloc[i])
            
            # Store in tracker for non-repainting
            if i == 0:
                tracker.tup_history[i] = up
                tracker.tdown_history[i] = down
                tup.iloc[i] = up
                tdown.iloc[i] = down
                trend.iloc[i] = 1
            else:
                # Get previous values from tracker (non-repainting)
                prev_tup = tracker.tup_history.get(i-1, up)
                prev_tdown = tracker.tdown_history.get(i-1, down)
                
                # Calculate current TUp and TDown
                if df['close'].iloc[i-1] > prev_tup:
                    current_tup = max(up, prev_tup)
                else:
                    current_tup = up
                    
                if df['close'].iloc[i-1] < prev_tdown:
                    current_tdown = min(down, prev_tdown)
                else:
                    current_tdown = down
                
                # Store in tracker (never update previous values)
                tracker.tup_history[i] = current_tup
                tracker.tdown_history[i] = current_tdown
                tup.iloc[i] = current_tup
                tdown.iloc[i] = current_tdown
                
                # Determine trend
                if df['close'].iloc[i] > prev_tdown:
                    trend.iloc[i] = 1  # Bullish
                elif df['close'].iloc[i] < prev_tup:
                    trend.iloc[i] = -1  # Bearish
                else:
                    trend.iloc[i] = trend.iloc[i-1]
        
        df['pvt_trend'] = trend
        df['pvt_tup'] = tup
        df['pvt_tdown'] = tdown
        df['pvt_signal'] = trend.diff().fillna(0)
        
        return df
        
    except Exception as e:
        print(f"Error in v3.3.0 Pivot Supertrend: {e}")
        import traceback
        traceback.print_exc()
        
        # Return df with default values
        df['pvt_trend'] = 1
        df['pvt_signal'] = 0
        df['pvt_tup'] = df['low']
        df['pvt_tdown'] = df['high']
        return df

def calculate_x_trend_v33(df):
    """v3.3.0: Fixed X Trend that actually flips (removed nextTrend logic)"""
    try:
        df = df.copy()
        
        # Calculate components
        lowest_low = df['low'].rolling(window=3, min_periods=1).min()
        highest_high = df['high'].rolling(window=2, min_periods=1).max()
        ma_low = df['low'].ewm(span=3, adjust=False).mean()
        ma_high = df['high'].rolling(window=2).mean()
        
        # Initialize X Trend variables
        x_trend = pd.Series(0.0, index=df.index)  # 0 = bullish, 1 = bearish
        low_max = pd.Series(df['low'].iloc[0] if len(df) > 0 else 0, index=df.index)
        high_min = pd.Series(df['high'].iloc[0] if len(df) > 0 else 0, index=df.index)
        
        for i in range(1, len(df)):
            # Copy previous values
            x_trend.iloc[i] = x_trend.iloc[i-1]
            low_max.iloc[i] = low_max.iloc[i-1]
            high_min.iloc[i] = high_min.iloc[i-1]
            
            # v3.3.0 FIXED: Direct flip logic without nextTrend
            if x_trend.iloc[i] == 0:  # Currently bullish
                low_max.iloc[i] = max(low_max.iloc[i], lowest_low.iloc[i]) if not pd.isna(lowest_low.iloc[i]) else low_max.iloc[i]
                
                # Check for bearish flip
                if (not pd.isna(ma_high.iloc[i]) and 
                    ma_high.iloc[i] < low_max.iloc[i] and 
                    df['close'].iloc[i] < df['low'].iloc[i-1]):
                    x_trend.iloc[i] = 1  # Flip to bearish
                    high_min.iloc[i] = highest_high.iloc[i] if not pd.isna(highest_high.iloc[i]) else high_min.iloc[i]
                    
            else:  # Currently bearish (x_trend == 1)
                high_min.iloc[i] = min(high_min.iloc[i], highest_high.iloc[i]) if not pd.isna(highest_high.iloc[i]) else high_min.iloc[i]
                
                # Check for bullish flip
                if (not pd.isna(ma_low.iloc[i]) and 
                    ma_low.iloc[i] > high_min.iloc[i] and 
                    df['close'].iloc[i] > df['high'].iloc[i-1]):
                    x_trend.iloc[i] = 0  # Flip to bullish
                    low_max.iloc[i] = lowest_low.iloc[i] if not pd.isna(lowest_low.iloc[i]) else low_max.iloc[i]
        
        # Calculate line position
        line_ht = pd.Series(index=df.index, dtype=float)
        for i in range(len(df)):
            if x_trend.iloc[i] == 0:
                line_ht.iloc[i] = low_max.iloc[i]  # Bullish - support line
            else:
                line_ht.iloc[i] = high_min.iloc[i]  # Bearish - resistance line
        
        df['x_trend'] = x_trend
        df['x_trend_signal'] = x_trend.diff().fillna(0)
        df['x_trend_line'] = line_ht
        df['x_low_max'] = low_max
        df['x_high_min'] = high_min
        
        return df
    except Exception as e:
        print(f"Error in v3.3.0 X Trend: {e}")
        df['x_trend'] = 0
        df['x_trend_signal'] = 0
        return df

def calculate_mtf_x_trend_v33(df, base_timeframe_minutes, htf_multiplier):
    """v3.3.0: Fixed MTF X Trend with proper time alignment"""
    try:
        df = df.copy()
        
        # Create MTF bars by resampling
        bars_per_htf = htf_multiplier
        
        # Group bars into HTF periods
        htf_groups = df.index // bars_per_htf
        
        # Create HTF OHLC data
        htf_data = df.groupby(htf_groups).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index(drop=True)
        
        # Calculate X Trend on HTF data
        htf_data = calculate_x_trend_v33(htf_data)
        
        # Map HTF X Trend back to original timeframe
        df['htf_x_trend'] = pd.Series(index=df.index, dtype=float)
        
        for i in range(len(df)):
            htf_index = i // bars_per_htf
            if htf_index < len(htf_data):
                df.loc[i, 'htf_x_trend'] = htf_data.loc[htf_index, 'x_trend']
            elif len(htf_data) > 0:
                # Use last available HTF value
                df.loc[i, 'htf_x_trend'] = htf_data.iloc[-1]['x_trend']
            else:
                df.loc[i, 'htf_x_trend'] = 0  # Default to bullish
        
        # Forward fill any NaN values
        df['htf_x_trend'].fillna(method='ffill', inplace=True)
        
        return df
    except Exception as e:
        print(f"Error in v3.3.0 MTF X Trend: {e}")
        df['htf_x_trend'] = df.get('x_trend', 0)
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
        print(f"Error in ADX calculation: {e}")
        df['adx'] = 25  # Default value
        return df

def calculate_ema(df, period=200):
    """Calculate EMA"""
    try:
        df = df.copy()
        df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
        return df
    except Exception as e:
        print(f"Error in EMA calculation: {e}")
        df['ema'] = df['close']
        return df

# ==================== v3.3.0 ENHANCED BACKTEST WITH RE-ENTRY LOGIC ====================

class TradeManager:
    """v3.3.0: Enhanced trade manager with re-entry logic"""
    def __init__(self):
        self.in_trade = False
        self.current_direction = 0  # 1 = long, -1 = short
        self.entry_price = 0
        self.entry_time = None
        self.entry_bar_index = 0
        
        # Pending states
        self.pvt_buy_pending = False
        self.pvt_sell_pending = False
        self.waiting_for_adx_buy = False
        self.waiting_for_adx_sell = False
        self.adx_was_above_threshold = False
        
        # v3.3.0: Re-entry management
        self.waiting_for_buy_reentry = False
        self.waiting_for_sell_reentry = False
        self.reentry_count = 0
        
        # Trade history
        self.trades = []
        
    def reset_reentry_on_trend_change(self, pvt_buy, pvt_sell):
        """Reset re-entry states on Pivot Supertrend changes"""
        if pvt_buy:
            self.waiting_for_sell_reentry = False
            self.reentry_count = 0
        if pvt_sell:
            self.waiting_for_buy_reentry = False
            self.reentry_count = 0

def run_backtest_v33(df, params, htf_multiplier=None, asset_name=""):
    """v3.3.0: Run backtest with re-entry logic and fixed X-Trend"""
    try:
        # Calculate indicators with v3.3.0 logic
        df = calculate_pivot_supertrend_v33(df, 
                                           pivot_period=params['pivot_period'],
                                           atr_factor=params['atr_factor'],
                                           atr_period=params['atr_period'])
        df = calculate_x_trend_v33(df)
        df = calculate_adx(df)
        df = calculate_ema(df, params.get('ema_period', 200))
        
        # Apply MTF if specified
        if htf_multiplier and htf_multiplier > 1:
            df = calculate_mtf_x_trend_v33(df, 1, htf_multiplier)  # Assuming 1-minute base
            use_htf = True
        else:
            df['htf_x_trend'] = df['x_trend']
            use_htf = False
        
        # Initialize trade manager
        tm = TradeManager()
        signals = []
        
        # Track for analysis
        x_trend_flips = 0
        reentry_trades = 0
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # Check for PVT flips
            pvt_buy_condition = (row['pvt_trend'] == 1) and (prev_row['pvt_trend'] == -1)
            pvt_sell_condition = (row['pvt_trend'] == -1) and (prev_row['pvt_trend'] == 1)
            
            # Reset re-entry states on PVT changes
            tm.reset_reentry_on_trend_change(pvt_buy_condition, pvt_sell_condition)
            
            # Update pending states
            if pvt_buy_condition:
                tm.pvt_buy_pending = True
                tm.pvt_sell_pending = False
                if params.get('use_adx', False) and not (row['adx'] >= params.get('adx_threshold', 25)):
                    tm.waiting_for_adx_buy = True
            
            if pvt_sell_condition:
                tm.pvt_sell_pending = True
                tm.pvt_buy_pending = False
                if params.get('use_adx', False) and not (row['adx'] >= params.get('adx_threshold', 25)):
                    tm.waiting_for_adx_sell = True
            
            # Update ADX waiting states
            if tm.waiting_for_adx_buy and (row['adx'] >= params.get('adx_threshold', 25)):
                tm.waiting_for_adx_buy = False
            if tm.waiting_for_adx_sell and (row['adx'] >= params.get('adx_threshold', 25)):
                tm.waiting_for_adx_sell = False
            
            # Check filters
            adx_filter = params.get('use_adx', False)
            adx_filter_passed = not adx_filter or row['adx'] >= params.get('adx_threshold', 25)
            
            # X Trend filter logic (v3.3.0 fixed)
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
            
            # Detect X-Trend flips for re-entry and exit logic
            xtrend_flipped_to_buy = xtrend_filter and xtrend_buy and (prev_row['x_trend'] == 1 or prev_row.get('htf_x_trend', 1) == 1)
            xtrend_flipped_to_sell = xtrend_filter and xtrend_sell and (prev_row['x_trend'] == 0 or prev_row.get('htf_x_trend', 0) == 0)
            
            if xtrend_flipped_to_buy or xtrend_flipped_to_sell:
                x_trend_flips += 1
            
            # Generate signals with v3.3.0 re-entry logic
            buy_signal = False
            sell_signal = False
            is_reentry = False
            
            # v3.3.0: Check for re-entry opportunities FIRST (higher priority)
            if tm.waiting_for_buy_reentry and row['pvt_trend'] == 1 and xtrend_buy and not tm.in_trade:
                if not adx_filter or adx_filter_passed:
                    buy_signal = True
                    tm.waiting_for_buy_reentry = False
                    tm.reentry_count += 1
                    is_reentry = True
                    reentry_trades += 1
            elif tm.waiting_for_sell_reentry and row['pvt_trend'] == -1 and xtrend_sell and not tm.in_trade:
                if not adx_filter or adx_filter_passed:
                    sell_signal = True
                    tm.waiting_for_sell_reentry = False
                    tm.reentry_count += 1
                    is_reentry = True
                    reentry_trades += 1
            # Normal entry logic (if no re-entry)
            elif not tm.waiting_for_buy_reentry and not tm.waiting_for_sell_reentry:
                # [Previous signal generation logic here - same as before]
                if not xtrend_filter:
                    if not adx_filter:
                        buy_signal = pvt_buy_condition
                        sell_signal = pvt_sell_condition
                    else:
                        buy_signal = pvt_buy_condition and adx_filter_passed
                        buy_signal = buy_signal or (tm.waiting_for_adx_buy and adx_filter_passed)
                        sell_signal = pvt_sell_condition and adx_filter_passed
                        sell_signal = sell_signal or (tm.waiting_for_adx_sell and adx_filter_passed)
                else:
                    # With X Trend filter
                    if pvt_buy_condition and xtrend_buy:
                        if not adx_filter or adx_filter_passed:
                            buy_signal = True
                            tm.pvt_buy_pending = False
                            tm.waiting_for_adx_buy = False
                    elif tm.pvt_buy_pending and xtrend_buy:
                        if not adx_filter or adx_filter_passed:
                            buy_signal = True
                            tm.pvt_buy_pending = False
                            tm.waiting_for_adx_buy = False
                    
                    if pvt_sell_condition and xtrend_sell:
                        if not adx_filter or adx_filter_passed:
                            sell_signal = True
                            tm.pvt_sell_pending = False
                            tm.waiting_for_adx_sell = False
                    elif tm.pvt_sell_pending and xtrend_sell:
                        if not adx_filter or adx_filter_passed:
                            sell_signal = True
                            tm.pvt_sell_pending = False
                            tm.waiting_for_adx_sell = False
            
            # Apply EMA filter AFTER signal generation
            ema_filter = params.get('use_ema', False)
            ema_filter_bullish = not ema_filter or row['close'] > row['ema']
            ema_filter_bearish = not ema_filter or row['close'] < row['ema']
            
            buy_signal = buy_signal and ema_filter_bullish
            sell_signal = sell_signal and ema_filter_bearish
            
            # Track ADX state for exit conditions
            tm.adx_was_above_threshold = adx_filter_passed
            
            # Process signals (entry on next bar's open)
            if not tm.in_trade:
                if buy_signal:
                    tm.in_trade = True
                    tm.current_direction = 1
                    tm.entry_price = row['close']  # Will use next bar's open in real trading
                    tm.entry_time = i
                    tm.entry_bar_index = i
                elif sell_signal:
                    tm.in_trade = True
                    tm.current_direction = -1
                    tm.entry_price = row['close']
                    tm.entry_time = i
                    tm.entry_bar_index = i
            
            # Exit conditions with v3.3.0 re-entry setup
            elif tm.in_trade:
                exit_signal = False
                exit_reason = ""
                setup_reentry = False
                
                if tm.current_direction == 1:  # Long position
                    # Priority 1: XTrend Flip (with re-entry setup)
                    if xtrend_flipped_to_sell:
                        exit_signal = True
                        exit_reason = "XTrend Flip"
                        # v3.3.0: Set up for re-entry if Supertrend still bullish
                        if row['pvt_trend'] == 1:
                            tm.waiting_for_buy_reentry = True
                            setup_reentry = True
                    # Priority 2: Opposite Signal
                    elif sell_signal:
                        exit_signal = True
                        exit_reason = "Opposite Signal"
                        tm.waiting_for_buy_reentry = False
                        tm.reentry_count = 0
                    # Priority 3: Trend Change
                    elif row['pvt_trend'] == -1:
                        exit_signal = True
                        exit_reason = "Trend Change"
                        tm.waiting_for_buy_reentry = False
                        tm.reentry_count = 0
                    # Priority 4: ADX Drop
                    elif params.get('use_adx', False) and tm.adx_was_above_threshold and not adx_filter_passed:
                        exit_signal = True
                        exit_reason = "ADX Drop"
                
                elif tm.current_direction == -1:  # Short position
                    # Priority 1: XTrend Flip (with re-entry setup)
                    if xtrend_flipped_to_buy:
                        exit_signal = True
                        exit_reason = "XTrend Flip"
                        # v3.3.0: Set up for re-entry if Supertrend still bearish
                        if row['pvt_trend'] == -1:
                            tm.waiting_for_sell_reentry = True
                            setup_reentry = True
                    # Priority 2: Opposite Signal
                    elif buy_signal:
                        exit_signal = True
                        exit_reason = "Opposite Signal"
                        tm.waiting_for_sell_reentry = False
                        tm.reentry_count = 0
                    # Priority 3: Trend Change
                    elif row['pvt_trend'] == 1:
                        exit_signal = True
                        exit_reason = "Trend Change"
                        tm.waiting_for_sell_reentry = False
                        tm.reentry_count = 0
                    # Priority 4: ADX Drop
                    elif params.get('use_adx', False) and tm.adx_was_above_threshold and not adx_filter_passed:
                        exit_signal = True
                        exit_reason = "ADX Drop"
                
                if exit_signal:
                    # Calculate profit
                    if 'BTC' in asset_name.upper() or 'ETH' in asset_name.upper() or 'XAU' in asset_name.upper():
                        # For crypto and gold, use points/dollars
                        if tm.current_direction == 1:
                            profit_pips = row['close'] - tm.entry_price
                        else:
                            profit_pips = tm.entry_price - row['close']
                    else:
                        # For forex, use standard pip calculation
                        if tm.current_direction == 1:
                            profit_pips = (row['close'] - tm.entry_price) / 0.0001
                        else:
                            profit_pips = (tm.entry_price - row['close']) / 0.0001
                    
                    signals.append({
                        'entry_time': tm.entry_time,
                        'exit_time': i,
                        'direction': 'long' if tm.current_direction == 1 else 'short',
                        'entry_price': tm.entry_price,
                        'exit_price': row['close'],
                        'profit_pips': profit_pips,
                        'exit_reason': exit_reason,
                        'is_reentry': is_reentry,
                        'reentry_count': tm.reentry_count if is_reentry else 0,
                        'setup_reentry': setup_reentry
                    })
                    
                    # Reset trade state
                    tm.in_trade = False
                    tm.current_direction = 0
        
        # Calculate metrics with v3.3.0 enhancements
        if len(signals) > 0:
            trades_df = pd.DataFrame(signals)
            winning_trades = trades_df[trades_df['profit_pips'] > 0]
            losing_trades = trades_df[trades_df['profit_pips'] < 0]
            
            # Count exit reasons
            xtrend_exits = len(trades_df[trades_df['exit_reason'] == 'XTrend Flip'])
            opposite_exits = len(trades_df[trades_df['exit_reason'] == 'Opposite Signal'])
            trend_exits = len(trades_df[trades_df['exit_reason'] == 'Trend Change'])
            adx_exits = len(trades_df[trades_df['exit_reason'] == 'ADX Drop'])
            
            # v3.3.0: Count re-entries
            reentry_count = len(trades_df[trades_df['is_reentry'] == True])
            reentry_setups = len(trades_df[trades_df['setup_reentry'] == True])
            
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
                'adx_exits': adx_exits,
                # v3.3.0 new metrics
                'x_trend_flips': x_trend_flips,
                'reentry_trades': reentry_count,
                'reentry_setups': reentry_setups,
                'reentry_success_rate': (reentry_count / reentry_setups * 100) if reentry_setups > 0 else 0
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
                'adx_exits': 0,
                'x_trend_flips': 0,
                'reentry_trades': 0,
                'reentry_setups': 0,
                'reentry_success_rate': 0
            }
        
        return metrics, signals
        
    except Exception as e:
        print(f"Error in v3.3.0 backtest: {e}")
        import traceback
        traceback.print_exc()
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
            'adx_exits': 0,
            'x_trend_flips': 0,
            'reentry_trades': 0,
            'reentry_setups': 0,
            'reentry_success_rate': 0
        }, []

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

def run_staged_optimization_v33(df, asset_name, use_xtrend, use_adx, use_ema, xtrend_grey, 
                               optimization_mode='Quick', use_htf=True, htf_mode='Essential',
                               max_bars=500, skip_low_volume=True, optimize_filters=True):
    """v3.3.0: Run optimization with fixed X-Trend and re-entry logic"""
    try:
        # Limit data for faster processing
        if len(df) > max_bars:
            df = df.tail(max_bars)
            st.info(f"Using last {max_bars} bars for optimization")
        
        # Store data period info
        if 'datetime' in df.columns:
            period_start = pd.to_datetime(df['datetime'].iloc[0])
            period_end = pd.to_datetime(df['datetime'].iloc[-1])
        else:
            period_start = pd.to_datetime(df['time'].iloc[0], unit='s')
            period_end = pd.to_datetime(df['time'].iloc[-1], unit='s')
        
        # Define parameter ranges based on optimization mode
        if optimization_mode == 'Quick':
            pivot_periods = [3, 5, 7]
            atr_factors = [1.0, 1.25, 1.5, 2.0]
            atr_periods = [10, 15, 20]
            htf_multipliers = [1, 2, 3] if use_htf else [1]
            adx_thresholds = [20, 25, 30] if optimize_filters else [25]
            ema_periods = [100, 200] if optimize_filters else [200]
        elif optimization_mode == 'Standard':
            pivot_periods = [3, 5, 7, 10]
            atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
            atr_periods = [10, 14, 15, 20]
            htf_multipliers = [1, 2, 3, 4, 6] if use_htf else [1]
            adx_thresholds = [15, 20, 25, 30, 35] if optimize_filters else [25]
            ema_periods = [50, 100, 150, 200] if optimize_filters else [200]
        else:  # Full
            pivot_periods = [3, 5, 7, 10, 15]
            atr_factors = [0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
            atr_periods = [10, 12, 14, 15, 18, 20]
            htf_multipliers = [1, 2, 3, 4, 6, 8, 12] if use_htf else [1]
            adx_thresholds = [15, 20, 25, 30, 35, 40] if optimize_filters else [25]
            ema_periods = [50, 100, 150, 200, 250] if optimize_filters else [200]
        
        # Filter HTF based on mode
        if use_htf and htf_mode == 'Essential':
            htf_multipliers = [x for x in htf_multipliers if x in [1, 2, 3, 4]]
        
        # === STAGE 1: OPTIMIZE CORE PARAMETERS ===
        st.info("🎯 **Stage 1/2**: Optimizing Core Parameters (v3.3.0 Non-repainting Supertrend + Fixed X-Trend)")
        
        stage1_combinations = len(pivot_periods) * len(atr_factors) * len(atr_periods) * len(htf_multipliers)
        
        st.info(f"""
        **Stage 1 - v3.3.0 Core Parameter Optimization:**
        📊 Combinations: {stage1_combinations:,}
        🎯 Testing: {len(pivot_periods)} Pivot × {len(atr_factors)} ATR Factor × {len(atr_periods)} ATR Period × {len(htf_multipliers)} HTF
        🔧 Features: Non-repainting Supertrend + Fixed X-Trend flips + Re-entry logic
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
                        status_text.text(f"Stage 1: Testing {combination_count}/{stage1_combinations} (v3.3.0 Logic)")
                        
                        params = {
                            'pivot_period': pivot_period,
                            'atr_factor': atr_factor,
                            'atr_period': atr_period,
                            'use_xtrend': use_xtrend,
                            'use_adx': False,  # No filters in Stage 1
                            'adx_threshold': 25,
                            'use_ema': False,
                            'ema_period': 200,
                            'xtrend_grey_disagree': xtrend_grey
                        }
                        
                        metrics, _ = run_backtest_v33(df, params, htf_mult, asset_name)
                        
                        # Skip if too few trades
                        if skip_low_volume and metrics['total_trades'] < 5:
                            continue
                        
                        # Calculate composite score (v3.3.0 enhanced)
                        if metrics['total_trades'] > 0:
                            # Give bonus for successful re-entries
                            reentry_bonus = metrics.get('reentry_success_rate', 0) * 0.1
                            score = (
                                metrics['win_rate'] * 0.3 +
                                min(metrics['profit_factor'], 3) * 20 +
                                (metrics['total_pips'] / metrics['total_trades']) * 0.5 +
                                reentry_bonus
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
                            'x_trend_flips': metrics.get('x_trend_flips', 0),
                            'reentry_trades': metrics.get('reentry_trades', 0),
                            'score': round(score, 2)
                        })
        
        # Get top 3 core configurations
        stage1_df = pd.DataFrame(stage1_results)
        stage1_df = stage1_df.sort_values('score', ascending=False)
        top_3_core = stage1_df.head(3)
        
        progress_bar.empty()
        status_text.empty()
        
        st.success(f"✅ Stage 1 Complete! Found {len(stage1_results)} valid v3.3.0 configurations")
        st.info("🔝 **Top 3 v3.3.0 Core Configurations:**")
        display_cols = ['pivot_period', 'atr_factor', 'atr_period', 'htf_timeframe', 
                       'win_rate', 'total_pips', 'x_trend_flips', 'reentry_trades', 'score']
        st.dataframe(top_3_core[display_cols], use_container_width=True)
        
        # === STAGE 2: OPTIMIZE FILTERS ===
        if not optimize_filters or (not use_adx and not use_ema):
            st.info("🎯 **Stage 2**: Skipped (no filter optimization requested)")
            final_results = stage1_results
        else:
            st.info("🎯 **Stage 2/2**: Optimizing Filters on Top 3 Core Configurations")
            
            stage2_combinations = len(top_3_core) * len(adx_thresholds) * len(ema_periods)
            
            st.info(f"""
            **Stage 2 - Filter Optimization:**
            📊 Combinations: {stage2_combinations:,}
            🎯 Testing: 3 Core Configs × {len(adx_thresholds)} ADX × {len(ema_periods)} EMA
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
                        status_text.text(f"Stage 2: Testing {combination_count}/{stage2_combinations}")
                        
                        params = {
                            'pivot_period': int(core_config['pivot_period']),
                            'atr_factor': core_config['atr_factor'],
                            'atr_period': int(core_config['atr_period']),
                            'use_xtrend': use_xtrend,
                            'use_adx': use_adx,
                            'adx_threshold': adx_threshold,
                            'use_ema': use_ema,
                            'ema_period': ema_period,
                            'xtrend_grey_disagree': xtrend_grey
                        }
                        
                        metrics, trades = run_backtest_v33(df, params, int(core_config['htf_multiplier']), asset_name)
                        
                        if skip_low_volume and metrics['total_trades'] < 5:
                            continue
                        
                        # Calculate score with v3.3.0 enhancements
                        if metrics['total_trades'] > 0:
                            reentry_bonus = metrics.get('reentry_success_rate', 0) * 0.1
                            score = (
                                metrics['win_rate'] * 0.3 +
                                min(metrics['profit_factor'], 3) * 20 +
                                (metrics['total_pips'] / metrics['total_trades']) * 0.5 +
                                reentry_bonus
                            )
                        else:
                            score = 0
                        
                        stage2_results.append({
                            'pivot_period': int(core_config['pivot_period']),
                            'atr_factor': core_config['atr_factor'],
                            'atr_period': int(core_config['atr_period']),
                            'adx_threshold': adx_threshold if use_adx else None,
                            'ema_period': ema_period if use_ema else None,
                            'htf_multiplier': int(core_config['htf_multiplier']),
                            'htf_timeframe': core_config['htf_timeframe'],
                            'use_xtrend': 'Yes' if use_xtrend else 'No',
                            'use_adx': f"ADX≥{adx_threshold}" if use_adx else 'No',
                            'use_ema': f"EMA{ema_period}" if use_ema else 'No',
                            'mtf_agree': 'Yes' if xtrend_grey else 'No',
                            'total_trades': metrics['total_trades'],
                            'win_rate': round(metrics['win_rate'], 2),
                            'total_pips': round(metrics['total_pips'], 2),
                            'profit_factor': round(metrics['profit_factor'], 2),
                            'avg_win': round(metrics['avg_win'], 2),
                            'avg_loss': round(metrics['avg_loss'], 2),
                            'xtrend_exits': metrics.get('xtrend_exits', 0),
                            'opposite_exits': metrics.get('opposite_exits', 0),
                            'trend_exits': metrics.get('trend_exits', 0),
                            'adx_exits': metrics.get('adx_exits', 0),
                            'x_trend_flips': metrics.get('x_trend_flips', 0),
                            'reentry_trades': metrics.get('reentry_trades', 0),
                            'reentry_setups': metrics.get('reentry_setups', 0),
                            'score': round(score, 2)
                        })
            
            progress_bar.empty()
            status_text.empty()
            
            final_results = stage2_results
            st.success(f"✅ Stage 2 Complete! Tested {len(final_results)} filter combinations")
        
        # Convert to DataFrame and sort
        results_df = pd.DataFrame(final_results)
        results_df = results_df.sort_values('score', ascending=False)
        
        # Add period info to results
        results_df['period_start'] = period_start
        results_df['period_end'] = period_end
        
        return results_df
        
    except Exception as e:
        st.error(f"v3.3.0 optimization error: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

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
        
        # Limit data for performance
        if len(data) > 1000:
            data = data.tail(1000)
            st.info(f"Using last 1000 bars for {symbol}")
        
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
            missing = [col for col in required if col not in df.columns]
            st.error(f"CSV must have columns: {required}")
            st.error(f"Missing: {missing}")
            return None
        
        # Ensure numeric types for price columns
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Ensure time is integer
        df['time'] = pd.to_numeric(df['time'], errors='coerce').astype('int64')
        
        # Remove any rows with NaN values
        df = df.dropna()
        
        # Limit to 1000 rows for performance
        if len(df) > 1000:
            df = df.tail(1000)
            st.info(f"Using last 1000 bars from {filename}")
        
        st.success(f"Successfully processed {filename}: {len(df)} valid bars")
        
        return df
        
    except Exception as e:
        st.error(f"Error processing CSV: {e}")
        return None

# ==================== MAIN APPLICATION ====================

def main():
    st.set_page_config(
        page_title="XPST Optimizer v3.3.0",
        page_icon="🎯",
        layout="wide"
    )
    
    # Header with v3.3.0 highlights
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🎯 XPST Optimizer v{__version__}</h1>
        <p style="color: #e8f4f8; margin: 5px 0 0 0;">cTrader v3.3.0 Logic Implementation</p>
        <p style="color: #d0e8f0; margin: 3px 0 0 0; font-size: 0.9em;">Last Updated: {__last_updated__}</p>
        <p style="color: #ffd700; margin: 8px 0 0 0; font-size: 0.95em; font-weight: bold;">
            🆕 v3.3.0: Fixed X-Trend Flips | Non-Repainting Supertrend | Re-Entry Logic
        </p>
        <p style="color: #98fb98; margin: 5px 0 0 0; font-size: 0.9em;">
            ✅ Matches: cTrader Indicator v3.3.0 | Enhanced MTF | Historical Value Storage
        </p>
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
    st.sidebar.header("📊 v3.3.0 Configuration")
    
    # Data Source Selection
    data_source = st.sidebar.radio(
        "Data Source",
        options=["Upload CSV", "Yahoo Finance"],
        index=0,
        help="Upload your CSV files or download from Yahoo Finance"
    )
    
    # Initialize variables
    selected_assets = []
    timeframe = '5m'
    period = '7d'
    uploaded_files = None
    
    if data_source == "Upload CSV":
        st.sidebar.subheader("📁 Upload CSV Files")
        uploaded_files = st.sidebar.file_uploader(
            "Choose CSV files",
            type=['csv'],
            accept_multiple_files=True,
            help="CSV must have columns: time, open, high, low, close, volume"
        )
        
        if uploaded_files:
            st.sidebar.success(f"✅ {len(uploaded_files)} file(s) uploaded")
    
    else:  # Yahoo Finance
        selected_assets = st.sidebar.multiselect(
            "Select Assets",
            options=list(assets.keys()),
            default=['EURUSD', 'BTCUSD'],
            format_func=lambda x: f"{x} ({assets[x]['name']})"
        )
        
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
    
    # v3.3.0 Optimization Settings
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ v3.3.0 Optimization Settings")
    
    # Optimization mode
    optimization_mode = st.sidebar.radio(
        "Optimization Mode",
        options=["Quick", "Standard", "Full"],
        index=0,
        help="""
        Quick: Faster optimization with fewer combinations
        Standard: Balanced optimization
        Full: Comprehensive optimization (slower)
        """
    )
    
    # Filter settings
    st.sidebar.markdown("### 🔧 Filter Settings")
    use_filters = st.sidebar.checkbox("Use Filters in Optimization", value=True)
    if use_filters:
        use_xtrend = st.sidebar.checkbox("Use X Trend Filter", value=True, 
                                        help="v3.3.0: Fixed X-Trend with proper flips")
        use_adx = st.sidebar.checkbox("Use ADX Filter", value=False)
        use_ema = st.sidebar.checkbox("Use EMA Filter", value=False)
        
        if use_xtrend:
            st.sidebar.markdown("**X Trend MTF Settings:**")
            use_htf = st.sidebar.checkbox("Test HTF Variations", value=True,
                                         help="Test multiple timeframe variations")
            if use_htf:
                xtrend_grey = st.sidebar.checkbox("Require MTF Agreement", value=False,
                                                 help="Both local and HTF must agree")
                htf_mode = st.sidebar.radio(
                    "HTF Testing Range",
                    options=["Essential", "All"],
                    index=0,
                    help="Essential: 1x-4x | All: 1x-12x"
                )
            else:
                xtrend_grey = False
                htf_mode = 'Essential'
        else:
            xtrend_grey = False
            use_htf = False
            htf_mode = 'Essential'
    else:
        use_xtrend = False
        use_adx = False
        use_ema = False
        xtrend_grey = False
        use_htf = False
        htf_mode = 'Essential'
    
    # Filter optimization
    optimize_filters = st.sidebar.checkbox(
        "Optimize Filter Parameters",
        value=True,
        help="Test multiple ADX thresholds and EMA periods"
    )
    
    # v3.3.0 Features
    st.sidebar.markdown("### 🆕 v3.3.0 Features")
    show_reentry_stats = st.sidebar.checkbox(
        "Show Re-Entry Statistics",
        value=True,
        help="Display re-entry trade analysis"
    )
    
    show_xtrend_analysis = st.sidebar.checkbox(
        "Show X-Trend Flip Analysis",
        value=True,
        help="Analyze X-Trend flip behavior"
    )
    
    # Advanced settings
    with st.sidebar.expander("🔧 Advanced Settings"):
        max_bars = st.slider(
            "Max Bars to Process",
            min_value=200,
            max_value=2000,
            value=500,
            step=100,
            help="Fewer bars = faster processing"
        )
        
        skip_low_volume = st.checkbox(
            "Skip Low Volume Results",
            value=True,
            help="Skip combinations with < 5 trades"
        )
    
    # Main content area
    st.markdown("### 📊 Data Management")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if data_source == "Upload CSV":
            if uploaded_files:
                if st.button("📤 Process CSV Files", type="primary", use_container_width=True):
                    st.session_state.downloaded_data.clear()
                    
                    for file in uploaded_files:
                        df = pd.read_csv(file)
                        processed = process_uploaded_csv(df, file.name)
                        if processed is not None:
                            # Extract asset name from filename
                            asset_name = file.name.replace('.csv', '').split('_')[0].upper()
                            # Handle special naming
                            if '1_' in file.name:
                                asset_name += "_1M"
                            elif '5_' in file.name:
                                asset_name += "_5M"
                            elif '15_' in file.name:
                                asset_name += "_15M"
                            st.session_state.downloaded_data[asset_name] = processed
                            st.success(f"✅ {asset_name}: {len(processed)} bars")
            else:
                st.info("👆 Please upload CSV files to proceed")
        
        else:  # Yahoo Finance
            if st.button("📥 Download Data", type="primary", use_container_width=True):
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
    
    with col2:
        if st.session_state.downloaded_data:
            if st.button("🚀 Run v3.3.0 Optimization", type="primary", use_container_width=True):
                st.session_state.optimization_results.clear()
                
                for asset, data in st.session_state.downloaded_data.items():
                    with st.container():
                        st.write(f"**Optimizing {asset} with v3.3.0 Logic...**")
                        
                        results = run_staged_optimization_v33(
                            data, asset, use_xtrend, use_adx, use_ema, xtrend_grey,
                            optimization_mode, use_htf, htf_mode,
                            max_bars, skip_low_volume, optimize_filters
                        )
                        
                        if not results.empty:
                            st.session_state.optimization_results[asset] = results
                            
                            # Show brief summary
                            best = results.iloc[0]
                            summary = f"Win Rate: {best['win_rate']}%, Profit: {best['total_pips']:.1f} pips"
                            
                            # v3.3.0: Show re-entry info if available
                            if 'reentry_trades' in best and best['reentry_trades'] > 0:
                                summary += f", Re-entries: {best['reentry_trades']}"
                            
                            st.success(f"Best: {summary}")
    
    with col3:
        if st.session_state.optimization_results:
            if st.button("📊 Clear Results", type="secondary", use_container_width=True):
                st.session_state.optimization_results.clear()
                st.session_state.downloaded_data.clear()
                st.rerun()
    
    # Display current data status
    if st.session_state.downloaded_data:
        st.markdown("---")
        st.markdown("### 📈 Loaded Data")
        
        data_cols = st.columns(len(st.session_state.downloaded_data))
        for idx, (asset, data) in enumerate(st.session_state.downloaded_data.items()):
            with data_cols[idx]:
                # Determine timeframe from data
                if len(data) > 1:
                    time_diff = data['time'].iloc[1] - data['time'].iloc[0]
                    tf_minutes = time_diff / 60
                    tf_str = f"{int(tf_minutes)}m" if tf_minutes < 60 else f"{int(tf_minutes/60)}h"
                else:
                    tf_str = "N/A"
                
                st.metric(
                    label=asset,
                    value=f"{len(data)} bars",
                    delta=f"{tf_str} timeframe"
                )
    
    # Results section
    if st.session_state.optimization_results:
        st.markdown("---")
        st.markdown("### 🏆 v3.3.0 Optimization Results")
        
        # Summary table
        summary_data = []
        for asset, results in st.session_state.optimization_results.items():
            best = results.iloc[0] if not results.empty else None
            if best is not None:
                summary_data.append({
                    'Asset': asset,
                    'Win Rate': f"{best['win_rate']}%",
                    'Total Pips': f"{best['total_pips']:.1f}",
                    'Profit Factor': f"{best.get('profit_factor', 0):.2f}",
                    'Trades': best.get('total_trades', 0),
                    'Re-entries': best.get('reentry_trades', 0),
                    'X-Trend Flips': best.get('x_trend_flips', 0),
                    'Score': f"{best.get('score', 0):.1f}"
                })
        
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True)
        
        # Detailed results tabs
        tabs = st.tabs(list(st.session_state.optimization_results.keys()))
        
        for tab, asset in zip(tabs, st.session_state.optimization_results.keys()):
            with tab:
                results = st.session_state.optimization_results[asset]
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("**🥇 Top 10 v3.3.0 Optimization Results:**")
                    
                    # Select display columns
                    display_cols = ['pivot_period', 'atr_factor', 'atr_period', 'htf_timeframe']
                    
                    if 'use_adx' in results.columns:
                        display_cols.append('use_adx')
                    if 'use_ema' in results.columns:
                        display_cols.append('use_ema')
                    
                    display_cols.extend(['total_trades', 'win_rate', 'total_pips', 'profit_factor'])
                    
                    # v3.3.0: Add new metrics if available
                    if 'reentry_trades' in results.columns:
                        display_cols.append('reentry_trades')
                    if 'x_trend_flips' in results.columns:
                        display_cols.append('x_trend_flips')
                    
                    display_cols.append('score')
                    
                    # Filter columns that exist
                    display_cols = [col for col in display_cols if col in results.columns]
                    
                    st.dataframe(
                        results[display_cols].head(10),
                        use_container_width=True,
                        hide_index=True
                    )
                
                with col2:
                    # Best configuration details
                    best = results.iloc[0]
                    
                    st.write("**📍 Optimal v3.3.0 Settings:**")
                    
                    # Format settings for cTrader
                    st.code(f"""// XPST v3.3.0 Settings for {asset}
// === CORE SETTINGS ===
Pivot Period: {best['pivot_period']}
ATR Factor: {best['atr_factor']}
ATR Period: {best['atr_period']}

// === FILTER SETTINGS ===
Use X Trend: {best.get('use_xtrend', 'Yes')}
Use ADX: {best.get('use_adx', 'No') != 'No'}
ADX Threshold: {best.get('adx_threshold', 25) if best.get('adx_threshold') else 25}
Use EMA: {best.get('use_ema', 'No') != 'No'}
EMA Period: {best.get('ema_period', 200) if best.get('ema_period') else 200}

// === MTF SETTINGS ===
HTF Multiplier: {best.get('htf_multiplier', 1)}
MTF Agreement: {best.get('mtf_agree', 'No')}

// === PERFORMANCE ===
Win Rate: {best['win_rate']}%
Total Trades: {best.get('total_trades', 0)}
Total Pips: {best['total_pips']:.1f}
Profit Factor: {best.get('profit_factor', 0):.2f}

// === v3.3.0 METRICS ===
X-Trend Flips: {best.get('x_trend_flips', 0)}
Re-Entry Trades: {best.get('reentry_trades', 0)}
Re-Entry Setups: {best.get('reentry_setups', 0)}
                    """)
                
                # v3.3.0 Analysis sections
                if show_reentry_stats and 'reentry_trades' in results.columns:
                    st.write("**🔄 Re-Entry Analysis:**")
                    
                    reentry_analysis = results[results['reentry_trades'] > 0]
                    if not reentry_analysis.empty:
                        avg_reentries = reentry_analysis['reentry_trades'].mean()
                        max_reentries = reentry_analysis['reentry_trades'].max()
                        
                        st.info(f"""
                        **Re-Entry Statistics:**
                        - Configurations with re-entries: {len(reentry_analysis)}
                        - Average re-entries per config: {avg_reentries:.1f}
                        - Maximum re-entries: {max_reentries}
                        - Best performer re-entries: {best.get('reentry_trades', 0)}
                        """)
                    else:
                        st.info("No re-entry trades detected in this optimization")
                
                if show_xtrend_analysis and 'x_trend_flips' in results.columns:
                    st.write("**📊 X-Trend Flip Analysis:**")
                    
                    avg_flips = results['x_trend_flips'].mean()
                    max_flips = results['x_trend_flips'].max()
                    min_flips = results['x_trend_flips'].min()
                    
                    st.info(f"""
                    **X-Trend Flip Statistics:**
                    - Average flips: {avg_flips:.1f}
                    - Range: {min_flips} - {max_flips}
                    - Best config flips: {best.get('x_trend_flips', 0)}
                    - Flip frequency: {best.get('x_trend_flips', 0) / best.get('total_trades', 1):.2f} per trade
                    """)
                
                # Exit reason analysis
                if 'xtrend_exits' in results.columns:
                    st.write("**📊 Exit Reason Analysis:**")
                    
                    col_exit1, col_exit2 = st.columns(2)
                    
                    with col_exit1:
                        exit_data = {
                            'Exit Type': ['XTrend Flip', 'Opposite Signal', 'Trend Change', 'ADX Drop'],
                            'Count': [
                                best.get('xtrend_exits', 0),
                                best.get('opposite_exits', 0),
                                best.get('trend_exits', 0),
                                best.get('adx_exits', 0)
                            ]
                        }
                        exit_df = pd.DataFrame(exit_data)
                        st.dataframe(exit_df, use_container_width=True, hide_index=True)
                    
                    with col_exit2:
                        st.info("""
                        **Exit Priority (v3.3.0):**
                        1. XTrend Flip (→ Re-entry)
                        2. Opposite Signal
                        3. Trend Change
                        4. ADX Drop
                        """)
                
                # Download results
                csv = results.to_csv(index=False)
                st.download_button(
                    label=f"📥 Download {asset} Results CSV",
                    data=csv,
                    file_name=f"xpst_v330_optimization_{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    else:
        if not st.session_state.downloaded_data:
            st.info("👈 Upload CSV files or select assets to begin v3.3.0 optimization")
        else:
            st.info("✨ Data ready! Click 'Run v3.3.0 Optimization' to find optimal settings")
    
    # Info boxes
    st.markdown("---")
    with st.expander("🆕 What's New in v3.3.0"):
        st.markdown("""
        ### 🚀 v3.3.0 Major Improvements (Matching cTrader):
        
        **1. FIXED: X-Trend Now Actually Flips! 🔄**
        - Removed buggy nextTrend logic that prevented flips
        - X-Trend now properly alternates between bullish (0) and bearish (1)
        - Direct flip detection without intermediate states
        
        **2. Non-Repainting Pivot Supertrend 📊**
        - Historical value storage prevents repainting
        - Center values calculated once and stored per bar
        - TUp/TDown values never update retroactively
        - Matches exact TradingView v3.1 formula
        
        **3. Re-Entry Logic After X-Trend Exits 🔁**
        - When exiting due to X-Trend flip, system checks if main trend continues
        - If Supertrend remains in same direction, enables re-entry
        - Tracks re-entry count and success rate
        - Improves profit capture in trending markets
        
        **4. Enhanced MTF X-Trend Calculation 📈**
        - Proper time alignment between timeframes
        - Fixed MTF bar synchronization
        - Accurate HTF trend detection
        - No more stuck MTF trends
        
        **5. Comprehensive Trade Analysis 📊**
        - X-Trend flip counter
        - Re-entry trade tracking
        - Re-entry setup vs execution rate
        - Exit reason breakdown with priorities
        
        ### 🎯 Key Benefits:
        - **More Accurate Signals**: X-Trend properly identifies trend changes
        - **Better Entries**: Re-entry logic captures trend continuations
        - **No Repainting**: Historical values locked in place
        - **Improved MTF**: Accurate multi-timeframe analysis
        - **Complete Analytics**: Full visibility into system behavior
        """)
    
    with st.expander("📋 How to Apply v3.3.0 Settings in cTrader"):
        st.markdown("""
        ### 📋 Applying Settings to cTrader Indicator v3.3.0:
        
        **Step 1: Core Settings**
        ```
        Pivot Point Period: [from optimization]
        ATR Factor: [from optimization]
        ATR Period: [from optimization]
        ```
        
        **Step 2: Filter Settings**
        ```
        Use X Trend Filter: [Yes/No from optimization]
        Use ADX Filter: [Yes/No from optimization]
        ADX Threshold: [from optimization, default 25]
        Use EMA Filter: [Yes/No from optimization]
        EMA Period: [from optimization, default 200]
        ```
        
        **Step 3: MTF Settings (if using X-Trend)**
        ```
        Use X Trend MTF: [Yes if HTF > 1]
        X Trend MTF Multiplier: [from optimization]
        Grey/Block on Disagreement: [from MTF Agreement setting]
        ```
        
        **Step 4: Display Settings**
        ```
        Show Buy/Sell Labels: Yes
        Show Exit Labels: Yes (to see re-entry markers)
        Show Statistics: Yes
        Max Trades to Track: 30
        ```
        
        ### 🔍 Verification:
        1. **X-Trend Flips**: Line should change color when trend changes
        2. **Re-Entries**: Look for "RE-ENTRY #1, #2" labels after X-Trend exits
        3. **Non-Repainting**: Supertrend line should not jump or change past values
        4. **Statistics**: Check exit reasons match optimization results
        
        ### ⚠️ Important Notes:
        - Ensure you're using cTrader Indicator v3.3.0 (not older versions)
        - Re-entry logic only activates after X-Trend flip exits
        - MTF requires higher timeframe data availability
        - Statistics update every 50 bars for performance
        """)
    
    # Footer
    st.markdown(
        f"""
        <div style="text-align: center; color: #666; margin-top: 40px;">
            <small>
            XPST Optimizer v{__version__} | cTrader v3.3.0 Logic Implementation<br>
            Fixed X-Trend | Non-Repainting | Re-Entry Logic | Enhanced MTF<br>
            Last Updated: {__last_updated__}
            </small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
