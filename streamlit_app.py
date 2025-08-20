# Fixed XPST Optimizer - All variable scope and logic issues resolved

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
if 'custom_assets' not in st.session_state:
    st.session_state.custom_assets = {}

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

def validate_custom_ticker(symbol):
    """Validate custom ticker symbol and suggest alternatives"""
    try:
        ticker = yf.Ticker(symbol)
        test_data = ticker.history(period="5d", interval="1d")
        
        if len(test_data) > 0:
            try:
                info = ticker.info
                name = info.get('longName', info.get('shortName', symbol))
                if len(name) > 50:
                    name = name[:47] + "..."
            except:
                name = symbol
            
            return {
                'valid': True,
                'symbol': symbol,
                'name': name,
                'suggestions': []
            }
        else:
            suggestions = generate_ticker_suggestions(symbol)
            return {
                'valid': False,
                'symbol': symbol,
                'name': None,
                'suggestions': suggestions
            }
    
    except Exception as e:
        suggestions = generate_ticker_suggestions(symbol)
        return {
            'valid': False,
            'symbol': symbol,
            'name': None,
            'suggestions': suggestions
        }

def generate_ticker_suggestions(symbol):
    """Generate ticker symbol suggestions based on common patterns"""
    suggestions = []
    
    variations = [
        f"{symbol}.L",     # London Stock Exchange
        f"{symbol}.TO",    # Toronto Stock Exchange  
        f"{symbol}.AX",    # Australian Securities Exchange
        f"{symbol}.DE",    # German exchanges
        f"{symbol}.PA",    # Paris Stock Exchange
        f"{symbol}=X",     # Forex pairs
        f"{symbol}-USD",   # Crypto pairs
        f"{symbol}USD",    # Alternative crypto format
        f"^{symbol}",      # Indices
    ]
    
    for variant in variations:
        try:
            test_ticker = yf.Ticker(variant)
            test_data = test_ticker.history(period="2d", interval="1d")
            if len(test_data) > 0:
                suggestions.append(variant)
                if len(suggestions) >= 3:
                    break
        except:
            continue
    
    if not suggestions:
        if len(symbol) == 6 and symbol.isalpha():
            suggestions.append(f"{symbol}=X")
        if len(symbol) <= 5:
            suggestions.extend([f"{symbol}-USD", f"{symbol}USD"])
        if len(symbol) <= 4:
            suggestions.extend([f"{symbol}.L", f"^{symbol}"])
    
    return suggestions[:3]

# XPST Calculation Functions
def calculate_atr(data, period=15):
    """Calculate Average True Range safely"""
    try:
        if len(data) < 2:
            return [1] * len(data)
            
        tr_list = []
        for i in range(1, min(len(data), 1000)):
            try:
                tr = max(
                    data.iloc[i]['high'] - data.iloc[i]['low'],
                    abs(data.iloc[i]['high'] - data.iloc[i-1]['close']),
                    abs(data.iloc[i]['low'] - data.iloc[i-1]['close'])
                )
                tr_list.append(tr)
            except:
                tr_list.append(1)  # Default value
        
        if not tr_list:
            return [1] * len(data)
            
        atr_values = [tr_list[0] if tr_list else 1]
        for i in range(len(tr_list)):
            if i < period - 1:
                atr_values.append(np.mean(tr_list[:i+1]))
            else:
                atr_values.append(np.mean(tr_list[max(0, i-period+1):i+1]))
        
        return atr_values
    except Exception as e:
        return [1] * len(data)

def find_pivots(data, period=5, pivot_type='high'):
    """Find pivot points safely"""
    try:
        pivots = [None] * len(data)
        price_col = 'high' if pivot_type == 'high' else 'low'
        
        for i in range(period, min(len(data) - period, 500)):
            try:
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
            except:
                continue
        
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
        
        for i in range(min(len(data), 500)):
            try:
                if (i < len(pivot_highs) and pivot_highs[i] is not None) or \
                   (i < len(pivot_lows) and pivot_lows[i] is not None):
                    lastpp = pivot_highs[i] if (i < len(pivot_highs) and pivot_highs[i]) else pivot_lows[i]
                    center = lastpp if center is None else (center * 2 + lastpp) / 3
                
                if center is None or i == 0:
                    results.append({'trend': 1})
                    continue
                
                atr_val = atr_values[i] if i < len(atr_values) else (atr_values[-1] if atr_values else 1)
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
            except:
                results.append({'trend': 1, 'up': 0, 'down': 0})
        
        return results
    except Exception as e:
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
        
        for i in range(min(len(data), 500)):
            try:
                if i < 3:
                    results.append({'x_trend': 0})
                    continue
                
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
            except:
                results.append({'x_trend': 0})
        
        return results
    except Exception as e:
        return None

