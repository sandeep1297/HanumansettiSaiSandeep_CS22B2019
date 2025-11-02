import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import time
from typing import Dict, Any, List, Optional
import json

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000/api/v1"
REFRESH_INTERVAL_SECONDS = 3 # Fast refresh for live stats

# --- Helper Functions (API Clients) ---

def fetch_analysis_data(params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetches full pairs analysis data from the FastAPI backend."""
    try:
        response = requests.post(f"{API_BASE_URL}/analysis", json=params, timeout=120)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching analysis data. Ensure the FastAPI server is running at {API_BASE_URL}: {e}")
        return None

def fetch_live_stats() -> Optional[Dict[str, Any]]:
    """Fetches real-time metrics from the FastAPI backend."""
    try:
        response = requests.get(f"{API_BASE_URL}/live_stats", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        # Server might be starting or momentarily busy
        return None 

# --- Helper Functions (Plotly Charts) ---

def create_price_chart(df: pd.DataFrame, sym1: str, sym2: str) -> go.Figure:
    """Creates an interactive line chart for the two symbols' closing prices."""
    fig = go.Figure()
    
    # Add Price 1 (Y) - Primary Y-axis
    fig.add_trace(go.Scatter(x=df['ts'], y=df['Price_Y'], mode='lines', name=sym1, yaxis='y1'))
    
    # Add Price 2 (X) - Secondary Y-axis
    fig.add_trace(go.Scatter(x=df['ts'], y=df['Price_X'], mode='lines', name=sym2, yaxis='y2', opacity=0.8))
    
    fig.update_layout(
        title=f'Price Correlation: {sym1} (Y) vs {sym2} (X)',
        xaxis_title='Time',
        # Primary Y-axis for sym1 (left)
        yaxis=dict(title=f'Price - {sym1}', side='left', showgrid=False),
        # Secondary Y-axis for sym2 (right)
        yaxis2=dict(title=f'Price - {sym2}', side='right', overlaying='y', showgrid=False),
        legend=dict(x=0.01, y=0.99),
        height=500,
        hovermode="x unified",
        template="plotly_dark"
    )
    return fig

def create_spread_zscore_chart(df: pd.DataFrame, window: int) -> go.Figure:
    """Creates a chart showing the spread and the Z-score."""
    fig = go.Figure()

    # Z-Score Trace (Primary Y-axis: 'y1')
    fig.add_trace(go.Scatter(x=df['ts'], y=df['Z_Score'], mode='lines', name='Z-Score (Left Axis)', yaxis='y1', line=dict(color='#0ea5e9')))
    # Mean is always 0 in Z-score calculation
    fig.add_trace(go.Scatter(x=df['ts'], y=df['Z_Score'].rolling(window=len(df)).mean(), mode='lines', name='Historical Mean', yaxis='y1', line=dict(color='grey', dash='dash')))

    # Spread Trace (Secondary Y-axis: 'y2')
    fig.add_trace(go.Scatter(x=df['ts'], y=df['Spread'], mode='lines', name='Spread (Right Axis)', yaxis='y2', opacity=0.4, line=dict(color='orange')))
    
    # 🐞 FIX 1: Changed 'yaxis' to 'yref' for hline shapes to reference the Z-Score axis ('y1')
    fig.add_hline(y=2.0, line_dash="dot", annotation_text="+2 Sigma", yref='y1', line_color='red')
    fig.add_hline(y=-2.0, line_dash="dot", annotation_text="-2 Sigma", yref='y1', line_color='red')
    fig.add_hline(y=0.0, line_dash="dash", annotation_text="Zero Line", yref='y1', line_color='grey')

    fig.update_layout(
        title=f'Spread and Z-Score (Rolling Window: {window})',
        xaxis_title='Time',
        yaxis=dict(title='Z-Score', side='left', showgrid=True),
        yaxis2=dict(title='Spread Value', side='right', overlaying='y', showgrid=False),
        hovermode="x unified",
        height=500,
        template="plotly_dark"
    )
    return fig

def create_correlation_chart(df: pd.DataFrame) -> go.Figure:
    """Creates a chart for the rolling correlation."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['ts'], y=df['Rolling_Correlation'], mode='lines', name='Rolling Correlation'))
    fig.update_layout(
        title='Rolling Correlation',
        xaxis_title='Time',
        yaxis_title='Correlation Coefficient',
        yaxis=dict(range=[-1.0, 1.0]), # Correlation is always between -1 and 1
        height=300,
        template="plotly_dark"
    )
    return fig

# --- Main Dashboard Function ---

def run_dashboard():
    # Use wide layout for better chart visibility
    st.set_page_config(layout="wide", page_title="Binance Quant Analytics")
    st.title("📈 Real-Time Quant Analytics Dashboard")
    st.caption("Data ingestion and analysis powered by Python (websockets, SQLAlchemy, FastAPI).")

    # --- Sidebar Controls ---
    st.sidebar.header("Analysis Parameters")
    
    SYMBOLS = ["BTCUSDT", "ETHUSDT"] 
    sym1 = st.sidebar.selectbox("Symbol 1 (Y)", SYMBOLS, index=0)
    sym2 = st.sidebar.selectbox("Symbol 2 (X)", SYMBOLS, index=1)
    
    if sym1 == sym2:
        st.sidebar.error("Symbols must be different for pairs analysis.")
        return

    timeframe_map = {'1 Minute': '1min', '5 Minutes': '5min', '15 Minutes': '15min'} # Note: aliases changed from 'T' to 'min' in analytics.resampling
    selected_timeframe_key = st.sidebar.radio("Timeframe", list(timeframe_map.keys()), index=1)
    timeframe = timeframe_map[selected_timeframe_key]

    rolling_window = st.sidebar.slider("Rolling Window Size (Bars)", min_value=10, max_value=200, value=60)
    lookback_minutes = st.sidebar.slider("Historical Lookback (Minutes)", min_value=60, max_value=1440, value=720, step=60) 

    st.sidebar.markdown("---")
    st.sidebar.subheader("Data Upload (Extension)")
    # Functionality to upload OHLC data (required feature)
    uploaded_file = st.sidebar.file_uploader("Upload Historical OHLC CSV (for backtesting)", type="csv")
    if uploaded_file is not None:
        st.sidebar.success(f"File '{uploaded_file.name}' uploaded successfully.")
        st.sidebar.caption("The analysis pipeline is designed to be extensible to use this data, though it currently runs on live stream data.")

    # --- Main Content Area ---

    # 1. Live Stats (Updates constantly)
    st.header("⚡️ Near Real-Time Metrics")
    live_stats_placeholder = st.empty()
    
    # 2. Main Analysis Trigger and Results
    st.header(f"📊 Full Pairs Analysis: {sym1} vs {sym2} ({selected_timeframe_key})")
    
    if 'analysis_data' not in st.session_state:
        st.session_state['analysis_data'] = None

    if st.button("Run Full Analysis & Recalculate OLS", key="run_analysis"):
        st.session_state['analysis_data'] = None
        
        api_params = {
            "symbol1": sym1,
            "symbol2": sym2,
            "timeframe": timeframe,
            "rolling_window": rolling_window,
            "lookback_minutes": lookback_minutes
        }
        
        with st.spinner(f'Fetching {lookback_minutes} minutes of ticks and calculating analytics...'):
            data = fetch_analysis_data(api_params)
        
        if data and data.get("status") == "success":
            st.session_state['analysis_data'] = data
            st.success("Analysis complete!")
        else:
            st.error("Analysis failed. See console for error details or check data availability.")
        
    # --- Display Results ---
    
    if st.session_state['analysis_data']:
        data = st.session_state['analysis_data']
        metadata = data['metadata']
        df = pd.DataFrame(data['timeseries_data'])
        df['ts'] = pd.to_datetime(df['ts']) 
        
        # Summary Metrics
        st.subheader("Summary Metrics & Cointegration Test")
        col1, col2, col3 = st.columns(3)
        col1.metric("Hedge Ratio (β)", f"{metadata.get('Hedge_Ratio'):.4f}")
        col2.metric("Data Bars Analyzed", len(df))
        
        # ADF Test Display
        adf_res = metadata['ADF_Test_Results']
        adf_pvalue = adf_res.get('p-value', 'N/A')
        stationarity_status = "✅ Stationary (p < 0.05)" if adf_res.get('Is_Stationary_95%', False) else "❌ Non-Stationary (Mean Reversion Risk)"
        col3.metric("ADF p-value", f"{adf_pvalue}")
        st.info(f"**Cointegration Check:** {stationarity_status}")
        
        st.markdown("---")

        # 3. Visualization Section
        # 🐞 FIX 2: Changed use_container_width=True to width='stretch'
        st.plotly_chart(create_price_chart(df, sym1, sym2), width='stretch')
        st.plotly_chart(create_spread_zscore_chart(df, rolling_window), width='stretch')
        st.plotly_chart(create_correlation_chart(df), width='stretch')

        # Data Export (Download button)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Full Time-Series Analysis Data (CSV)",
            data=csv,
            file_name=f'pairs_analysis_{sym1}_{sym2}_{timeframe}.csv',
            mime='text/csv',
        )

    # --- Live Stats Loop ---
    while True:
        live_data = fetch_live_stats()
        
        with live_stats_placeholder.container():
            st.subheader("⚡️ Near Real-Time Metrics (BTCUSDT/ETHUSDT)")
            col1, col2, col3, col4 = st.columns(4)
            
            if live_data and live_data.get("status") == "live":
                z_score = live_data['latest_z_score']
                alert_status = "🟢 Neutral"
                if z_score > 2.0:
                    # Rule-based alert
                    st.toast("🚨 ALERT: Z-Score > +2.0 (Short Spread Opportunity)", icon="🚨")
                    alert_status = f"🔴 SHORT Spread Alert ({z_score})"
                elif z_score < -2.0:
                    st.toast("🚨 ALERT: Z-Score < -2.0 (Long Spread Opportunity)", icon="🚨")
                    alert_status = f"🟢 LONG Spread Alert ({z_score})"
                    
                col1.metric("Latest Z-Score", f"{z_score:.4f}", help=alert_status)
                col2.metric("Latest Spread", f"{live_data['latest_spread']:.4f}")
                col3.metric("BTCUSDT Price", f"${live_data['latest_price_y']:.2f}")
                col4.metric("ETHUSDT Price", f"${live_data['latest_price_x']:.2f}")
            else:
                 st.warning("Waiting for API server (or data accumulation)...")

        # Control the update speed
        time.sleep(REFRESH_INTERVAL_SECONDS)


if __name__ == '__main__':
    run_dashboard()