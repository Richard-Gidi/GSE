"""
IC Securities Portfolio Analyser
Install:  pip install streamlit plotly pdfplumber pandas requests beautifulsoup4 lxml
Run:      streamlit run akwasi.py
"""

import base64, io, re, warnings
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pdfplumber
import streamlit as st

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# THEME  —  dark / light palettes
# ─────────────────────────────────────────────────────────────────────────────
DARK = dict(
    BG="#0f1117", CARD="#1a1d2e", BORDER="#232640",
    TEXT="#e8eaf6", MUTED="#8892b0",
)
LIGHT = dict(
    BG="#f4f6fb", CARD="#ffffff", BORDER="#dde1f0",
    TEXT="#1a1d2e", MUTED="#6b7280",
)

# Accent colours are the same in both themes
PURPLE = "#6c63ff"
GREEN  = "#00d68f"
RED    = "#ff3d71"
AMBER  = "#ffaa00"
BLUE   = "#0095ff"

st.set_page_config(page_title="IC Portfolio Analyser", page_icon="📈",
                   layout="wide", initial_sidebar_state="collapsed")

# Resolve theme from session state (default: dark)
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"
_p  = DARK if st.session_state["theme"] == "dark" else LIGHT
BG     = _p["BG"]
CARD   = _p["CARD"]
BORDER = _p["BORDER"]
TEXT   = _p["TEXT"]
MUTED  = _p["MUTED"]

T = dict(
    paper_bgcolor=BG, plot_bgcolor=CARD,
    font=dict(color=TEXT, family="Segoe UI, system-ui"),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    margin=dict(l=16, r=16, t=44, b=16),
)