def calculate_adx(data, period=14):
    """Calculate ADX (Average Directional Index) safely"""
    try:
        if len(data) < period + 1:
            return [25] * len(data)  # Return default ADX value
        
        tr_list = []
        for i in range(1, len(data)):
            try:
                tr = max(
                    data.iloc[i]['high'] - data.iloc[i]['low'],
                    abs(data.iloc[i]['high'] - data.iloc[i-1]['close']),
                    abs(data.iloc[i]['low'] - data.iloc[i-1]['close'])
                )
                tr_list.append(tr)
            except:
                tr_list.append(1)
        
        dm_plus = []
        dm_minus = []
        for i in range(1, len(data)):
            try:
                high_diff = data.iloc[i]['high'] - data.iloc[i-1]['high']
                low_diff = data.iloc[i-1]['low'] - data.iloc[i]['low']
                
                dm_plus.append(high_diff if (high_diff > low_diff and high_diff > 0) else 0)
                dm_minus.append(low_diff if (low_diff > high_diff and low_diff > 0) else 0)
            except:
                dm_plus.append(0)
                dm_minus.append(0)
        
        def smooth_series(series, period):
            smoothed = []
            for i in range(len(series)):
                if i < period - 1:
                    smoothed.append(np.mean(series[:i+1]) if series[:i+1] else 0)
                else:
                    smoothed.append(np.mean(series[max(0, i-period+1):i+1]))
            return smoothed
        
        tr_smooth = smooth_series(tr_list, period)
        dm_plus_smooth = smooth_series(dm_plus, period)
        dm_minus_smooth = smooth_series(dm_minus, period)
        
        di_plus = [(dm_plus_smooth[i] / tr_smooth[i]) * 100 if tr_smooth[i] != 0 else 0 
                   for i in range(len(tr_smooth))]
        di_minus = [(dm_minus_smooth[i] / tr_smooth[i]) * 100 if tr_smooth[i] != 0 else 0 
                    for i in range(len(tr_smooth))]
        
        dx = []
        for i in range(len(di_plus)):
            di_sum = di_plus[i] + di_minus[i]
            if di_sum != 0:
                dx.append(abs(di_plus[i] - di_minus[i]) / di_sum * 100)
            else:
                dx.append(0)
        
        adx = smooth_series(dx, period)
        return [25] + adx  # Default first value
    except:
        return [25] * len(data)

