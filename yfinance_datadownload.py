import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io
from datetime import datetime, timedelta
import requests
import json
import asyncio
import concurrent.futures
from typing import List, Dict, Tuple

# App Version Control
APP_VERSION = "2.2.0"
VERSION_DATE = "2025-08-25"
CHANGELOG = {
    "2.2.0": {
        "date": "2025-08-25",
        "changes": [
            "Added multiple timeframe selection capability",
            "Implemented automatic period limits based on yfinance constraints",
            "Added smart timeframe validation and recommendations",
            "Enhanced download progress tracking",
            "Improved error handling for timeframe-specific downloads"
        ]
    },
    "2.1.0": {
        "date": "2025-08-21",
        "changes": [
            "Added version control and changelog",
            "Fixed Yahoo Finance timeframe/period compatibility issues",
            "Improved real-time search with autocomplete",
            "Added popular stocks database for instant suggestions",
            "Enhanced UI with better visual feedback"
        ]
    }
}

# Set page config
st.set_page_config(
    page_title="YFinance Data Downloader", 
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'selected_assets' not in st.session_state:
    st.session_state.selected_assets = []
if 'selected_timeframes' not in st.session_state:
    st.session_state.selected_timeframes = ['1d']
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'show_search_results' not in st.session_state:
    st.session_state.show_search_results = False
if 'last_search_query' not in st.session_state:
    st.session_state.last_search_query = ""

# Predefined assets with their yfinance symbols and descriptions
predefined_assets = {
    'BTCUSD (Bitcoin/USD)': 'BTC-USD',
    'ETHUSD (Ethereum/USD)': 'ETH-USD', 
    'XAUUSD (Gold/USD)': 'GC=F',
    'EURUSD (Euro/USD)': 'EURUSD=X',
    'GBPUSD (GBP/USD)': 'GBPUSD=X',
    'USDJPY (USD/JPY)': 'USDJPY=X',
    'AUDUSD (AUD/USD)': 'AUDUSD=X',
    'USDCAD (USD/CAD)': 'USDCAD=X',
    'NZDUSD (NZD/USD)': 'NZDUSD=X',
    'USDCHF (USD/CHF)': 'USDCHF=X'
}

# Enhanced timeframe configuration with automatic period limits
TIMEFRAME_CONFIG = {
    '1m': {
        'name': '1 Minute',
        'yf_interval': '1m',
        'max_days': 7,
        'recommended_period': '7d',
        'available_periods': ['1d', '2d', '3d', '5d', '7d'],
        'description': 'Intraday 1-minute data (max 7 days)',
        'icon': '🟢'
    },
    '2m': {
        'name': '2 Minutes',
        'yf_interval': '2m',
        'max_days': 60,
        'recommended_period': '5d',
        'available_periods': ['1d', '2d', '3d', '5d', '7d', '1mo'],
        'description': 'Intraday 2-minute data (max 60 days)',
        'icon': '🟢'
    },
    '5m': {
        'name': '5 Minutes',
        'yf_interval': '5m',
        'max_days': 60,
        'recommended_period': '5d',
        'available_periods': ['1d', '2d', '3d', '5d', '7d', '1mo'],
        'description': 'Intraday 5-minute data (max 60 days)',
        'icon': '🔵'
    },
    '10m': {
        'name': '10 Minutes',
        'yf_interval': '15m',  # yfinance doesn't have 10m, use 15m as closest
        'max_days': 60,
        'recommended_period': '5d',
        'available_periods': ['1d', '2d', '3d', '5d', '7d', '1mo'],
        'description': '15-minute data (closest to 10m, max 60 days)',
        'icon': '🔵'
    },
    '15m': {
        'name': '15 Minutes',
        'yf_interval': '15m',
        'max_days': 60,
        'recommended_period': '5d',
        'available_periods': ['1d', '2d', '3d', '5d', '7d', '1mo'],
        'description': 'Intraday 15-minute data (max 60 days)',
        'icon': '🔵'
    },
    '1h': {
        'name': '1 Hour',
        'yf_interval': '1h',
        'max_days': 730,
        'recommended_period': '1mo',
        'available_periods': ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y'],
        'description': 'Hourly data (max 2 years)',
        'icon': '🟡'
    },
    '4h': {
        'name': '4 Hours',
        'yf_interval': '1h',  # Use 1h and resample to 4h later
        'max_days': 730,
        'recommended_period': '3mo',
        'available_periods': ['5d', '1mo', '3mo', '6mo', '1y', '2y'],
        'description': '4-hour data (resampled from 1h, max 2 years)',
        'icon': '🟠'
    },
    '1d': {
        'name': 'Daily',
        'yf_interval': '1d',
        'max_days': None,  # No limit for daily data
        'recommended_period': '1y',
        'available_periods': ['5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'],
        'description': 'Daily data (unlimited history)',
        'icon': '🔴'
    }
}

# Enhanced database with stocks, crypto, forex, and commodities for instant suggestions
POPULAR_ASSETS = {
    # Stocks
    'apple': {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology'},
    'microsoft': {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology'},
    'google': {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology'},
    'alphabet': {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology'},
    'tesla': {'symbol': 'TSLA', 'name': 'Tesla, Inc.', 'sector': 'Automotive'},
    'amazon': {'symbol': 'AMZN', 'name': 'Amazon.com, Inc.', 'sector': 'E-commerce'},
    'meta': {'symbol': 'META', 'name': 'Meta Platforms, Inc.', 'sector': 'Technology'},
    'facebook': {'symbol': 'META', 'name': 'Meta Platforms, Inc.', 'sector': 'Technology'},
    'nvidia': {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'Technology'},
    'netflix': {'symbol': 'NFLX', 'name': 'Netflix, Inc.', 'sector': 'Media'},
    'uber': {'symbol': 'UBER', 'name': 'Uber Technologies, Inc.', 'sector': 'Transportation'},
    'zoom': {'symbol': 'ZM', 'name': 'Zoom Video Communications', 'sector': 'Technology'},
    'spotify': {'symbol': 'SPOT', 'name': 'Spotify Technology S.A.', 'sector': 'Media'},
    'visa': {'symbol': 'V', 'name': 'Visa Inc.', 'sector': 'Financial'},
    'mastercard': {'symbol': 'MA', 'name': 'Mastercard Incorporated', 'sector': 'Financial'},
    'paypal': {'symbol': 'PYPL', 'name': 'PayPal Holdings, Inc.', 'sector': 'Financial'},
    'coca': {'symbol': 'KO', 'name': 'The Coca-Cola Company', 'sector': 'Consumer'},
    'pepsi': {'symbol': 'PEP', 'name': 'PepsiCo, Inc.', 'sector': 'Consumer'},
    'walmart': {'symbol': 'WMT', 'name': 'Walmart Inc.', 'sector': 'Retail'},
    'disney': {'symbol': 'DIS', 'name': 'The Walt Disney Company', 'sector': 'Media'},
    'nike': {'symbol': 'NKE', 'name': 'NIKE, Inc.', 'sector': 'Consumer'},
    'spy': {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF Trust', 'sector': 'ETF'},
    'qqq': {'symbol': 'QQQ', 'name': 'Invesco QQQ Trust', 'sector': 'ETF'},
    
    # Cryptocurrencies - Major ones
    'bitcoin': {'symbol': 'BTC-USD', 'name': 'Bitcoin USD', 'sector': 'Cryptocurrency'},
    'btc': {'symbol': 'BTC-USD', 'name': 'Bitcoin USD', 'sector': 'Cryptocurrency'},
    'ethereum': {'symbol': 'ETH-USD', 'name': 'Ethereum USD', 'sector': 'Cryptocurrency'},
    'eth': {'symbol': 'ETH-USD', 'name': 'Ethereum USD', 'sector': 'Cryptocurrency'},
    'litecoin': {'symbol': 'LTC-USD', 'name': 'Litecoin USD', 'sector': 'Cryptocurrency'},
    'ltc': {'symbol': 'LTC-USD', 'name': 'Litecoin USD', 'sector': 'Cryptocurrency'},
    'ripple': {'symbol': 'XRP-USD', 'name': 'XRP USD', 'sector': 'Cryptocurrency'},
    'xrp': {'symbol': 'XRP-USD', 'name': 'XRP USD', 'sector': 'Cryptocurrency'},
    'cardano': {'symbol': 'ADA-USD', 'name': 'Cardano USD', 'sector': 'Cryptocurrency'},
    'ada': {'symbol': 'ADA-USD', 'name': 'Cardano USD', 'sector': 'Cryptocurrency'},
    'polkadot': {'symbol': 'DOT-USD', 'name': 'Polkadot USD', 'sector': 'Cryptocurrency'},
    'dot': {'symbol': 'DOT-USD', 'name': 'Polkadot USD', 'sector': 'Cryptocurrency'},
    'chainlink': {'symbol': 'LINK-USD', 'name': 'Chainlink USD', 'sector': 'Cryptocurrency'},
    'link': {'symbol': 'LINK-USD', 'name': 'Chainlink USD', 'sector': 'Cryptocurrency'},
    'stellar': {'symbol': 'XLM-USD', 'name': 'Stellar USD', 'sector': 'Cryptocurrency'},
    'xlm': {'symbol': 'XLM-USD', 'name': 'Stellar USD', 'sector': 'Cryptocurrency'},
    'dogecoin': {'symbol': 'DOGE-USD', 'name': 'Dogecoin USD', 'sector': 'Cryptocurrency'},
    'doge': {'symbol': 'DOGE-USD', 'name': 'Dogecoin USD', 'sector': 'Cryptocurrency'},
    'solana': {'symbol': 'SOL-USD', 'name': 'Solana USD', 'sector': 'Cryptocurrency'},
    'sol': {'symbol': 'SOL-USD', 'name': 'Solana USD', 'sector': 'Cryptocurrency'},
    'avalanche': {'symbol': 'AVAX-USD', 'name': 'Avalanche USD', 'sector': 'Cryptocurrency'},
    'avax': {'symbol': 'AVAX-USD', 'name': 'Avalanche USD', 'sector': 'Cryptocurrency'},
    'polygon': {'symbol': 'MATIC-USD', 'name': 'Polygon USD', 'sector': 'Cryptocurrency'},
    'matic': {'symbol': 'MATIC-USD', 'name': 'Polygon USD', 'sector': 'Cryptocurrency'},
    'binance': {'symbol': 'BNB-USD', 'name': 'Binance Coin USD', 'sector': 'Cryptocurrency'},
    'bnb': {'symbol': 'BNB-USD', 'name': 'Binance Coin USD', 'sector': 'Cryptocurrency'},
    
    # Forex Pairs
    'eurusd': {'symbol': 'EURUSD=X', 'name': 'EUR/USD', 'sector': 'Forex'},
    'gbpusd': {'symbol': 'GBPUSD=X', 'name': 'GBP/USD', 'sector': 'Forex'},
    'usdjpy': {'symbol': 'USDJPY=X', 'name': 'USD/JPY', 'sector': 'Forex'},
    'audusd': {'symbol': 'AUDUSD=X', 'name': 'AUD/USD', 'sector': 'Forex'},
    'usdcad': {'symbol': 'USDCAD=X', 'name': 'USD/CAD', 'sector': 'Forex'},
    'nzdusd': {'symbol': 'NZDUSD=X', 'name': 'NZD/USD', 'sector': 'Forex'},
    'usdchf': {'symbol': 'USDCHF=X', 'name': 'USD/CHF', 'sector': 'Forex'},
    'eurjpy': {'symbol': 'EURJPY=X', 'name': 'EUR/JPY', 'sector': 'Forex'},
    'gbpjpy': {'symbol': 'GBPJPY=X', 'name': 'GBP/JPY', 'sector': 'Forex'},
    'eurgbp': {'symbol': 'EURGBP=X', 'name': 'EUR/GBP', 'sector': 'Forex'},
    
    # Commodities
    'gold': {'symbol': 'GC=F', 'name': 'Gold Futures', 'sector': 'Commodity'},
    'silver': {'symbol': 'SI=F', 'name': 'Silver Futures', 'sector': 'Commodity'},
    'oil': {'symbol': 'CL=F', 'name': 'Crude Oil Futures', 'sector': 'Commodity'},
    'crude': {'symbol': 'CL=F', 'name': 'Crude Oil Futures', 'sector': 'Commodity'},
    'natgas': {'symbol': 'NG=F', 'name': 'Natural Gas Futures', 'sector': 'Commodity'},
    'copper': {'symbol': 'HG=F', 'name': 'Copper Futures', 'sector': 'Commodity'},
    'wheat': {'symbol': 'ZW=F', 'name': 'Wheat Futures', 'sector': 'Commodity'},
    'corn': {'symbol': 'ZC=F', 'name': 'Corn Futures', 'sector': 'Commodity'},
}

@st.cache_data(ttl=300)
def get_instant_suggestions(query):
    """Get instant suggestions from popular stocks database with caching"""
    if not query or len(query) < 2:
        return []
    
    query_lower = query.lower()
    suggestions = []
    
    for key, stock in POPULAR_STOCKS.items():
        if (query_lower in key or 
            query_lower in stock['symbol'].lower() or 
            query_lower in stock['name'].lower()):
            suggestions.append(stock)
    
    seen = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion['symbol'] not in seen:
            seen.add(suggestion['symbol'])
            unique_suggestions.append(suggestion)
            if len(unique_suggestions) >= 5:
                break
    
    return unique_suggestions

@st.cache_data(ttl=300)
def search_ticker(query):
    """Search for ticker symbols using yfinance with caching"""
    if not query or len(query) < 2:
        return []
    
    try:
        search_results = []
        variations = [query.upper(), f"{query.upper()}.TO", f"{query.upper()}.L"]
        
        for variation in variations[:2]:
            try:
                ticker = yf.Ticker(variation)
                info = ticker.info
                
                if info and 'longName' in info and info['longName']:
                    search_results.append({
                        'symbol': variation,
                        'name': info.get('longName', ''),
                        'sector': info.get('sector', ''),
                        'exchange': info.get('exchange', '')
                    })
                    if len(search_results) >= 3:
                        break
            except:
                continue
        
        seen = set()
        unique_results = []
        for result in search_results:
            if result['symbol'] not in seen:
                seen.add(result['symbol'])
                unique_results.append(result)
        
        return unique_results[:3]
        
    except Exception as e:
        return []

def get_optimal_period_for_timeframe(timeframe: str) -> str:
    """Get the optimal period for a given timeframe"""
    config = TIMEFRAME_CONFIG.get(timeframe, {})
    return config.get('recommended_period', '1mo')

def validate_timeframe_combinations(timeframes: List[str]) -> Dict[str, str]:
    """Validate selected timeframes and return recommended periods"""
    recommendations = {}
    for tf in timeframes:
        recommendations[tf] = get_optimal_period_for_timeframe(tf)
    return recommendations

def resample_to_4h(df):
    """Resample 1-hour data to 4-hour data"""
    if df.empty:
        return df
    
    # Resample to 4-hour intervals
    df_4h = df.resample('4h').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    })
    
    # Remove rows with NaN values (weekends, holidays)
    df_4h = df_4h.dropna()
    return df_4h

def download_single_asset_timeframe(asset: str, timeframe: str, period: str) -> Tuple[str, str, str, pd.DataFrame, str]:
    """Download data for a single asset and timeframe combination"""
    try:
        config = TIMEFRAME_CONFIG[timeframe]
        ticker = yf.Ticker(asset)
        
        # Download data with the yfinance interval
        data = ticker.history(
            period=period,
            interval=config['yf_interval']
        )
        
        # Special handling for 4-hour data (resample from 1-hour)
        if timeframe == '4h' and not data.empty:
            data = resample_to_4h(data)
        
        if not data.empty:
            return asset, timeframe, period, data, "success"
        else:
            return asset, timeframe, period, pd.DataFrame(), "no_data"
            
    except Exception as e:
        return asset, timeframe, period, pd.DataFrame(), f"error: {str(e)}"

def download_multiple_assets_timeframes(assets: List[str], timeframes: List[str], period_map: Dict[str, str]) -> List[Tuple]:
    """Download data for multiple assets and timeframes using concurrent execution"""
    results = []
    
    # Create all combinations of assets and timeframes
    tasks = []
    for asset in assets:
        for timeframe in timeframes:
            period = period_map[timeframe]
            tasks.append((asset, timeframe, period))
    
    # Use ThreadPoolExecutor for concurrent downloads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {
            executor.submit(download_single_asset_timeframe, asset, tf, period): (asset, tf, period)
            for asset, tf, period in tasks
        }
        
        for future in concurrent.futures.as_completed(future_to_task):
            result = future.result()
            results.append(result)
    
    return results

# Add CSS styling
st.markdown(
    '<style>'
    '.sidebar{background-color:#f0f2f6;padding:20px;border-radius:10px;margin-bottom:20px;}'
    '.sidebar-header{font-size:1.2rem;font-weight:bold;color:#2c3e50;margin-bottom:15px;}'
    '.selected-asset{background-color:#e74c3c;color:white;padding:5px 10px;border-radius:15px;margin:2px;display:inline-block;font-size:0.9rem;}'
    '.selected-timeframe{background-color:#3498db;color:white;padding:5px 10px;border-radius:15px;margin:2px;display:inline-block;font-size:0.9rem;}'
    '.main-header{background:linear-gradient(90deg,#3498db,#2980b9);color:white;padding:20px;border-radius:10px;text-align:center;margin-bottom:20px;}'
    '.main-header h1{margin:0;font-size:2.5rem;}'
    '.main-header p{margin:5px 0 0 0;font-size:1.1rem;opacity:0.9;}'
    '.download-section{background-color:#ecf0f1;padding:20px;border-radius:10px;margin-top:20px;}'
    '.version-info{background-color:#f8f9fa;padding:10px;border-radius:5px;border-left:4px solid #3498db;margin:10px 0;font-size:0.9rem;}'
    '.changelog-item{background-color:#fff;padding:8px;margin:5px 0;border-radius:4px;border-left:3px solid #27ae60;}'
    '.version-header{color:#2c3e50;font-weight:bold;margin-bottom:5px;}'
    '.timeframe-card{background-color:#ffffff;border:2px solid #ecf0f1;border-radius:8px;padding:10px;margin:5px 0;transition:all 0.3s;}'
    '.timeframe-card:hover{border-color:#3498db;box-shadow:0 2px 8px rgba(52,152,219,0.2);}'
    '.timeframe-card.selected{border-color:#3498db;background-color:#ebf3fd;}'
    '.timeframe-info{font-size:0.8rem;color:#7f8c8d;margin-top:5px;}'
    '</style>', 
    unsafe_allow_html=True
)

# Create layout with sidebar and main content
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown('<div class="sidebar">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-header">📊 Configuration</div>', unsafe_allow_html=True)
    
    # Assets Selection Section
    st.markdown('<div class="sidebar-header">🏠 Select Assets</div>', unsafe_allow_html=True)
    
    # Predefined Assets dropdown
    st.markdown("**Predefined Assets**")
    selected_predefined = st.selectbox(
        "Choose options",
        options=[''] + list(predefined_assets.keys()),
        key="predefined_dropdown"
    )
    
    if selected_predefined and selected_predefined != '':
        symbol = predefined_assets[selected_predefined]
        if symbol not in st.session_state.selected_assets:
            st.session_state.selected_assets.append(symbol)
            st.rerun()
    
    # Display selected assets
    if st.session_state.selected_assets:
        st.markdown("**Selected Assets:**")
        for asset in st.session_state.selected_assets:
            col_asset, col_remove = st.columns([3, 1])
            with col_asset:
                display_name = asset
                for display, symbol in predefined_assets.items():
                    if symbol == asset:
                        display_name = display.split(' (')[0]
                        break
                asset_html = f'<div class="selected-asset">{display_name}</div>'
                st.markdown(asset_html, unsafe_allow_html=True)
            with col_remove:
                if st.button("❌", key=f"remove_{asset}", help="Remove asset"):
                    st.session_state.selected_assets.remove(asset)
                    st.rerun()
    
    st.markdown("---")
    
    # Add Custom Ticker
    st.markdown("**Add Custom Ticker:**")
    st.markdown("Enter Symbol or Company Name")
    
    search_query = st.text_input(
        "search_ticker",
        placeholder="e.g., Apple, AAPL, Tesla...",
        label_visibility="collapsed",
        key="search_input"
    )
    
    # Auto-suggest as user types
    if search_query and search_query != st.session_state.last_search_query:
        st.session_state.last_search_query = search_query
        if len(search_query) >= 2:
            instant_suggestions = get_instant_suggestions(search_query)
            if instant_suggestions:
                st.session_state.search_results = instant_suggestions
                st.session_state.show_search_results = True
            else:
                st.session_state.search_results = search_ticker(search_query)
                st.session_state.show_search_results = True
        else:
            st.session_state.show_search_results = False
    
    # Search and Add buttons
    col_search, col_add = st.columns([2, 1])
    with col_search:
        if st.button("🔍 Search More", use_container_width=True, disabled=not search_query):
            st.session_state.search_results = search_ticker(search_query)
            st.session_state.show_search_results = True
    
    with col_add:
        if st.button("➕ Add Direct", help="Add as exact symbol", disabled=not search_query):
            if search_query.upper() not in st.session_state.selected_assets:
                st.session_state.selected_assets.append(search_query.upper())
                st.session_state.show_search_results = False
                st.session_state.last_search_query = ""
                st.rerun()
    
    # Display search results
    if st.session_state.show_search_results and st.session_state.search_results:
        st.markdown("**💡 Suggestions:**")
        
        for i, result in enumerate(st.session_state.search_results):
            col_info, col_select = st.columns([5, 1])
            
            with col_info:
                is_selected = result['symbol'] in st.session_state.selected_assets
                status_icon = "✅" if is_selected else "📈"
                bg_color = '#e8f5e8' if is_selected else '#f8f9fa'
                
                card_html = f'<div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 2px 0;"><strong style="color: #2c3e50;">{status_icon} {result["symbol"]}</strong> - {result["name"]}<br><small style="color: #7f8c8d;"><em>{result.get("sector", "N/A")}</em></small></div>'
                st.markdown(card_html, unsafe_allow_html=True)
            
            with col_select:
                if not is_selected:
                    if st.button("✅", key=f"select_{result['symbol']}_{i}", help="Add this ticker"):
                        st.session_state.selected_assets.append(result['symbol'])
                        st.session_state.show_search_results = False
                        st.session_state.last_search_query = ""
                        st.rerun()
                else:
                    st.markdown("*Added*")
    
    elif st.session_state.show_search_results and not st.session_state.search_results and search_query:
        st.info("💭 No suggestions found. Try a different term or use 'Add Direct' to add the symbol as-is.")
    
    # Quick suggestions when no search query
    if not search_query:
        st.markdown("**🔥 Popular Picks:**")
        popular_quick = [
            {'symbol': 'AAPL', 'name': 'Apple Inc.'},
            {'symbol': 'TSLA', 'name': 'Tesla, Inc.'},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corp.'},
            {'symbol': 'SPY', 'name': 'S&P 500 ETF'}
        ]
        
        cols = st.columns(2)
        for i, stock in enumerate(popular_quick):
            with cols[i % 2]:
                if stock['symbol'] not in st.session_state.selected_assets:
                    if st.button(f"📈 {stock['symbol']}", key=f"quick_{stock['symbol']}", 
                               help=stock['name'], use_container_width=True):
                        st.session_state.selected_assets.append(stock['symbol'])
                        st.rerun()
    
    st.markdown("---")
    
    # Multiple Timeframe Selection
    st.markdown('<div class="sidebar-header">⏰ Timeframe Selection</div>', unsafe_allow_html=True)
    st.markdown("**Select Multiple Timeframes:**")
    
    # Create timeframe selection with visual cards
    for tf_key, tf_config in TIMEFRAME_CONFIG.items():
        col_check, col_info = st.columns([1, 4])
        
        with col_check:
            is_selected = tf_key in st.session_state.selected_timeframes
            if st.checkbox("", value=is_selected, key=f"tf_{tf_key}", label_visibility="collapsed"):
                if tf_key not in st.session_state.selected_timeframes:
                    st.session_state.selected_timeframes.append(tf_key)
            else:
                if tf_key in st.session_state.selected_timeframes:
                    st.session_state.selected_timeframes.remove(tf_key)
        
        with col_info:
            card_class = "timeframe-card selected" if is_selected else "timeframe-card"
            card_html = f'''
            <div class="{card_class}">
                <strong>{tf_config['icon']} {tf_config['name']}</strong>
                <div class="timeframe-info">
                    {tf_config['description']}<br>
                    <em>Recommended: {tf_config['recommended_period']}</em>
                </div>
            </div>
            '''
            st.markdown(card_html, unsafe_allow_html=True)
    
    # Display selected timeframes
    if st.session_state.selected_timeframes:
        st.markdown("**Selected Timeframes:**")
        for tf in st.session_state.selected_timeframes:
            tf_config = TIMEFRAME_CONFIG[tf]
            tf_html = f'<div class="selected-timeframe">{tf_config["icon"]} {tf_config["name"]}</div>'
            st.markdown(tf_html, unsafe_allow_html=True)
    
    # Quick timeframe presets
    st.markdown("**Quick Presets:**")
    col_preset1, col_preset2 = st.columns(2)
    
    with col_preset1:
        if st.button("📈 Intraday", help="1m, 5m, 15m, 1h", use_container_width=True):
            st.session_state.selected_timeframes = ['1m', '5m', '15m', '1h']
            st.rerun()
    
    with col_preset2:
        if st.button("📊 Standard", help="5m, 1h, 1d", use_container_width=True):
            st.session_state.selected_timeframes = ['5m', '1h', '1d']
            st.rerun()
    
    st.markdown("---")
    
    # Version display in sidebar
    sidebar_version = f'<div style="text-align: center; padding: 10px; background-color: #ecf0f1; border-radius: 5px;"><small><strong>v{APP_VERSION}</strong> • {VERSION_DATE}</small></div>'
    st.markdown(sidebar_version, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    # Main content area
    header_html = f'<div class="main-header"><h1>📊 YFinance Data Downloader</h1><p>Multi-Timeframe Trading Data Downloader - v{APP_VERSION}</p></div>'
    st.markdown(header_html, unsafe_allow_html=True)
    
    # Configuration summary
    if st.session_state.selected_assets and st.session_state.selected_timeframes:
        st.markdown(f"**👥 Selected: {len(st.session_state.selected_assets)} assets × {len(st.session_state.selected_timeframes)} timeframes = {len(st.session_state.selected_assets) * len(st.session_state.selected_timeframes)} files**")
        
        # Show period recommendations for selected timeframes
        period_recommendations = validate_timeframe_combinations(st.session_state.selected_timeframes)
        
        st.markdown("**📋 Automatic Period Selection:**")
        for tf, period in period_recommendations.items():
            tf_config = TIMEFRAME_CONFIG[tf]
            st.markdown(f"• {tf_config['icon']} **{tf_config['name']}**: {period} ({tf_config['description'].split('(')[1].replace(')', '')})")
        
        # Download button
        st.markdown('<div class="download-section">', unsafe_allow_html=True)
        
        if st.button("🚀 Download Multi-Timeframe Data & Get ZIP File", type="primary", use_container_width=True):
            try:
                # Validate that we have assets and timeframes
                if not st.session_state.selected_assets:
                    st.error("❌ Please select at least one asset.")
                elif not st.session_state.selected_timeframes:
                    st.error("❌ Please select at least one timeframe.")
                else:
                    # Show download progress
                    total_combinations = len(st.session_state.selected_assets) * len(st.session_state.selected_timeframes)
                    progress_text = st.empty()
                    progress_bar = st.progress(0)
                    
                    progress_text.text(f'Preparing to download {total_combinations} asset-timeframe combinations...')
                    
                    # Download all combinations concurrently
                    results = download_multiple_assets_timeframes(
                        st.session_state.selected_assets,
                        st.session_state.selected_timeframes,
                        period_recommendations
                    )
                    
                    # Process results and create ZIP file
                    zip_buffer = io.BytesIO()
                    successful_downloads = 0
                    failed_downloads = []
                    
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for i, (asset, timeframe, period, data, status) in enumerate(results):
                            progress_bar.progress((i + 1) / len(results))
                            progress_text.text(f'Processing {asset} - {TIMEFRAME_CONFIG[timeframe]["name"]} ({i+1}/{len(results)})')
                            
                            if status == "success" and not data.empty:
                                # Create filename with timeframe and period info
                                filename = f"{asset}_{timeframe}_{period}_{datetime.now().strftime('%Y%m%d')}.csv"
                                csv_string = data.to_csv()
                                zip_file.writestr(filename, csv_string)
                                successful_downloads += 1
                                
                                # Show success message
                                tf_config = TIMEFRAME_CONFIG[timeframe]
                                st.success(f"✅ {asset} - {tf_config['name']} ({period}): {len(data)} records")
                                
                            elif status == "no_data":
                                failed_downloads.append(f"{asset} - {TIMEFRAME_CONFIG[timeframe]['name']}: No data available")
                                st.warning(f"⚠️ {asset} - {TIMEFRAME_CONFIG[timeframe]['name']}: No data available for {period}")
                                
                            else:
                                failed_downloads.append(f"{asset} - {TIMEFRAME_CONFIG[timeframe]['name']}: {status}")
                                st.error(f"❌ {asset} - {TIMEFRAME_CONFIG[timeframe]['name']}: {status}")
                    
                    progress_text.text('Finalizing ZIP file...')
                    
                    if successful_downloads > 0:
                        zip_buffer.seek(0)
                        
                        # Create download button
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"yfinance_multi_timeframe_{timestamp}.zip"
                        
                        st.download_button(
                            label=f"📦 Download ZIP File ({successful_downloads} files)",
                            data=zip_buffer.getvalue(),
                            file_name=filename,
                            mime="application/zip",
                            use_container_width=True
                        )
                        
                        # Show summary
                        st.success(f"🎉 Successfully downloaded {successful_downloads} out of {total_combinations} combinations!")
                        
                        if failed_downloads:
                            st.warning(f"⚠️ {len(failed_downloads)} downloads failed or had no data:")
                            for failure in failed_downloads:
                                st.write(f"• {failure}")
                    
                    else:
                        st.error("❌ No data was successfully downloaded. Please check your asset symbols and try again.")
                    
                    # Clear progress indicators
                    progress_text.empty()
                    progress_bar.empty()
                        
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Preview section
        st.markdown("### 📈 Data Preview")
        
        if st.session_state.selected_assets and st.session_state.selected_timeframes:
            col_preview_asset, col_preview_tf = st.columns(2)
            
            with col_preview_asset:
                preview_asset = st.selectbox(
                    "Select asset to preview:",
                    options=st.session_state.selected_assets,
                    key="preview_asset"
                )
            
            with col_preview_tf:
                preview_timeframe = st.selectbox(
                    "Select timeframe:",
                    options=st.session_state.selected_timeframes,
                    key="preview_timeframe"
                )
            
            if st.button("Preview Data", use_container_width=True):
                try:
                    period = get_optimal_period_for_timeframe(preview_timeframe)
                    
                    with st.spinner(f'Loading preview for {preview_asset} - {TIMEFRAME_CONFIG[preview_timeframe]["name"]}...'):
                        asset, timeframe, period_used, preview_data, status = download_single_asset_timeframe(
                            preview_asset, preview_timeframe, period
                        )
                        
                        if status == "success" and not preview_data.empty:
                            st.dataframe(preview_data.head(10), use_container_width=True)
                            st.info(f"Showing first 10 rows of {len(preview_data)} total records for {TIMEFRAME_CONFIG[preview_timeframe]['name']} timeframe")
                            
                            # Add a simple line chart for closing prices
                            if 'Close' in preview_data.columns:
                                st.line_chart(preview_data['Close'].tail(100), height=300)
                                st.caption(f"Last 100 closing prices for {preview_asset}")
                        
                        elif status == "no_data":
                            st.warning(f"No data available for {preview_asset} with {TIMEFRAME_CONFIG[preview_timeframe]['name']} timeframe")
                        else:
                            st.error(f"Error loading preview: {status}")
                            
                except Exception as e:
                    st.error(f"Error loading preview: {str(e)}")
    
    else:
        # Instructions when nothing is selected
        missing = []
        if not st.session_state.selected_assets:
            missing.append("assets")
        if not st.session_state.selected_timeframes:
            missing.append("timeframes")
        
        st.info(f"👈 Please select {' and '.join(missing)} from the sidebar to get started.")
        
        # Feature highlights
        st.markdown("### ✨ New Multi-Timeframe Features")
        
        features_text = """
        **🎯 Smart Timeframe Management:**
        - Select multiple timeframes simultaneously (1m, 2m, 5m, 15m, 1h, 4h, daily)
        - Automatic period optimization based on yfinance limits
        - Visual timeframe cards with data availability info
        
        **⚡ Performance Improvements:**
        - Concurrent downloads for faster processing
        - Cached search results for better responsiveness  
        - Progress tracking for multi-timeframe downloads
        
        **📊 Enhanced Data Handling:**
        - 4-hour data resampled from 1-hour intervals
        - Automatic period validation per timeframe
        - Smart filename generation with timestamps
        
        **🎛️ Quick Presets:**
        - **Intraday**: 1m, 5m, 15m, 1h for day trading
        - **Standard**: 5m, 1h, 1d for general analysis
        """
        
        st.markdown(features_text)
        
        # Version Info Section
        st.markdown("### ℹ️ App Information")
        version_html = f'<div class="version-info"><strong>📊 YFinance Data Downloader v{APP_VERSION}</strong><br>Released: {VERSION_DATE}<br>Status: ✅ Active & Updated with Multi-Timeframe Support</div>'
        st.markdown(version_html, unsafe_allow_html=True)

# Footer
st.markdown("---")
col_footer1, col_footer2, col_footer3 = st.columns([2, 1, 1])

with col_footer1:
    st.markdown(f"*YFinance Multi-Timeframe Data Downloader v{APP_VERSION} - Perfect for algorithmic trading and technical analysis.*")

with col_footer2:
    st.markdown("*Data: Yahoo Finance*")

with col_footer3:
    st.markdown(f"*Updated: {VERSION_DATE}*")