st.markdown(f"""<style>
html, body, [class*="css"] {{ font-family: 'Segoe UI', system-ui, sans-serif; }}
.stApp {{ background:{BG} !important; }}
section[data-testid="stSidebar"] {{ background:{CARD} !important; }}
hr {{ border-color:{BORDER} !important; margin:20px 0 !important; }}

/* override Streamlit's own background tokens */
[data-testid="stAppViewContainer"] {{ background:{BG} !important; }}
[data-testid="stHeader"] {{ background:{BG} !important; }}
[data-testid="stToolbar"] {{ background:{BG} !important; }}
.block-container {{ color:{TEXT}; }}

.kpi {{ background:{CARD}; border-radius:14px; padding:18px 20px;
        border-left:4px solid {PURPLE}; margin-bottom:4px;
        transition:transform .15s;
        box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.kpi:hover {{ transform:translateY(-2px); }}
.kpi.g {{ border-left-color:{GREEN}; }}
.kpi.r {{ border-left-color:{RED}; }}
.kpi.y {{ border-left-color:{AMBER}; }}
.kpi.b {{ border-left-color:{BLUE}; }}
.kpi-lbl {{ font-size:.72rem; color:{MUTED}; text-transform:uppercase;
            letter-spacing:.06em; margin-bottom:6px; }}
.kpi-val {{ font-size:1.45rem; font-weight:800; color:{TEXT}; }}
.kpi-sub {{ font-size:.75rem; color:{MUTED}; margin-top:4px; }}

.ibox {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px;
         padding:14px 16px; text-align:center; height:100%;
         box-shadow:0 1px 4px rgba(0,0,0,.06); }}
.ibox-icon {{ font-size:1.6rem; }}
.ibox-lbl  {{ font-size:.7rem; color:{MUTED}; text-transform:uppercase;
              letter-spacing:.05em; margin:6px 0 2px; }}
.ibox-val  {{ font-size:1rem; font-weight:700; color:{TEXT}; }}

.shdr {{ font-size:1rem; font-weight:700; color:{TEXT};
         border-left:4px solid {PURPLE}; padding-left:10px; margin:8px 0 14px; }}

.pos {{ color:{GREEN} !important; }}
.neg {{ color:{RED}   !important; }}

.hero {{ font-size:2.4rem; font-weight:900;
         background:linear-gradient(135deg,{PURPLE},{GREEN});
         -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.hero-sub {{ color:{MUTED}; font-size:1rem; margin-top:4px; }}

[data-testid="stFileUploadDropzone"] {{
    background:{CARD} !important; border:2px dashed {PURPLE}55 !important;
    border-radius:14px !important; padding:32px !important; }}
[data-testid="stDataFrame"] {{ border-radius:12px; overflow:hidden; }}
.js-plotly-plot {{ border-radius:12px; }}
</style>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SMALL HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", cls=""):
    sub_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    return (f"<div class='kpi {cls}'><div class='kpi-lbl'>{label}</div>"
            f"<div class='kpi-val'>{value}</div>{sub_html}</div>")

def insight(icon, label, value, cls=""):
    return (f"<div class='ibox'><div class='ibox-icon'>{icon}</div>"
            f"<div class='ibox-lbl'>{label}</div>"
            f"<div class='ibox-val {cls}'>{value}</div></div>")

def shdr(text):
    st.markdown(f"<div class='shdr'>{text}</div>", unsafe_allow_html=True)

def pn(v):
    return "pos" if v >= 0 else "neg"

def _normalize(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())

def _to_float(val):
    try:
        f = float(re.sub(r"[^\d.\-]", "", str(val).replace(",", "")))
        return f if f == f else None
    except Exception:
        return None

def tx_type(desc):
    if re.search(r"\bBought\b",              desc, re.I): return "Buy"
    if re.search(r"\bSold\b",                desc, re.I): return "Sell"
    if re.search(r"Contribution|Funding",    desc, re.I): return "Credit"
    if re.search(r"Withdrawal|Transfer.*Payout", desc, re.I): return "Withdrawal"
    return "Other"


# ─────────────────────────────────────────────────────────────────────────────
# PRICE PARSER  —  afx.kwayisi.org/gse/
# ─────────────────────────────────────────────────────────────────────────────
def _parse_afx_html(html: str, tickers: tuple) -> dict:
    from bs4 import BeautifulSoup
    norm_to_orig = {_normalize(t): t for t in tickers}
    wanted       = set(norm_to_orig)
    results      = {}

    soup  = BeautifulSoup(html, "html.parser")
    table = None
    div   = soup.find("div", class_="t")
    if div:
        table = div.find("table")
    if not table:
        for tbl in soup.find_all("table"):
            hdrs = [th.get_text(strip=True) for th in tbl.find_all("th")]
            if "Ticker" in hdrs and "Price" in hdrs:
                table = tbl
                break
    if not table:
        return {}

    headers    = [th.get_text(strip=True) for th in table.find_all("th")]
    ticker_idx = headers.index("Ticker")
    price_idx  = headers.index("Price")
    change_idx = headers.index("Change") if "Change" in headers else None

    for tr in table.find("tbody").find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) <= price_idx:
            continue
        sym = _normalize(cells[ticker_idx].get_text(strip=True))
        if sym not in wanted:
            continue
        price = _to_float(cells[price_idx].get_text(strip=True))
        if not price or price <= 0:
            continue
        chg  = (_to_float(cells[change_idx].get_text(strip=True)) or 0.0
                if change_idx and len(cells) > change_idx else 0.0)
        prev = price - chg
        results[norm_to_orig[sym]] = {
            "price":      price,
            "change_abs": chg,
            "change_pct": round((chg / prev * 100) if prev else 0.0, 2),
        }
    return results


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_live(tickers: tuple) -> dict:
    import requests, urllib3
    urllib3.disable_warnings()
    try:
        r = requests.get("https://afx.kwayisi.org/gse/",
                         headers={"User-Agent": "Mozilla/5.0"},
                         timeout=10, verify=False)
        if r.status_code == 200:
            return _parse_afx_html(r.text, tickers)
    except Exception:
        pass
    return {}


def get_live_prices(tickers: tuple) -> dict:
    # 1. Streamlit Secrets (base64-encoded HTML)
    try:
        html = base64.b64decode(st.secrets["gse_html_b64"]).decode("utf-8")
        return _parse_afx_html(html, tickers)
    except Exception:
        pass
    # 2. Session state (sidebar upload / paste)
    html = st.session_state.get("gse_html", "")
    if html:
        return _parse_afx_html(html, tickers)
    # 3. Live network fetch
    return _fetch_live(tickers)


# ─────────────────────────────────────────────────────────────────────────────
# PDF PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse_pdf(pdf_bytes: bytes) -> dict:
    equities, transactions, portfolio_summary, funds_data = [], [], {}, {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = full_text.split("\n")

    # Portfolio summary
    for i, line in enumerate(lines):
        if "Total Value" in line and "Allocation" in line:
            for l in lines[i+1 : i+10]:
                m = re.match(r"(Funds|Fixed Income|Equities|Cash)\s+([\d,\.]+)\s+([\d\.]+)", l.strip())
                if m:
                    portfolio_summary[m.group(1)] = {
                        "value": float(m.group(2).replace(",", "")),
                        "alloc": float(m.group(3)),
                    }
                m2 = re.match(r"([\d,\.]+)\s+100\.00", l.strip())
                if m2:
                    portfolio_summary["Total"] = float(m2.group(1).replace(",", ""))

    # Funds
    m = re.search(
        r"IC Liquidity\s+([\d,\.]+)\s+-([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)", full_text)
    if m:
        funds_data = {
            "name": "IC Liquidity",
            "invested":     float(m.group(1).replace(",", "")),
            "redeemed":     float(m.group(2).replace(",", "")),
            "market_value": float(m.group(5)),
        }

    # Equities
    equity_pat = re.compile(
        r"^([A-Z]{2,8})\s+(GH[A-Z0-9]+|TG[A-Z0-9]+)\s+([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d,\.]+)")
    for line in lines:
        m = equity_pat.match(line.strip())
        if m:
            qty  = float(m.group(3).replace(",", ""))
            cost = float(m.group(4))
            tc   = qty * cost
            mv   = float(m.group(6).replace(",", ""))
            gl   = mv - tc
            equities.append({
                "ticker":          m.group(1),
                "qty":             qty,
                "avg_cost":        cost,
                "statement_price": float(m.group(5)),
                "live_price":      None,
                "market_value":    mv,
                "total_cost":      tc,
                "gain_loss":       gl,
                "gain_pct":        (gl / tc * 100) if tc else 0,
            })

    # Transactions
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
                transactions.append({
                    "date":        datetime.strptime(date_str, "%d/%m/%Y"),
                    "date_str":    date_str,
                    "description": desc,
                    "credit":      credit if credit > 0 else 0,
                    "debit":       abs(debit) if debit < 0 else 0,
                    "type":        tx_type(desc),
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
        "equities":          equities,
        "transactions":      transactions,
        "portfolio_summary": portfolio_summary,
        "funds":             funds_data,
        "client_name":       _field("Client Name:"),
        "account_number":    _field("Account Number:"),
        "report_date":       _field("Report Date:"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# INJECT LIVE PRICES
# ─────────────────────────────────────────────────────────────────────────────
def inject_live_prices(equities: list, live: dict) -> list:
    out = []
    for e in equities:
        e = e.copy()
        if e["ticker"] in live:
            lp = live[e["ticker"]]["price"]
            mv = e["qty"] * lp
            gl = mv - e["total_cost"]
            e.update({
                "live_price":   lp,
                "market_value": mv,
                "gain_loss":    gl,
                "gain_pct":     (gl / e["total_cost"] * 100) if e["total_cost"] else 0,
                "change_pct":   live[e["ticker"]]["change_pct"],
                "change_abs":   live[e["ticker"]]["change_abs"],
            })
        else:
            e["live_price"] = e["change_pct"] = e["change_abs"] = None
        out.append(e)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def chart_gain_loss(eq):
    df = pd.DataFrame(eq).sort_values("gain_pct")
    colors = [GREEN if v >= 0 else RED for v in df["gain_pct"]]
    fig = go.Figure(go.Bar(
        x=df["gain_pct"], y=df["ticker"], orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df["gain_pct"]], textposition="outside",
        hovertemplate="<b>%{y}</b><br>Return: %{x:.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="Return per Stock (%)", xaxis_title="Return (%)", **T, height=380)
    return fig


def chart_pl_waterfall(eq):
    df    = pd.DataFrame(eq).sort_values("gain_loss")
    total = df["gain_loss"].sum()
    vals  = df["gain_loss"].tolist() + [total]
    cols  = [GREEN if v >= 0 else RED for v in vals]
    fig = go.Figure(go.Bar(
        x=df["ticker"].tolist() + ["TOTAL"],
        y=vals,
        marker_color=cols,
        text=[f"{'+'if v>=0 else ''}GHS {v:,.0f}" for v in vals],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>P&L: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="P&L Contribution per Stock (GHS)", yaxis_title="GHS",
                      **T, height=340)
    return fig


def chart_market_vs_cost(eq):
    df = pd.DataFrame(eq).sort_values("market_value", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Cost Basis",   x=df["ticker"], y=df["total_cost"],
                         marker_color=BLUE, opacity=0.85,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Cost</extra>"))
    fig.add_trace(go.Bar(name="Market Value", x=df["ticker"], y=df["market_value"],
                         marker_color=PURPLE, opacity=0.85,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Market</extra>"))
    fig.update_layout(title="Market Value vs Cost Basis", yaxis_title="GHS",
                      barmode="group", legend=dict(bgcolor=CARD, bordercolor=BORDER),
                      **T, height=360)
    return fig


def chart_allocation_treemap(ps):
    cmap = {"Equities": PURPLE, "Cash": BLUE, "Funds": AMBER, "Fixed Income": GREEN}
    labels, parents, values, colors = [], [], [], []
    for k, v in ps.items():
        if k == "Total" or v["value"] == 0:
            continue
        labels.append(k)
        parents.append("")
        values.append(v["value"])
        colors.append(cmap.get(k, MUTED))
    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        marker=dict(colors=colors, line=dict(width=2, color=BG)),
        texttemplate="<b>%{label}</b><br>GHS %{value:,.0f}<br>%{percentRoot:.1%}",
        hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f}<extra></extra>",
    ))
    layout = {**T, "title": "Portfolio Allocation", "height": 320, "margin": dict(l=8, r=8, t=44, b=8)}
    fig.update_layout(**layout)
    return fig


def chart_stock_weight_bar(eq):
    df    = pd.DataFrame(eq).sort_values("market_value")
    total = df["market_value"].sum()
    df["weight"] = df["market_value"] / total * 100
    fig = go.Figure(go.Bar(
        x=df["weight"], y=df["ticker"], orientation="h",
        marker=dict(color=df["weight"],
                    colorscale=[[0, BLUE],[0.5, PURPLE],[1, GREEN]],
                    line=dict(width=0)),
        text=[f"{w:.1f}%" for w in df["weight"]], textposition="outside",
        customdata=df["market_value"],
        hovertemplate="<b>%{y}</b><br>Weight: %{x:.2f}%<br>GHS %{customdata:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Stock Weight in Equity Portfolio", xaxis_title="Weight (%)",
                      **T, height=360, showlegend=False)
    return fig


def chart_price_comparison(eq):
    df = pd.DataFrame(eq)
    df = df[df["live_price"].notna()].copy()
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Statement Price", x=df["ticker"], y=df["statement_price"],
                         marker_color=AMBER, opacity=0.85))
    fig.add_trace(go.Bar(name="Live Price",      x=df["ticker"], y=df["live_price"],
                         marker_color=GREEN, opacity=0.85))
    fig.update_layout(title="Statement vs Live Price", yaxis_title="GHS per Share",
                      barmode="group", legend=dict(bgcolor=CARD), **T, height=320)
    return fig


def chart_cashflow(txs):
    df = pd.DataFrame(txs)
    if df.empty:
        return None
    df["month"] = df["date"].dt.to_period("M")
    m = df.groupby("month").agg(credits=("credit","sum"), debits=("debit","sum")).reset_index()
    m["month_str"] = m["month"].astype(str)
    m["net"]       = m["credits"] - m["debits"]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Credits", x=m["month_str"], y=m["credits"],
                         marker_color=GREEN, opacity=0.85,
                         hovertemplate="%{x}<br>GHS %{y:,.2f}<extra>Credits</extra>"))
    fig.add_trace(go.Bar(name="Debits",  x=m["month_str"], y=m["debits"],
                         marker_color=RED, opacity=0.85,
                         hovertemplate="%{x}<br>GHS %{y:,.2f}<extra>Debits</extra>"))
    fig.add_trace(go.Scatter(name="Net", x=m["month_str"], y=m["net"],
                             mode="lines+markers", line=dict(color=AMBER, width=2),
                             marker=dict(size=5),
                             hovertemplate="%{x}<br>Net GHS %{y:,.2f}<extra></extra>"))
    fig.add_hline(y=0, line_color=MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="Monthly Cash Flow", barmode="group",
                      xaxis_tickangle=-30, yaxis_title="GHS",
                      legend=dict(bgcolor=CARD), **T, height=370)
    return fig


def chart_cumulative(txs, total_value):
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        fill="tozeroy", fillcolor="rgba(108,99,255,0.12)",
        line=dict(color=PURPLE, width=2), name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>GHS %{y:,.2f}<extra>Net Invested</extra>",
    ))
    fig.add_hline(y=total_value, line_color=GREEN, line_dash="dash", line_width=2,
                  annotation_text=f"Current Value  GHS {total_value:,.0f}",
                  annotation_font_color=GREEN)
    fig.update_layout(title="Cumulative Net Invested vs Portfolio Value",
                      xaxis_title="Date", yaxis_title="GHS", **T, height=340)
    return fig


def chart_breakeven(eq):
    losers = [e for e in eq if e["gain_pct"] < 0]
    if not losers:
        return None
    df         = pd.DataFrame(losers)
    price_col  = df["live_price"].fillna(df["statement_price"])
    pct_needed = (df["avg_cost"] - price_col) / price_col * 100
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Current Price",    x=df["ticker"], y=price_col,
                         marker_color=RED, opacity=0.85,
                         hovertemplate="%{x}<br>Current: GHS %{y:.4f}<extra></extra>"))
    fig.add_trace(go.Bar(name="Break-even Price", x=df["ticker"], y=df["avg_cost"],
                         marker_color=AMBER, opacity=0.85,
                         hovertemplate="%{x}<br>Break-even: GHS %{y:.4f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        name="% Rally Needed", x=df["ticker"], y=pct_needed,
        mode="markers+text", yaxis="y2",
        marker=dict(size=12, color=AMBER, symbol="diamond"),
        text=[f"+{v:.1f}%" for v in pct_needed], textposition="top center",
        hovertemplate="%{x}: needs %{y:.1f}% rally<extra></extra>",
    ))
    fig.update_layout(**{
        **T,
        "title": "Break-even Analysis — Losing Positions",
        "yaxis":  dict(title="Price (GHS)", gridcolor=BORDER),
        "yaxis2": dict(title="% Rally Needed", overlaying="y", side="right",
                       showgrid=False, color=AMBER),
        "barmode": "group",
        "legend":  dict(bgcolor=CARD),
        "height":  360,
    })
    return fig


def chart_concentration(eq):
    df  = pd.DataFrame(eq)
    tot = df["market_value"].sum()
    w   = df["market_value"] / tot
    hhi = round((w ** 2).sum() * 10000)

    if hhi < 1500:   risk, risk_color = "Low",      GREEN
    elif hhi < 2500: risk, risk_color = "Moderate", AMBER
    else:            risk, risk_color = "High",      RED

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Concentration (HHI)", "Exposure Ranking"],
                        specs=[[{"type":"indicator"}, {"type":"xy"}]])

    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=hhi,
        number=dict(font=dict(color=risk_color, size=32)),
        gauge=dict(
            axis=dict(range=[0, 10000], tickcolor=MUTED),
            bar=dict(color=risk_color),
            bgcolor=CARD,
            steps=[
                dict(range=[0,    1500], color="rgba(0,214,143,0.13)"),
                dict(range=[1500, 2500], color="rgba(255,170,0,0.13)"),
                dict(range=[2500,10000], color="rgba(255,61,113,0.13)"),
            ],
        ),
        title=dict(text=f"Risk: <b>{risk}</b>", font=dict(color=risk_color)),
    ), row=1, col=1)

    df_s = df.sort_values("market_value", ascending=True)
    ws   = (df_s["market_value"] / tot * 100).values
    fig.add_trace(go.Bar(
        x=ws, y=df_s["ticker"].values, orientation="h",
        marker=dict(color=ws, colorscale=[[0,GREEN],[0.5,AMBER],[1,RED]],
                    line=dict(width=0)),
        text=[f"{v:.1f}%" for v in ws], textposition="outside",
        hovertemplate="<b>%{y}</b>: %{x:.1f}%<extra></extra>",
        showlegend=False,
    ), row=1, col=2)

    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=CARD,
        font=dict(color=TEXT, family="Segoe UI"),
        margin=dict(l=16, r=16, t=60, b=16), height=360,
        xaxis2=dict(gridcolor=BORDER, title="Weight (%)"),
        yaxis2=dict(gridcolor=BORDER),
    )
    return fig, hhi, risk, risk_color


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        # ── Theme toggle ──────────────────────────────────────────────────────
        is_dark = st.session_state.get("theme", "dark") == "dark"
        col_icon, col_btn = st.columns([1, 3])
        with col_icon:
            st.markdown(f"<div style='font-size:1.6rem;padding-top:6px'>{'🌙' if is_dark else '☀️'}</div>",
                        unsafe_allow_html=True)
        with col_btn:
            label = "Switch to Light" if is_dark else "Switch to Dark"
            if st.button(label, use_container_width=True):
                st.session_state["theme"] = "light" if is_dark else "dark"
                st.rerun()
        st.divider()

        st.markdown("### 📡 GSE Prices")
        if st.secrets.get("gse_html_b64", ""):
            st.success("✅ Loaded from Streamlit Secrets")
            st.caption("To refresh: update `gse_html_b64` in **Settings → Secrets**.")
        else:
            st.info("Add `gse_html_b64` in **Settings → Secrets** for automatic prices.")
            st.divider()
            up = st.file_uploader("Upload gse.html", type=["html","htm","txt"])
            if up:
                st.session_state["gse_html"]      = up.read().decode("utf-8", errors="ignore")
                st.session_state["gse_html_name"] = up.name
            paste = st.text_area("Or paste page source", height=80, placeholder="<!DOCTYPE html>...")
            if paste and paste.strip().startswith("<"):
                st.session_state["gse_html"]      = paste
                st.session_state["gse_html_name"] = "pasted"
            if "gse_html" in st.session_state:
                st.success(f"✅ {st.session_state.get('gse_html_name','loaded')}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    render_sidebar()

    # Header
    cl, ct, ctheme = st.columns([1, 7, 2])
    with cl:
        st.markdown("<div style='font-size:3rem;padding-top:6px'>📈</div>", unsafe_allow_html=True)
    with ct:
        st.markdown("<div class='hero'>IC Portfolio Analyser</div>"
                    "<div class='hero-sub'>Upload your IC Securities statement · "
                    "Live GSE prices · Instant insights</div>", unsafe_allow_html=True)
    with ctheme:
        is_dark = st.session_state.get("theme", "dark") == "dark"
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        if st.button("🌙 Dark" if not is_dark else "☀️ Light",
                     use_container_width=True, key="header_theme_btn"):
            st.session_state["theme"] = "light" if is_dark else "dark"
            st.rerun()
    st.markdown("---")

    # Upload
    uploaded = st.file_uploader("**Drop your IC Securities Account Statement (PDF)**", type=["pdf"])
    if not uploaded:
        c1, c2, c3, c4 = st.columns(4)
        for col, icon, lbl in [(c1,"🏆","Performance Analysis"),(c2,"🌳","Portfolio Treemap"),
                                (c3,"🔮","What-If Simulator"),  (c4,"⚖️","Risk & Concentration")]:
            with col:
                st.markdown(f"<div class='ibox'><div class='ibox-icon'>{icon}</div>"
                            f"<div class='ibox-lbl'>{lbl}</div></div>", unsafe_allow_html=True)
        st.stop()

    # Parse PDF
    with st.spinner("📄 Parsing statement..."):
        data = parse_pdf(uploaded.read())

    eq  = data["equities"]
    txs = data["transactions"]
    ps  = data["portfolio_summary"]

    if not eq:
        st.error("Could not parse equity data. Please check the PDF format.")
        st.stop()

    # Live prices
    tickers = tuple(e["ticker"] for e in eq)
    live    = get_live_prices(tickers)
    eq      = inject_live_prices(eq, live)
    n_live  = sum(1 for e in eq if e["live_price"] is not None)

    if n_live == len(eq):
        st.success(f"📡 All {n_live} live prices loaded from GSE")
    elif n_live:
        st.warning(f"📡 {n_live}/{len(eq)} live prices · {len(eq)-n_live} using statement price")
    else:
        st.info("📋 Showing statement prices — update `gse_html_b64` in Secrets for live data")

    # Manual override
    with st.expander("✏️ Override prices manually", expanded=False):
        cols = st.columns(5)
        overrides = {}
        for i, e in enumerate(eq):
            default = float(e["live_price"] or e["statement_price"])
            val = cols[i % 5].number_input(e["ticker"], min_value=0.0, value=default,
                                           step=0.01, format="%.4f", key=f"ov_{e['ticker']}")
            if val > 0:
                overrides[e["ticker"]] = val
        if st.button("✅ Apply", type="primary"):
            st.cache_data.clear()
            eq = inject_live_prices(
                eq, {t: {"price":p,"change_pct":0,"change_abs":0} for t,p in overrides.items()})
            n_live = len(eq)
            st.success("Applied.")

    # ── Derived metrics ───────────────────────────────────────────────────────
    equities_val  = sum(e["market_value"] for e in eq)
    total_cost    = sum(e["total_cost"]   for e in eq)
    total_gain    = sum(e["gain_loss"]    for e in eq)
    gain_pct      = (total_gain / total_cost * 100) if total_cost else 0
    cash_val      = ps.get("Cash",  {}).get("value", 0)
    funds_val     = ps.get("Funds", {}).get("value", 0)
    total_value   = equities_val + cash_val + funds_val
    total_credits = sum(t["credit"] for t in txs)
    total_debits  = sum(t["debit"]  for t in txs)
    net_invested  = total_credits - total_debits
    overall_roi   = ((total_value - net_invested) / net_invested * 100) if net_invested else 0
    winners       = sum(1 for e in eq if e["gain_pct"] >= 0)
    best          = max(eq, key=lambda e: e["gain_pct"])
    worst         = min(eq, key=lambda e: e["gain_pct"])
    biggest       = max(eq, key=lambda e: e["market_value"])
    active_month  = "N/A"
    if txs:
        _tdf         = pd.DataFrame(txs)
        _tdf["month"] = _tdf["date"].dt.to_period("M")
        active_month  = str(_tdf["month"].value_counts().idxmax())

    # ── Client bar (always visible, above tabs) ──────────────────────────────
    st.markdown(f"""
    <div style="background:{CARD};border-radius:12px;padding:14px 20px;
                display:flex;justify-content:space-between;align-items:center;
                margin-bottom:20px;flex-wrap:wrap;gap:10px;">
      <div><span style="color:{MUTED};font-size:.8rem;">CLIENT</span><br>
           <span style="font-size:1.1rem;font-weight:700;color:{TEXT};">{data['client_name']}</span></div>
      <div><span style="color:{MUTED};font-size:.8rem;">ACCOUNT</span><br>
           <span style="font-size:1rem;font-weight:600;color:{PURPLE};">{data['account_number']}</span></div>
      <div><span style="color:{MUTED};font-size:.8rem;">REPORT DATE</span><br>
           <span style="font-size:1rem;font-weight:600;color:{TEXT};">{data['report_date']}</span></div>
      <div><span style="color:{MUTED};font-size:.8rem;">POSITIONS</span><br>
           <span style="font-size:1rem;font-weight:600;color:{TEXT};">
           {len(eq)} stocks · {len(txs)} transactions</span></div>
    </div>""", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview",
        "📈 Performance",
        "⚖️ Risk & Scenarios",
        "💸 Cash Flow",
        "📋 Holdings",
    ])

    # ── TAB 1: Overview ───────────────────────────────────────────────────────
    with tab1:
        shdr("📊 Portfolio Summary")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(kpi("Total Portfolio Value", f"GHS {total_value:,.2f}",
                                 f"As of {data['report_date']}", "b"), unsafe_allow_html=True)
        with c2: st.markdown(kpi("Unrealised Gain / Loss",
                                 f"<span class='{pn(total_gain)}'>{'+'if total_gain>=0 else ''}"
                                 f"GHS {total_gain:,.2f}</span>",
                                 f"<span class='{pn(gain_pct)}'>{gain_pct:+.2f}%</span> on cost basis",
                                 "g" if total_gain >= 0 else "r"), unsafe_allow_html=True)
        with c3: st.markdown(kpi("Total Cost Basis", f"GHS {total_cost:,.2f}",
                                 f"{len(eq)} positions"), unsafe_allow_html=True)
        with c4: st.markdown(kpi("Overall ROI",
                                 f"<span class='{pn(overall_roi)}'>{overall_roi:+.2f}%</span>",
                                 f"Net invested GHS {net_invested:,.2f}",
                                 "g" if overall_roi >= 0 else "r"), unsafe_allow_html=True)
        st.markdown("")
        c5, c6, c7, c8 = st.columns(4)
        with c5: st.markdown(kpi("Equities Value", f"GHS {equities_val:,.2f}",
                                 f"{ps.get('Equities',{}).get('alloc',0):.1f}% of portfolio"),
                             unsafe_allow_html=True)
        with c6: st.markdown(kpi("Cash Balance", f"GHS {cash_val:,.2f}",
                                 f"{ps.get('Cash',{}).get('alloc',0):.1f}% of portfolio", "y"),
                             unsafe_allow_html=True)
        with c7: st.markdown(kpi("Total Contributions", f"GHS {total_credits:,.2f}",
                                 f"{len(txs)} transactions"), unsafe_allow_html=True)
        with c8: st.markdown(kpi("Total Withdrawals", f"GHS {total_debits:,.2f}",
                                 f"Net GHS {net_invested:,.2f}", "r"), unsafe_allow_html=True)

        st.markdown("---")
        shdr("💡 Quick Insights")
        i1, i2, i3, i4, i5, i6 = st.columns(6)
        with i1: st.markdown(insight("🏆","Best Performer",  f"{best['ticker']} ({best['gain_pct']:+.1f}%)", "pos"), unsafe_allow_html=True)
        with i2: st.markdown(insight("📉","Worst Performer", f"{worst['ticker']} ({worst['gain_pct']:+.1f}%)", "neg"), unsafe_allow_html=True)
        with i3: st.markdown(insight("💎","Largest Position",f"{biggest['ticker']} · GHS {biggest['market_value']:,.0f}"), unsafe_allow_html=True)
        with i4: st.markdown(insight("⚡","Most Active Month", active_month), unsafe_allow_html=True)
        with i5: st.markdown(insight("✅","Winning Positions", f"{winners} / {len(eq)}", "pos"), unsafe_allow_html=True)
        with i6: st.markdown(insight("📡","Live Prices", f"{n_live} / {len(eq)}"), unsafe_allow_html=True)

        movers = sorted([e for e in eq if e.get("change_pct") is not None],
                        key=lambda e: abs(e["change_pct"]), reverse=True)
        if movers:
            st.markdown("---")
            shdr("🚀 Today's Movers")
            mcols = st.columns(min(len(movers), 5))
            for col, e in zip(mcols, movers[:5]):
                chg  = e["change_pct"] or 0
                chga = e["change_abs"] or 0
                cls  = "pos" if chg >= 0 else "neg"
                col.markdown(
                    f"<div class='ibox'>"
                    f"<div class='ibox-lbl'>{e['ticker']}</div>"
                    f"<div class='ibox-val' style='font-size:1.3rem;'>GHS {e['live_price']:.2f}</div>"
                    f"<div class='ibox-val {cls}' style='font-size:.9rem;'>"
                    f"{'▲' if chg>=0 else '▼'} {abs(chg):.2f}% ({chga:+.4f})</div>"
                    f"</div>", unsafe_allow_html=True)

    # ── TAB 2: Performance ────────────────────────────────────────────────────
    with tab2:
        shdr("📈 Performance Analysis")
        cl, cr = st.columns([3, 2])
        with cl: st.plotly_chart(chart_gain_loss(eq), use_container_width=True)
        with cr: st.plotly_chart(chart_stock_weight_bar(eq), use_container_width=True)

        cl, cr = st.columns([3, 2])
        with cl: st.plotly_chart(chart_market_vs_cost(eq), use_container_width=True)
        with cr: st.plotly_chart(chart_allocation_treemap(ps), use_container_width=True)

        st.plotly_chart(chart_pl_waterfall(eq), use_container_width=True)

        pc = chart_price_comparison(eq)
        if pc:
            st.plotly_chart(pc, use_container_width=True)

    # ── TAB 3: Risk & Scenarios ───────────────────────────────────────────────
    with tab3:
        be = chart_breakeven(eq)
        if be:
            shdr("🎯 Break-even Analysis")
            st.plotly_chart(be, use_container_width=True)
            st.markdown("---")

        shdr("⚖️ Concentration Risk")
        conc_fig, hhi, risk, risk_color = chart_concentration(eq)
        st.plotly_chart(conc_fig, use_container_width=True)
        st.markdown(
            f"<div style='text-align:center;color:{MUTED};font-size:.85rem;margin-top:-10px;'>"
            f"HHI: <b style='color:{risk_color}'>{hhi}</b> · "
            f"Concentration: <b style='color:{risk_color}'>{risk}</b> · "
            f"(Low &lt;1500 · Moderate 1500–2500 · High &gt;2500)"
            f"</div>", unsafe_allow_html=True)

        st.markdown("---")
        shdr("🔮 What-If Scenario Simulator")
        st.caption("Adjust sliders to model price changes and see the impact on your portfolio.")

        rows_of_5 = [eq[i:i+5] for i in range(0, len(eq), 5)]
        sim_mult  = {}
        for row in rows_of_5:
            cols = st.columns(len(row))
            for col, e in zip(cols, row):
                chg = col.slider(e["ticker"], min_value=-50, max_value=100, value=0,
                                 step=1, format="%d%%", key=f"sim_{e['ticker']}")
                sim_mult[e["ticker"]] = 1 + chg / 100

        sim_mv    = sum(e["market_value"] * sim_mult.get(e["ticker"], 1) for e in eq)
        sim_total = sim_mv + cash_val + funds_val
        sim_gain  = sum((e["market_value"] * sim_mult.get(e["ticker"],1)) - e["total_cost"] for e in eq)
        sim_delta = sim_total - total_value
        sim_roi   = ((sim_total - net_invested) / net_invested * 100) if net_invested else 0

        sc1, sc2, sc3 = st.columns(3)
        with sc1: st.markdown(kpi("Simulated Portfolio Value", f"GHS {sim_total:,.2f}",
                                  f"{'+'if sim_delta>=0 else ''}GHS {sim_delta:,.2f} vs current",
                                  "g" if sim_delta >= 0 else "r"), unsafe_allow_html=True)
        with sc2: st.markdown(kpi("Simulated Equity G/L",
                                  f"<span class='{pn(sim_gain)}'>{'+'if sim_gain>=0 else ''}"
                                  f"GHS {sim_gain:,.2f}</span>",
                                  f"{(sim_gain/total_cost*100):+.2f}% on cost",
                                  "g" if sim_gain >= 0 else "r"), unsafe_allow_html=True)
        with sc3: st.markdown(kpi("Simulated ROI",
                                  f"<span class='{pn(sim_roi)}'>{sim_roi:+.2f}%</span>",
                                  f"vs current {overall_roi:+.2f}%",
                                  "g" if sim_roi >= 0 else "r"), unsafe_allow_html=True)

        sim_df = pd.DataFrame([{
            "ticker":    e["ticker"],
            "current":   e["market_value"],
            "simulated": e["market_value"] * sim_mult.get(e["ticker"], 1),
        } for e in eq]).sort_values("simulated", ascending=False)
        fig_sim = go.Figure()
        fig_sim.add_trace(go.Bar(name="Current",   x=sim_df["ticker"], y=sim_df["current"],
                                 marker_color=PURPLE, opacity=0.7))
        fig_sim.add_trace(go.Bar(name="Simulated", x=sim_df["ticker"], y=sim_df["simulated"],
                                 marker_color=GREEN, opacity=0.85))
        fig_sim.update_layout(title="Current vs Simulated Market Value", yaxis_title="GHS",
                              barmode="group", legend=dict(bgcolor=CARD), **T, height=320)
        st.plotly_chart(fig_sim, use_container_width=True)

    # ── TAB 4: Cash Flow ──────────────────────────────────────────────────────
    with tab4:
        shdr("💸 Cash Flow & History")
        cf = chart_cashflow(txs)
        if cf:
            st.plotly_chart(cf, use_container_width=True)

        cl, cr = st.columns([3, 2])
        with cl:
            cumul = chart_cumulative(txs, total_value)
            if cumul:
                st.plotly_chart(cumul, use_container_width=True)
        with cr:
            tx_df2 = pd.DataFrame(txs)
            if not tx_df2.empty:
                tx_df2["amount"] = tx_df2["credit"] + tx_df2["debit"]
                grp = tx_df2.groupby("type")["amount"].sum().reset_index()
                cmap = {"Buy":BLUE,"Sell":AMBER,"Credit":GREEN,"Withdrawal":RED,"Other":MUTED}
                fig_tt = go.Figure(go.Bar(
                    x=grp["type"], y=grp["amount"],
                    marker_color=[cmap.get(t, MUTED) for t in grp["type"]],
                    text=[f"GHS {v:,.0f}" for v in grp["amount"]], textposition="outside",
                    hovertemplate="%{x}: GHS %{y:,.2f}<extra></extra>",
                ))
                fig_tt.update_layout(title="Volume by Transaction Type",
                                     yaxis_title="GHS", **T, height=320)
                st.plotly_chart(fig_tt, use_container_width=True)

    # ── TAB 5: Holdings ───────────────────────────────────────────────────────
    with tab5:
        shdr("📋 Equity Positions")
        pos_rows = []
        for e in sorted(eq, key=lambda x: x["market_value"], reverse=True):
            pos_rows.append({
                "Ticker":       e["ticker"],
                "Qty":          f"{e['qty']:,.0f}",
                "Avg Cost":     f"{e['avg_cost']:.4f}",
                "Stmt Price":   f"{e['statement_price']:.4f}",
                "Live Price":   f"{e['live_price']:.4f}" if e["live_price"] else "—",
                "Today Δ%":     f"{e['change_pct']:+.2f}%" if e.get("change_pct") is not None else "—",
                "Today ΔGHS":   f"{e['change_abs']:+.4f}" if e.get("change_abs") is not None else "—",
                "Cost Basis":   f"GHS {e['total_cost']:,.2f}",
                "Market Value": f"GHS {e['market_value']:,.2f}",
                "Gain/Loss":    f"{'+'if e['gain_loss']>=0 else ''}GHS {e['gain_loss']:,.2f}",
                "Return %":     f"{e['gain_pct']:+.1f}%",
                "Break-even":   "✅ In profit" if e["gain_pct"] >= 0 else f"Need GHS {e['avg_cost']:.4f}",
            })

        df_pos = pd.DataFrame(pos_rows)

        def _style(row):
            s = [""] * len(row)
            ig = list(row.index).index("Gain/Loss")
            ir = list(row.index).index("Return %")
            c  = f"color:{GREEN};font-weight:700" if "+" in row["Gain/Loss"] else f"color:{RED};font-weight:700"
            s[ig] = s[ir] = c
            return s

        st.dataframe(df_pos.style.apply(_style, axis=1),
                     use_container_width=True, hide_index=True)

        st.markdown("---")
        shdr("🕒 Transaction History")
        tx_df = pd.DataFrame(txs).sort_values("date", ascending=False)
        emoji = {"Buy":"🔵","Sell":"🟡","Credit":"🟢","Withdrawal":"🔴","Other":"⚪"}
        tx_df["Type"] = tx_df["type"].map(lambda t: f"{emoji.get(t,'⚪')} {t}")

        cf1, cf2 = st.columns([2, 3])
        with cf1:
            filt = st.multiselect("Filter", options=list(tx_df["Type"].unique()),
                                   default=list(tx_df["Type"].unique()),
                                   label_visibility="collapsed")
        with cf2:
            srch = st.text_input("Search", placeholder="Search description...",
                                 label_visibility="collapsed")

        view = tx_df[tx_df["Type"].isin(filt)]
        if srch:
            view = view[view["description"].str.contains(srch, case=False, na=False)]

        view_show = view[["date_str","Type","description","credit","debit"]].rename(columns={
            "date_str":"Date","description":"Description",
            "credit":"Credit (GHS)","debit":"Debit (GHS)"})
        view_show["Credit (GHS)"] = view_show["Credit (GHS)"].apply(lambda v: f"+{v:,.2f}" if v>0 else "—")
        view_show["Debit (GHS)"]  = view_show["Debit (GHS)"].apply( lambda v: f"-{v:,.2f}" if v>0 else "—")
        view_show["Description"]  = view_show["Description"].str[:100]
        st.dataframe(view_show, use_container_width=True, hide_index=True, height=400)

    # Footer (outside tabs)
    st.markdown(f"""
    <div style="text-align:center;color:{MUTED};font-size:.8rem;padding:24px 0 8px;">
      IC Portfolio Analyser · Prices via afx.kwayisi.org ·
      For informational purposes only · Past performance is not indicative of future results
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()