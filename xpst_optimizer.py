import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

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
        
        high_values = df['high'].rolling(window=2*period+1, center=True).apply(
            lambda x: x[period] if len(x) == 2*period+1 and x[period] == max(x) else np.nan
        )
        
        low_values = df['low'].rolling(window=2*period+1, center=True).apply(
            lambda x: x[period] if len(x) == 2*period+1 and x[period] == min(x) else np.nan
        )
        
        return high_values, low_values
    except Exception as e:
        st.error(f"Error in pivot calculation: {e}")
        return pd.Series(index=df.index, dtype=float), pd.Series(index=df.index, dtype=float)

def calculate_pivot_supertrend(df, pivot_period=5, atr_factor=1.25, atr_period=15):
    """Calculate Pivot Supertrend based on TradingView XPST v3.1"""
    try:
        df = df.copy()
        
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
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=atr_period).mean()
        
        # Calculate bands
        up = center - (atr_factor * atr)
        down = center + (atr_factor * atr)
        
        # Initialize trailing stop and trend
        tup = pd.Series(index=df.index, dtype=float)
        tdown = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)
        
        for i in range(1, len(df)):
            # Update TUp
            if df['close'].iloc[i-1] > tup.iloc[i-1] if not pd.isna(tup.iloc[i-1]) else False:
                tup.iloc[i] = max(up.iloc[i], tup.iloc[i-1]) if not pd.isna(tup.iloc[i-1]) else up.iloc[i]
            else:
                tup.iloc[i] = up.iloc[i]
            
            # Update TDown
            if df['close'].iloc[i-1] < tdown.iloc[i-1] if not pd.isna(tdown.iloc[i-1]) else False:
                tdown.iloc[i] = min(down.iloc[i], tdown.iloc[i-1]) if not pd.isna(tdown.iloc[i-1]) else down.iloc[i]
            else:
                tdown.iloc[i] = down.iloc[i]
            
            # Determine trend
            if df['close'].iloc[i] > tdown.iloc[i-1] if not pd.isna(tdown.iloc[i-1]) else False:
                trend.iloc[i] = 1
            elif df['close'].iloc[i] < tup.iloc[i-1] if not pd.isna(tup.iloc[i-1]) else False:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1] if i > 0 else 1
        
        # Set initial values
        if len(df) > 0:
            tup.iloc[0] = up.iloc[0]
            tdown.iloc[0] = down.iloc[0]
            trend.iloc[0] = 1
        
        df['pvt_trend'] = trend
        df['pvt_tup'] = tup
        df['pvt_tdown'] = tdown
        df['pvt_signal'] = trend.diff().fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Error in Pivot Supertrend calculation: {e}")
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

def run_backtest(df, params, htf_multiplier=None):
    """Run backtest with exact XPST v3.1 logic"""
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
                elif sell_signal:
                    position = 'short'
                    entry_price = row['close']
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
                        'entry_time': df.index[i-1],
                        'exit_time': df.index[i],
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
                        'entry_time': df.index[i-1],
                        'exit_time': df.index[i],
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
        
        return metrics
        
    except Exception as e:
        st.error(f"Error in backtest: {e}")
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pips': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0
        }

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

def process_uploaded_csv(df, filename):
    """Process uploaded CSV file to match expected format"""
    try:
        df = df.copy()
        
        # Ensure column names are lowercase
        df.columns = [col.lower() for col in df.columns]
        
        # Check for required columns
        required = ['time', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required):
            st.error(f"CSV must have columns: {required}")
            return None
        
        # Limit to 1000 rows for performance
        if len(df) > 1000:
            df = df.tail(1000)
            st.info(f"Using last 1000 bars from {filename}")
        
        return df
        
    except Exception as e:
        st.error(f"Error processing CSV: {e}")
        return None

def run_optimization_with_filters(df, asset_name, use_xtrend, use_adx, use_ema, xtrend_grey):
    """Run optimization with specified filter settings"""
    try:
        results = []
        
        # Parameter ranges
        pivot_periods = [3, 5, 7, 10]
        atr_factors = [1.0, 1.25, 1.5, 2.0, 2.5]
        atr_periods = [10, 14, 15, 20]
        htf_multipliers = [1, 2, 3, 4, 6, 8, 12, 16]
        
        # Progress tracking
        total_combinations = len(pivot_periods) * len(atr_factors) * len(atr_periods) * len(htf_multipliers)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        combination_count = 0
        
        for pivot_period in pivot_periods:
            for atr_factor in atr_factors:
                for atr_period in atr_periods:
                    for htf_mult in htf_multipliers:
                        combination_count += 1
                        progress = combination_count / total_combinations
                        progress_bar.progress(progress)
                        status_text.text(f"Testing combination {combination_count}/{total_combinations}")
                        
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
                        
                        # Calculate composite score
                        if metrics['total_trades'] > 0:
                            score = (
                                metrics['win_rate'] * 0.3 +
                                min(metrics['profit_factor'], 3) * 20 +
                                (metrics['total_pips'] / metrics['total_trades']) * 0.5
                            )
                        else:
                            score = 0
                        
                        results.append({
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
        
        progress_bar.empty()
        status_text.empty()
        
        # Convert to DataFrame and sort
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('score', ascending=False)
        
        return results_df
        
    except Exception as e:
        st.error(f"Optimization error: {e}")
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
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🎯 XPST Optimizer v3.1</h1>
        <p style="color: #e8f4f8; margin: 5px 0 0 0;">TradingView Consistency Verified Edition</p>
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
        else:
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
                        
                        # Pass filter settings to optimization
                        results = run_optimization_with_filters(
                            data, asset, use_xtrend, use_adx, use_ema, xtrend_grey
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
                    # Top configurations
                    st.write("**🥇 Top 10 Configurations:**")
                    display_cols = ['pivot_period', 'atr_factor', 'atr_period', 
                                  'htf_timeframe', 'total_trades', 'win_rate', 
                                  'total_pips', 'profit_factor', 'score']
                    st.dataframe(
                        results[display_cols].head(10),
                        use_container_width=True,
                        hide_index=True
                    )
                
                with col2:
                    # Best configuration details
                    best = results.iloc[0]
                    st.write("**📍 Optimal Settings:**")
                    st.code(f"""
// XPST v3.1 Settings for {asset}
Pivot Period: {best['pivot_period']}
ATR Factor: {best['atr_factor']}
ATR Period: {best['atr_period']}
HTF Multiplier: {best['htf_multiplier']}x

// Performance
Win Rate: {best['win_rate']}%
Total Trades: {best['total_trades']}
Total Pips: {best['total_pips']:.1f}
Profit Factor: {best['profit_factor']:.2f}
                    """)
                
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
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666;">
            <small>
            XPST Optimizer v3.1 | Matches TradingView Implementation<br>
            Data provided by Yahoo Finance | Optimized for XPST v3.1 Pine Script
            </small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
