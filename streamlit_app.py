# Stable Full XPST Optimizer - Built on working foundation
# Enhanced with full optimization features and robust error handling

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import time
import warnings

warnings.filterwarnings('ignore')

# Set page configuration
st.set_page_config(
    page_title="XPST Optimizer",
    page_icon="🎯",
    layout="wide"
)

# Initialize session state
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = {}
if 'downloaded_data' not in st.session_state:
    st.session_state.downloaded_data = {}

# Password protection
def check_password():
    def password_entered():
        if st.session_state["password"] == "XPST2024!":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("## 🔒 Private XPST Optimizer Access")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password")
        return False
    else:
        return True

# XPST Calculation Functions
def calculate_atr(data, period=15):
    """Calculate Average True Range safely"""
    try:
        tr_list = []
        for i in range(1, min(len(data), 1000)):  # Limit for performance
            tr = max(
                data.iloc[i]['high'] - data.iloc[i]['low'],
                abs(data.iloc[i]['high'] - data.iloc[i-1]['close']),
                abs(data.iloc[i]['low'] - data.iloc[i-1]['close'])
            )
            tr_list.append(tr)
        
        atr_values = [tr_list[0] if tr_list else 1]
        for i in range(len(tr_list)):
            if i < period - 1:
                atr_values.append(np.mean(tr_list[:i+1]))
            else:
                atr_values.append(np.mean(tr_list[i-period+1:i+1]))
        
        return atr_values
    except:
        return [1] * len(data)

def find_pivots(data, period=5, pivot_type='high'):
    """Find pivot points safely"""
    try:
        pivots = [None] * len(data)
        price_col = 'high' if pivot_type == 'high' else 'low'
        
        for i in range(period, min(len(data) - period, 500)):  # Limit for performance
            current_price = data.iloc[i][price_col]
            is_pivot = True
            
            for j in range(1, period + 1):
                if pivot_type == 'high':
                    if (data.iloc[i-j][price_col] >= current_price or 
                        data.iloc[i+j][price_col] >= current_price):
                        is_pivot = False
                        break
                else:
                    if (data.iloc[i-j][price_col] <= current_price or 
                        data.iloc[i+j][price_col] <= current_price):
                        is_pivot = False
                        break
            
            if is_pivot:
                pivots[i] = current_price
        
        return pivots
    except:
        return [None] * len(data)

def calculate_pivot_supertrend(data, pivot_period=5, atr_factor=1.25, atr_period=15):
    """Calculate Pivot Supertrend with error handling"""
    try:
        if len(data) < 50:
            return None
            
        pivot_highs = find_pivots(data, pivot_period, 'high')
        pivot_lows = find_pivots(data, pivot_period, 'low')
        atr_values = calculate_atr(data, atr_period)
        
        results = []
        center = None
        
        for i in range(min(len(data), 500)):  # Limit for performance
            # Update center
            if (i < len(pivot_highs) and pivot_highs[i] is not None) or \
               (i < len(pivot_lows) and pivot_lows[i] is not None):
                lastpp = pivot_highs[i] if (i < len(pivot_highs) and pivot_highs[i]) else pivot_lows[i]
                center = lastpp if center is None else (center * 2 + lastpp) / 3
            
            if center is None or i == 0:
                results.append({'trend': 1})
                continue
            
            # Calculate supertrend
            atr_val = atr_values[i] if i < len(atr_values) else atr_values[-1]
            up = center - (atr_factor * atr_val)
            down = center + (atr_factor * atr_val)
            
            prev = results[i-1] if results else {'trend': 1, 'up': up, 'down': down}
            prev_close = data.iloc[i-1]['close'] if i > 0 else data.iloc[i]['close']
            current_close = data.iloc[i]['close']
            
            t_up = max(up, prev.get('up', up)) if prev_close > prev.get('up', up) else up
            t_down = min(down, prev.get('down', down)) if prev_close < prev.get('down', down) else down
            
            if current_close > prev.get('down', down):
                trend = 1
            elif current_close < prev.get('up', up):
                trend = -1
            else:
                trend = prev.get('trend', 1)
            
            results.append({'trend': trend, 'up': t_up, 'down': t_down})
        
        return results
    except Exception as e:
        st.error(f"Error in Pivot Supertrend calculation: {str(e)}")
        return None

