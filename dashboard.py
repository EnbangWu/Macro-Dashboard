"""Streamlit-based US macroeconomic dashboard using live API data.

This app fetches macroeconomic indicators from FRED and the BLS public API
and visualizes recent trends.  A FRED API key can be supplied via the
``FRED_API_KEY`` environment variable for series that require it.
"""

from __future__ import annotations

import os
from datetime import datetime

import altair as alt
import pandas as pd
import pandas_datareader.data as web
import requests
import streamlit as st

START_DATE = datetime(2018, 1, 1)


@st.cache_data(show_spinner=False)
def fetch_fred(series: str) -> pd.DataFrame:
    """Return a DataFrame for a given FRED series."""
    try:
        df = web.DataReader(series, "fred", START_DATE, datetime.today())
        df = df.reset_index().rename(columns={series: "value", "DATE": "date"})
        return df
    except Exception:
        # fallback to FRED API if pandas_datareader fails
        api_key = st.secrets.get("FRED_API_KEY") or os.getenv("FRED_API_KEY")
        if not api_key:
            raise
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": START_DATE.strftime("%Y-%m-%d"),
        }
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        out = pd.DataFrame(r.json()["observations"])
        out["date"] = pd.to_datetime(out["date"])
        out["value"] = pd.to_numeric(out["value"], errors="coerce")
        return out[["date", "value"]]


@st.cache_data(show_spinner=False)
def fetch_bls(series_id: str) -> pd.DataFrame:
    """Fetch a monthly series from the BLS public API."""
    payload = {
        "seriesid": [series_id],
        "startyear": START_DATE.year,
        "endyear": datetime.today().year,
    }
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

    series = (
        r.json()
        .get("Results", {})
        .get("series", [{}])[0]
        .get("data", [])
    )
    rows: list[dict[str, float | pd.Timestamp]] = []
    for item in series:
        if item.get("period") == "M13":  # annual

            continue
        month = int(item["period"][1:])
        date = pd.to_datetime(f"{item['year']}-{month:02d}-01")
        rows.append({"date": date, "value": float(item["value"])})

    if not rows:
        return pd.DataFrame(columns=["date", "value"])
    return pd.DataFrame(rows).sort_values("date")



st.set_page_config(page_title="US Macro Dashboard", layout="wide")

# Load series

# Use official BLS series identifiers
series_map = {
    "CEU0000000001": "Non-Farm Payrolls (thous)",
    "LNS14000000": "Unemployment Rate (%)",

    "CES0500000003": "Avg Hourly Earnings (USD)",
    "CPIAUCSL": "CPI",
    "CPILFESL": "Core CPI",
    "PCEPI": "PCE",
    "PCEPILFE": "Core PCE",
    "FEDFUNDS": "Fed Funds Rate",
}

fred_ids = ["CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "FEDFUNDS"]

# BLS series IDs (payrolls, unemployment rate, hourly earnings)
bls_ids = ["CEU0000000001", "LNS14000000", "CES0500000003"]


data_frames = {}
for sid in fred_ids:
    data_frames[sid] = fetch_fred(sid)
for sid in bls_ids:
    data_frames[sid] = fetch_bls(sid)

# Compute derived metrics
cpi = data_frames["CPIAUCSL"].set_index("date")
cpi["yoy"] = cpi["value"].pct_change(12) * 100
cpi["mom"] = cpi["value"].pct_change() * 100
core_cpi = data_frames["CPILFESL"].set_index("date")
core_cpi["yoy"] = core_cpi["value"].pct_change(12) * 100
core_cpi["mom"] = core_cpi["value"].pct_change() * 100
pce = data_frames["PCEPI"].set_index("date")
pce["yoy"] = pce["value"].pct_change(12) * 100
core_pce = data_frames["PCEPILFE"].set_index("date")
core_pce["yoy"] = core_pce["value"].pct_change(12) * 100

# Latest metrics
latest = {}
for sid, df in data_frames.items():
    latest[sid] = df.iloc[-1]["value"]
    if len(df) > 1:
        latest[f"prev_{sid}"] = df.iloc[-2]["value"]
    else:
        latest[f"prev_{sid}"] = float("nan")

st.title("US Macro Dashboard")

cols = st.columns(4)
for i, sid in enumerate(series_map.keys()):
    val = latest[sid]
    prev = latest.get(f"prev_{sid}", float("nan"))
    delta = val - prev if pd.notna(prev) else None
    with cols[i % 4]:
        st.metric(series_map[sid], f"{val:.2f}", delta=None if delta is None else f"{delta:.2f}")

st.subheader("Inflation Trends")
infl_df = pd.DataFrame({
    "date": cpi.index,
    "CPI YoY": cpi["yoy"],
    "Core CPI YoY": core_cpi["yoy"],
    "PCE YoY": pce["yoy"],
    "Core PCE YoY": core_pce["yoy"],
}).melt("date", var_name="series", value_name="value")
chart = (
    alt.Chart(infl_df)
    .mark_line()
    .encode(x="date:T", y="value:Q", color="series:N")
    .properties(height=300)
)
st.altair_chart(chart, use_container_width=True)

st.subheader("Fed Funds Rate")
rate_chart = (
    alt.Chart(data_frames["FEDFUNDS"])
    .mark_line(color="orange")
    .encode(x="date:T", y="value:Q")
)
st.altair_chart(rate_chart, use_container_width=True)

st.subheader("CPI vs Fed Funds Rate")
combo = (
    alt.Chart(cpi.reset_index())
    .mark_line(color="steelblue")
    .encode(x="date:T", y="yoy:Q")
    +
    alt.Chart(data_frames["FEDFUNDS"])
    .mark_line(color="orange")
    .encode(x="date:T", y="value:Q")
)
st.altair_chart(combo, use_container_width=True)

with st.sidebar:
    st.header("Upcoming Events")
    events = pd.DataFrame(
        {
            "Event": ["FOMC Meeting", "NFP Release", "CPI Release"],
            "Date": ["2025-07-30", "2025-07-05", "2025-07-11"],
        }
    )
    st.table(events)

if __name__ == "__main__":
    import sys
    import streamlit.web.cli as stcli

    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())