def calculate_ema(data, period=21):
    """Calculate EMA (Exponential Moving Average) safely"""
    try:
        if len(data) < period:
            return data['close'].tolist()
        
        ema_values = []
        multiplier = 2 / (period + 1)
        
        # Use SMA for initial EMA value
        sma = data['close'].iloc[:period].mean()
        ema_values.extend([sma] * period)
        
        for i in range(period, len(data)):
            try:
                ema = (data['close'].iloc[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
                ema_values.append(ema)
            except:
                ema_values.append(ema_values[-1] if ema_values else data['close'].iloc[i])
        
        return ema_values
    except:
        return data['close'].tolist()

def run_sequential_optimization(data, asset, use_xtrend, htf_multipliers, use_adx, adx_thresholds, use_ema, ema_periods):
    """Run intelligent sequential optimization for Fast Mode"""
    results = []
    
    st.markdown(f"#### 🔄 Sequential Optimization for {asset}")
    
    # Determine HTF multipliers to test
    if use_xtrend:
        if htf_multipliers:
            # Test 1x (local) + selected HTF multipliers
            test_htf_multipliers = [1] + htf_multipliers
            st.caption(f"🔄 X Trend enabled: Testing 1x + {htf_multipliers}")
        else:
            # Only test 1x (local timeframe)
            test_htf_multipliers = [1]
            st.caption("🔄 X Trend enabled: Testing 1x (local timeframe only)")
    else:
        # No X Trend filter - use dummy HTF (won't be used in signals)
        test_htf_multipliers = [1]
        st.caption("⚠️ X Trend disabled: Using Pivot Supertrend only")
    
    # Stage 1: Find optimal Pivot Period + ATR Factor combination
    st.caption("🎯 Stage 1: Optimizing Pivot Period + ATR Factor...")
    stage1_results = []
    
    pivot_options = [3, 5, 7]
    atr_factor_options = [1.0, 1.25, 1.5]
    
    for pp in pivot_options:
        for af in atr_factor_options:
            result = test_parameters(data, pp, af, 15, 1, use_xtrend, False, 25, False, 21)  # Fixed defaults
            if result and result['total_trades'] >= 3:
                stage1_results.append((result['score'], pp, af))
    
    if not stage1_results:
        st.error(f"❌ {asset}: No valid Stage 1 results")
        return []
    
    # Get best Pivot + ATR combination
    stage1_results.sort(reverse=True)
    best_pp, best_af = stage1_results[0][1], stage1_results[0][2]
    st.success(f"✅ Stage 1: Best Pivot={best_pp}, ATR Factor={best_af} (Score: {stage1_results[0][0]:.0f})")
    
    # Stage 2: Optimize ATR Period with best Pivot + ATR Factor
    st.caption("📊 Stage 2: Optimizing ATR Period...")
    stage2_results = []
    
    atr_period_options = [10, 15, 20]
    
    for ap in atr_period_options:
        result = test_parameters(data, best_pp, best_af, ap, 1, use_xtrend, False, 25, False, 21)
        if result and result['total_trades'] >= 3:
            stage2_results.append((result['score'], ap))
    
    if not stage2_results:
        best_ap = 15  # Default fallback
    else:
        stage2_results.sort(reverse=True)
        best_ap = stage2_results[0][1]
        st.success(f"✅ Stage 2: Best ATR Period={best_ap} (Score: {stage2_results[0][0]:.0f})")
    
    # Stage 3: Optimize HTF with best core parameters (only if X Trend enabled)
    if use_xtrend and len(test_htf_multipliers) > 1:
        st.caption("🔄 Stage 3: Optimizing HTF Multiplier...")
        stage3_results = []
        
        for htf in test_htf_multipliers[:4]:  # Limit for speed
            result = test_parameters(data, best_pp, best_af, best_ap, htf, use_xtrend, False, 25, False, 21)
            if result and result['total_trades'] >= 3:
                stage3_results.append((result['score'], htf))
        
        if not stage3_results:
            best_htf = 1  # Default to local timeframe
        else:
            stage3_results.sort(reverse=True)
            best_htf = stage3_results[0][1]
            if best_htf == 1:
                st.success(f"✅ Stage 3: Best HTF = 1x (local timeframe) (Score: {stage3_results[0][0]:.0f})")
            else:
                st.success(f"✅ Stage 3: Best HTF Multiplier={best_htf}x (Score: {stage3_results[0][0]:.0f})")
    else:
        best_htf = 1  # Use local timeframe
        if use_xtrend:
            st.success("✅ Stage 3: Using 1x (local timeframe only)")
        else:
            st.success("✅ Stage 3: X Trend disabled - using local timeframe")
    
    # Add best core configuration to results
    best_core_result = test_parameters(data, best_pp, best_af, best_ap, best_htf, use_xtrend, False, 25, False, 21)
    if best_core_result:
        results.append(best_core_result)
    
    # Stage 4: Optimize ADX if enabled
    if use_adx and adx_thresholds:
        st.caption("🎲 Stage 4: Optimizing ADX Filter...")
        best_adx_score = 0
        best_adx_threshold = 25
        
        for threshold in [20, 25, 30]:  # Limited set for speed
            result = test_parameters(data, best_pp, best_af, best_ap, best_htf, use_xtrend, True, threshold, False, 21)
            if result and result['total_trades'] >= 3:
                results.append(result)
                if result['score'] > best_adx_score:
                    best_adx_score = result['score']
                    best_adx_threshold = threshold
        
        if best_adx_score > 0:
            st.success(f"✅ Stage 4: Best ADX Threshold={best_adx_threshold} (Score: {best_adx_score:.0f})")
    
    # Stage 5: Optimize EMA if enabled
    if use_ema and ema_periods:
        st.caption("📈 Stage 5: Optimizing EMA Filter...")
        best_ema_score = 0
        best_ema_period = 21
        
        for period in [21, 50, 100]:  # Limited set for speed
            result = test_parameters(data, best_pp, best_af, best_ap, best_htf, use_xtrend, False, 25, True, period)
            if result and result['total_trades'] >= 3:
                results.append(result)
                if result['score'] > best_ema_score:
                    best_ema_score = result['score']
                    best_ema_period = period
        
        if best_ema_score > 0:
            st.success(f"✅ Stage 5: Best EMA Period={best_ema_period} (Score: {best_ema_score:.0f})")
    
    # Stage 6: Test combined filters if both enabled
    if use_adx and use_ema and adx_thresholds and ema_periods:
        st.caption("🔗 Stage 6: Testing Combined Filters...")
        
        # Use best individual filter settings found in stages 4 & 5
        best_adx_threshold = 25  # Default if not found above
        best_ema_period = 21     # Default if not found above
        
        # Find actual best values from previous results
        for result in results:
            if result.get('use_adx') and not result.get('use_ema'):
                best_adx_threshold = result.get('adx_threshold', 25)
            elif result.get('use_ema') and not result.get('use_adx'):
                best_ema_period = result.get('ema_period', 21)
        
        combined_result = test_parameters(data, best_pp, best_af, best_ap, best_htf, use_xtrend,
                                        True, best_adx_threshold, True, best_ema_period)
        if combined_result and combined_result['total_trades'] >= 3:
            results.append(combined_result)
            st.success(f"✅ Stage 6: Combined filters (Score: {combined_result['score']:.0f})")
    
    st.success(f"🎉 Sequential optimization complete! Found {len(results)} valid configurations")
    return results

def run_matrix_optimization(data, asset, pivot_periods, atr_factors, atr_periods, use_xtrend, htf_multipliers, filter_combinations):
    """Run traditional matrix optimization for Balanced/Comprehensive modes"""
    results = []
    
    # Determine HTF multipliers to test
    if use_xtrend:
        if htf_multipliers:
            test_htf_multipliers = [1] + htf_multipliers
        else:
            test_htf_multipliers = [1]
    else:
        test_htf_multipliers = [1]
    
    total_combos = (len(pivot_periods) * len(atr_factors) * 
                   len(atr_periods) * len(test_htf_multipliers) * 
                   len(filter_combinations))
    current_combo = 0
    
    st.info(f"🔄 Matrix optimization: {total_combos} combinations")
    
    for pp in pivot_periods:
        for af in atr_factors:
            for ap in atr_periods:
                for htf in test_htf_multipliers:
                    for filters in filter_combinations:
                        current_combo += 1
                        
                        if current_combo % 20 == 0:
                            progress_text = f"    {asset}: {current_combo}/{total_combos} ({current_combo/total_combos*100:.1f}%)"
                            st.caption(progress_text)
                        
                        result = test_parameters(
                            data, pp, af, ap, htf, use_xtrend,
                            use_adx=filters.get('use_adx', False),
                            adx_threshold=filters.get('adx_threshold', 25),
                            use_ema=filters.get('use_ema', False),
                            ema_period=filters.get('ema_period', 21)
                        )
                        if result and result['total_trades'] >= 3:
                            results.append(result)
    
    return results

def test_parameters(data, pivot_period, atr_factor, atr_period, htf_multiplier, use_xtrend=True,
                   use_adx=False, adx_threshold=25, use_ema=False, ema_period=21):
    """Test parameter combination with comprehensive error handling"""
    try:
        # Limit data size for performance
        if len(data) > 1000:
            data = data.tail(1000).copy()
        
        # Calculate indicators
        pivot_st = calculate_pivot_supertrend(data, pivot_period, atr_factor, atr_period)
        
        if not pivot_st:
            return None
        
        # Calculate X Trend only if enabled
        if use_xtrend:
            x_trend_local = calculate_x_trend(data)
            if not x_trend_local:
                return None
            
            # Create HTF data only if htf_multiplier > 1
            if htf_multiplier > 1:
                htf_data = []
                for i in range(0, len(data), htf_multiplier):
                    try:
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
                    except:
                        continue
                
                if len(htf_data) < 10:
                    return None
                
                htf_df = pd.concat(htf_data, ignore_index=True)
                x_trend_htf = calculate_x_trend(htf_df)
                
                if not x_trend_htf:
                    return None
                
                # Map HTF to local timeframe safely
                htf_mapped = []
                for i in range(len(data)):
                    htf_index = min(i // htf_multiplier, len(x_trend_htf) - 1)
                    htf_mapped.append(x_trend_htf[htf_index]['x_trend'])
            else:
                # Use local X Trend (1x timeframe)
                htf_mapped = [x_trend['x_trend'] for x_trend in x_trend_local]
        else:
            # X Trend disabled - create dummy values (won't be used in signals)
            htf_mapped = [0] * len(data)
        
        # Calculate filters
        adx_values = calculate_adx(data) if use_adx else None
        ema_values = calculate_ema(data, ema_period) if use_ema else None
        
        # Simulate trades
        trades = []
        in_trade = False
        current_trade = None
        max_trades = 50
        
        for i in range(1, min(len(data), len(pivot_st), len(htf_mapped))):
            if len(trades) >= max_trades:
                break
                
            try:
                prev_trend = pivot_st[i-1]['trend']
                current_trend = pivot_st[i]['trend']
                
                pvt_buy = current_trend == 1 and prev_trend == -1
                pvt_sell = current_trend == -1 and prev_trend == 1
                
                # X Trend filter (only if enabled)
                if use_xtrend:
                    x_trend_bullish = htf_mapped[i] == 0
                    x_trend_bearish = htf_mapped[i] == 1
                else:
                    # X Trend disabled - always pass
                    x_trend_bullish = True
                    x_trend_bearish = True
                
                # ADX filter
                adx_filter_passed = True
                if use_adx and adx_values and i < len(adx_values):
                    adx_filter_passed = adx_values[i] >= adx_threshold
                
                # EMA filter
                ema_filter_bullish = True
                ema_filter_bearish = True
                if use_ema and ema_values and i < len(ema_values):
                    current_close = data.iloc[i]['close']
                    ema_filter_bullish = current_close > ema_values[i]
                    ema_filter_bearish = current_close < ema_values[i]
                
                buy_signal = (pvt_buy and x_trend_bullish and 
                             adx_filter_passed and ema_filter_bullish)
                sell_signal = (pvt_sell and x_trend_bearish and 
                              adx_filter_passed and ema_filter_bearish)
                
                if buy_signal or sell_signal:
                    # Close existing trade
                    if in_trade and current_trade:
                        current_trade['exit_price'] = data.iloc[i]['close']
                        current_trade['pips'] = (
                            (current_trade['exit_price'] - current_trade['entry_price']) *
                            current_trade['direction']
                        )
                        current_trade['profit'] = current_trade['pips'] > 0
                        trades.append(current_trade)
                    
                    # Open new trade
                    current_trade = {
                        'entry_price': data.iloc[i]['close'],
                        'direction': 1 if buy_signal else -1,
                    }
                    in_trade = True
            except:
                continue
        
        if len(trades) < 3:
            return None
        
        # Calculate performance metrics
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
            'use_xtrend': use_xtrend,
            'use_adx': use_adx,
            'adx_threshold': adx_threshold if use_adx else None,
            'use_ema': use_ema,
            'ema_period': ema_period if use_ema else None,
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
        'BTCUSD': {'yf': 'BTC-USD', 'name': 'Bitcoin/USD', 'type': 'Crypto'},
        'ETHUSD': {'yf': 'ETH-USD', 'name': 'Ethereum/USD', 'type': 'Crypto'},
        'XAUUSD': {'yf': 'GC=F', 'name': 'Gold/USD', 'type': 'Commodity'},
        'EURUSD': {'yf': 'EURUSD=X', 'name': 'Euro/USD', 'type': 'Forex'},
        'GBPUSD': {'yf': 'GBPUSD=X', 'name': 'GBP/USD', 'type': 'Forex'},
        'USDJPY': {'yf': 'USDJPY=X', 'name': 'USD/JPY', 'type': 'Forex'},
        'AUDUSD': {'yf': 'AUDUSD=X', 'name': 'AUD/USD', 'type': 'Forex'},
        'USDCAD': {'yf': 'USDCAD=X', 'name': 'USD/CAD', 'type': 'Forex'}
    }
    
    # Sidebar configuration
    st.sidebar.header("📊 Configuration")
    
    # Asset selection
    st.sidebar.subheader("🏦 Select Assets")
    
    selected_assets = st.sidebar.multiselect(
        "Predefined Assets",
        options=list(assets.keys()),
        default=['EURUSD'],
        format_func=lambda x: f"{x} ({assets[x]['name']})"
    )
    
    # Custom ticker input
    st.sidebar.markdown("**Add Custom Ticker:**")
    custom_ticker = st.sidebar.text_input(
        "Enter Symbol (e.g., AAPL, TSLA, SPY)",
        placeholder="Type ticker symbol...",
        help="Enter any Yahoo Finance symbol. We'll validate and suggest alternatives if needed."
    )
    
    # Custom ticker validation and addition
    if custom_ticker:
        custom_ticker = custom_ticker.upper().strip()
        
        if st.sidebar.button(f"➕ Add {custom_ticker}"):
            test_result = validate_custom_ticker(custom_ticker)
            
            if test_result['valid']:
                custom_key = f"CUSTOM_{custom_ticker}"
                st.session_state.custom_assets[custom_key] = {
                    'yf': test_result['symbol'], 
                    'name': test_result['name'],
                    'type': 'Custom'
                }
                st.sidebar.success(f"✅ Added: {test_result['name']}")
                st.rerun()
                
            else:
                st.sidebar.error(f"❌ Symbol '{custom_ticker}' not found")
                if test_result['suggestions']:
                    st.sidebar.warning("💡 Did you mean one of these?")
                    for suggestion in test_result['suggestions']:
                        if st.sidebar.button(f"Use {suggestion}", key=f"suggest_{suggestion}"):
                            custom_key = f"CUSTOM_{suggestion}"
                            test_suggestion = validate_custom_ticker(suggestion)
                            if test_suggestion['valid']:
                                st.session_state.custom_assets[custom_key] = {
                                    'yf': test_suggestion['symbol'],
                                    'name': test_suggestion['name'],
                                    'type': 'Custom'
                                }
                                st.sidebar.success(f"✅ Added: {test_suggestion['name']}")
                                st.rerun()
    
    # Show selected custom assets
    if st.session_state.custom_assets:
        st.sidebar.markdown("**Custom Assets Added:**")
        assets_to_remove = []
        for asset_key, asset_info in st.session_state.custom_assets.items():
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.caption(f"• {asset_info['name']}")
            with col2:
                if st.button("❌", key=f"remove_{asset_key}", help="Remove"):
                    assets_to_remove.append(asset_key)
        
        for asset_key in assets_to_remove:
            del st.session_state.custom_assets[asset_key]
            st.rerun()
    
    # Combine all assets and create final selection list
    all_assets = assets.copy()
    all_assets.update(st.session_state.custom_assets)
    custom_asset_keys = list(st.session_state.custom_assets.keys())
    all_selected_assets = selected_assets + custom_asset_keys
    
    # Timeframe selection
    st.sidebar.subheader("⏰ Timeframe Settings")
    
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        options=['1m', '5m', '15m', '30m', '1h', '4h', '1d'],
        index=2  # Default to 15m
    )
    
    timeframe_periods = {
        '1m': ['1d', '5d', '7d'],
        '5m': ['1d', '5d', '1mo'],
        '15m': ['1d', '5d', '1mo', '3mo'],
        '30m': ['5d', '1mo', '3mo', '6mo'],
        '1h': ['1mo', '3mo', '6mo', '1y'],
        '4h': ['1mo', '3mo', '6mo', '1y', '2y'],
        '1d': ['6mo', '1y', '2y', '5y', '10y', 'max']
    }
    
    available_periods = timeframe_periods[timeframe]
    period = st.sidebar.selectbox("Period", available_periods, index=len(available_periods)-1)
    
    # Advanced settings
    st.sidebar.subheader("⚙️ Advanced Settings")
    
    min_bars = st.sidebar.number_input("Minimum Bars", 500, 2000, 800)
    
    use_adx = st.sidebar.checkbox("Use ADX Filter", value=False)
    adx_thresholds = [20, 25, 30, 35] if use_adx else []
    if use_adx:
        st.sidebar.caption("ADX thresholds to test: 20, 25, 30, 35")
    
    use_ema = st.sidebar.checkbox("Use EMA Filter", value=False)
    ema_periods = [13, 21, 50, 100, 200] if use_ema else []
    if use_ema:
        st.sidebar.caption("EMA periods to test: 13, 21, 50, 100, 200")
    
    # X Trend Filter Configuration
    st.sidebar.subheader("🔄 X Trend Filter")
    use_xtrend = st.sidebar.checkbox("Use X Trend Filter", value=True, 
                                    help="Enable/disable X Trend confirmation filter")
    
    if use_xtrend:
        htf_multipliers = st.sidebar.multiselect(
            "HTF Multipliers (Optional)",
            options=[2, 3, 4, 6, 8],
            default=[],
            help="Higher timeframe multipliers to test. Leave empty to use only local timeframe (1x)"
        )
        
        if htf_multipliers:
            st.sidebar.caption(f"Will test: 1x (local) + {htf_multipliers}")
        else:
            st.sidebar.caption("Will test: 1x (local timeframe only)")
    else:
        htf_multipliers = []
        st.sidebar.caption("⚠️ X Trend filter disabled - using Pivot Supertrend only")
    
    # Optimization Mode (moved to bottom)
    st.sidebar.subheader("🚀 Optimization Mode")
    optimization_mode = st.sidebar.selectbox(
        "Mode",
        options=["Fast", "Balanced", "Comprehensive"],
        index=0,
        help="Fast: ~2-5 min, Balanced: ~15-30 min, Comprehensive: ~45-90 min"
    )
    
    if optimization_mode == "Fast":
        st.sidebar.info("⚡ **Fast Mode**: Sequential optimization (~20-30 combinations)\n\n"
                       "**Smart Process:**\n"
                       "• Stage 1: Find optimal Pivot + ATR Factor\n"
                       "• Stage 2: Optimize ATR Period\n"
                       "• Stage 3: Optimize HTF Multiplier\n"
                       "• Stage 4-6: Layer on optimal filters\n\n"
                       "**Recommended for:**\n"
                       "• Daily optimization and quick testing\n"
                       "• Rapid strategy validation\n"
                       "• High-quality results in minimal time\n"
                       "• Smart sequential parameter discovery")
    elif optimization_mode == "Balanced":
        st.sidebar.info("⚖️ **Balanced Mode**: Tests key combinations (~500-800 combinations)\n\n"
                       "**Recommended for:**\n" 
                       "• Weekly optimization for good quality\n"
                       "• Regular strategy refinement\n"
                       "• Production trading setups\n"
                       "• Balance between speed and thoroughness")
    else:
        st.sidebar.info("🔬 **Comprehensive Mode**: Tests all combinations (~2000+ combinations)\n\n"
                       "**Recommended for:**\n"
                       "• Monthly optimization for maximum quality\n"
                       "• Final strategy validation\n"
                       "• Research and backtesting\n"
                       "• When you need the absolute best parameters")
    
    # Main content
    if not all_selected_assets:
        st.info("👆 Please select at least one asset from the sidebar")
        st.stop()
    
    st.subheader(f"📥 Selected: {len(all_selected_assets)} assets, {timeframe} timeframe")
    
    # Download and optimize
    if st.button("🚀 Download Data & Run Optimization", type="primary"):
        st.session_state.optimization_results = {}
        st.session_state.downloaded_data = {}
        
        # Download data
        st.markdown("### 📥 Downloading Data...")
        downloaded_data = {}
        
        progress_bar = st.progress(0)
        for i, asset in enumerate(all_selected_assets):
            progress_bar.progress(i / len(all_selected_assets))
            
            try:
                with st.spinner(f"Downloading {asset}..."):
                    yf_symbol = all_assets[asset]['yf']
                    ticker = yf.Ticker(yf_symbol)
                    data = ticker.history(period=period, interval=timeframe)
                    
                    if len(data) >= min_bars:
                        data.reset_index(inplace=True)
                        if 'Datetime' in data.columns:
                            data['time'] = data['Datetime']
                        elif 'Date' in data.columns:
                            data['time'] = data['Date']
                        
                        data.columns = data.columns.str.lower()
                        downloaded_data[asset] = data
                        
                        display_name = all_assets[asset]['name']
                        st.success(f"✅ {display_name}: {len(data)} bars")
                    else:
                        display_name = all_assets[asset]['name']
                        st.error(f"❌ {display_name}: Only {len(data)} bars (need {min_bars})")
                
                time.sleep(0.1)
            except Exception as e:
                display_name = all_assets.get(asset, {}).get('name', asset)
                st.error(f"❌ {display_name}: {str(e)}")
        
        progress_bar.progress(1.0)
        
        if not downloaded_data:
            st.error("No data downloaded successfully")
            st.stop()
        
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
                    # Sequential optimization based on mode
                    if optimization_mode == "Fast":
                        st.info("🔄 **Sequential Fast Optimization**: Core Parameters → Filters")
                        results = run_sequential_optimization(data, asset, use_xtrend, htf_multipliers, 
                                                            use_adx, adx_thresholds, use_ema, ema_periods)
                        
                    elif optimization_mode == "Balanced":
                        # Balanced Mode: Reduced but comprehensive
                        pivot_periods = [3, 5, 7]
                        atr_factors = [1.0, 1.25, 1.5]
                        atr_periods = [10, 15, 20]
                        
                        filter_combinations = [{'use_adx': False, 'use_ema': False}]
                        if use_adx:
                            for threshold in [25, 30]:
                                filter_combinations.append({
                                    'use_adx': True, 'adx_threshold': threshold, 
                                    'use_ema': False
                                })
                        if use_ema:
                            for period in [21, 50]:
                                filter_combinations.append({
                                    'use_adx': False, 
                                    'use_ema': True, 'ema_period': period
                                })
                        
                        results = run_matrix_optimization(data, asset, pivot_periods, atr_factors, 
                                                        atr_periods, use_xtrend, htf_multipliers, filter_combinations)
                                
                    else:  # Comprehensive Mode
                        pivot_periods = [3, 5, 7]
                        atr_factors = [1.0, 1.25, 1.5]
                        atr_periods = [10, 15, 20]
                        
                        filter_combinations = [{'use_adx': False, 'use_ema': False}]
                        if use_adx:
                            for threshold in adx_thresholds:
                                filter_combinations.append({
                                    'use_adx': True, 'adx_threshold': threshold, 
                                    'use_ema': False
                                })
                        if use_ema:
                            for period in ema_periods:
                                filter_combinations.append({
                                    'use_adx': False, 
                                    'use_ema': True, 'ema_period': period
                                })
                        if use_adx and use_ema:
                            for threshold in adx_thresholds:
                                for period in ema_periods:
                                    filter_combinations.append({
                                        'use_adx': True, 'adx_threshold': threshold,
                                        'use_ema': True, 'ema_period': period
                                    })
                        
                        results = run_matrix_optimization(data, asset, pivot_periods, atr_factors, 
                                                        atr_periods, use_xtrend, htf_multipliers, filter_combinations)
                    
                    if results:
                        results.sort(key=lambda x: x['score'], reverse=True)
                        optimization_results[asset] = {
                            'results': results[:5],
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
                    st.error(f"❌ Error optimizing {asset}: {str(e)}")
        
        main_progress.progress(1.0)
        st.session_state.optimization_results = optimization_results
        st.rerun()
    
    # Display results
    if st.session_state.optimization_results:
        st.markdown("---")
        st.subheader("🏆 Optimization Results")
        
        results_summary = []
        for asset, results in st.session_state.optimization_results.items():
            best = results['best']
            
            if asset.startswith('CUSTOM_'):
                asset_name = st.session_state.custom_assets[asset]['name']
                asset_type = 'Custom'
            else:
                asset_name = assets[asset]['name']  
                asset_type = assets[asset].get('type', 'Unknown')
            
            results_summary.append({
                'Asset': asset.replace('CUSTOM_', '') if asset.startswith('CUSTOM_') else asset,
                'Asset Name': asset_name,
                'Type': asset_type,
                'Score': best['score'],
                'Win Rate (%)': best['win_rate'],
                'Total Pips': best['total_pips'],
                'Total Trades': best['total_trades'],
                'Risk:Reward': best['risk_reward']
            })
        
        if results_summary:
            summary_df = pd.DataFrame(results_summary)
            summary_df = summary_df.sort_values('Score', ascending=False)
            
            st.markdown("### 📊 Performance Summary")
            st.dataframe(summary_df, use_container_width=True)
            
            st.markdown("### 📋 Detailed Results")
            for asset, results in st.session_state.optimization_results.items():
                if asset.startswith('CUSTOM_'):
                    display_name = st.session_state.custom_assets[asset]['name']
                    asset_display = f"{display_name}"
                else:
                    display_name = assets[asset]['name']
                    asset_display = f"{asset} ({display_name})"
                    
                with st.expander(f"📊 {asset_display} - Score: {results['best']['score']:.0f}", expanded=True):
                    best = results['best']
                    data_info = results['data_info']
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🎯 Optimal Parameters")
                        st.write(f"**Pivot Period**: {best['pivot_period']}")
                        st.write(f"**ATR Factor**: {best['atr_factor']}")
                        st.write(f"**ATR Period**: {best['atr_period']}")
                        
                        if best.get('use_xtrend'):
                            if best['htf_multiplier'] == 1:
                                st.write(f"**X Trend Filter**: Enabled (1x - local timeframe)")
                            else:
                                st.write(f"**X Trend Filter**: Enabled ({best['htf_multiplier']}x HTF)")
                        else:
                            st.write(f"**X Trend Filter**: Disabled")
                        
                        if best.get('use_adx'):
                            st.write(f"**ADX Filter**: Enabled (≥{best.get('adx_threshold', 25)})")
                        else:
                            st.write(f"**ADX Filter**: Disabled")
                            
                        if best.get('use_ema'):
                            st.write(f"**EMA Filter**: Enabled ({best.get('ema_period', 21)} period)")
                        else:
                            st.write(f"**EMA Filter**: Disabled")
                    
                    with col2:
                        st.markdown("#### 📈 Performance Metrics")
                        st.write(f"**Total Trades**: {best['total_trades']}")
                        st.write(f"**Win Rate**: {best['win_rate']:.1f}%")
                        st.write(f"**Total Pips**: {best['total_pips']:.2f}")
                        st.write(f"**Risk:Reward**: {best['risk_reward']:.2f}:1")
                        st.write(f"**Score**: {best['score']:.0f}")
                    
                    # PineScript settings
                    st.markdown("#### ⚙️ PineScript Settings")
                    pinescript_settings = f"""// XPST Settings for {asset}
prd = {best['pivot_period']}
Factor = {best['atr_factor']}
Pd = {best['atr_period']}
use_xtrend = {str(best.get('use_xtrend', True)).lower()}"""

                    if best.get('use_xtrend'):
                        if best['htf_multiplier'] > 1:
                            pinescript_settings += f"\nuse_xtrend_htf_color = true\nxtrend_htf_tf = \"{timeframe}\""
                        else:
                            pinescript_settings += f"\nuse_xtrend_htf_color = false"
                    
                    pinescript_settings += f"\nuse_adx = {str(best.get('use_adx', False)).lower()}"

                    if best.get('use_adx'):
                        pinescript_settings += f"\nadx_threshold = {best.get('adx_threshold', 25)}"
                    
                    pinescript_settings += f"\nuse_ema = {str(best.get('use_ema', False)).lower()}"
                    
                    if best.get('use_ema'):
                        pinescript_settings += f"\nema_period = {best.get('ema_period', 21)}"
                    
                    st.code(pinescript_settings, language="pinescript")
                    
                    # Top configurations table
                    st.markdown("#### 📋 Top 5 Configurations")
                    top_configs = []
                    for i, result in enumerate(results['results'][:5]):
                        top_configs.append({
                            'Rank': i + 1,
                            'PP': result['pivot_period'],
                            'ATR Factor': result['atr_factor'],
                            'ATR Period': result['atr_period'],
                            'HTF': f"{result['htf_multiplier']}x",
                            'Trades': result['total_trades'],
                            'Win%': f"{result['win_rate']:.1f}%",
                            'Pips': f"{result['total_pips']:.0f}",
                            'Score': f"{result['score']:.0f}"
                        })
                    
                    config_df = pd.DataFrame(top_configs)
                    st.dataframe(config_df, use_container_width=True)
            
            # Export functionality
            st.markdown("### 💾 Export Results")
            
            export_data = []
            for asset, results in st.session_state.optimization_results.items():
                best = results['best']
                data_info = results['data_info']
                
                if asset.startswith('CUSTOM_'):
                    asset_name = st.session_state.custom_assets[asset]['name']
                    asset_type = 'Custom'
                else:
                    asset_name = assets[asset]['name']
                    asset_type = assets[asset].get('type', 'Unknown')
                
                export_data.append({
                    'Asset': asset.replace('CUSTOM_', '') if asset.startswith('CUSTOM_') else asset,
                    'Asset_Name': asset_name,
                    'Asset_Type': asset_type,
                    'Data_Bars': data_info['rows'],
                    'Timeframe': data_info['timeframe'],
                    'Period': data_info['period'],
                    'Optimal_Pivot_Period': best['pivot_period'],
                    'Optimal_ATR_Factor': best['atr_factor'],
                    'Optimal_ATR_Period': best['atr_period'],
                    'Optimal_HTF_Multiplier': best['htf_multiplier'],
                    'Use_ADX': best.get('use_adx', False),
                    'ADX_Threshold': best.get('adx_threshold', ''),
                    'Use_EMA': best.get('use_ema', False),
                    'EMA_Period': best.get('ema_period', ''),
                    'Total_Trades': best['total_trades'],
                    'Win_Rate': best['win_rate'],
                    'Total_Pips': best['total_pips'],
                    'Risk_Reward': best['risk_reward'],
                    'Score': best['score']
                })
            
            export_df = pd.DataFrame(export_data)
            csv = export_df.to_csv(index=False)
            
            st.download_button(
                label="📁 Download Results as CSV",
                data=csv,
                file_name=f"XPST_Optimization_Results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("No optimization results found. Please try different settings or assets.")
    
    elif st.session_state.downloaded_data and not st.session_state.optimization_results:
        st.info("📊 Data downloaded. Click the optimization button to start the analysis.")
    
    # Footer
    st.markdown("---")
    st.markdown("🎯 **XPST Optimizer** | Built with Streamlit & Yahoo Finance")

if __name__ == "__main__":
    main()
