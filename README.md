# Macro Dashboard

This Streamlit application visualizes key U.S. macroeconomic indicators using live data from the FRED and BLS APIs.

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

Set a `FRED_API_KEY` environment variable if you need access to restricted FRED
series and run:

```bash
streamlit run dashboard.py
```

If the `streamlit` command is unavailable, you can instead launch the app with:

```bash
python dashboard.py
```

The dashboard displays metrics for employment, inflation and interest rates along with trend charts and a small events sidebar.
