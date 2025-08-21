import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io
import base64
from datetime import datetime, timedelta
import os

# Set page config
st.set_page_config(
    page_title="YFinance Data Downloader", 
    page_icon="📊",
    layout="wide"
)

# Custom CSS to style the app
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #34495e;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .predefined-asset {
        background-color: #e74c3c;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        margin: 0.25rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="main-header">📊 YFinance Data Downloader</div>', unsafe_allow_html=True)

# Predefined Assets Section
st.markdown('<div class="section-header">Predefined Assets</div>', unsafe_allow_html=True)

# Initialize session state for selected assets
if 'selected_assets' not in st.session_state:
    st.session_state.selected_assets = []

# Predefined assets with their yfinance symbols
predefined_assets = {
    'BTCUSD': 'BTC-USD',
    'XAUUSD': 'GC=F',  # Gold futures
    'ETHUSD': 'ETH-USD',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X'
}

# Create columns for predefined assets
cols = st.columns(3)
for i, (display_name, symbol) in enumerate(predefined_assets.items()):
    with cols[i % 3]:
        if st.button(f"📈 {display_name}", key=f"predefined_{symbol}"):
            if symbol not in st.session_state.selected_assets:
                st.session_state.selected_assets.append(symbol)

# Display selected predefined assets
if st.session_state.selected_assets:
    st.write("**Selected Assets:**")
    selected_cols = st.columns(len(st.session_state.selected_assets))
    for i, asset in enumerate(st.session_state.selected_assets):
        with selected_cols[i]:
            display_name = [k for k, v in predefined_assets.items() if v == asset][0] if asset in predefined_assets.values() else asset
            if st.button(f"❌ {display_name}", key=f"remove_{asset}"):
                st.session_state.selected_assets.remove(asset)
                st.rerun()

# Add Custom Ticker Section
st.markdown('<div class="section-header">Add Custom Ticker:</div>', unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    custom_ticker = st.text_input(
        "Enter Symbol (e.g., AAPL, TSLA, SPY)",
        placeholder="Type ticker symbol...",
        help="Enter any valid Yahoo Finance ticker symbol"
    )
with col2:
    if st.button("Add Ticker", disabled=not custom_ticker):
        if custom_ticker.upper() not in st.session_state.selected_assets:
            st.session_state.selected_assets.append(custom_ticker.upper())
            st.rerun()

# Timeframe Settings Section
st.markdown('<div class="section-header">⏰ Timeframe Settings</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.write("**Timeframe**")
    timeframe_options = {
        '1m': '1m',
        '5m': '5m', 
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '4h': '4h',
        '1d': '1d'
    }
    selected_timeframe = st.selectbox(
        "Select timeframe:",
        options=list(timeframe_options.keys()),
        index=6,  # Default to 1d
        label_visibility="collapsed"
    )

with col2:
    st.write("**Period**")
    period_options = {
        '7d': '7d',
        '1mo': '1mo',
        '3mo': '3mo', 
        '6mo': '6mo',
        '1y': '1y',
        '2y': '2y',
        '5y': '5y',
        'max': 'max'
    }
    selected_period = st.selectbox(
        "Select period:",
        options=list(period_options.keys()),
        index=0,  # Default to 7d
        label_visibility="collapsed"
    )

# Download Section
st.markdown('<div class="section-header">📥 Download Data</div>', unsafe_allow_html=True)

if st.session_state.selected_assets:
    if st.button("🚀 Download Price Data", type="primary", use_container_width=True):
        try:
            with st.spinner('Downloading data...'):
                # Create a BytesIO object to store the zip file
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for asset in st.session_state.selected_assets:
                        try:
                            # Download data from yfinance
                            ticker = yf.Ticker(asset)
                            data = ticker.history(
                                period=period_options[selected_period],
                                interval=timeframe_options[selected_timeframe]
                            )
                            
                            if not data.empty:
                                # Prepare filename
                                filename = f"{asset}_{selected_timeframe}_{selected_period}.csv"
                                
                                # Convert to CSV string
                                csv_string = data.to_csv()
                                
                                # Add to zip file
                                zip_file.writestr(filename, csv_string)
                                
                                st.success(f"✅ Downloaded {asset}")
                            else:
                                st.warning(f"⚠️ No data found for {asset}")
                                
                        except Exception as e:
                            st.error(f"❌ Error downloading {asset}: {str(e)}")
                
                # Prepare download
                zip_buffer.seek(0)
                
                # Create download button
                st.download_button(
                    label="📦 Download ZIP File",
                    data=zip_buffer.getvalue(),
                    file_name=f"trading_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
                
                st.success("🎉 Data ready for download!")
                
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
else:
    st.info("👆 Please select at least one asset to download data.")

# Instructions
with st.expander("📋 Instructions"):
    st.markdown("""
    **How to use this app:**
    
    1. **Select Assets**: Choose from predefined crypto/forex pairs or add custom ticker symbols
    2. **Configure Timeframe**: Select the data interval (1m, 5m, 1h, 1d, etc.)
    3. **Choose Period**: Select how much historical data to download (7d, 1mo, 1y, etc.)
    4. **Download**: Click the download button to get a ZIP file with all your data
    
    **For TradingView Pine Script:**
    - The CSV files contain OHLCV data that you can use for backtesting
    - Each file is named with the format: `SYMBOL_TIMEFRAME_PERIOD.csv`
    - Data includes: Open, High, Low, Close, Volume columns
    
    **Supported Symbols:**
    - Stocks: AAPL, TSLA, MSFT, etc.
    - Crypto: BTC-USD, ETH-USD, etc.  
    - Forex: EURUSD=X, GBPUSD=X, etc.
    - Commodities: GC=F (Gold), CL=F (Oil), etc.
    """)

# Footer
st.markdown("---")
st.markdown("*YFinance Data Downloader - Perfect for TradingView Pine Script developers. Data provided by Yahoo Finance.*")
