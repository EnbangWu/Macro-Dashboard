"""Streamlit-based US macroeconomic dashboard using live API data.

This app fetches macroeconomic indicators from FRED and the BLS public API
and visualizes recent trends. A FRED API key can be supplied via the
``FRED_API_KEY`` environment variable or placed in ``.streamlit/secrets.toml``
for Streamlit Cloud deployments.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st

START_DATE = datetime(2018, 1, 1)



def _get_secret(name: str) -> str | None:
    """Return a secret from the environment or Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets[name]
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def fetch_fred(series: str) -> pd.DataFrame:
    """Return a DataFrame for a given FRED series using the FRED API."""
    api_key = _get_secret("FRED_API_KEY")

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series,
        "file_type": "json",
        "observation_start": START_DATE.strftime("%Y-%m-%d"),
    }
    if api_key:
        params["api_key"] = api_key
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    out = pd.DataFrame(r.json().get("observations", []))
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


CALENDAR_COLUMNS = [
    "Date",
    "Country",
    "Event",
    "Actual",
    "Forecast",
    "TEForecast",
    "Previous",
    "Importance",
    "date_only",
    "time",
]


@st.cache_data(show_spinner=False)
def fetch_calendar() -> pd.DataFrame:
    """Return upcoming U.S. economic events using the Trading Economics API."""
    api_key = _get_secret("TRADING_ECON_API_KEY") or "guest:guest"
    today = datetime.utcnow().date()
    end = today + timedelta(days=14)
    params = {
        "c": api_key,
        "d1": today.strftime("%Y-%m-%d"),
        "d2": end.strftime("%Y-%m-%d"),
        "format": "json",
    }
    url = "https://api.tradingeconomics.com/calendar/country/united states"
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        data = []

    if not isinstance(data, list):
        data = []

    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=CALENDAR_COLUMNS)

    df = df[df.get("Country") == "United States"]
    df["Date"] = pd.to_datetime(df.get("Date"), errors="coerce")
    df["date_only"] = df["Date"].dt.date
    df["time"] = df["Date"].dt.strftime("%H:%M")
    for col in CALENDAR_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[CALENDAR_COLUMNS]



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

latest: dict[str, float] = {}
for sid, df in data_frames.items():
    if df.empty:
        latest[sid] = float("nan")
        latest[f"prev_{sid}"] = float("nan")
        continue

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
infl_df = pd.DataFrame(
    {
        "date": cpi.index,
        "CPI YoY": cpi["yoy"],
        "Core CPI YoY": core_cpi["yoy"],
        "PCE YoY": pce["yoy"],
        "Core PCE YoY": core_pce["yoy"],
    }
).melt("date", var_name="series", value_name="value")

# Hover across the x-axis and display all series values at once
infl_hover = alt.selection_point(
    on="pointermove",
    fields=["date"],
    nearest=True,
    empty="none",
)
infl_lines = (
    alt.Chart(infl_df)
    .mark_line()
    .encode(x="date:T", y="value:Q", color="series:N")
)
infl_points = infl_lines.mark_point().encode(
    opacity=alt.condition(infl_hover, alt.value(1), alt.value(0))
).add_params(infl_hover)
infl_tooltips = (
    alt.Chart(infl_df)
    .transform_pivot("series", value="value", groupby=["date"])
    .mark_rule(color="gray")
    .encode(
        x="date:T",
        opacity=alt.condition(infl_hover, alt.value(0.3), alt.value(0)),
        tooltip=[
            "date:T",
            alt.Tooltip("CPI YoY:Q", title="CPI YoY", format=".2f"),
            alt.Tooltip("Core CPI YoY:Q", title="Core CPI YoY", format=".2f"),
            alt.Tooltip("PCE YoY:Q", title="PCE YoY", format=".2f"),
            alt.Tooltip("Core PCE YoY:Q", title="Core PCE YoY", format=".2f"),
        ],
    )
    .add_params(infl_hover)
)
infl_chart = alt.layer(infl_lines, infl_points, infl_tooltips).properties(height=300)
st.altair_chart(infl_chart, use_container_width=True)

