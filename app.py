import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# Load stock list
@st.cache_data
def load_stocklist():
    file_path = "stocklist.xlsx"
    xls = pd.ExcelFile(file_path)
    sheets = xls.sheet_names  # Get sheet names
    return {sheet: pd.read_excel(xls, sheet_name=sheet)['Symbol'].dropna().tolist() for sheet in sheets}

# Fetch stock data from yfinance
def get_stock_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        earnings = stock.calendar
        
        # Fundamental Factors
        earnings_surprise = info.get('earningsSurprise', np.nan)  # % Earnings Beat
        revenue_growth = info.get('revenueGrowth', np.nan)
        
        # Technical Factors
        hist = stock.history(period="6mo")
        if not hist.empty:
            price_above_sma = 1 if hist['Close'][-1] > hist['Close'].rolling(50).mean()[-1] else 0
            rising_volume = 1 if hist['Volume'][-1] > hist['Volume'].rolling(20).mean()[-1] else 0
        else:
            price_above_sma = np.nan
            rising_volume = np.nan
        
        # Next Earnings Date
        next_earnings_date = earnings.get('Earnings Date', [np.nan])[0]

        return {
            "Symbol": symbol,
            "Earnings Surprise %": earnings_surprise if pd.notna(earnings_surprise) else 0,
            "Revenue Growth": revenue_growth if pd.notna(revenue_growth) else 0,
            "Price > 50-day SMA": price_above_sma,
            "Rising Volume": rising_volume,
            "Next Earnings Date": next_earnings_date
        }
    except Exception as e:
        return None

# Rank stocks based on Earnings Momentum & Breakout Strategy
def calculate_stock_scores(df, risk_tolerance):
    df = df.dropna().reset_index(drop=True)
    
    # Assigning Scores
    df["Fundamental Score"] = df["Earnings Surprise %"].rank(ascending=False) + df["Revenue Growth"].rank(ascending=False)
    df["Technical Score"] = df["Price > 50-day SMA"] + df["Rising Volume"]

    # Calculate Breakout Probability %
    df["Breakout Probability %"] = ((df["Fundamental Score"] * 0.6) + (df["Technical Score"] * 0.4)) * 10
    
    # Adjusting allocation based on risk tolerance
    if risk_tolerance == "Aggressive":
        df["Position Size"] = df["Fundamental Score"] * 1.2 + df["Technical Score"] * 0.8
    elif risk_tolerance == "Conservative":
        df["Position Size"] = df["Fundamental Score"] * 0.8 + df["Technical Score"] * 1.2
    else:
        df["Position Size"] = df["Fundamental Score"] + df["Technical Score"]

    df = df.sort_values(by="Breakout Probability %", ascending=False)
    
    return df

# Streamlit UI
st.title("📊 Earnings Momentum + Breakout Strategy")

# Load stocklist
stocklist = load_stocklist()
sheet_selection = st.selectbox("Select Stock List", options=list(stocklist.keys()))

# User Inputs
risk_tolerance = st.radio("Select Risk Tolerance", ["Conservative", "Balanced", "Aggressive"], index=1)
time_horizon = st.radio("Select Time Horizon", ["Hold until Earnings", "Hold 3M Post-Earnings"], index=0)

# Fetch data for selected stocks
symbols = stocklist[sheet_selection]
st.write(f"Fetching data for {len(symbols)} stocks...")

stock_data = [get_stock_data(symbol) for symbol in symbols]
stock_df = pd.DataFrame([s for s in stock_data if s])

# Check if data exists
if not stock_df.empty:
    filtered_df = calculate_stock_scores(stock_df, risk_tolerance)
    
    # Display top stock picks with Breakout Probability %
    st.subheader("🏆 Pre-Earnings Stock Picks")
    st.dataframe(filtered_df[["Symbol", "Next Earnings Date", "Breakout Probability %", "Position Size"]].head(10))
    
    # Entry & Exit Strategy
    st.subheader("📈 Entry/Exit Points")
    filtered_df["Entry Point"] = "Buy now (pre-earnings)"
    filtered_df["Exit Point"] = "Sell after earnings" if time_horizon == "Hold until Earnings" else "Hold 3 months"
    st.dataframe(filtered_df[["Symbol", "Breakout Probability %", "Entry Point", "Exit Point"]].head(10))

else:
    st.warning("No stock data found. Try selecting another sheet or check stock symbols.")
