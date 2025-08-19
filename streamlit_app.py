# Fixed Streamlit XPST Optimizer - Resolves result display and progress issues
# Password-protected trading strategy optimizer with Yahoo Finance integration

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import warnings

warnings.filterwarnings('ignore')

# Set page configuration
st.set_page_config(
    page_title="XPST Optimizer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = {}
if 'downloaded_data' not in st.session_state:
    st.session_state.downloaded_data = {}
if 'optimization_complete' not in st.session_state:
    st.session_state.optimization_complete = False

# Password protection function
def check_password():
    """Password protection for the app"""
    def password_entered():
        if st.session_state["password"] == "XPST2024!":  # Change this password!
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("## 🔒 Private XPST Optimizer Access")
        st.markdown("This application is private. Please enter the access password.")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.markdown("---")
        st.markdown("*Contact the administrator for access credentials.*")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("## 🔒 Private XPST Optimizer Access")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password. Please try again.")
        return False
    else:
        return True

# Main XPST Optimizer Class
class StreamlitXPSTOptimizer:
    def __init__(self):
        self.assets = {
            'BTCUSD': {'yf_symbol': 'BTC-USD', 'name': 'Bitcoin/USD', 'type': 'Crypto'},
            'ETHUSD': {'yf_symbol': 'ETH-USD', 'name': 'Ethereum/USD', 'type': 'Crypto'},
            'XAUUSD': {'yf_symbol': 'GC=F', 'name': 'Gold/USD', 'type': 'Commodity'},
            'EURUSD': {'yf_symbol': 'EURUSD=X', 'name': 'Euro/USD', 'type': 'Forex'},
            'GBPUSD': {'yf_symbol': 'GBPUSD=X', 'name': 'GBP/USD', 'type': 'Forex'},
            'USDJPY': {'yf_symbol': 'USDJPY=X', 'name': 'USD/JPY', 'type': 'Forex'},
            'AUDUSD': {'yf_symbol': 'AUDUSD=X', 'name': 'AUD/USD', 'type': 'Forex'},
            'USDCAD': {'yf_symbol': 'USDCAD=X', 'name': 'USD/CAD', 'type': 'Forex'}
        }
        
        self.timeframes = {
            '1m': {'name': '1 Minute', 'periods': ['1d', '5d', '7d'], 'max_bars': '~7-8K'},
            '5m': {'name': '5 Minutes', 'periods': ['1d', '5d', '1mo', '3mo'], 'max_bars': '~8-12K'},
            '15m': {'name': '15 Minutes', 'periods': ['1d', '5d', '1mo', '3mo', '6mo'], 'max_bars': '~15-20K'},
            '30m': {'name': '30 Minutes', 'periods': ['1d', '5d', '1mo', '3mo', '6mo', '1y'], 'max_bars': '~20-25K'},
            '1h': {'name': '1 Hour', 'periods': ['1mo', '3mo', '6mo', '1y', '2y'], 'max_bars': '~25-30K'},
            '1d': {'name': '1 Day', 'periods': ['1y', '2y', '5y', '10y', 'max'], 'max_bars': '~5000+'}
        }

    def calculate_atr(self, data, period=15):
        """Calculate Average True Range"""
        try:
            tr_list = []
            for i in range(1, len(data)):
                tr = max(
                    data.iloc[i]['high'] - data.iloc[i]['low'],
                    abs(data.iloc[i]['high'] - data.iloc[i-1]['close']),
                    abs(data.iloc[i]['low'] - data.iloc[i-1]['close'])
                )
                tr_list.append(tr)
            
            atr_values = [0]
            for i in range(len(tr_list)):
                if i < period - 1:
                    atr_values.append(np.mean(tr_list[:i+1]))
                else:
                    atr_values.append(np.mean(tr_list[i-period+1:i+1]))
            
            return atr_values
        except Exception as e:
            st.error(f"Error calculating ATR: {str(e)}")
            return [1] * len(data)

    def find_pivot_highs(self, data, period=5):
        """Find pivot high points"""
        try:
            pivots = [None] * len(data)
            for i in range(period, len(data) - period):
                current_high = data.iloc[i]['high']
                is_pivot = True
                for j in range(1, period + 1):
                    if (data.iloc[i-j]['high'] >= current_high or
                        data.iloc[i+j]['high'] >= current_high):
                        is_pivot = False
                        break
                if is_pivot:
                    pivots[i] = current_high
            return pivots
        except Exception as e:
            st.error(f"Error finding pivot highs: {str(e)}")
            return [None] * len(data)

    def find_pivot_lows(self, data, period=5):
        """Find pivot low points"""
        try:
            pivots = [None] * len(data)
            for i in range(period, len(data) - period):
                current_low = data.iloc[i]['low']
                is_pivot = True
                for j in range(1, period + 1):
                    if (data.iloc[i-j]['low'] <= current_low or
                        data.iloc[i+j]['low'] <= current_low):
                        is_pivot = False
                        break
                if is_pivot:
                    pivots[i] = current_low
            return pivots
        except Exception as e:
            st.error(f"Error finding pivot lows: {str(e)}")
            return [None] * len(data)

    def calculate_pivot_supertrend(self, data, pivot_period=5, atr_factor=1.25, atr_period=15):
        """Calculate Pivot Supertrend"""
        try:
            pivot_highs = self.find_pivot_highs(data, pivot_period)
            pivot_lows = self.find_pivot_lows(data, pivot_period)
            atr_values = self.calculate_atr(data, atr_period)
            
            results = []
            center = None
            
            for i in range(len(data)):
                if pivot_highs[i] is not None or pivot_lows[i] is not None:
                    lastpp = pivot_highs[i] or pivot_lows[i]
                    center = lastpp if center is None else (center * 2 + lastpp) / 3
                
                if center is None or i == 0:
                    results.append({'trend': 1, 'trailing_stop': None})
                    continue
                
                up = center - (atr_factor * atr_values[i])
                down = center + (atr_factor * atr_values[i])
                
                prev = results[i-1]
                prev_close = data.iloc[i-1]['close']
                current_close = data.iloc[i]['close']
                
                t_up = max(up, prev.get('up', up)) if prev_close > prev.get('up', up) else up
                t_down = min(down, prev.get('down', down)) if prev_close < prev.get('down', down) else down
                
                if current_close > prev.get('down', down):
                    trend = 1
                elif current_close < prev.get('up', up):
                    trend = -1
                else:
                    trend = prev.get('trend', 1)
                
                results.append({
                    'up': t_up,
                    'down': t_down,
                    'trend': trend,
                    'trailing_stop': t_up if trend == 1 else t_down
                })
            
            return results
        except Exception as e:
            st.error(f"Error calculating Pivot Supertrend: {str(e)}")
            return [{'trend': 1, 'trailing_stop': None}] * len(data)

    def calculate_x_trend(self, data):
        """Calculate X Trend"""
        try:
            results = []
            next_trend = 0
            x_trend = 0
            low_max = 0
            high_min = 0
            
            for i in range(len(data)):
                if i < 3:
                    results.append({'x_trend': 0, 'line_ht': data.iloc[i]['close']})
                    continue
                
                lowest_low = min(data.iloc[max(0, i-2):i+1]['low'])
                highest_high = max(data.iloc[max(0, i-1):i+1]['high'])
                
                ma_low = np.mean(data.iloc[max(0, i-2):i+1]['low'])
                ma_high = np.mean(data.iloc[max(0, i-1):i+1]['high'])
                
                if i == 3:
                    low_max = lowest_low
                    high_min = highest_high
                
                current_close = data.iloc[i]['close']
                prev_low = data.iloc[i-1]['low']
                prev_high = data.iloc[i-1]['high']
                
                if next_trend == 1:
                    low_max = max(low_max, lowest_low)
                    if ma_high < low_max and current_close < prev_low:
                        x_trend = 1
                        next_trend = 0
                        high_min = highest_high
                
                if next_trend == 0:
                    high_min = min(high_min, highest_high)
                    if ma_low > high_min and current_close > prev_high:
                        x_trend = 0
                        next_trend = 1
                        low_max = lowest_low
                
                line_ht = results[i-1]['line_ht'] if i > 0 else current_close
                if x_trend == 0:
                    line_ht = max(low_max, line_ht)
                if x_trend == 1:
                    line_ht = min(high_min, line_ht)
                
                results.append({'x_trend': x_trend, 'line_ht': line_ht})
            
            return results
        except Exception as e:
            st.error(f"Error calculating X Trend: {str(e)}")
            return [{'x_trend': 0, 'line_ht': data.iloc[i]['close'] if i < len(data) else 0} for i in range(len(data))]

    def create_htf_data(self, data, multiplier=3):
        """Create higher timeframe data"""
        try:
            htf_data = []
            for i in range(0, len(data), multiplier):
                slice_data = data.iloc[i:min(i + multiplier, len(data))]
                if len(slice_data) > 0:
                    htf_bar = {
                        'time': slice_data.iloc[0]['time'],
                        'open': slice_data.iloc[0]['open'],
                        'high': slice_data['high'].max(),
                        'low': slice_data['low'].min(),
                        'close': slice_data.iloc[-1]['close'],
                        'volume': slice_data['volume'].sum()
                    }
                    htf_data.append(htf_bar)
            return pd.DataFrame(htf_data)
        except Exception as e:
            st.error(f"Error creating HTF data: {str(e)}")
            return pd.DataFrame()

    def test_parameters(self, data, pivot_period, atr_factor, atr_period, htf_multiplier=3):
        """Test a parameter combination"""
        try:
            if len(data) < 50:  # Minimum data requirement
                return None
                
            pivot_st = self.calculate_pivot_supertrend(data, pivot_period, atr_factor, atr_period)
            x_trend_local = self.calculate_x_trend(data)
            
            htf_data = self.create_htf_data(data, htf_multiplier)
            if len(htf_data) < 10:
                return None
            
            x_trend_htf = self.calculate_x_trend(htf_data)
            
            # Map HTF to local timeframe
            htf_mapped = []
            for i in range(len(data)):
                htf_index = i // htf_multiplier
                if htf_index < len(x_trend_htf):
                    htf_mapped.append(x_trend_htf[htf_index]['x_trend'])
                else:
                    htf_mapped.append(0)
            
            # Generate signals and calculate trades
            trades = []
            in_trade = False
            current_trade = None
            
            for i in range(1, len(data)):
                if i >= len(pivot_st) or i >= len(htf_mapped):
                    break
                    
                prev_trend = pivot_st[i-1]['trend']
                current_trend = pivot_st[i]['trend']
                pvt_buy = current_trend == 1 and prev_trend == -1
                pvt_sell = current_trend == -1 and prev_trend == 1
                
                x_trend_bullish = htf_mapped[i] == 0
                x_trend_bearish = htf_mapped[i] == 1
                
                buy_signal = pvt_buy and x_trend_bullish
                sell_signal = pvt_sell and x_trend_bearish
                
                if buy_signal or sell_signal:
                    if in_trade and current_trade:
                        current_trade['exit_price'] = data.iloc[i]['close']
                        current_trade['pips'] = (
                            (current_trade['exit_price'] - current_trade['entry_price']) *
                            current_trade['direction']
                        )
                        current_trade['profit'] = current_trade['pips'] > 0
                        trades.append(current_trade)
                    
                    current_trade = {
                        'entry_price': data.iloc[i]['close'],
                        'direction': 1 if buy_signal else -1,
                        'type': 'BUY' if buy_signal else 'SELL'
                    }
                    in_trade = True
            
            if len(trades) == 0:
                return None
            
            # Calculate metrics
            winning_trades = [t for t in trades if t['profit']]
            total_pips = sum(t['pips'] for t in trades)
            win_rate = len(winning_trades) / len(trades) * 100
            avg_win = np.mean([t['pips'] for t in winning_trades]) if winning_trades else 0
            losing_trades = [t for t in trades if not t['profit']]
            avg_loss = abs(np.mean([t['pips'] for t in losing_trades])) if losing_trades else 0
            risk_reward = avg_win / avg_loss if avg_loss > 0 else 0
            
            return {
                'pivot_period': pivot_period,
                'atr_factor': atr_factor,
                'atr_period': atr_period,
                'htf_multiplier': htf_multiplier,
                'total_trades': len(trades),
                'win_rate': win_rate,
                'total_pips': total_pips,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'risk_reward': risk_reward,
                'score': total_pips * 0.4 + win_rate * 3 + risk_reward * 20
            }
        
        except Exception as e:
            st.error(f"Error testing parameters: {str(e)}")
            return None

    def get_htf_timeframe_name(self, base_tf, multiplier):
        """Convert base timeframe and multiplier to readable timeframe"""
        tf_map = {
            ('1m', 2): '2m', ('1m', 3): '3m', ('1m', 4): '4m', ('1m', 5): '5m',
            ('1m', 10): '10m', ('1m', 15): '15m', ('1m', 30): '30m', ('1m', 60): '1h',
            ('5m', 2): '10m', ('5m', 3): '15m', ('5m', 4): '20m', ('5m', 6): '30m',
            ('5m', 12): '1h', ('5m', 24): '2h', ('5m', 48): '4h',
            ('15m', 2): '30m', ('15m', 3): '45m', ('15m', 4): '1h', ('15m', 8): '2h',
            ('15m', 16): '4h', ('15m', 24): '6h', ('15m', 32): '8h',
            ('30m', 2): '1h', ('30m', 4): '2h', ('30m', 8): '4h', ('30m', 16): '8h',
            ('1h', 2): '2h', ('1h', 4): '4h', ('1h', 6): '6h', ('1h', 24): '1d',
            ('1d', 2): '2d', ('1d', 7): '1w', ('1d', 30): '1M'
        }
        
        return tf_map.get((base_tf, multiplier), f"{base_tf}x{multiplier}")

def download_data(optimizer, selected_assets, timeframe, period, min_bars):
    """Download data for selected assets with proper error handling"""
    downloaded_data = {}
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, asset in enumerate(selected_assets):
            try:
                progress_bar.progress((i) / len(selected_assets))
                status_text.text(f"📥 Downloading {asset}...")
                
                yf_symbol = optimizer.assets[asset]['yf_symbol']
                ticker = yf.Ticker(yf_symbol)
                data = ticker.history(period=period, interval=timeframe)
                
                if len(data) >= min_bars:
                    # Format data
                    data.reset_index(inplace=True)
                    if 'Datetime' in data.columns:
                        data['time'] = data['Datetime']
                    elif 'Date' in data.columns:
                        data['time'] = data['Date']
                    
                    data.columns = data.columns.str.lower()
                    required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
                    
                    if all(col in data.columns for col in required_cols):
                        downloaded_data[asset] = data[required_cols]
                        st.success(f"✅ {asset}: {len(data)} bars downloaded")
                    else:
                        st.error(f"❌ {asset}: Missing required columns")
                else:
                    st.error(f"❌ {asset}: Only {len(data)} bars (need {min_bars})")
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                st.error(f"❌ {asset}: Error - {str(e)}")
        
        progress_bar.progress(1.0)
        status_text.text("✅ Download complete!")
    
    return downloaded_data

def run_optimization(optimizer, downloaded_data, htf_multipliers):
    """Run optimization with proper progress tracking and error handling"""
    optimization_results = {}
    
    # Progress tracking
    total_assets = len(downloaded_data)
    progress_container = st.container()
    
    with progress_container:
        main_progress = st.progress(0)
        asset_status = st.empty()
        detail_progress = st.empty()
        
        for asset_idx, (asset, data) in enumerate(downloaded_data.items()):
            try:
                asset_status.text(f"🔄 Optimizing {asset} ({asset_idx + 1}/{total_assets})...")
                main_progress.progress(asset_idx / total_assets)
                
                # Parameter ranges (reduced for faster testing)
                pivot_periods = [3, 4, 5, 6, 7]
                atr_factors = [0.8, 1.0, 1.25, 1.5, 1.75, 2.0]
                atr_periods = [10, 12, 15, 18, 20, 25]
                
                results = []
                total_combinations = len(pivot_periods) * len(atr_factors) * len(atr_periods) * len(htf_multipliers)
                current_combination = 0
                
                for pp in pivot_periods:
                    for af in atr_factors:
                        for ap in atr_periods:
                            for htf_mult in htf_multipliers:
                                current_combination += 1
                                
                                # Update detailed progress every 50 combinations
                                if current_combination % 50 == 0:
                                    detail_progress.text(f"    Progress: {current_combination}/{total_combinations} ({current_combination/total_combinations*100:.1f}%)")
                                
                                result = optimizer.test_parameters(data, pp, af, ap, htf_mult)
                                if result and result['total_trades'] >= 3:
                                    results.append(result)
                
                if results:
                    results.sort(key=lambda x: x['score'], reverse=True)
                    optimization_results[asset] = {
                        'results': results[:10],  # Top 10
                        'best': results[0],
                        'data_info': {
                            'rows': len(data),
                            'timeframe': st.session_state.get('current_timeframe', '5m'),
                            'period': st.session_state.get('current_period', '1mo')
                        }
                    }
                    st.success(f"✅ {asset}: {len(results)} configurations found")
                else:
                    st.warning(f"⚠️ {asset}: No profitable configurations found")
                
            except Exception as e:
                st.error(f"❌ Error optimizing {asset}: {str(e)}")
        
        main_progress.progress(1.0)
        asset_status.text("✅ Optimization complete!")
        detail_progress.empty()
    
    return optimization_results

# Main Streamlit Application
def main():
    if not check_password():
        st.stop()
    
    # Header
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); 
                padding: 30px; border-radius: 15px; margin-bottom: 30px; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 2.5em;">🎯 XPST Optimizer</h1>
        <h3 style="color: #e8f4f8; margin: 10px 0 0 0;">Interactive Trading Strategy Optimizer</h3>
        <p style="color: #b8d4f1; margin: 5px 0 0 0;">Optimize Xtreme Pivot Supertrend parameters with Yahoo Finance data</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize optimizer
    optimizer = StreamlitXPSTOptimizer()
    
    # Sidebar configuration
    st.sidebar.header("📊 Configuration")
    
    # Asset selection
    st.sidebar.subheader("🏦 Select Assets")
    
    crypto_assets = [k for k, v in optimizer.assets.items() if v['type'] == 'Crypto']
    forex_assets = [k for k, v in optimizer.assets.items() if v['type'] == 'Forex']
    commodity_assets = [k for k, v in optimizer.assets.items() if v['type'] == 'Commodity']
    
    selected_crypto = st.sidebar.multiselect(
        "💰 Cryptocurrencies",
        crypto_assets,
        default=[],
        format_func=lambda x: f"{x} ({optimizer.assets[x]['name']})"
    )
    
    selected_forex = st.sidebar.multiselect(
        "💱 Forex Pairs",
        forex_assets,
        default=[],
        format_func=lambda x: f"{x} ({optimizer.assets[x]['name']})"
    )
    
    selected_commodities = st.sidebar.multiselect(
        "🥇 Commodities",
        commodity_assets,
        default=[],
        format_func=lambda x: f"{x} ({optimizer.assets[x]['name']})"
    )
    
    selected_assets = selected_crypto + selected_forex + selected_commodities
    
    # Timeframe selection
    st.sidebar.subheader("⏰ Timeframe Settings")
    
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        options=list(optimizer.timeframes.keys()),
        index=1,  # Default to 5m
        format_func=lambda x: f"{optimizer.timeframes[x]['name']} ({optimizer.timeframes[x]['max_bars']})"
    )
    
    # Update period options based on timeframe
    available_periods = optimizer.timeframes[timeframe]['periods']
    period = st.sidebar.selectbox("Period", available_periods, index=0)
    
    # Store current settings in session state
    st.session_state.current_timeframe = timeframe
    st.session_state.current_period = period
    
    # Advanced settings
    st.sidebar.subheader("⚙️ Advanced Settings")
    min_bars = st.sidebar.number_input("Minimum Bars", min_value=500, max_value=5000, value=1000)
    
    htf_multipliers = st.sidebar.multiselect(
        "HTF Multipliers",
        options=[2, 3, 4, 6, 8, 12, 16],
        default=[2, 3, 4],  # Reduced default for faster testing
        help="Higher timeframe multipliers to test"
    )
    
    # Reset button
    if st.sidebar.button("🔄 Reset All", type="secondary"):
        st.session_state.optimization_results = {}
        st.session_state.downloaded_data = {}
        st.session_state.optimization_complete = False
        st.rerun()
    
    # Main content
    if not selected_assets:
        st.info("👆 Please select at least one asset from the sidebar to get started!")
        
        # Show asset information
        st.subheader("📋 Available Assets")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 💰 Cryptocurrencies")
            for asset in crypto_assets:
                st.markdown(f"• **{asset}**: {optimizer.assets[asset]['name']}")
        
        with col2:
            st.markdown("### 💱 Forex Pairs")
            for asset in forex_assets:
                st.markdown(f"• **{asset}**: {optimizer.assets[asset]['name']}")
        
        with col3:
            st.markdown("### 🥇 Commodities")
            for asset in commodity_assets:
                st.markdown(f"• **{asset}**: {optimizer.assets[asset]['name']}")
        
        return
    
    # Download and optimization section
    st.subheader(f"📥 Data Download & Optimization ({len(selected_assets)} assets selected)")
    
    # Display selected assets
    selected_display = ", ".join([f"{asset} ({optimizer.assets[asset]['name']})" for asset in selected_assets])
    st.info(f"**Selected Assets**: {selected_display}")
    st.info(f"**Settings**: {timeframe} timeframe, {period} period, minimum {min_bars} bars")
    
    # Download and optimize button
    if st.button("🚀 Download Data & Run Optimization", type="primary", use_container_width=True):
        # Clear previous results
        st.session_state.optimization_results = {}
        st.session_state.downloaded_data = {}
        st.session_state.optimization_complete = False
        
        # Download data
        st.markdown("### 📥 Downloading Data...")
        downloaded_data = download_data(optimizer, selected_assets, timeframe, period, min_bars)
        
        if not downloaded_data:
            st.error("No data downloaded successfully. Please adjust settings and try again.")
            return
        
        # Store downloaded data
        st.session_state.downloaded_data = downloaded_data
        
        # Run optimization
        st.markdown("### 🔄 Running Optimization...")
        st.info("This may take several minutes depending on the number of assets and HTF multipliers selected.")
        
        optimization_results = run_optimization(optimizer, downloaded_data, htf_multipliers)
        
        # Store results
        st.session_state.optimization_