st.subheader("Fed Funds Rate")
rate_hover = alt.selection_point(
    on="pointermove",
    fields=["date"],
    nearest=True,
    empty="none",
)
rate_base = alt.Chart(data_frames["FEDFUNDS"]).encode(x="date:T", y="value:Q")
rate_line = rate_base.mark_line(color="orange")
rate_points = (
    rate_base.mark_point(color="orange")
    .encode(
        tooltip=["date:T", "value:Q"],
        opacity=alt.condition(rate_hover, alt.value(1), alt.value(0)),
    )
    .add_params(rate_hover)
)
rate_rule = (
    alt.Chart(data_frames["FEDFUNDS"])
    .mark_rule(color="gray")
    .encode(x="date:T")
    .transform_filter(rate_hover)
)
rate_chart = alt.layer(rate_line, rate_rule, rate_points).properties(height=300)
st.altair_chart(rate_chart, use_container_width=True)

st.subheader("CPI vs Fed Funds Rate")
combo_df = (
    pd.concat(
        [
            cpi["yoy"].rename("CPI YoY"),
            data_frames["FEDFUNDS"].set_index("date")["value"].rename("Fed Funds Rate"),
        ],
        axis=1,
    )
    .reset_index()
    .melt("date", var_name="series", value_name="value")
)

combo_hover = alt.selection_point(
    on="pointermove",
    fields=["date"],
    nearest=True,
    empty="none",
)
combo_lines = (
    alt.Chart(combo_df)
    .mark_line()
    .encode(x="date:T", y="value:Q", color="series:N")
)
combo_points = combo_lines.mark_point().encode(
    opacity=alt.condition(combo_hover, alt.value(1), alt.value(0))
).add_params(combo_hover)
combo_tooltips = (
    alt.Chart(combo_df)
    .transform_pivot("series", value="value", groupby=["date"])
    .mark_rule(color="gray")
    .encode(
        x="date:T",
        opacity=alt.condition(combo_hover, alt.value(0.3), alt.value(0)),
        tooltip=[
            "date:T",
            alt.Tooltip("CPI YoY:Q", title="CPI YoY", format=".2f"),
            alt.Tooltip("Fed Funds Rate:Q", title="Fed Funds Rate", format=".2f"),
        ],
    )
    .add_params(combo_hover)
)
combo_chart = alt.layer(combo_lines, combo_points, combo_tooltips).properties(height=300)
st.altair_chart(combo_chart, use_container_width=True)


with st.sidebar:
    st.header("Economic Calendar (next 14 days)")
    calendar_df = fetch_calendar()
    if "date_only" not in calendar_df.columns:
        calendar_df["date_only"] = pd.NaT
    start = datetime.utcnow().date()
    for day in pd.date_range(start, periods=14):
        st.subheader(day.strftime("%b %d, %Y"))
        day_events = calendar_df[calendar_df["date_only"] == day.date()]
        if day_events.empty:
            st.write("No events scheduled")
            continue
        for _, ev in day_events.sort_values("Date").iterrows():
            def _fmt(x):
                return x if x not in (None, "") else "N/A"

            actual = _fmt(ev.get("Actual"))
            forecast = _fmt(ev.get("Forecast") or ev.get("TEForecast"))
            previous = _fmt(ev.get("Previous"))
            time = ev.get("time") or ""
            importance = int(ev.get("Importance", 1))
            dots = "\u2022" * importance
            highlight = ev.get("Event") in [
                "FOMC Meeting",
                "Non Farm Payrolls",
                "ADP Employment Change",
            ]
            style = "color:#ff4b4b;font-weight:bold;" if highlight else ""
            title = f"<span style='{style}'>{ev.get('Event')}</span>"
            st.markdown(
                f"{dots} {time} {ev.get('Country')} - {title}<br>Actual: {actual} | Forecast: {forecast} | Previous: {previous}",
                unsafe_allow_html=True,
            )

if __name__ == "__main__":
    import sys
    import streamlit.runtime as st_runtime

    if not st_runtime.exists():
        import streamlit.web.cli as stcli

        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())

