import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import talib as ta  # Importing TA-Lib for technical indicators

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
        
        # Fetch historical price data (6 months)
        hist = stock.history(period="6mo")
        
        if not hist.empty:
            # Calculate technical indicators using TA-Lib
            hist['EMA50'] = ta.EMA(hist['Close'], timeperiod=50)
            hist['RSI'] = ta.RSI(hist['Close'], timeperiod=14)
            hist['MACD'], hist['MACD_Signal'], _ = ta.MACD(hist['Close'], fastperiod=12, slowperiod=26, signalperiod=9)
            hist['Volume Surge'] = hist['Volume'] / hist['Volume'].rolling(20).mean()
            
            # Additional technical indicators you may want to include:
            hist['SMA200'] = ta.SMA(hist['Close'], timeperiod=200)  # 200-day Simple Moving Average
            hist['STOCH_K'], hist['STOCH_D'] = ta.STOCH(hist['High'], hist['Low'], hist['Close'], fastk_period=14, slowk_period=3, slowd_period=3)  # Stochastic Oscillator
            hist['Bollinger_Upper'], hist['Bollinger_Middle'], hist['Bollinger_Lower'] = ta.BBANDS(hist['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)  # Bollinger Bands
            
            # Technical analysis conditions
            price_above_ema = 1 if hist['Close'].iloc[-1] > hist['EMA50'].iloc[-1] else 0
            rsi_positive = 1 if hist['RSI'].iloc[-1] > 50 else 0
            macd_crossover = 1 if hist['MACD'].iloc[-1] > hist['MACD_Signal'].iloc[-1] else 0
            volume_surge = 1 if hist['Volume Surge'].iloc[-1] > 1.5 else 0
            price_above_sma200 = 1 if hist['Close'].iloc[-1] > hist['SMA200'].iloc[-1] else 0  # Additional condition for SMA200
            stochastic_overbought = 1 if hist['STOCH_K'].iloc[-1] > 80 else 0  # Additional condition for Stochastic overbought
            bollinger_breakout = 1 if hist['Close'].iloc[-1] > hist['Bollinger_Upper'].iloc[-1] else 0  # Breakout from upper Bollinger Band
        else:
            price_above_ema = rsi_positive = macd_crossover = volume_surge = price_above_sma200 = stochastic_overbought = bollinger_breakout = np.nan

        # Next Earnings Date
        next_earnings_date = earnings.get('Earnings Date', [np.nan])[0]

        return {
            "Symbol": symbol,
            "Earnings Surprise %": earnings_surprise if pd.notna(earnings_surprise) else 0,
            "Revenue Growth": revenue_growth if pd.notna(revenue_growth) else 0,
            "Price > EMA50": price_above_ema,
            "RSI > 50": rsi_positive,
            "MACD Bullish": macd_crossover,
            "Volume Surge": volume_surge,
            "Price > SMA200": price_above_sma200,  # Added SMA200 condition
            "Stochastic Overbought": stochastic_overbought,  # Added Stochastic condition
            "Bollinger Breakout": bollinger_breakout,  # Added Bollinger Bands breakout condition
            "Next Earnings Date": next_earnings_date
        }
    except Exception as e:
        return None

# Rank stocks based on Earnings Momentum & Breakout Strategy
def calculate_stock_scores(df, risk_tolerance):
    df = df.dropna().reset_index(drop=True)
    
    # Assigning Scores
    df["Fundamental Score"] = df["Earnings Surprise %"].rank(ascending=False) + df["Revenue Growth"].rank(ascending=False)
    df["Technical Score"] = df["Price > EMA50"] + df["RSI > 50"] + df["MACD Bullish"] + df["Volume Surge"] + df["Price > SMA200"] + df["Stochastic Overbought"] + df["Bollinger Breakout"]

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
