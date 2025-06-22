# Macro Dashboard

This Streamlit application visualizes key U.S. macroeconomic indicators using live data from the FRED and BLS APIs.
All FRED series are retrieved directly via the FRED REST API using the ``requests`` library.

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

Set a `FRED_API_KEY` environment variable (or provide it in
`.streamlit/secrets.toml` when using Streamlit Cloud) if you need access to
restricted FRED series and run:

```bash
streamlit run dashboard.py
```

If the `streamlit` command is unavailable, you can instead launch the app with:

```bash
python dashboard.py
```

The dashboard displays metrics for employment, inflation and interest rates along with trend charts and a small events sidebar.
