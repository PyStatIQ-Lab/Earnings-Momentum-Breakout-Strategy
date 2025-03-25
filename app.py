import streamlit as st
import yfinance as yf
import pandas as pd
import ta  # Using 'ta' for technical indicators

# Load stock list
@st.cache_data
def load_stocklist():
    xls = pd.ExcelFile("stocklist.xlsx")
    return {sheet: xls.parse(sheet) for sheet in xls.sheet_names}

stock_data = load_stocklist()
sheet_names = list(stock_data.keys())

# User inputs
st.title("Earnings Momentum + Breakout Strategy")
st.sidebar.header("Stock Selection")
selected_sheet = st.sidebar.selectbox("Select Stock List", sheet_names)
st.sidebar.header("Strategy Settings")
risk_tolerance = st.sidebar.slider("Risk Tolerance", 1, 10, 5)
time_horizon = st.sidebar.radio("Time Horizon", ["Short-term", "Medium-term"])

# Get stock symbols
symbols = stock_data[selected_sheet]["Symbol"].dropna().tolist()

def get_stock_data(symbol):
    df = yf.download(symbol, period="6mo", interval="1d")
    if df.empty:
        return None
    df["50SMA"] = ta.trend.sma_indicator(df["Close"], window=50)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    df["Volume Change"] = df["Volume"].pct_change()
    return df

st.subheader("🏆 Pre-Earnings Stock Picks")
final_picks = []

for symbol in symbols:
    df = get_stock_data(symbol)
    if df is not None and len(df) > 50:
        latest = df.iloc[-1]
        
        price_above_sma = latest["Close"] > latest["50SMA"]
        rsi_positive = latest["RSI"] > 50
        volume_surge = latest["Volume Change"] > 0.2
        
        if price_above_sma and rsi_positive and volume_surge:
            probability = (price_above_sma * 0.4 + rsi_positive * 0.4 + volume_surge * 0.2) * 100
            final_picks.append({"Symbol": symbol, "Probability": f"{probability:.2f}%"})

if final_picks:
    st.table(pd.DataFrame(final_picks))
else:
    st.write("No stocks meet the criteria.")
