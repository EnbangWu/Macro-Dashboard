import streamlit as st
import pandas as pd
import pandas_datareader.data as web
from datetime import datetime

st.title('Macro Economic Dashboard')

# Fetch data from FRED
start = datetime(2010, 1, 1)
end = datetime.today()

series = {
    'Non-Farm Payrolls (PAYEMS)': 'PAYEMS',
    'CPI (CPIAUCSL)': 'CPIAUCSL',
    'PCE (PCE)': 'PCE',
    'Fed Funds Rate (FEDFUNDS)': 'FEDFUNDS',
    '10Y Treasury (DGS10)': 'DGS10',
}

@st.cache_data
def load_data(symbol):
    return web.DataReader(symbol, 'fred', start, end)

data_frames = {name: load_data(code) for name, code in series.items()}

# Plot line charts
for name, df in data_frames.items():
    st.subheader(name)
    st.line_chart(df)

# Upcoming events
st.sidebar.header('Upcoming Releases')
calendar = pd.DataFrame({
    'Event': ['Non-Farm Payrolls', 'CPI Release', 'FOMC Meeting'],
    'Date': ['2024-09-06', '2024-09-12', '2024-09-18']
})
st.sidebar.table(calendar)
