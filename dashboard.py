"""
IC Securities Portfolio Analyser — Streamlit Dashboard
=======================================================
Install:  pip install streamlit plotly pdfplumber pandas requests beautifulsoup4 lxml
Run:      streamlit run akwasi.py
"""

import io, re, warnings
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pdfplumber
import streamlit as st

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IC Portfolio Analyser",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}
.stApp { background: #0f1117; }

/* ── KPI cards ── */
.kpi-card {
    background: #1a1d2e;
    border-radius: 14px;
    padding: 18px 20px;
    border-left: 4px solid #6c63ff;
    margin-bottom: 4px;
    transition: transform .15s;
}
.kpi-card:hover { transform: translateY(-2px); }
.kpi-card.green  { border-left-color: #00d68f; }
.kpi-card.red    { border-left-color: #ff3d71; }
.kpi-card.yellow { border-left-color: #ffaa00; }
.kpi-card.blue   { border-left-color: #0095ff; }
.kpi-label { font-size: .72rem; color: #8892b0; text-transform: uppercase;
             letter-spacing: .06em; margin-bottom: 6px; }
.kpi-value { font-size: 1.45rem; font-weight: 800; color: #e8eaf6; }
.kpi-sub   { font-size: .75rem; color: #8892b0; margin-top: 4px; }
.pos { color: #00d68f !important; }
.neg { color: #ff3d71 !important; }

/* ── Section headers ── */
.section-hdr {
    font-size: 1rem; font-weight: 700; color: #e8eaf6;
    border-left: 4px solid #6c63ff; padding-left: 10px;
    margin: 8px 0 14px;
}

/* ── Insight row ── */
.insight-box {
    background: #1a1d2e; border: 1px solid #232640;
    border-radius: 12px; padding: 14px 16px; text-align: center;
}
.insight-icon { font-size: 1.6rem; }
.insight-lbl  { font-size: .7rem; color: #8892b0; text-transform: uppercase;
                letter-spacing: .05em; margin: 6px 0 2px; }
.insight-val  { font-size: 1rem; font-weight: 700; color: #e8eaf6; }

/* ── Price source badge ── */
.price-badge {
    display: inline-block; background: #00d68f22; color: #00d68f;
    padding: 3px 10px; border-radius: 20px; font-size: .75rem;
    font-weight: 600; margin-left: 8px;
}
.price-badge.stale { background: #ffaa0022; color: #ffaa00; }
.price-badge.manual { background: #6c63ff22; color: #6c63ff; }

/* ── Upload zone ── */
[data-testid="stFileUploadDropzone"] {
    background: #1a1d2e !important;
    border: 2px dashed #6c63ff55 !important;
    border-radius: 14px !important;
    padding: 32px !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: #6c63ff !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* ── Plotly charts ── */
.js-plotly-plot { border-radius: 12px; }

/* ── Divider ── */
hr { border-color: #232640 !important; margin: 20px 0 !important; }

/* ── Header gradient ── */
.hero-title {
    font-size: 2.4rem; font-weight: 900;
    background: linear-gradient(135deg, #6c63ff, #00d68f);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-sub { color: #8892b0; font-size: 1rem; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

PLOTLY_THEME = dict(
    paper_bgcolor="#0f1117",
    plot_bgcolor="#1a1d2e",
    font=dict(color="#e8eaf6", family="Segoe UI, system-ui"),
    xaxis=dict(gridcolor="#232640", zerolinecolor="#232640"),
    yaxis=dict(gridcolor="#232640", zerolinecolor="#232640"),
    margin=dict(l=16, r=16, t=40, b=16),
)

STOCK_COLORS = [
    "#6c63ff","#00d68f","#ff3d71","#ffaa00","#0095ff",
    "#ff6b6b","#48dbfb","#ff9f43","#a29bfe","#fd79a8",
]

# ─────────────────────────────────────────────────────────────────────────────
# LIVE PRICE FETCHER  — afx.kwayisi.org / dev.kwayisi.org
# Tries HTTPS then HTTP, picks up system proxy, 3 endpoint variants.
# ─────────────────────────────────────────────────────────────────────────────

_ENDPOINTS = [
    "https://dev.kwayisi.org/apis/gse/live",
    "http://dev.kwayisi.org/apis/gse/live",   # HTTP fallback if HTTPS blocked
]
_TICK_TMPL  = "https://dev.kwayisi.org/apis/gse/{}"
_AFX_URLS   = [
    "https://afx.kwayisi.org/gse/",
    "http://afx.kwayisi.org/gse/",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}


def _normalize(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _to_float(val) -> float | None:
    try:
        if pd.isna(val):
            return None
        f = float(re.sub(r"[^\d.\-]", "", str(val).replace(",", "")))
        return f if f == f else None
    except Exception:
        return None


def _make_session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()
    s.headers.update(_HEADERS)
    s.trust_env = True   # picks up HTTP_PROXY / HTTPS_PROXY / system proxy
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429,500,502,503,504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    return s


def _get_json(session, urls: list, timeout=20, debug: list = None) -> list | None:
    """Try each URL in turn; return parsed JSON list on first success."""
    import urllib3
    urllib3.disable_warnings()
    for url in urls:
        for verify in (True, False):
            try:
                r = session.get(url, timeout=timeout, verify=verify)
                if r.status_code == 200:
                    data = r.json()
                    if debug is not None:
                        debug.append(f"  ✅ {url} → {len(data)} records (verify={verify})")
                    return data if isinstance(data, list) else None
                if debug is not None:
                    debug.append(f"  ✗ {url} → HTTP {r.status_code}")
            except Exception as e:
                if debug is not None:
                    debug.append(f"  ✗ {url} (verify={verify}) → {type(e).__name__}: {str(e)[:80]}")
    return None


def _parse_rec(rec, norm_to_orig, wanted_norm):
    sym_norm = _normalize(str(rec.get("name", rec.get("symbol", rec.get("ticker", "")))))
    if sym_norm not in wanted_norm:
        return None
    price   = _to_float(rec.get("price"))
    if not price or price <= 0:
        return None
    chg_abs = _to_float(rec.get("change")) or 0.0
    prev    = price - chg_abs
    chg_pct = (chg_abs / prev * 100) if prev else 0.0
    orig    = norm_to_orig[sym_norm]
    return orig, {"price": price, "source": "afx.kwayisi.org ✓",
                  "change_pct": round(chg_pct, 2), "change_abs": round(chg_abs, 4)}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_prices(tickers: tuple) -> tuple[dict, str]:
    """Returns (prices_dict, debug_log)."""
    norm_to_orig = {_normalize(t): t for t in tickers}
    wanted_norm  = set(norm_to_orig.keys())
    results, debug = {}, []

    session = _make_session()

    # ── 1. Bulk JSON ──────────────────────────────────────────────────────────
    debug.append("── Bulk JSON API ──")
    data = _get_json(session, _ENDPOINTS, debug=debug)
    if data:
        for rec in data:
            hit = _parse_rec(rec, norm_to_orig, wanted_norm)
            if hit:
                orig, payload = hit
                results[orig] = payload
                debug.append(f"  ✓ {orig}: {payload['price']} ({payload['change_pct']:+.2f}%)")

    # ── 2. Per-ticker JSON (for misses) ───────────────────────────────────────
    missing = [t for t in tickers if t not in results]
    if missing:
        debug.append(f"\n── Per-ticker API for {missing} ──")
        for t in missing:
            url = _TICK_TMPL.format(t.lower())
            data = _get_json(session, [url, url.replace("https://","http://")], debug=debug)
            if data:
                rec = data[0] if isinstance(data, list) else data
                if "name" not in rec:
                    rec["name"] = t
                hit = _parse_rec(rec, norm_to_orig, wanted_norm)
                if hit:
                    results[hit[0]] = hit[1]

    # ── 3. HTML scrape ────────────────────────────────────────────────────────
    missing = [t for t in tickers if t not in results]
    if missing:
        missing_norm = {_normalize(t) for t in missing}
        debug.append(f"\n── HTML scrape for {missing} ──")
        import urllib3; urllib3.disable_warnings()
        for url in _AFX_URLS:
            for verify in (True, False):
                try:
                    r = session.get(url, timeout=20, verify=verify)
                    if r.status_code != 200:
                        continue
                    debug.append(f"  ✅ {url} (verify={verify})")
                    dfs = pd.read_html(io.StringIO(r.text), thousands=",")
                    debug.append(f"  Tables: {len(dfs)}")
                    for i, df in enumerate(dfs):
                        df.columns = df.columns.astype(str).str.strip()
                        sym_col = next((c for c in df.columns
                                        if c.upper() in ("SYMBOL","TICKER","CODE","STOCK")), None)
                        if sym_col is None:
                            for c in df.columns:
                                if df[c].astype(str).apply(_normalize).isin(missing_norm).sum() > 0:
                                    sym_col = c; break
                        if not sym_col: continue
                        price_col = next((c for c in df.columns
                                          if any(k in c.lower() for k in ("price","close","last"))), None)
                        if price_col is None:
                            for c in df.columns:
                                if c == sym_col: continue
                                v = [_to_float(x) for x in df[c].dropna().head(10)]
                                if sum(1 for x in v if x and 0.001 < x < 99999) >= 3:
                                    price_col = c; break
                        if not price_col: continue
                        pct_col = next((c for c in df.columns if "%" in c), None)
                        chg_col = next((c for c in df.columns
                                        if "change" in c.lower() and "%" not in c), None)
                        debug.append(f"  Table {i}: sym={sym_col} price={price_col} pct={pct_col}")
                        for _, row in df.iterrows():
                            sn = _normalize(str(row.get(sym_col,"")))
                            if sn not in missing_norm: continue
                            p = _to_float(row.get(price_col))
                            if not p or p <= 0: continue
                            orig = norm_to_orig[sn]
                            results[orig] = {
                                "price": p, "source": "afx.kwayisi.org ✓",
                                "change_pct": round(_to_float(row.get(pct_col)) or 0, 2),
                                "change_abs": round(_to_float(row.get(chg_col)) or 0, 4),
                            }
                            debug.append(f"  ✓ {orig}: {p}")
                    break
                except Exception as e:
                    debug.append(f"  ✗ {url} (verify={verify}): {type(e).__name__}: {str(e)[:80]}")

    session.close()
    still = [t for t in tickers if t not in results]
    if still:
        debug.append(f"\n⚠ No live price for: {still}")
    debug.append(f"\nMatched: {len(results)}/{len(tickers)}")
    return results, "\n".join(debug)


# ─────────────────────────────────────────────────────────────────────────────
# PDF PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse_pdf(pdf_bytes: bytes) -> dict:
    equities, transactions, portfolio_summary = [], [], {}
    funds_data = {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    lines = full_text.split("\n")

    # ── Portfolio summary ──
    for i, line in enumerate(lines):
        if "Total Value" in line and "Allocation" in line:
            for j in range(i + 1, min(i + 10, len(lines))):
                l = lines[j].strip()
                m = re.match(
                    r"(Funds|Fixed Income|Equities|Cash)\s+([\d,\.]+)\s+([\d\.]+)", l)
                if m:
                    portfolio_summary[m.group(1)] = {
                        "value": float(m.group(2).replace(",", "")),
                        "alloc": float(m.group(3)),
                    }
                m2 = re.match(r"([\d,\.]+)\s+100\.00", l)
                if m2:
                    portfolio_summary["Total"] = float(m2.group(1).replace(",", ""))

    # ── Funds ──
    m = re.search(
        r"IC Liquidity\s+([\d,\.]+)\s+-([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)",
        full_text)
    if m:
        funds_data = {
            "name": "IC Liquidity",
            "invested":      float(m.group(1).replace(",", "")),
            "redeemed":      float(m.group(2).replace(",", "")),
            "gain_loss":     float(m.group(3)),
            "market_price":  float(m.group(4)),
            "market_value":  float(m.group(5)),
        }

    # ── Equities ──
    equity_pat = re.compile(
        r"^([A-Z]{2,8})\s+(GH[A-Z0-9]+|TG[A-Z0-9]+)\s+([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d,\.]+)")
    for line in lines:
        m = equity_pat.match(line.strip())
        if m:
            qty   = float(m.group(3).replace(",", ""))
            cost  = float(m.group(4))
            price = float(m.group(5))
            mval  = float(m.group(6).replace(",", ""))
            total_cost = qty * cost
            gl    = mval - total_cost
            glpct = (gl / total_cost * 100) if total_cost > 0 else 0
            equities.append({
                "ticker": m.group(1), "isin": m.group(2),
                "qty": qty, "avg_cost": cost,
                "statement_price": price,
                "live_price": None, "price_source": "Statement",
                "market_value": mval,
                "total_cost": total_cost,
                "gain_loss": gl, "gain_pct": glpct,
            })

    # ── Transactions ──
    for line in lines:
        line = line.strip()
        dm = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.*)", line)
        if not dm:
            continue
        date_str, rest = dm.group(1), dm.group(2).strip()
        nums = re.findall(r"-?[\d,]+\.\d{2}", rest)
        if len(nums) >= 2:
            try:
                credit = float(nums[-2].replace(",", ""))
                debit  = float(nums[-1].replace(",", ""))
                desc   = rest[: rest.rfind(nums[-2])].strip()
                dt     = datetime.strptime(date_str, "%d/%m/%Y")
                transactions.append({
                    "date": dt, "date_str": date_str, "description": desc,
                    "credit": credit if credit > 0 else 0,
                    "debit":  abs(debit) if debit < 0 else 0,
                })
            except Exception:
                pass

    def _field(label):
        m = re.search(re.escape(label) + r"\s*(.+)", full_text)
        if not m:
            return ""
        v = m.group(1).strip().split("\n")[0].strip()
        return re.split(r"\s{3,}|\s+(?:Report Date|Account Number|Address|Report Currency):", v)[0].strip()

    return {
        "equities": equities,
        "transactions": transactions,
        "portfolio_summary": portfolio_summary,
        "funds": funds_data,
        "client_name":    _field("Client Name:"),
        "account_number": _field("Account Number:"),
        "report_date":    _field("Report Date:"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# INJECT LIVE PRICES
# ─────────────────────────────────────────────────────────────────────────────
def inject_live_prices(equities: list, live: dict) -> list:
    updated = []
    for e in equities:
        e = e.copy()
        t = e["ticker"]
        if t in live:
            lp   = live[t]["price"]
            src  = live[t]["source"]
            chg  = live[t]["change_pct"]
            chga = live[t].get("change_abs", 0.0)
            mval = e["qty"] * lp
            gl   = mval - e["total_cost"]
            glp  = (gl / e["total_cost"] * 100) if e["total_cost"] else 0
            e.update({
                "live_price":     lp,
                "price_source":   src,
                "price_change":   chg,
                "price_change_abs": chga,
                "market_value":   mval,
                "gain_loss":      gl,
                "gain_pct":       glp,
            })
        else:
            e["live_price"]       = None
            e["price_source"]     = "Statement"
            e["price_change"]     = 0.0
            e["price_change_abs"] = 0.0
        updated.append(e)
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# CHART BUILDERS (Plotly)
# ─────────────────────────────────────────────────────────────────────────────
def chart_allocation(ps):
    labels, values, colors = [], [], []
    cm = {"Equities": "#6c63ff", "Cash": "#0095ff",
          "Funds": "#ffaa00", "Fixed Income": "#00d68f"}
    for k, v in ps.items():
        if k == "Total" or v["value"] == 0:
            continue
        labels.append(k)
        values.append(v["value"])
        colors.append(cm.get(k, "#ccc"))
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55, marker=dict(colors=colors, line=dict(color="#0f1117", width=3)),
        textinfo="label+percent", textfont=dict(size=12),
    ))
    fig.update_layout(title="Portfolio Allocation", **PLOTLY_THEME,
                      showlegend=False, height=340)
    return fig


def chart_gain_loss(equities):
    df = pd.DataFrame(equities).sort_values("gain_pct")
    colors = [("#00d68f" if v >= 0 else "#ff3d71") for v in df["gain_pct"]]
    fig = go.Figure(go.Bar(
        x=df["gain_pct"], y=df["ticker"], orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df["gain_pct"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Return: %{x:.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#8892b0", line_dash="dash", line_width=1)
    fig.update_layout(title="Gain / Loss per Stock (%)",
                      xaxis_title="Return (%)", **PLOTLY_THEME, height=380)
    return fig


def chart_market_vs_cost(equities):
    df = pd.DataFrame(equities).sort_values("market_value", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Cost Basis", x=df["ticker"], y=df["total_cost"],
        marker_color="#0095ff", opacity=0.85,
        hovertemplate="%{x}: GHS %{y:,.2f}<extra>Cost</extra>",
    ))
    fig.add_trace(go.Bar(
        name="Market Value", x=df["ticker"], y=df["market_value"],
        marker_color="#6c63ff", opacity=0.85,
        hovertemplate="%{x}: GHS %{y:,.2f}<extra>Market</extra>",
    ))
    fig.update_layout(title="Market Value vs Cost Basis",
                      yaxis_title="GHS", barmode="group",
                      legend=dict(bgcolor="#1a1d2e", bordercolor="#232640"),
                      **PLOTLY_THEME, height=360)
    return fig


def chart_cashflow(transactions):
    df = pd.DataFrame(transactions)
    if df.empty:
        return None
    df["month"] = df["date"].dt.to_period("M")
    m = df.groupby("month").agg(
        credits=("credit", "sum"), debits=("debit", "sum")
    ).reset_index()
    m["month_str"] = m["month"].astype(str)
    m["net"] = m["credits"] - m["debits"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Credits", x=m["month_str"], y=m["credits"],
        marker_color="#00d68f", opacity=0.85,
        hovertemplate="%{x}<br>Credits: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Debits", x=m["month_str"], y=m["debits"],
        marker_color="#ff3d71", opacity=0.85,
        hovertemplate="%{x}<br>Debits: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Net", x=m["month_str"], y=m["net"],
        mode="lines+markers", line=dict(color="#ffaa00", width=2),
        marker=dict(size=5),
        hovertemplate="%{x}<br>Net: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#8892b0", line_dash="dash", line_width=1)
    fig.update_layout(title="Monthly Cash Flow", barmode="group",
                      xaxis_tickangle=-30, yaxis_title="GHS",
                      legend=dict(bgcolor="#1a1d2e"),
                      **PLOTLY_THEME, height=370)
    return fig


def chart_cumulative(transactions, total_value):
    df = pd.DataFrame(transactions).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        fill="tozeroy", fillcolor="rgba(108,99,255,0.12)",
        line=dict(color="#6c63ff", width=2), name="Net Invested",
        hovertemplate="%{x|%b %d %Y}<br>GHS %{y:,.2f}<extra>Net Invested</extra>",
    ))
    fig.add_hline(y=total_value, line_color="#00d68f", line_dash="dash",
                  line_width=2,
                  annotation_text=f"Portfolio Value GHS {total_value:,.2f}",
                  annotation_font_color="#00d68f")
    fig.update_layout(title="Cumulative Net Invested vs Current Portfolio Value",
                      xaxis_title="Date", yaxis_title="GHS",
                      **PLOTLY_THEME, height=360)
    return fig


def chart_stock_weight(equities):
    df = pd.DataFrame(equities).sort_values("market_value", ascending=False)
    fig = go.Figure(go.Pie(
        labels=df["ticker"], values=df["market_value"],
        hole=0.4,
        marker=dict(colors=STOCK_COLORS[:len(df)],
                    line=dict(color="#0f1117", width=3)),
        textinfo="label+percent", textfont=dict(size=11),
        hovertemplate="%{label}<br>GHS %{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(title="Stock Weight in Equity Portfolio",
                      showlegend=False, **PLOTLY_THEME, height=340)
    return fig


def chart_price_comparison(equities):
    df = pd.DataFrame(equities)
    df = df[df["live_price"].notna()].copy()
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Statement Price", x=df["ticker"], y=df["statement_price"],
        marker_color="#ffaa00", opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        name="Live Price", x=df["ticker"], y=df["live_price"],
        marker_color="#00d68f", opacity=0.85,
    ))
    fig.update_layout(title="Statement Price vs Live Market Price",
                      yaxis_title="GHS per Share", barmode="group",
                      legend=dict(bgcolor="#1a1d2e"),
                      **PLOTLY_THEME, height=340)
    return fig


def chart_tx_type_breakdown(transactions):
    df = pd.DataFrame(transactions)
    if df.empty:
        return None

    def categorise(desc):
        if re.search(r"\bBought\b", desc, re.I):   return "Buy"
        if re.search(r"\bSold\b",   desc, re.I):   return "Sell"
        if re.search(r"Contribution|Funding",  desc, re.I): return "Credit"
        if re.search(r"Withdrawal|Transfer.*Payout", desc, re.I): return "Withdrawal"
        return "Other"

    df["type"] = df["description"].apply(categorise)
    df["amount"] = df["credit"] + df["debit"]
    grp = df.groupby("type")["amount"].sum().reset_index()
    color_map = {"Buy": "#0095ff", "Sell": "#ffaa00",
                 "Credit": "#00d68f", "Withdrawal": "#ff3d71", "Other": "#8892b0"}
    fig = go.Figure(go.Bar(
        x=grp["type"], y=grp["amount"],
        marker_color=[color_map.get(t, "#ccc") for t in grp["type"]],
        text=[f"GHS {v:,.0f}" for v in grp["amount"]],
        textposition="outside",
        hovertemplate="%{x}: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Transaction Volume by Type",
                      yaxis_title="GHS", **PLOTLY_THEME, height=300)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", cls=""):
    color_cls = cls or ""
    return f"""
<div class="kpi-card {color_cls}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  {"<div class='kpi-sub'>" + sub + "</div>" if sub else ""}
</div>"""

def pos_neg_cls(v):
    return "pos" if v >= 0 else "neg"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # ── Hero header ──────────────────────────────────────────────────────────
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.markdown("<div style='font-size:3rem;padding-top:8px'>📈</div>",
                    unsafe_allow_html=True)
    with col_title:
        st.markdown("""
        <div class="hero-title">IC Portfolio Analyser</div>
        <div class="hero-sub">Upload your IC Securities statement PDF · Live GSE prices · Instant insights</div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Upload ────────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "**Drop your IC Securities Account Statement (PDF)**",
        type=["pdf"],
        help="Supports IC Securities account portfolio statements in standard PDF format",
    )

    if not uploaded:
        # Landing state
        c1, c2, c3, c4 = st.columns(4)
        for col, icon, label in [
            (c1, "🏆", "Gain/Loss per Stock"),
            (c2, "📊", "Portfolio Allocation"),
            (c3, "💸", "Cash Flow Analysis"),
            (c4, "📡", "Live GSE Prices"),
        ]:
            with col:
                st.markdown(f"""
                <div class="insight-box">
                  <div class="insight-icon">{icon}</div>
                  <div class="insight-lbl">{label}</div>
                </div>""", unsafe_allow_html=True)
        st.stop()

    # ── Parse PDF ─────────────────────────────────────────────────────────────
    with st.spinner("📄 Parsing statement..."):
        data = parse_pdf(uploaded.read())

    eq   = data["equities"]
    txs  = data["transactions"]
    ps   = data["portfolio_summary"]

    if not eq:
        st.error("Could not parse equity data from this PDF. Please check the format.")
        st.stop()

    # ── Fetch live prices ─────────────────────────────────────────────────────
    tickers = tuple(e["ticker"] for e in eq)
    live_prices = {}
    fetch_debug = ""

    with st.spinner("📡 Fetching live prices from afx.kwayisi.org..."):
        try:
            live_prices, fetch_debug = fetch_live_prices(tickers)
        except Exception as ex:
            fetch_debug = f"Exception: {ex}"

    eq = inject_live_prices(eq, live_prices)

    # ── Price source summary + manual override ────────────────────────────────
    n_live  = sum(1 for e in eq if e["live_price"] is not None)
    n_stmt  = len(eq) - n_live

    source_counts = {}
    for e in eq:
        if e["live_price"] is not None:
            src = e["price_source"].strip()
            source_counts[src] = source_counts.get(src, 0) + 1
    src_parts  = [f"**{v}** via {k}" for k, v in source_counts.items()]
    src_detail = " · ".join(src_parts) if src_parts else ""

    if n_live == len(eq):
        st.success(f"📡 All {n_live} live prices fetched · {src_detail} · *(refreshes every 5 min)*")
    elif n_live > 0:
        st.warning(f"📡 **{n_live}/{len(eq)} live prices** fetched · {src_detail}"
                    + (f" · {n_stmt} using statement price" if n_stmt else ""))
    else:
        st.error("⚠️ Live price fetch failed — showing statement prices.")

    # ── Manual price override (always available, collapsed by default) ────────
    with st.expander(
        "✏️ Enter prices manually" if n_live == 0 else "✏️ Override prices manually",
        expanded=(n_live == 0),
    ):
        if n_live == 0:
            st.info(
                "Auto-fetch couldn't reach afx.kwayisi.org — likely a network/firewall issue. "
                "Visit [afx.kwayisi.org/gse](https://afx.kwayisi.org/gse/) and enter "
                "today's prices below, then click **Apply**."
            )
        else:
            st.caption("Override any auto-fetched price with a value you enter manually.")

        override_cols = st.columns(5)
        manual_prices = {}
        for i, e in enumerate(eq):
            col = override_cols[i % 5]
            default = e["live_price"] if e["live_price"] else e["price"]
            val = col.number_input(
                e["ticker"],
                min_value=0.0,
                value=float(default),
                step=0.01,
                format="%.4f",
                key=f"manual_{e['ticker']}",
            )
            if val and val > 0:
                manual_prices[e["ticker"]] = val

        if st.button("✅ Apply manual prices", type="primary"):
            st.cache_data.clear()
            override_live = {
                t: {"price": p, "source": "Manual entry", "change_pct": 0.0, "change_abs": 0.0}
                for t, p in manual_prices.items()
            }
            eq = inject_live_prices(eq, override_live)
            n_live = len(eq)
            st.success(f"Applied manual prices for {len(override_live)} stocks.")

    # ── Diagnostics (collapsed) ───────────────────────────────────────────────
    with st.expander("🔍 Fetch diagnostics", expanded=False):
        st.code(fetch_debug or "No debug info.", language="text")

    # ── Compute KPIs ──────────────────────────────────────────────────────────
    total_value    = sum(e["market_value"] for e in eq) + ps.get("Cash", {}).get("value", 0) + \
                     ps.get("Funds", {}).get("value", 0)
    equities_val   = sum(e["market_value"] for e in eq)
    total_cost     = sum(e["total_cost"] for e in eq)
    total_gain     = sum(e["gain_loss"] for e in eq)
    gain_pct       = (total_gain / total_cost * 100) if total_cost else 0
    total_credits  = sum(t["credit"] for t in txs)
    total_debits   = sum(t["debit"]  for t in txs)
    net_invested   = total_credits - total_debits
    overall_return = ((total_value - net_invested) / net_invested * 100) if net_invested else 0
    cash_val       = ps.get("Cash", {}).get("value", 0)
    cash_alloc     = ps.get("Cash", {}).get("alloc", 0)
    equities_alloc = ps.get("Equities", {}).get("alloc", 0)
    winners        = sum(1 for e in eq if e["gain_pct"] >= 0)
    best           = max(eq, key=lambda e: e["gain_pct"])
    worst          = min(eq, key=lambda e: e["gain_pct"])
    biggest        = max(eq, key=lambda e: e["market_value"])

    active_month = "N/A"
    if txs:
        tx_df = pd.DataFrame(txs)
        tx_df["month"] = tx_df["date"].dt.to_period("M")
        active_month = str(tx_df["month"].value_counts().idxmax())

    # ── Client header bar ─────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:#1a1d2e;border-radius:12px;padding:14px 20px;
                display:flex;justify-content:space-between;align-items:center;
                margin-bottom:20px;flex-wrap:wrap;gap:10px;">
      <div>
        <span style="color:#8892b0;font-size:.8rem;">CLIENT</span><br>
        <span style="font-size:1.1rem;font-weight:700;color:#e8eaf6;">{data['client_name']}</span>
      </div>
      <div>
        <span style="color:#8892b0;font-size:.8rem;">ACCOUNT</span><br>
        <span style="font-size:1rem;font-weight:600;color:#6c63ff;">{data['account_number']}</span>
      </div>
      <div>
        <span style="color:#8892b0;font-size:.8rem;">REPORT DATE</span><br>
        <span style="font-size:1rem;font-weight:600;color:#e8eaf6;">{data['report_date']}</span>
      </div>
      <div>
        <span style="color:#8892b0;font-size:.8rem;">POSITIONS</span><br>
        <span style="font-size:1rem;font-weight:600;color:#e8eaf6;">{len(eq)} stocks · {len(txs)} transactions</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI Row 1 ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">📊 Portfolio Overview</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi("Total Portfolio Value",
                        f"GHS {total_value:,.2f}",
                        f"As of {data['report_date']}", "blue"),
                    unsafe_allow_html=True)
    with c2:
        gc = pos_neg_cls(total_gain)
        st.markdown(kpi("Unrealised Gain / Loss",
                        f"<span class='{gc}'>{'+'if total_gain>=0 else ''}GHS {total_gain:,.2f}</span>",
                        f"<span class='{gc}'>{gain_pct:+.2f}%</span> on cost basis",
                        "green" if total_gain >= 0 else "red"),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(kpi("Total Cost Basis",
                        f"GHS {total_cost:,.2f}",
                        f"{len(eq)} equity positions"),
                    unsafe_allow_html=True)
    with c4:
        rc = pos_neg_cls(overall_return)
        st.markdown(kpi("Overall ROI",
                        f"<span class='{rc}'>{overall_return:+.2f}%</span>",
                        f"Net invested: GHS {net_invested:,.2f}",
                        "green" if overall_return >= 0 else "red"),
                    unsafe_allow_html=True)

    st.markdown("")
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(kpi("Equities Value",
                        f"GHS {equities_val:,.2f}",
                        f"{equities_alloc:.1f}% of portfolio", ""),
                    unsafe_allow_html=True)
    with c6:
        st.markdown(kpi("Cash Balance",
                        f"GHS {cash_val:,.2f}",
                        f"{cash_alloc:.1f}% of portfolio", "yellow"),
                    unsafe_allow_html=True)
    with c7:
        st.markdown(kpi("Total Contributions",
                        f"GHS {total_credits:,.2f}",
                        f"{len(txs)} total transactions"),
                    unsafe_allow_html=True)
    with c8:
        st.markdown(kpi("Total Withdrawals",
                        f"GHS {total_debits:,.2f}",
                        f"Net: GHS {net_invested:,.2f}", "red"),
                    unsafe_allow_html=True)

    st.markdown("---")

    # ── Quick Insights ────────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">💡 Quick Insights</div>', unsafe_allow_html=True)
    i1, i2, i3, i4, i5, i6 = st.columns(6)
    with i1:
        st.markdown(f"""<div class="insight-box">
          <div class="insight-icon">🏆</div>
          <div class="insight-lbl">Best Performer</div>
          <div class="insight-val pos">{best['ticker']} ({best['gain_pct']:+.1f}%)</div>
        </div>""", unsafe_allow_html=True)
    with i2:
        st.markdown(f"""<div class="insight-box">
          <div class="insight-icon">📉</div>
          <div class="insight-lbl">Worst Performer</div>
          <div class="insight-val neg">{worst['ticker']} ({worst['gain_pct']:+.1f}%)</div>
        </div>""", unsafe_allow_html=True)
    with i3:
        st.markdown(f"""<div class="insight-box">
          <div class="insight-icon">💎</div>
          <div class="insight-lbl">Largest Position</div>
          <div class="insight-val">{biggest['ticker']} (GHS {biggest['market_value']:,.0f})</div>
        </div>""", unsafe_allow_html=True)
    with i4:
        st.markdown(f"""<div class="insight-box">
          <div class="insight-icon">⚡</div>
          <div class="insight-lbl">Most Active Month</div>
          <div class="insight-val">{active_month}</div>
        </div>""", unsafe_allow_html=True)
    with i5:
        st.markdown(f"""<div class="insight-box">
          <div class="insight-icon">✅</div>
          <div class="insight-lbl">Winning Positions</div>
          <div class="insight-val pos">{winners} / {len(eq)} stocks</div>
        </div>""", unsafe_allow_html=True)
    with i6:
        st.markdown(f"""<div class="insight-box">
          <div class="insight-icon">📡</div>
          <div class="insight-lbl">Live Prices</div>
          <div class="insight-val">{n_live} / {len(eq)} fetched</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Charts: Gain/Loss + Allocation ───────────────────────────────────────
    st.markdown('<div class="section-hdr">📈 Performance Analysis</div>', unsafe_allow_html=True)
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.plotly_chart(chart_gain_loss(eq), use_container_width=True)
    with col_right:
        st.plotly_chart(chart_allocation(ps), use_container_width=True)

    # ── Charts: Market vs Cost + Stock Weight ─────────────────────────────────
    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.plotly_chart(chart_market_vs_cost(eq), use_container_width=True)
    with col_right:
        st.plotly_chart(chart_stock_weight(eq), use_container_width=True)

    # ── Live vs Statement price chart ────────────────────────────────────────
    price_chart = chart_price_comparison(eq)
    if price_chart:
        st.plotly_chart(price_chart, use_container_width=True)
    else:
        st.info("📡 Live price comparison unavailable — no live prices fetched. Check your internet connection.")

    st.markdown("---")

    # ── Cash flow charts ──────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">💸 Cash Flow & History</div>', unsafe_allow_html=True)
    cf = chart_cashflow(txs)
    if cf:
        st.plotly_chart(cf, use_container_width=True)

    col_left, col_right = st.columns([3, 2])
    with col_left:
        cumul = chart_cumulative(txs, total_value)
        if cumul:
            st.plotly_chart(cumul, use_container_width=True)
    with col_right:
        tx_type = chart_tx_type_breakdown(txs)
        if tx_type:
            st.plotly_chart(tx_type, use_container_width=True)

    st.markdown("---")

    # ── Equity Positions Table ────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">📋 Equity Positions Detail</div>', unsafe_allow_html=True)

    rows = []
    for e in sorted(eq, key=lambda x: x["market_value"], reverse=True):
        live_str = f"GHS {e['live_price']:.4f}" if e["live_price"] else "—"
        rows.append({
            "Ticker":         e["ticker"],
            "Qty":            f"{e['qty']:,.0f}",
            "Avg Cost (GHS)": f"{e['avg_cost']:.4f}",
            "Stmt Price":     f"{e['statement_price']:.4f}",
            "Live Price":     live_str,
            "Price Source":   e["price_source"],
            "Daily Chg%":     f"{e.get('price_change', 0):+.2f}%" if e.get("live_price") else "—",
            "Daily Chg GHS":  f"{e.get('price_change_abs', 0):+.4f}" if e.get("live_price") else "—",
            "Cost Basis":     f"GHS {e['total_cost']:,.2f}",
            "Market Value":   f"GHS {e['market_value']:,.2f}",
            "Gain/Loss GHS":  f"{'+'if e['gain_loss']>=0 else ''}{e['gain_loss']:,.2f}",
            "Return %":       f"{e['gain_pct']:+.1f}%",
        })

    df_display = pd.DataFrame(rows)

    def _style_row(row):
        styles = [""] * len(row)
        gl = row["Gain/Loss GHS"]
        pct_col = list(row.index).index("Return %")
        gl_col  = list(row.index).index("Gain/Loss GHS")
        if "+" in gl or (gl.replace(",","").replace(".","").replace("-","").isdigit() and float(gl.replace(",","")) >= 0):
            styles[gl_col]  = "color: #00d68f; font-weight: 700"
            styles[pct_col] = "color: #00d68f; font-weight: 700"
        else:
            styles[gl_col]  = "color: #ff3d71; font-weight: 700"
            styles[pct_col] = "color: #ff3d71; font-weight: 700"
        return styles

    st.dataframe(
        df_display.style.apply(_style_row, axis=1),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")

    # ── Transaction History ───────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">🕒 Transaction History</div>', unsafe_allow_html=True)

    tx_df = pd.DataFrame(txs).sort_values("date", ascending=False)
    tx_df["Type"] = tx_df["description"].apply(lambda d:
        "🔵 Buy"        if re.search(r"\bBought\b", d, re.I) else
        "🟡 Sell"       if re.search(r"\bSold\b",   d, re.I) else
        "🟢 Credit"     if re.search(r"Contribution|Funding", d, re.I) else
        "🔴 Withdrawal" if re.search(r"Withdrawal|Transfer.*Payout", d, re.I) else
        "⚪ Other"
    )

    col_filter, col_search = st.columns([2, 3])
    with col_filter:
        tx_type_filter = st.multiselect(
            "Filter by type",
            options=["🔵 Buy", "🟡 Sell", "🟢 Credit", "🔴 Withdrawal", "⚪ Other"],
            default=["🔵 Buy", "🟡 Sell", "🟢 Credit", "🔴 Withdrawal", "⚪ Other"],
            label_visibility="collapsed",
        )
    with col_search:
        search = st.text_input("Search transactions", placeholder="Search description...",
                               label_visibility="collapsed")

    filtered = tx_df[tx_df["Type"].isin(tx_type_filter)]
    if search:
        filtered = filtered[filtered["description"].str.contains(search, case=False, na=False)]

    display_cols = {
        "date_str": "Date", "Type": "Type",
        "description": "Description", "credit": "Credit (GHS)", "debit": "Debit (GHS)"
    }
    tx_show = filtered[list(display_cols.keys())].rename(columns=display_cols)
    tx_show["Credit (GHS)"] = tx_show["Credit (GHS)"].apply(
        lambda v: f"+{v:,.2f}" if v > 0 else "—")
    tx_show["Debit (GHS)"] = tx_show["Debit (GHS)"].apply(
        lambda v: f"-{v:,.2f}" if v > 0 else "—")
    tx_show["Description"] = tx_show["Description"].str[:100]

    st.dataframe(tx_show, use_container_width=True, hide_index=True, height=420)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;color:#8892b0;font-size:.8rem;padding:24px 0 8px;">
      IC Portfolio Analyser · Live prices via afx.kwayisi.org (dev.kwayisi.org API) ·
      For informational purposes only · Past performance is not indicative of future results
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()