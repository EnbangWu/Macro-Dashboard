# Macro Dashboard

This Streamlit application visualizes key U.S. macroeconomic indicators using live data from the FRED and BLS APIs.
All FRED series are retrieved directly via the FRED REST API using the ``requests`` library.

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

Set `FRED_API_KEY` and `TRADING_ECON_API_KEY` environment variables (or provide
them in `.streamlit/secrets.toml` when using Streamlit Cloud) if you need
access to restricted FRED series or a personal Trading Economics key and run:

```bash
streamlit run dashboard.py
```

If the `streamlit` command is unavailable, you can instead launch the app with:

```bash
python dashboard.py
```

The dashboard displays metrics for employment, inflation and interest rates along with trend charts and a sidebar showing a 14‑day U.S. economic calendar of high‑importance events. Key items such as FOMC meetings, Non Farm Payrolls, ADP Employment changes and CPI releases are highlighted.

Note that the default `guest:guest` key and many free accounts only return a
limited snapshot of events and may exclude U.S. data entirely. If the sidebar is
empty, verify that your `TRADING_ECON_API_KEY` grants access to United States
calendar entries.
