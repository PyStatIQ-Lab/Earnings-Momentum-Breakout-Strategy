import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta  # Importing pandas_ta for technical indicators

# Load stock list
@st.cache_data
def load_stocklist():
    file_path = "stocklist.xlsx"
    xls = pd.ExcelFile(file_path)
    sheets = xls.sheet_names  # Get sheet names
    return {sheet: pd.read_excel(xls, sheet_name=sheet)['Symbol'].dropna().tolist() for sheet in sheets}

# Fetch stock data from yfinance and calculate technical indicators
def get_stock_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        earnings = stock.calendar
        
        # Fundamental Factors
        earnings_surprise = info.get('earningsSurprise', np.nan)  # % Earnings Beat
        revenue_growth = info.get('revenueGrowth', np.nan)
        pe_ratio = info.get('trailingPE', np.nan)  # P/E Ratio
        pb_ratio = info.get('priceToBook', np.nan)  # P/B Ratio
        debt_to_equity = info.get('debtToEquity', np.nan)  # Debt-to-Equity Ratio
        dividend_yield = info.get('dividendYield', np.nan)  # Dividend Yield
        
        # Fetch historical price data (6 months)
        hist = stock.history(period="6mo")
        
        if not hist.empty:
            # Technical Indicators
            hist['EMA50'] = ta.ema(hist['Close'], length=50)
            hist['EMA20'] = ta.ema(hist['Close'], length=20)
            hist['EMA200'] = ta.ema(hist['Close'], length=200)
            hist['RSI'] = ta.rsi(hist['Close'], length=14)
            hist['MACD'], hist['MACD_Signal'], _ = ta.macd(hist['Close'])
            hist['Volume Surge'] = hist['Volume'] / hist['Volume'].rolling(20).mean()
            hist['BB_upper'], hist['BB_middle'], hist['BB_lower'] = ta.bbands(hist['Close'], length=20, std=2)
            hist['StochK'], hist['StochD'] = ta.stoch(hist['High'], hist['Low'], hist['Close'], k=14, d=3)
            hist['ATR'] = ta.atr(hist['High'], hist['Low'], hist['Close'], length=14)
        
        # Technical Factors (Signal Calculation)
        price_above_ema50 = 1 if hist['Close'].iloc[-1] > hist['EMA50'].iloc[-1] else 0
        rsi_positive = 1 if hist['RSI'].iloc[-1] > 50 else 0
        macd_crossover = 1 if hist['MACD'].iloc[-1] > hist['MACD_Signal'].iloc[-1] else 0
        volume_surge = 1 if hist['Volume Surge'].iloc[-1] > 1.5 else 0
        price_above_ema20 = 1 if hist['Close'].iloc[-1] > hist['EMA20'].iloc[-1] else 0
        bollinger_breakout = 1 if hist['Close'].iloc[-1] > hist['BB_upper'].iloc[-1] else 0
        
        # Next Earnings Date
        next_earnings_date = earnings.get('Earnings Date', [np.nan])[0]

        return {
            "Symbol": symbol,
            "Earnings Surprise %": earnings_surprise if pd.notna(earnings_surprise) else 0,
            "Revenue Growth": revenue_growth if pd.notna(revenue_growth) else 0,
            "P/E Ratio": pe_ratio if pd.notna(pe_ratio) else 0,
            "P/B Ratio": pb_ratio if pd.notna(pb_ratio) else 0,
            "Debt-to-Equity": debt_to_equity if pd.notna(debt_to_equity) else 0,
            "Dividend Yield": dividend_yield if pd.notna(dividend_yield) else 0,
            "Price > EMA50": price_above_ema50,
            "RSI > 50": rsi_positive,
            "MACD Bullish": macd_crossover,
            "Volume Surge": volume_surge,
            "Price > EMA20": price_above_ema20,
            "Bollinger Band Breakout": bollinger_breakout,
            "Next Earnings Date": next_earnings_date
        }
    except Exception as e:
        return None

# Rank stocks based on Earnings Momentum & Breakout Strategy
def calculate_stock_scores(df, risk_tolerance):
    df = df.dropna().reset_index(drop=True)
    
    # Assigning Scores
    df["Fundamental Score"] = df["Earnings Surprise %"].rank(ascending=False) + df["Revenue Growth"].rank(ascending=False) + df["P/E Ratio"].rank(ascending=True) + df["P/B Ratio"].rank(ascending=True) + df["Debt-to-Equity"].rank(ascending=True)
    df["Technical Score"] = df["Price > EMA50"] + df["RSI > 50"] + df["MACD Bullish"] + df["Volume Surge"] + df["Price > EMA20"] + df["Bollinger Band Breakout"]
    
    # Calculate Breakout Probability %
    df["Breakout Probability %"] = ((df["Fundamental Score"] * 0.5) + (df["Technical Score"] * 0.5)) * 10
    
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