def calculate_x_trend(data):
    """Calculate X Trend with error handling"""
    try:
        if len(data) < 10:
            return None
            
        results = []
        next_trend = 0
        x_trend = 0
        low_max = 0
        high_min = 0
        
        for i in range(min(len(data), 500)):  # Limit for performance
            if i < 3:
                results.append({'x_trend': 0})
                continue
            
            # Simple calculations
            start_idx = max(0, i-2)
            lowest_low = data.iloc[start_idx:i+1]['low'].min()
            
            start_idx_high = max(0, i-1)
            highest_high = data.iloc[start_idx_high:i+1]['high'].max()
            
            ma_low = data.iloc[max(0, i-2):i+1]['low'].mean()
            ma_high = data.iloc[max(0, i-1):i+1]['high'].mean()
            
            if i == 3:
                low_max = lowest_low
                high_min = highest_high
            
            current_close = data.iloc[i]['close']
            prev_low = data.iloc[i-1]['low'] if i > 0 else current_close
            prev_high = data.iloc[i-1]['high'] if i > 0 else current_close
            
            # X Trend logic
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
            
            results.append({'x_trend': x_trend})
        
        return results
    except Exception as e:
        st.error(f"Error in X Trend calculation: {str(e)}")
        return None

def test_parameters(data, pivot_period, atr_factor, atr_period, htf_multiplier):
    """Test parameter combination with comprehensive error handling"""
    try:
        # Limit data size for performance
        if len(data) > 1000:
            data = data.tail(1000).copy()
        
        # Calculate indicators
        pivot_st = calculate_pivot_supertrend(data, pivot_period, atr_factor, atr_period)
        x_trend_local = calculate_x_trend(data)
        
        if not pivot_st or not x_trend_local:
            return None
        
        # Create HTF data
        htf_data = []
        for i in range(0, len(data), htf_multiplier):
            slice_data = data.iloc[i:min(i + htf_multiplier, len(data))]
            if len(slice_data) > 0:
                htf_bar = pd.DataFrame([{
                    'time': slice_data.iloc[0]['time'],
                    'open': slice_data.iloc[0]['open'],
                    'high': slice_data['high'].max(),
                    'low': slice_data['low'].min(),
                    'close': slice_data.iloc[-1]['close'],
                    'volume': slice_data['volume'].sum()
                }])
                htf_data.append(htf_bar)
        
        if len(htf_data) < 10:
            return None
        
        htf_df = pd.concat(htf_data, ignore_index=True)
        x_trend_htf = calculate_x_trend(htf_df)
        
        if not x_trend_htf:
            return None
        
        # Map HTF to local timeframe
        htf_mapped = []
        for i in range(len(data)):
            htf_index = i // htf_multiplier
            if htf_index < len(x_trend_htf):
                htf_mapped.append(x_trend_htf[htf_index]['x_trend'])
            else:
                htf_mapped.append(0)
        
        # Generate signals
        trades = []
        in_trade = False
        current_trade = None
        
        max_trades = 50  # Limit trades for performance
        
        for i in range(1, min(len(data), len(pivot_st), len(htf_mapped))):
            if len(trades) >= max_trades:
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
                }
                in_trade = True
        
        if len(trades) < 3:
            return None
        
        # Calculate metrics
        winning_trades = [t for t in trades if t['profit']]
        total_pips = sum(t['pips'] for t in trades)
        win_rate = len(winning_trades) / len(trades) * 100
        avg_win = np.mean([t['pips'] for t in winning_trades]) if winning_trades else 0
        losing_trades = [t for t in trades if not t['profit']]
        avg_loss = abs(np.mean([t['pips'] for t in losing_trades])) if losing_trades else 1
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
        return None

