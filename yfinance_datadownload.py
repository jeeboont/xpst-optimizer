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

# App Version Control
APP_VERSION = "2.1.0"
VERSION_DATE = "2025-08-21"
CHANGELOG = {
    "2.1.0": {
        "date": "2025-08-21",
        "changes": [
            "Added version control and changelog",
            "Fixed Yahoo Finance timeframe/period compatibility issues",
            "Improved real-time search with autocomplete",
            "Added popular stocks database for instant suggestions",
            "Enhanced UI with better visual feedback"
        ]
    },
    "2.0.0": {
        "date": "2025-08-21", 
        "changes": [
            "Complete UI redesign with left sidebar",
            "Added real-time ticker search functionality",
            "Implemented smart timeframe/period validation",
            "Added data preview feature",
            "Enhanced error handling and user feedback"
        ]
    },
    "1.0.0": {
        "date": "2025-08-21",
        "changes": [
            "Initial release",
            "Basic asset selection and data download",
            "ZIP file export functionality",
            "Support for stocks, crypto, forex, and commodities"
        ]
    }
}

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

# Popular stocks database for instant suggestions
POPULAR_STOCKS = {
    # Technology
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
    'adobe': {'symbol': 'ADBE', 'name': 'Adobe Inc.', 'sector': 'Technology'},
    'salesforce': {'symbol': 'CRM', 'name': 'Salesforce, Inc.', 'sector': 'Technology'},
    
    # Finance
    'berkshire': {'symbol': 'BRK-B', 'name': 'Berkshire Hathaway Inc.', 'sector': 'Financial'},
    'jpmorgan': {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'sector': 'Financial'},
    'visa': {'symbol': 'V', 'name': 'Visa Inc.', 'sector': 'Financial'},
    'mastercard': {'symbol': 'MA', 'name': 'Mastercard Incorporated', 'sector': 'Financial'},
    'paypal': {'symbol': 'PYPL', 'name': 'PayPal Holdings, Inc.', 'sector': 'Financial'},
    
    # Healthcare
    'johnson': {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'sector': 'Healthcare'},
    'pfizer': {'symbol': 'PFE', 'name': 'Pfizer Inc.', 'sector': 'Healthcare'},
    'moderna': {'symbol': 'MRNA', 'name': 'Moderna, Inc.', 'sector': 'Healthcare'},
    
    # Consumer
    'coca': {'symbol': 'KO', 'name': 'The Coca-Cola Company', 'sector': 'Consumer'},
    'pepsi': {'symbol': 'PEP', 'name': 'PepsiCo, Inc.', 'sector': 'Consumer'},
    'walmart': {'symbol': 'WMT', 'name': 'Walmart Inc.', 'sector': 'Retail'},
    'disney': {'symbol': 'DIS', 'name': 'The Walt Disney Company', 'sector': 'Media'},
    'nike': {'symbol': 'NKE', 'name': 'NIKE, Inc.', 'sector': 'Consumer'},
    'starbucks': {'symbol': 'SBUX', 'name': 'Starbucks Corporation', 'sector': 'Consumer'},
    
    # ETFs and Indices
    'spy': {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF Trust', 'sector': 'ETF'},
    'qqq': {'symbol': 'QQQ', 'name': 'Invesco QQQ Trust', 'sector': 'ETF'},
    'vti': {'symbol': 'VTI', 'name': 'Vanguard Total Stock Market ETF', 'sector': 'ETF'},
    
    # Crypto-related
    'bitcoin': {'symbol': 'BTC-USD', 'name': 'Bitcoin USD', 'sector': 'Cryptocurrency'},
    'ethereum': {'symbol': 'ETH-USD', 'name': 'Ethereum USD', 'sector': 'Cryptocurrency'},
    'coinbase': {'symbol': 'COIN', 'name': 'Coinbase Global, Inc.', 'sector': 'Cryptocurrency'},
}

def get_instant_suggestions(query):
    """Get instant suggestions from popular stocks database"""
    if not query or len(query) < 2:
        return []
    
    query_lower = query.lower()
    suggestions = []
    
    # Search in popular stocks
    for key, stock in POPULAR_STOCKS.items():
        if (query_lower in key or 
            query_lower in stock['symbol'].lower() or 
            query_lower in stock['name'].lower()):
            suggestions.append(stock)
    
    # Remove duplicates and limit results
    seen = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion['symbol'] not in seen:
            seen.add(suggestion['symbol'])
            unique_suggestions.append(suggestion)
            if len(unique_suggestions) >= 5:
                break
    
    return unique_suggestions
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
    .version-info {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #3498db;
        margin: 10px 0;
        font-size: 0.9rem;
    }
    .changelog-item {
        background-color: #fff;
        padding: 8px;
        margin: 5px 0;
        border-radius: 4px;
        border-left: 3px solid #27ae60;
    }
    .version-header {
        color: #2c3e50;
        font-weight: bold;
        margin-bottom: 5px;
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

# Timeframe and period compatibility mapping
timeframe_periods = {
    '1m': ['1d', '5d', '7d'],  # Yahoo Finance limits 1m data to max 7 days
    '2m': ['1d', '5d', '7d'], 
    '5m': ['1d', '5d', '7d'],  # Short timeframes limited to 7 days max
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
    
    # Search input with real-time suggestions
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
            # Get instant suggestions
            instant_suggestions = get_instant_suggestions(search_query)
            if instant_suggestions:
                st.session_state.search_results = instant_suggestions
                st.session_state.show_search_results = True
            else:
                # If no instant suggestions, try live search
                st.session_state.search_results = search_ticker(search_query)
                st.session_state.show_search_results = True
        else:
            st.session_state.show_search_results = False
    
    # Search and Add buttons
    col_search, col_add = st.columns([2, 1])
    with col_search:
        if st.button("🔍 Search More", use_container_width=True, disabled=not search_query):
            # Detailed search using yfinance
            st.session_state.search_results = search_ticker(search_query)
            st.session_state.show_search_results = True
    
    with col_add:
        if st.button("➕ Add Direct", help="Add as exact symbol", disabled=not search_query):
            if search_query.upper() not in st.session_state.selected_assets:
                st.session_state.selected_assets.append(search_query.upper())
                st.session_state.show_search_results = False
                # Clear search
                st.session_state.last_search_query = ""
                st.rerun()
    
    # Display search results with improved styling
    if st.session_state.show_search_results and st.session_state.search_results:
        st.markdown("**💡 Suggestions:**")
        
        # Create a container for better styling
        with st.container():
            for i, result in enumerate(st.session_state.search_results):
                # Create a card-like appearance for each suggestion
                col_info, col_select = st.columns([5, 1])
                
                with col_info:
                    # Check if already selected
                    is_selected = result['symbol'] in st.session_state.selected_assets
                    status_icon = "✅" if is_selected else "📈"
                    
                    st.markdown(f"""
                    <div style="background-color: {'#e8f5e8' if is_selected else '#f8f9fa'}; 
                                padding: 8px; border-radius: 5px; margin: 2px 0;">
                        <strong style="color: #2c3e50;">{status_icon} {result['symbol']}</strong> - {result['name']}<br>
                        <small style="color: #7f8c8d;"><em>{result.get('sector', 'N/A')}</em></small>
                    </div>
                    """, unsafe_allow_html=True)
                
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
    header_html = f'<div class="main-header"><h1>📊 YFinance Data Downloader</h1><p>Interactive Trading Data Downloader - v{APP_VERSION}</p></div>'
    st.markdown(header_html, unsafe_allow_html=True)
    
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
        
        # Version Info Section
        st.markdown("### ℹ️ App Information")
        version_html = f'<div class="version-info"><strong>📊 YFinance Data Downloader v{APP_VERSION}</strong><br>Released: {VERSION_DATE}<br>Status: ✅ Active & Updated</div>'
        st.markdown(version_html, unsafe_allow_html=True)
        
        # Instructions
        st.markdown("### 📋 How to Use")
        instructions_text = "1. **Select Assets**: Choose from predefined options or search by company name\n\n"
        instructions_text += "2. **Configure Timeframe**: Select data interval and period (auto-validated)\n\n"
        instructions_text += "3. **Download**: Get a ZIP file with CSV data for all selected assets\n\n"
        instructions_text += "**Enhanced Search Features:**\n"
        instructions_text += "- **Real-time suggestions** as you type (2+ characters)\n"
        instructions_text += "- **Popular companies** database with instant results\n"
        instructions_text += "- **Smart matching** by company name, ticker, or sector\n"
        instructions_text += "- **Visual indicators** show already selected stocks\n\n"
        instructions_text += "**Search Examples:**\n"
        instructions_text += "- Type \"apple\" → Get AAPL instantly\n"
        instructions_text += "- Type \"tech\" → See technology stocks\n"
        instructions_text += "- Type \"etf\" → Find popular ETFs\n"
        instructions_text += "- Type exact symbols like \"MSFT\" for direct match"
        st.markdown(instructions_text)

# Version Control and Changelog Section (in sidebar)
with col1:
    st.markdown("---")
    
    # Version display in sidebar
    sidebar_version = f'<div style="text-align: center; padding: 10px; background-color: #ecf0f1; border-radius: 5px;"><small><strong>v{APP_VERSION}</strong> • {VERSION_DATE}</small></div>'
    st.markdown(sidebar_version, unsafe_allow_html=True)
    
    # Changelog expander
    with st.expander("📋 Version History & Changelog"):
        st.markdown("### Recent Updates")
        
        for version, info in list(CHANGELOG.items())[:3]:  # Show last 3 versions
            changes_text = "<br>".join([f"• {change}" for change in info['changes']])
            changelog_html = f'<div class="changelog-item"><div class="version-header">v{version} - {info["date"]}</div>{changes_text}</div>'
            st.markdown(changelog_html, unsafe_allow_html=True)
        
        if len(CHANGELOG) > 3:
            st.markdown(f"*...and {len(CHANGELOG) - 3} more versions*")
        
        # Technical Info
        st.markdown("### 🛠️ Technical Details")
        tech_details = f"- **Framework**: Streamlit {st.__version__}\n"
        tech_details += "- **Data Source**: Yahoo Finance (yfinance)\n"
        tech_details += "- **Python Version**: 3.13+\n"
        tech_details += f"- **Last Updated**: {VERSION_DATE}\n"
        tech_details += "- **Dependencies**: pandas, yfinance, zipfile"
        st.markdown(tech_details)

# Main content continuation
with col2:

# Footer
st.markdown("---")
col_footer1, col_footer2, col_footer3 = st.columns([2, 1, 1])

with col_footer1:
    st.markdown(f"*YFinance Data Downloader v{APP_VERSION} - Perfect for TradingView Pine Script developers.*")

with col_footer2:
    st.markdown("*Data: Yahoo Finance*")

with col_footer3:
    st.markdown(f"*Updated: {VERSION_DATE}*")
