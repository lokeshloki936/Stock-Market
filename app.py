import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import datetime

# --- Configuration ---
# Get your API Key from Alpha Vantage: https://www.alphavantage.co/
# IMPORTANT: This API key is now embedded.
API_KEY = 'IOPOMGZYQH86ES0Z' # Your Alpha Vantage API key

# --- Helper Function to Fetch Data ---
# Cache data for 1 hour (3600 seconds) to avoid hitting API limits frequently
# This is crucial for free API tiers which have rate limits (e.g., 5 calls/minute, 500 calls/day)
@st.cache_data(ttl=3600)
def get_stock_data(symbol, interval='5min'):
    """Fetches intraday stock data from Alpha Vantage."""
    if not API_KEY or API_KEY == 'IOPOMGZYQH86ES0Z': # Safety check, though it's now embedded
        st.error("Please ensure your Alpha Vantage API key is correctly set in the script.")
        return None

    function = "TIME_SERIES_INTRADAY"
    # Added outputsize=compact to get typically 100 data points for intraday
    url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&interval={interval}&outputsize=compact&apikey={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        # Check for common Alpha Vantage error messages
        if "Time Series (5min)" not in data:
            if "Error Message" in data:
                st.error(f"Alpha Vantage API Error: {data['Error Message']}")
            elif "Note" in data:
                st.warning(f"Alpha Vantage API Note: {data['Note']} - You might be hitting rate limits. Please wait a minute and try again if on a free tier.")
            else:
                st.error(f"Could not fetch data for {symbol}. Raw response: {data}")
            return None

        # The key for time series data might vary based on interval, e.g., "Time Series (5min)"
        # We need to find the correct key dynamically
        time_series_key = next((key for key in data if "Time Series" in key), None)
        if time_series_key is None:
            st.error(f"Could not find time series data in Alpha Vantage response for {symbol}. Response: {data}")
            return None

        time_series = data[time_series_key]
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df = df.rename(columns={
            '1. open': 'open',
            '2. high': 'high',
            '3. low': 'low',
            '4. close': 'close',
            '5. volume': 'volume'
        })
        df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index(ascending=True) # Ensure chronological order
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Network or API request error: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred while processing data: {e}")
        return None

# --- Streamlit UI Setup ---
# Removed 'icon' argument due to previous TypeError
st.set_page_config(layout="wide", page_title="Real-Time Stock Dashboard")

st.title("📈 Real-Time Stock Market Dashboard")
st.markdown("Track and visualize live stock market data.")

# Sidebar for user input
st.sidebar.header("Stock Selection")
# Pre-defined list of popular stock symbols (can be expanded)
default_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'NFLX', 'SBUX', 'VZ', 'JPM']
selected_symbol_input = st.sidebar.text_input("Enter Stock Symbol (e.g., AAPL)", "AAPL").upper()

st.sidebar.markdown("---")
st.sidebar.header("Dashboard Options")
chart_type = st.sidebar.radio("Select Chart Type", ("Candlestick", "Line Chart (Close Price)"), index=0)
show_volume = st.sidebar.checkbox("Show Volume on Chart", True)

st.sidebar.markdown("---")
st.sidebar.info(
    "Data provided by Alpha Vantage. "
    "Free tier has rate limits (typically 5 API calls per minute, 500 calls per day). "
    "Data is cached for 1 hour to reduce API calls."
)
st.sidebar.write(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# --- Main Dashboard Logic ---
if selected_symbol_input:
    st.header(f"Live Data for {selected_symbol_input}")

    # Fetch data
    stock_data = get_stock_data(selected_symbol_input)

    if stock_data is not None and not stock_data.empty:
        # Display basic financial indicators (latest data)
        latest_data = stock_data.iloc[-1]
        st.subheader("Current Financial Indicators")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Open", f"${latest_data['open']:.2f}")
        with col2:
            st.metric("High", f"${latest_data['high']:.2f}")
        with col3:
            st.metric("Low", f"${latest_data['low']:.2f}")
        with col4:
            st.metric("Close", f"${latest_data['close']:.2f}")
        with col5:
            st.metric("Volume", f"{int(latest_data['volume']):,}")

        # Plotting the data
        st.subheader("Historical Price Movement (5-minute intervals)")
        fig = go.Figure()

        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(x=stock_data.index,
                                        open=stock_data['open'],
                                        high=stock_data['high'],
                                        low=stock_data['low'],
                                        close=stock_data['close'],
                                        name='Price',
                                        increasing_line_color='green', # Green for price increase
                                        decreasing_line_color='red')) # Red for price decrease
        elif chart_type == "Line Chart (Close Price)":
            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['close'],
                                     mode='lines', name='Close Price', line=dict(color='blue', width=2)))

        # Add volume subplot if selected
        if show_volume:
            # Use secondary y-axis for volume to prevent scale issues with price
            fig.add_trace(go.Bar(x=stock_data.index, y=stock_data['volume'], name='Volume',
                                 yaxis='y2', marker_color='rgba(128, 128, 128, 0.5)')) # Greyish translucent bars
            fig.update_layout(
                yaxis2=dict(
                    title='Volume',
                    overlaying='y',
                    side='right',
                    showgrid=False,
                    rangemode='tozero' # Ensure volume starts from 0
                )
            )

        fig.update_layout(
            xaxis_rangeslider_visible=False, # Hide the range slider for cleaner look
            title_text=f"{selected_symbol_input} Intraday Price Chart", # Removed "Last 100 data points" as outputsize=compact gives latest 100
            xaxis_title="Time",
            yaxis_title="Price ($)",
            height=600,
            hovermode="x unified", # Shows combined hover info for all traces at x-coordinate
            template="plotly_dark", # Looks good for dashboards
            legend=dict(x=0, y=1.0, xanchor='left') # Position legend
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Raw Data Preview (Last 10 entries)")
        st.dataframe(stock_data.tail(10)) # Display last 10 rows of the DataFrame
    else:
        st.warning(f"No data could be retrieved for '{selected_symbol_input}'. Please check the symbol or your API key, or try again later.")
else:
    st.info("Enter a stock symbol in the sidebar to view its data.")