# Main application
def main():
    if not check_password():
        st.stop()
    
    # Header
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); 
                padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🎯 XPST Optimizer</h1>
        <p style="color: #e8f4f8; margin: 5px 0 0 0;">Interactive Trading Strategy Optimizer</p>
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
    
    # Asset selection
    selected_assets = st.sidebar.multiselect(
        "Select Assets",
        options=list(assets.keys()),
        default=['EURUSD'],
        format_func=lambda x: f"{x} ({assets[x]['name']})"
    )
    
    # Timeframe selection
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        options=['5m', '15m', '30m', '1h'],
        index=1  # Default to 15m
    )
    
    timeframe_periods = {
        '5m': ['1d', '5d', '1mo'],
        '15m': ['1d', '5d', '1mo', '3mo'],
        '30m': ['5d', '1mo', '3mo', '6mo'],
        '1h': ['1mo', '3mo', '6mo', '1y']
    }
    
    period = st.sidebar.selectbox(
        "Period",
        options=timeframe_periods[timeframe],
        index=-1  # Last option
    )
    
    # Advanced settings
    st.sidebar.subheader("⚙️ Advanced Settings")
    min_bars = st.sidebar.number_input("Minimum Bars", 500, 2000, 800)
    
    htf_multipliers = st.sidebar.multiselect(
        "HTF Multipliers",
        options=[2, 3, 4, 6, 8],
        default=[2, 3, 4],
        help="Higher timeframe multipliers to test"
    )
    
    # Main content
    if not selected_assets:
        st.info("👆 Please select at least one asset from the sidebar")
        st.stop()
    
    st.subheader(f"📥 Selected: {len(selected_assets)} assets, {timeframe} timeframe")
    
    # Download and optimize
    if st.button("🚀 Download Data & Run Optimization", type="primary"):
        # Clear previous results
        st.session_state.optimization_results = {}
        st.session_state.downloaded_data = {}
        
        # Download data
        st.markdown("### 📥 Downloading Data...")
        downloaded_data = {}
        
        progress_bar = st.progress(0)
        for i, asset in enumerate(selected_assets):
            progress_bar.progress(i / len(selected_assets))
            
            try:
                with st.spinner(f"Downloading {asset}..."):
                    yf_symbol = assets[asset]['yf']
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
                        downloaded_data[asset] = data
                        st.success(f"✅ {asset}: {len(data)} bars")
                    else:
                        st.error(f"❌ {asset}: Only {len(data)} bars (need {min_bars})")
                
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                st.error(f"❌ {asset}: {str(e)}")
        
        progress_bar.progress(1.0)
        
        if not downloaded_data:
            st.error("No data downloaded successfully")
            st.stop()
        
        # Store downloaded data
        st.session_state.downloaded_data = downloaded_data
        
        # Run optimization
        st.markdown("### 🔄 Running Optimization...")
        optimization_results = {}
        
        total_assets = len(downloaded_data)
        main_progress = st.progress(0)
        
        for asset_idx, (asset, data) in enumerate(downloaded_data.items()):
            main_progress.progress(asset_idx / total_assets)
            
            with st.spinner(f"Optimizing {asset}... ({asset_idx + 1}/{total_assets})"):
                try:
                    # Reduced parameter ranges for faster processing
                    pivot_periods = [3, 5, 7]
                    atr_factors = [1.0, 1.25, 1.5]
                    atr_periods = [10, 15, 20]
                    
                    results = []
                    total_combos = len(pivot_periods) * len(atr_factors) * len(atr_periods) * len(htf_multipliers)
                    current_combo = 0
                    
                    for pp in pivot_periods:
                        for af in atr_factors:
                            for ap in atr_periods:
                                for htf in htf_multipliers:
                                    current_combo += 1
                                    
                                    result = test_parameters(data, pp, af, ap, htf)
                                    if result and result['total_trades'] >= 3:
                                        results.append(result)
                    
                    if results:
                        results.sort(key=lambda x: x['score'], reverse=True)
                        optimization_results[asset] = {
                            'results': results[:5],  # Top 5
                            'best': results[0],
                            'data_info': {
                                'rows': len(data),
                                'timeframe': timeframe,
                                'period': period
                            }
                        }
                        st.success(f"✅ {asset}: {len(results)} configurations found")
                    else:
                        st.warning(f"⚠️ {asset}: No profitable configurations found")
                
                except Exception as e:
                    st.error(f"❌ {asset}: Optimization error - {str(e)}")
        
        main_progress.progress(1.0)
        
        # Store results
        st.session_state.optimization_results = optimization_results
        
        # Force refresh to show results
        st.rerun()
    
    # Display results
    if st.session_state.optimization_results:
        st.markdown("---")
        st.subheader("🏆 Optimization Results")
        
        for asset, results in st.session_state.optimization_results.items():
            with st.expander(f"📊 {asset} - Score: {results['best']['score']:.0f}", expanded=True):
                best = results['best']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 🎯 Optimal Parameters")
                    st.write(f"**Pivot Period**: {best['pivot_period']}")
                    st.write(f"**ATR Factor**: {best['atr_factor']}")
                    st.write(f"**ATR Period**: {best['atr_period']}")
                    st.write(f"**HTF Multiplier**: {best['htf_multiplier']}x")
                
                with col2:
                    st.markdown("#### 📈 Performance")
                    st.write(f"**Total Trades**: {best['total_trades']}")
                    st.write(f"**Win Rate**: {best['win_rate']:.1f}%")
                    st.write(f"**Total Pips**: {best['total_pips']:.2f}")
                    st.write(f"**Risk:Reward**: {best['risk_reward']:.2f}:1")
                
                # PineScript settings
                st.markdown("#### ⚙️ PineScript Settings")
                st.code(f"""
// XPST Settings for {asset}
prd = {best['pivot_period']}
Factor = {best['atr_factor']}
Pd = {best['atr_period']}
use_xtrend = true
use_xtrend_htf_color = true
xtrend_htf_tf = "{timeframe}"
""", language="pinescript")
    
    # Footer
    st.markdown("---")
    st.markdown("🎯 **XPST Optimizer** | Built with Streamlit & Yahoo Finance")

if __name__ == "__main__":
    main()