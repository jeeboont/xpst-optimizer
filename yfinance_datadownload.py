import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io
import base64
from datetime import datetime, timedelta
import os
import requests
import json

# Set page config
st.set_page_config(
    page_title="YFinance Data Downloader", 
    page_icon="📊",
    layout="wide"
)

# Custom CSS to create sidebar layout and styling
st.markdown("""
<style>
    .main-content {
        margin-left: 0px;
    }
    .sidebar {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
    }
    .selected-asset {
        background-color: #e74c3c;
        color: white;
        padding: 5px 10px;
        border-radius: 15px;
        margin: 2px;
        display: inline-block;
        font-size: 0.9rem;
    }
    .main-header {
        background: linear-gradient(90deg, #3498db, #2980b9);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
    }
    .main-header p {
        margin: 5px 0 0 0;
        font-size: 1.1rem;
        opacity: 0.9;
    }
    .download-section {
        background-color: #ecf0f1;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }
    .stSelectbox > div > div > select {
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'selected_assets' not in st.session_state:
    st.session_state.selected_assets = []
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'show_search_results' not in st.session_state:
    st.session_state.show_search_results = False

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

# Timeframe and period compatibility mapping
timeframe_periods = {
    '1m': ['1d', '5d', '7d'],
    '2m': ['1d', '5d', '7d'], 
    '5m': ['1d', '5d', '7d'],
    '15m': ['1d', '5d', '7d'],
    '30m': ['1d', '5d', '7d'],
    '60m': ['1d', '5d', '7d'],
    '90m': ['1d', '5d', '7d'],
    '1h': ['1d', '5d', '7d'],
    '1d': ['5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'],
    '5d': ['1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'],
    '1wk': ['1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'],
    '1mo': ['1y', '2y', '5y', '10y', 'ytd', 'max'],
    '3mo': ['2y', '5y', '10y', 'ytd', 'max']
}

# Function to search for tickers
def search_ticker(query):
    """Search for ticker symbols using yfinance"""
    if not query or len(query) < 2:
        return []
    
    try:
        # Use yfinance's Ticker search functionality
        # This is a simple approach - in practice, you might want to use a more comprehensive search
        search_results = []
        
        # Common stock exchanges and suffixes to try
        variations = [
            query.upper(),
            f"{query.upper()}.TO",  # Toronto
            f"{query.upper()}.L",   # London
            f"{query.upper()}.T",   # Tokyo
            f"{query.upper()}.HK",  # Hong Kong
        ]
        
        for variation in variations[:3]:  # Limit to first 3 variations
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
                    if len(search_results) >= 5:  # Limit results
                        break
            except:
                continue
        
        # Also try some popular ticker patterns
        if query.upper() in ['APPLE', 'AAPL']:
            search_results.insert(0, {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'})
        elif query.upper() in ['MICROSOFT', 'MSFT']:
            search_results.insert(0, {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology', 'exchange': 'NASDAQ'})
        elif query.upper() in ['TESLA', 'TSLA']:
            search_results.insert(0, {'symbol': 'TSLA', 'name': 'Tesla, Inc.', 'sector': 'Consumer Cyclical', 'exchange': 'NASDAQ'})
        elif query.upper() in ['GOOGLE', 'GOOGL', 'ALPHABET']:
            search_results.insert(0, {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'})
        elif query.upper() in ['AMAZON', 'AMZN']:
            search_results.insert(0, {'symbol': 'AMZN', 'name': 'Amazon.com, Inc.', 'sector': 'Consumer Cyclical', 'exchange': 'NASDAQ'})
        elif query.upper() in ['NVIDIA', 'NVDA']:
            search_results.insert(0, {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'Technology', 'exchange': 'NASDAQ'})
        elif query.upper() in ['META', 'FACEBOOK', 'FB']:
            search_results.insert(0, {'symbol': 'META', 'name': 'Meta Platforms, Inc.', 'sector': 'Technology', 'exchange': 'NASDAQ'})
        elif query.upper() in ['NETFLIX', 'NFLX']:
            search_results.insert(0, {'symbol': 'NFLX', 'name': 'Netflix, Inc.', 'sector': 'Communication Services', 'exchange': 'NASDAQ'})
        
        # Remove duplicates
        seen = set()
        unique_results = []
        for result in search_results:
            if result['symbol'] not in seen:
                seen.add(result['symbol'])
                unique_results.append(result)
        
        return unique_results[:5]  # Return max 5 results
        
    except Exception as e:
        st.error(f"Search error: {str(e)}")
        return []

# Create layout with sidebar and main content
col1, col2 = st.columns([1, 2])

with col1:
    # Sidebar content
    st.markdown('<div class="sidebar">', unsafe_allow_html=True)
    
    # Configuration header
    st.markdown('<div class="sidebar-header">📊 Configuration</div>', unsafe_allow_html=True)
    
    # Select Assets section
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
                # Find display name
                display_name = asset
                for display, symbol in predefined_assets.items():
                    if symbol == asset:
                        display_name = display.split(' (')[0]
                        break
                st.markdown(f'<div class="selected-asset">{display_name}</div>', unsafe_allow_html=True)
            with col_remove:
                if st.button("❌", key=f"remove_{asset}", help="Remove asset"):
                    st.session_state.selected_assets.remove(asset)
                    st.rerun()
    
    st.markdown("---")
    
    # Add Custom Ticker
    st.markdown("**Add Custom Ticker:**")
    st.markdown("Enter Symbol or Company Name")
    
    # Search input
    search_query = st.text_input(
        "search_ticker",
        placeholder="e.g., Apple, AAPL, Tesla...",
        label_visibility="collapsed",
        key="search_input"
    )
    
    # Search and Add buttons
    col_search, col_add = st.columns([2, 1])
    with col_search:
        if st.button("🔍 Search", use_container_width=True, disabled=not search_query):
            st.session_state.search_results = search_ticker(search_query)
            st.session_state.show_search_results = True
    
    with col_add:
        if st.button("➕ Add", help="Add as exact symbol", disabled=not search_query):
            if search_query.upper() not in st.session_state.selected_assets:
                st.session_state.selected_assets.append(search_query.upper())
                st.session_state.show_search_results = False
                st.rerun()
    
    # Display search results
    if st.session_state.show_search_results and st.session_state.search_results:
        st.markdown("**Search Results:**")
        for result in st.session_state.search_results:
            col_info, col_select = st.columns([4, 1])
            with col_info:
                st.markdown(f"""
                **{result['symbol']}** - {result['name']}  
                *{result.get('sector', 'N/A')} | {result.get('exchange', 'N/A')}*
                """)
            with col_select:
                if st.button("✅", key=f"select_{result['symbol']}", help="Add this ticker"):
                    if result['symbol'] not in st.session_state.selected_assets:
                        st.session_state.selected_assets.append(result['symbol'])
                        st.session_state.show_search_results = False
                        st.rerun()
    
    elif st.session_state.show_search_results and not st.session_state.search_results:
        st.info("No results found. Try searching with a different term or add the symbol directly.")
    
    st.markdown("---")
    
    # Timeframe Settings
    st.markdown('<div class="sidebar-header">⏰ Timeframe Settings</div>', unsafe_allow_html=True)
    
    # Timeframe selection
    st.markdown("**Timeframe**")
    selected_timeframe = st.selectbox(
        "timeframe",
        options=list(timeframe_periods.keys()),
        index=8,  # Default to 1d
        label_visibility="collapsed"
    )
    
    # Period selection based on timeframe
    st.markdown("**Period**")
    available_periods = timeframe_periods[selected_timeframe]
    selected_period = st.selectbox(
        "period",
        options=available_periods,
        index=0,  # Default to first available
        label_visibility="collapsed"
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    # Main content area
    st.markdown("""
    <div class="main-header">
        <h1>📊 YFinance Data Downloader</h1>
        <p>Interactive Trading Data Downloader</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Selected assets summary
    if st.session_state.selected_assets:
        st.markdown(f"**👥 Selected: {len(st.session_state.selected_assets)} assets, {selected_timeframe} timeframe**")
        
        # Download button
        st.markdown('<div class="download-section">', unsafe_allow_html=True)
        
        if st.button("🚀 Download Data & Get ZIP File", type="primary", use_container_width=True):
            try:
                with st.spinner('Downloading data...'):
                    # Create a BytesIO object to store the zip file
                    zip_buffer = io.BytesIO()
                    successful_downloads = 0
                    
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for asset in st.session_state.selected_assets:
                            try:
                                # Download data from yfinance
                                ticker = yf.Ticker(asset)
                                data = ticker.history(
                                    period=selected_period,
                                    interval=selected_timeframe
                                )
                                
                                if not data.empty:
                                    # Prepare filename
                                    filename = f"{asset}_{selected_timeframe}_{selected_period}.csv"
                                    
                                    # Convert to CSV string
                                    csv_string = data.to_csv()
                                    
                                    # Add to zip file
                                    zip_file.writestr(filename, csv_string)
                                    
                                    successful_downloads += 1
                                    st.success(f"✅ Downloaded {asset} - {len(data)} records")
                                else:
                                    st.warning(f"⚠️ No data found for {asset}")
                                    
                            except Exception as e:
                                st.error(f"❌ Error downloading {asset}: {str(e)}")
                    
                    if successful_downloads > 0:
                        # Prepare download
                        zip_buffer.seek(0)
                        
                        # Create download button
                        st.download_button(
                            label="📦 Download ZIP File",
                            data=zip_buffer.getvalue(),
                            file_name=f"yfinance_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                        
                        st.success(f"🎉 {successful_downloads} files ready for download!")
                    else:
                        st.error("❌ No data was successfully downloaded. Please check your asset symbols and try again.")
                        
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Results preview section
        st.markdown("### 📈 Data Preview")
        
        if st.session_state.selected_assets:
            preview_asset = st.selectbox(
                "Select asset to preview:",
                options=st.session_state.selected_assets,
                key="preview_asset"
            )
            
            if st.button("Preview Data", use_container_width=True):
                try:
                    with st.spinner(f'Loading preview for {preview_asset}...'):
                        ticker = yf.Ticker(preview_asset)
                        preview_data = ticker.history(
                            period=selected_period,
                            interval=selected_timeframe
                        )
                        
                        if not preview_data.empty:
                            st.dataframe(preview_data.head(10), use_container_width=True)
                            st.info(f"Showing first 10 rows of {len(preview_data)} total records")
                        else:
                            st.warning(f"No data available for {preview_asset}")
                except Exception as e:
                    st.error(f"Error loading preview: {str(e)}")
    
    else:
        st.info("👈 Please select at least one asset from the sidebar to get started.")
        
        # Instructions
        st.markdown("### 📋 How to Use")
        st.markdown("""
        1. **Select Assets**: Choose from predefined options or add custom ticker symbols
        2. **Configure Timeframe**: Select data interval and period (combinations are automatically validated)
        3. **Download**: Get a ZIP file with CSV data for all selected assets
        
        **Supported Search Terms:**
        - **Company Names**: Apple, Microsoft, Tesla, Amazon, etc.
        - **Ticker Symbols**: AAPL, MSFT, TSLA, AMZN, etc.
        - **Crypto**: Bitcoin (BTC-USD), Ethereum (ETH-USD)
        - **Forex**: Euro USD, GBP USD, etc.
        
        **Tip**: Use the search function in the sidebar to find ticker symbols by company name!
        """)

# Footer
st.markdown("---")
st.markdown("*YFinance Data Downloader - Perfect for TradingView Pine Script developers. Data provided by Yahoo Finance.*")
