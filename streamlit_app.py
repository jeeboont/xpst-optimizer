# Minimal Working XPST Optimizer - Guaranteed to Deploy
# Simplified version to fix deployment issues

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import warnings

warnings.filterwarnings('ignore')

# Set page configuration
st.set_page_config(
    page_title="XPST Optimizer",
    page_icon="🎯",
    layout="wide"
)

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

# Main application
def main():
    if not check_password():
        st.stop()
    
    # Header
    st.title("🎯 XPST Optimizer")
    st.markdown("**Interactive Trading Strategy Optimizer**")
    
    # Test message
    st.success("✅ App is working! The complex optimization features are being updated.")
    
    # Asset configuration
    assets = {
        'BTCUSD': 'BTC-USD',
        'ETHUSD': 'ETH-USD', 
        'XAUUSD': 'GC=F',
        'EURUSD': 'EURUSD=X',
        'GBPUSD': 'GBPUSD=X',
        'USDJPY': 'USDJPY=X'
    }
    
    # Sidebar
    st.sidebar.header("Configuration")
    
    # Asset selection
    selected_asset = st.sidebar.selectbox(
        "Select Asset",
        options=list(assets.keys()),
        index=0
    )
    
    # Timeframe selection
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        options=['5m', '15m', '30m', '1h'],
        index=0
    )
    
    period = st.sidebar.selectbox(
        "Period", 
        options=['1d', '5d', '1mo'],
        index=2
    )
    
    # Test data download
    if st.button("🧪 Test Data Download"):
        try:
            with st.spinner(f"Testing download for {selected_asset}..."):
                yf_symbol = assets[selected_asset]
                ticker = yf.Ticker(yf_symbol)
                data = ticker.history(period=period, interval=timeframe)
                
                if len(data) > 0:
                    st.success(f"✅ Successfully downloaded {len(data)} bars for {selected_asset}")
                    
                    # Show sample data
                    st.subheader("Sample Data")
                    st.dataframe(data.head(10))
                    
                    # Basic statistics
                    st.subheader("Basic Statistics")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total Bars", len(data))
                    with col2:
                        st.metric("Avg Close", f"{data['Close'].mean():.2f}")
                    with col3:
                        st.metric("Max High", f"{data['High'].max():.2f}")
                    with col4:
                        st.metric("Min Low", f"{data['Low'].min():.2f}")
                    
                else:
                    st.error("❌ No data received")
                    
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    # Status information
    st.markdown("---")
    st.info("""
    **Status Update**: 
    - ✅ Basic app functionality working
    - ✅ Data download working  
    - ⏳ Full optimization features being updated
    - 🔄 Please check back soon for complete functionality
    """)
    
    # Debug info
    if st.checkbox("Show Debug Info"):
        st.markdown("### 🔧 Debug Information")
        st.write("Selected Asset:", selected_asset)
        st.write("Yahoo Finance Symbol:", assets[selected_asset])
        st.write("Timeframe:", timeframe)
        st.write("Period:", period)
        st.write("Streamlit Version:", st.__version__)

if __name__ == "__main__":
    main()