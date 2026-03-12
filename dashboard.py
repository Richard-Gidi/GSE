"""
IC Securities Portfolio Analyser — ULTRA EDITION (March 2026)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICE FETCHING (3-layer, no HTML scraping):
  1. GSE Live API    → dev.kwayisi.org/apis/gse/live          (all tickers, one call)
  2. Per-ticker API  → dev.kwayisi.org/apis/gse/equities/{tk} (fallback per stock)
  3. Manual override → user slider in the UI (always available)

New in this edition:
  • Zero HTML scraping — 100% JSON API, never breaks on site redesigns
  • Concurrent per-ticker fetches (ThreadPoolExecutor) for speed
  • Price-freshness badge with age indicator
  • Animated gradient progress bar for Health Score
  • Sector / industry tags from GSE equities endpoint
  • Dividend yield column from API data
  • P/E ratio column from API data
  • Sharpe-proxy metric on Overview
  • One-click share price sparkline popover (expandable)
  • Smarter rebalance engine (equal-weight target diff)
  • "Reset simulation" button
  • Footer shows data timestamp

Install:  pip install streamlit plotly pdfplumber pandas requests
Run:      streamlit run akwasi.py
"""

import base64, io, re, time, warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pdfplumber
import requests
import streamlit as st

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IC Portfolio Analyser",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
# DESIGN TOKENS
# ──────────────────────────────────────────────────────────────────────────────
T = SimpleNamespace(
    BG="#080b14", CARD="#0f1423", CARD2="#161d30",
    BORDER="#1e2640", BORDER2="#28305a",
    TEXT="#eaedf8", TEXT2="#b8bdd8", MUTED="#6b7594",
    SHADOW="rgba(0,0,0,0.55)",
)
PURPLE = "#7c6fff"; GREEN = "#00e5a0"; RED = "#ff3f6c"
AMBER  = "#ffb300"; BLUE  = "#0ea5e9"; TEAL  = "#00c9b1"
PINK   = "#f472b6"; INDIGO = "#818cf8"

_ACCENT_MAP = {
    "b": (BLUE,   PURPLE),
    "g": (GREEN,  TEAL),
    "r": (RED,    PINK),
    "y": (AMBER,  "#ff9800"),
    "t": (TEAL,   GREEN),
    "p": (PURPLE, INDIGO),
    "":  (PURPLE, TEAL),
}

def _plotly_base() -> dict:
    return dict(
        paper_bgcolor=T.BG, plot_bgcolor=T.CARD,
        font=dict(color=T.TEXT, family="Inter, Segoe UI, system-ui", size=12),
        xaxis=dict(gridcolor=T.BORDER, zerolinecolor=T.BORDER, tickcolor=T.MUTED,
                   tickfont=dict(color=T.MUTED)),
        yaxis=dict(gridcolor=T.BORDER, zerolinecolor=T.BORDER, tickcolor=T.MUTED,
                   tickfont=dict(color=T.MUTED)),
        margin=dict(l=16, r=16, t=48, b=16),
        legend=dict(bgcolor=T.CARD2, bordercolor=T.BORDER, borderwidth=1,
                    font=dict(color=T.TEXT)),
        hoverlabel=dict(bgcolor=T.CARD2, bordercolor=T.BORDER2,
                        font=dict(color=T.TEXT, family="Inter")),
    )

# ──────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ──────────────────────────────────────────────────────────────────────────────
def _inject_css():
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html,body,[class*="css"]{{font-family:'Inter','Segoe UI',system-ui,sans-serif;}}

/* ── APP SHELL ── */
.stApp,[data-testid="stAppViewContainer"]{{
    background:
      radial-gradient(ellipse 70% 50% at 10% 0%,{PURPLE}14 0%,transparent 60%),
      radial-gradient(ellipse 60% 40% at 90% 90%,{TEAL}10 0%,transparent 60%),
      {T.BG} !important;
    min-height:100vh;
}}
[data-testid="stHeader"],[data-testid="stToolbar"]{{background:transparent!important;backdrop-filter:blur(12px);}}
section[data-testid="stSidebar"]{{background:rgba(10,13,28,.97)!important;border-right:1px solid {T.BORDER}!important;}}
.block-container{{color:{T.TEXT};padding-top:1.5rem!important;max-width:1440px;}}

/* ── KPI CARDS ── */
.kpi{{
    position:relative;background:rgba(15,20,35,.85);backdrop-filter:blur(18px);
    border-radius:20px;padding:22px 22px 18px;border:1px solid {T.BORDER};
    margin-bottom:6px;transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s,border-color .22s;
    box-shadow:0 4px 24px {T.SHADOW};overflow:hidden;
}}
.kpi:hover{{transform:translateY(-5px) scale(1.01);box-shadow:0 14px 36px {T.SHADOW};border-color:{PURPLE}66;}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:20px 20px 0 0;}}
.kpi::after{{content:'';position:absolute;top:-80px;right:-80px;width:160px;height:160px;
             background:rgba(108,99,255,.04);border-radius:50%;pointer-events:none;}}
.kpi.b::before{{background:linear-gradient(90deg,{BLUE},{PURPLE});}}
.kpi.g::before{{background:linear-gradient(90deg,{GREEN},{TEAL});}}
.kpi.r::before{{background:linear-gradient(90deg,{RED},{PINK});}}
.kpi.y::before{{background:linear-gradient(90deg,{AMBER},#ff9800);}}
.kpi.t::before{{background:linear-gradient(90deg,{TEAL},{GREEN});}}
.kpi.p::before{{background:linear-gradient(90deg,{PURPLE},{INDIGO});}}
.kpi::before{{background:linear-gradient(90deg,{PURPLE},{TEAL});}}
.kpi-icon{{font-size:1.5rem;float:right;opacity:.18;line-height:1;margin-top:-2px;}}
.kpi-lbl{{font-size:.64rem;color:{T.MUTED};text-transform:uppercase;letter-spacing:.12em;margin-bottom:10px;font-weight:700;}}
.kpi-val{{font-size:1.55rem;font-weight:800;color:{T.TEXT};line-height:1.15;letter-spacing:-.025em;}}
.kpi-sub{{font-size:.73rem;color:{T.MUTED};margin-top:7px;line-height:1.45;}}
.kpi-badge{{display:inline-flex;align-items:center;gap:3px;font-size:.7rem;font-weight:700;
            padding:3px 10px;border-radius:20px;margin-top:8px;letter-spacing:.02em;}}
.kpi-badge.pos{{background:rgba(0,229,160,.13);color:{GREEN};border:1px solid rgba(0,229,160,.22);}}
.kpi-badge.neg{{background:rgba(255,63,108,.13);color:{RED};border:1px solid rgba(255,63,108,.22);}}
.kpi-badge.neu{{background:rgba(124,111,255,.13);color:{PURPLE};border:1px solid rgba(124,111,255,.22);}}

/* ── HEALTH BAR ── */
.health-wrap{{background:{T.CARD};border:1px solid {T.BORDER};border-radius:14px;
              padding:16px 20px;margin-bottom:6px;}}
.health-track{{background:{T.BORDER};border-radius:12px;height:10px;overflow:hidden;margin:8px 0;}}
.health-fill{{height:100%;border-radius:12px;transition:width .8s cubic-bezier(.4,0,.2,1);}}

/* ── INSIGHT BOXES ── */
.ibox{{background:rgba(15,20,35,.8);backdrop-filter:blur(12px);border:1px solid {T.BORDER};
       border-radius:16px;padding:18px 14px 16px;text-align:center;height:100%;
       transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s;
       box-shadow:0 2px 10px {T.SHADOW};position:relative;overflow:hidden;}}
.ibox::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;
              background:linear-gradient(90deg,transparent,{PURPLE}55,transparent);opacity:0;transition:opacity .2s;}}
.ibox:hover{{transform:translateY(-3px);box-shadow:0 8px 24px {T.SHADOW};}}
.ibox:hover::after{{opacity:1;}}
.ibox-icon{{font-size:2rem;line-height:1;}}
.ibox-lbl{{font-size:.63rem;color:{T.MUTED};text-transform:uppercase;letter-spacing:.1em;margin:10px 0 5px;font-weight:700;}}
.ibox-val{{font-size:.93rem;font-weight:700;color:{T.TEXT};letter-spacing:-.01em;}}

/* ── MOVER CARDS ── */
.mover{{background:rgba(15,20,35,.8);backdrop-filter:blur(12px);border:1px solid {T.BORDER};
        border-radius:18px;padding:18px 14px;text-align:center;
        box-shadow:0 2px 12px {T.SHADOW};transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s;}}
.mover:hover{{transform:translateY(-5px);box-shadow:0 12px 32px {T.SHADOW};border-color:{PURPLE}55;}}
.mover-tick{{font-size:.68rem;font-weight:800;color:{T.MUTED};text-transform:uppercase;letter-spacing:.1em;
             background:{T.CARD2};display:inline-block;padding:3px 12px;border-radius:10px;margin-bottom:8px;}}
.mover-price{{font-size:1.5rem;font-weight:800;color:{T.TEXT};margin:4px 0;letter-spacing:-.02em;}}
.mover-chg{{font-size:.85rem;font-weight:700;padding:4px 12px;border-radius:12px;display:inline-block;}}
.mover-chg.pos{{background:rgba(0,229,160,.14);color:{GREEN};}}
.mover-chg.neg{{background:rgba(255,63,108,.14);color:{RED};}}

/* ── SECTION HEADERS ── */
.shdr{{display:flex;align-items:center;gap:10px;font-size:1rem;font-weight:800;
       color:{T.TEXT};margin:20px 0 18px;letter-spacing:-.015em;}}
.shdr::before{{content:'';display:inline-block;width:4px;height:20px;
               background:linear-gradient(180deg,{PURPLE},{TEAL});border-radius:4px;flex-shrink:0;}}

/* ── CLIENT BAR ── */
.cbar{{background:rgba(15,20,35,.85);backdrop-filter:blur(18px);border:1px solid {T.BORDER};
       border-radius:20px;padding:18px 28px;display:flex;justify-content:space-between;
       align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:16px;
       box-shadow:0 4px 24px {T.SHADOW};position:relative;overflow:hidden;}}
.cbar::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;
               background:linear-gradient(90deg,{PURPLE},{TEAL},{GREEN});}}
.cbar-lbl{{font-size:.62rem;color:{T.MUTED};text-transform:uppercase;letter-spacing:.1em;font-weight:700;margin-bottom:4px;}}
.cbar-val{{font-size:1rem;font-weight:700;color:{T.TEXT};letter-spacing:-.01em;}}
.cbar-acc{{font-size:.95rem;font-weight:700;background:linear-gradient(135deg,{PURPLE},{TEAL});
           -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}

/* ── HERO ── */
.hero{{font-size:2.6rem;font-weight:900;line-height:1.05;letter-spacing:-.04em;
       background:linear-gradient(135deg,{PURPLE} 0%,{TEAL} 60%,{GREEN} 100%);
       -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.hero-sub{{color:{T.MUTED};font-size:.9rem;margin-top:6px;line-height:1.6;font-weight:400;}}
.hero-badge{{display:inline-block;background:rgba(124,111,255,.15);color:{PURPLE};
             border:1px solid rgba(124,111,255,.3);font-size:.68rem;font-weight:800;
             padding:3px 12px;border-radius:12px;letter-spacing:.07em;text-transform:uppercase;margin-bottom:8px;}}

/* ── PRICE BADGE ── */
.pill{{display:inline-flex;align-items:center;gap:4px;padding:3px 11px;border-radius:20px;
       font-size:.73rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;}}
.pill.live{{background:rgba(0,229,160,.13);color:{GREEN};border:1px solid rgba(0,229,160,.28);}}
.pill.partial{{background:rgba(255,179,0,.13);color:{AMBER};border:1px solid rgba(255,179,0,.28);}}
.pill.offline{{background:rgba(124,111,255,.13);color:{PURPLE};border:1px solid rgba(124,111,255,.28);}}

/* ── TABS ── */
[data-testid="stTabs"] [role="tablist"]{{background:rgba(15,20,35,.85)!important;
    backdrop-filter:blur(12px)!important;border-radius:16px!important;padding:5px!important;
    border:1px solid {T.BORDER}!important;gap:3px;box-shadow:0 2px 14px {T.SHADOW};}}
[data-testid="stTabs"] [role="tab"]{{border-radius:11px!important;color:{T.MUTED}!important;
    font-weight:600!important;font-size:.87rem!important;padding:9px 22px!important;
    transition:all .18s ease!important;border:none!important;}}
[data-testid="stTabs"] [role="tab"]:hover{{color:{T.TEXT}!important;background:{T.CARD2}!important;}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{{
    background:linear-gradient(135deg,{PURPLE},{INDIGO})!important;color:white!important;
    box-shadow:0 4px 14px rgba(124,111,255,.4)!important;}}

/* ── UPLOAD ZONE ── */
[data-testid="stFileUploadDropzone"]{{background:rgba(15,20,35,.7)!important;
    border:2px dashed {PURPLE}55!important;border-radius:20px!important;padding:44px!important;
    transition:all .2s!important;backdrop-filter:blur(12px);}}
[data-testid="stFileUploadDropzone"]:hover{{border-color:{PURPLE}cc!important;background:rgba(124,111,255,.06)!important;}}

/* ── DATAFRAME ── */
[data-testid="stDataFrame"]{{border-radius:14px!important;overflow:hidden;border:1px solid {T.BORDER}!important;}}
.js-plotly-plot{{border-radius:18px!important;overflow:hidden;border:1px solid {T.BORDER};}}
[data-testid="stExpander"]{{background:rgba(15,20,35,.75)!important;border:1px solid {T.BORDER}!important;border-radius:14px!important;}}

/* ── LANDING CARDS ── */
.land-card{{background:rgba(15,20,35,.8);backdrop-filter:blur(16px);border:1px solid {T.BORDER};
            border-radius:22px;padding:34px 22px;text-align:center;
            transition:transform .25s cubic-bezier(.34,1.56,.64,1),box-shadow .25s,border-color .25s;
            box-shadow:0 4px 22px {T.SHADOW};height:100%;position:relative;overflow:hidden;}}
.land-card:hover{{transform:translateY(-7px) scale(1.01);box-shadow:0 18px 44px {T.SHADOW};border-color:{PURPLE}55;}}
.land-icon{{font-size:2.8rem;margin-bottom:14px;display:block;}}
.land-title{{font-size:1.05rem;font-weight:800;color:{T.TEXT};margin-bottom:8px;}}
.land-desc{{font-size:.8rem;color:{T.MUTED};line-height:1.65;}}

/* ── MISC ── */
.pos{{color:{GREEN}!important;font-weight:700;}}
.neg{{color:{RED}!important;font-weight:700;}}
.rich-divider{{height:1px;background:linear-gradient(90deg,transparent,{PURPLE}44,{TEAL}44,transparent);border:none;margin:28px 0;}}
*::-webkit-scrollbar{{width:6px;height:6px;}}
*::-webkit-scrollbar-track{{background:{T.BG};}}
*::-webkit-scrollbar-thumb{{background:{T.BORDER2};border-radius:3px;}}
*::-webkit-scrollbar-thumb:hover{{background:{PURPLE};}}
::selection{{background:{PURPLE}44;color:{T.TEXT};}}
</style>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# UI COMPONENT HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", cls="", badge=None, icon=None):
    icons = {"b":"💼","g":"📈","r":"📉","y":"💰","t":"🌊","p":"🔮","":"📊"}
    ico = icon or icons.get(cls, "📊")
    badge_html = ""
    if badge is not None:
        dc = "pos" if badge >= 0 else "neg"
        arrow = "▲" if badge >= 0 else "▼"
        badge_html = f"<div class='kpi-badge {dc}'>{arrow} {abs(badge):.2f}%</div>"
    sub_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    return (f"<div class='kpi {cls}'>"
            f"<span class='kpi-icon'>{ico}</span>"
            f"<div class='kpi-lbl'>{label}</div>"
            f"<div class='kpi-val'>{value}</div>"
            f"{sub_html}{badge_html}</div>")

def insight(icon, label, value, cls=""):
    return (f"<div class='ibox'>"
            f"<div class='ibox-icon'>{icon}</div>"
            f"<div class='ibox-lbl'>{label}</div>"
            f"<div class='ibox-val {cls}'>{value}</div></div>")

def mover_card(ticker, price, chg_pct, chg_abs):
    cls = "pos" if chg_pct >= 0 else "neg"
    arrow = "▲" if chg_pct >= 0 else "▼"
    return (f"<div class='mover'>"
            f"<div class='mover-tick'>{ticker}</div>"
            f"<div class='mover-price'>GHS&nbsp;{price:.4f}</div>"
            f"<div class='mover-chg {cls}'>{arrow} {abs(chg_pct):.2f}%</div>"
            f"<div style='font-size:.73rem;color:{T.MUTED};margin-top:6px;'>"
            f"Δ&nbsp;{chg_abs:+.4f} GHS</div></div>")

def shdr(text, sub=None):
    sub_part = (f"<span style='font-size:.77rem;font-weight:400;opacity:.55;margin-left:8px;'>"
                f"{sub}</span>") if sub else ""
    st.markdown(f"<div class='shdr'>{text}{sub_part}</div>", unsafe_allow_html=True)

def health_bar(score: int):
    """Animated gradient health bar."""
    if score >= 75:
        fill_grad = f"linear-gradient(90deg,{GREEN},{TEAL})"
        label_color = GREEN
        rating = "Excellent"
    elif score >= 55:
        fill_grad = f"linear-gradient(90deg,{TEAL},{AMBER})"
        label_color = AMBER
        rating = "Good"
    elif score >= 35:
        fill_grad = f"linear-gradient(90deg,{AMBER},{RED})"
        label_color = AMBER
        rating = "Fair"
    else:
        fill_grad = f"linear-gradient(90deg,{RED},{PINK})"
        label_color = RED
        rating = "Needs Attention"
    st.markdown(
        f"<div class='health-wrap'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<div style='font-size:.68rem;color:{T.MUTED};font-weight:700;text-transform:uppercase;letter-spacing:.1em;'>Portfolio Health Score</div>"
        f"<div style='font-size:.78rem;font-weight:800;color:{label_color};'>{rating}</div></div>"
        f"<div class='health-track'>"
        f"<div class='health-fill' style='width:{score}%;background:{fill_grad};'></div></div>"
        f"<div style='display:flex;justify-content:space-between;'>"
        f"<div style='font-size:1.8rem;font-weight:900;color:{label_color};letter-spacing:-.03em;'>{score}<span style='font-size:1rem;font-weight:600;opacity:.6;'>/100</span></div>"
        f"<div style='font-size:.72rem;color:{T.MUTED};text-align:right;line-height:1.5;'>"
        f"ROI weight 35%<br>Win Rate 25%<br>Diversification 20%<br>Concentration 20%</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

def pn(v):
    return "pos" if v >= 0 else "neg"

# ──────────────────────────────────────────────────────────────────────────────
# STRING / NUMBER UTILITIES
# ──────────────────────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())

def _float(val) -> float | None:
    try:
        f = float(re.sub(r"[^\d.\-]", "", str(val).replace(",", "")))
        return f if f == f else None
    except Exception:
        return None

def tx_type(desc: str) -> str:
    if re.search(r"\bBought\b", desc, re.I): return "Buy"
    if re.search(r"\bSold\b", desc, re.I):   return "Sell"
    if re.search(r"Contribution|Funding",    desc, re.I): return "Credit"
    if re.search(r"Withdrawal|Transfer.*Payout", desc, re.I): return "Withdrawal"
    return "Other"

# ──────────────────────────────────────────────────────────────────────────────
# ██████╗ ██████╗ ██╗ ██████╗███████╗    ███████╗███████╗████████╗ ██████╗██╗  ██╗
# ██╔══██╗██╔══██╗██║██╔════╝██╔════╝    ██╔════╝██╔════╝╚══██╔══╝██╔════╝██║  ██║
# ██████╔╝██████╔╝██║██║     █████╗      █████╗  █████╗     ██║   ██║     ███████║
# ██╔═══╝ ██╔══██╗██║██║     ██╔══╝      ██╔══╝  ██╔══╝     ██║   ██║     ██╔══██║
# ██║     ██║  ██║██║╚██████╗███████╗    ██║     ███████╗   ██║   ╚██████╗██║  ██║
# ╚═╝     ╚═╝  ╚═╝╚═╝ ╚═════╝╚══════╝   ╚═╝     ╚══════╝   ╚═╝    ╚═════╝╚═╝  ╚═╝
#
#  THREE-LAYER PRICE SYSTEM — NO HTML SCRAPING
#  Layer 1: Bulk live endpoint  (one request for all tickers)
#  Layer 2: Per-ticker equity   (concurrent fallback)
#  Layer 3: Manual user override (UI)
# ──────────────────────────────────────────────────────────────────────────────

GSE_LIVE_URL     = "https://dev.kwayisi.org/apis/gse/live"
GSE_EQUITY_URL   = "https://dev.kwayisi.org/apis/gse/equities/{ticker}"
_HEADERS = {"User-Agent": "Mozilla/5.0 IC-Portfolio-Analyser/3.0", "Accept": "application/json"}

def _parse_equity_item(item: dict, orig_ticker: str) -> dict | None:
    """Parse one equity record from GSE API (works for both /live and /equities/{tk})."""
    price = _float(item.get("price") or item.get("closingPrice") or item.get("last"))
    if not price or price <= 0:
        return None
    change_abs = _float(item.get("change") or item.get("priceChange") or 0) or 0.0
    prev = price - change_abs
    change_pct = round((change_abs / prev * 100) if prev else 0.0, 4)
    # Extra fundamental data the API sometimes returns
    pe    = _float(item.get("pe")  or item.get("peRatio"))
    div_y = _float(item.get("dividendYield") or item.get("yield"))
    sector = (item.get("sector") or item.get("industry") or "").strip()
    return {
        "price":      price,
        "change_abs": change_abs,
        "change_pct": change_pct,
        "pe":         pe,
        "div_yield":  div_y,
        "sector":     sector or "N/A",
    }

@st.cache_data(ttl=180, show_spinner=False)   # 3-minute cache
def _bulk_fetch(tickers: tuple) -> tuple[dict, str, float]:
    """
    Returns (prices_dict, source_label, fetch_timestamp).
    prices_dict = { ticker: { price, change_abs, change_pct, pe, div_yield, sector } }
    """
    norm_map = {_norm(t): t for t in tickers}
    wanted   = set(norm_map)
    results  = {}
    source   = "statement"
    ts       = time.time()

    # ── LAYER 1: bulk live endpoint ──────────────────────────────────────────
    try:
        r = requests.get(GSE_LIVE_URL, headers=_HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            # The API returns a list of objects
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("data") or data.get("equities") or data.get("stocks") or list(data.values())
            else:
                items = []
            for item in items:
                sym = _norm(item.get("name") or item.get("ticker") or item.get("symbol") or "")
                if sym not in wanted:
                    continue
                parsed = _parse_equity_item(item, norm_map[sym])
                if parsed:
                    results[norm_map[sym]] = parsed
    except Exception:
        pass

    still_needed = wanted - {_norm(k) for k in results}

    # ── LAYER 2: per-ticker concurrent fallback ───────────────────────────────
    if still_needed:
        def _fetch_one(ticker_norm: str):
            orig = norm_map[ticker_norm]
            for variant in [orig, ticker_norm, ticker_norm.lower()]:
                try:
                    url = GSE_EQUITY_URL.format(ticker=variant)
                    r = requests.get(url, headers=_HEADERS, timeout=8)
                    if r.status_code == 200:
                        payload = r.json()
                        # payload can be the object itself or wrapped
                        item = payload if isinstance(payload, dict) else {}
                        if "data" in item:
                            item = item["data"]
                        parsed = _parse_equity_item(item, orig)
                        if parsed:
                            return orig, parsed
                except Exception:
                    continue
            return orig, None

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_fetch_one, sym): sym for sym in still_needed}
            for future in as_completed(futures):
                orig, parsed = future.result()
                if parsed:
                    results[orig] = parsed

    if results:
        source = "live" if len(results) == len(tickers) else "partial"

    return results, source, ts


def get_live_prices(tickers: tuple) -> tuple[dict, str, float]:
    """Public entry-point. Returns (prices, source, timestamp)."""
    return _bulk_fetch(tickers)


def inject_live_prices(equities: list, live: dict) -> list:
    out = []
    for e in equities:
        e = e.copy()
        if e["ticker"] in live:
            lv = live[e["ticker"]]
            lp = lv["price"]
            mv = e["qty"] * lp
            gl = mv - e["total_cost"]
            e.update({
                "live_price":  lp,
                "market_value": mv,
                "gain_loss":   gl,
                "gain_pct":    (gl / e["total_cost"] * 100) if e["total_cost"] else 0,
                "change_pct":  lv["change_pct"],
                "change_abs":  lv["change_abs"],
                "pe":          lv.get("pe"),
                "div_yield":   lv.get("div_yield"),
                "sector":      lv.get("sector", "N/A"),
            })
        else:
            e["live_price"] = e["change_pct"] = e["change_abs"] = None
            e["pe"] = e["div_yield"] = None
            e["sector"] = "N/A"
        out.append(e)
    return out

# ──────────────────────────────────────────────────────────────────────────────
# PDF PARSER
# ──────────────────────────────────────────────────────────────────────────────
def parse_pdf(pdf_bytes: bytes) -> dict:
    equities, transactions, portfolio_summary, funds_data = [], [], {}, {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = full_text.split("\n")

    # Portfolio summary table
    for i, line in enumerate(lines):
        if "Total Value" in line and "Allocation" in line:
            for l in lines[i + 1:i + 10]:
                m = re.match(r"(Funds|Fixed Income|Equities|Cash)\s+([\d,\.]+)\s+([\d\.]+)", l.strip())
                if m:
                    portfolio_summary[m.group(1)] = {
                        "value": float(m.group(2).replace(",", "")),
                        "alloc": float(m.group(3)),
                    }
                m2 = re.match(r"([\d,\.]+)\s+100\.00", l.strip())
                if m2:
                    portfolio_summary["Total"] = float(m2.group(1).replace(",", ""))

    # IC Liquidity fund
    m = re.search(r"IC Liquidity\s+([\d,\.]+)\s+-([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)", full_text)
    if m:
        funds_data = {
            "name": "IC Liquidity",
            "invested": float(m.group(1).replace(",", "")),
            "redeemed": float(m.group(2).replace(",", "")),
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
                desc   = rest[:rest.rfind(nums[-2])].strip()
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

# ──────────────────────────────────────────────────────────────────────────────
# CHARTS
# ──────────────────────────────────────────────────────────────────────────────
def chart_gain_loss(eq):
    df = pd.DataFrame(eq).sort_values("gain_pct")
    colors = [GREEN if v >= 0 else RED for v in df["gain_pct"]]
    fig = go.Figure(go.Bar(
        x=df["gain_pct"], y=df["ticker"], orientation="h",
        marker=dict(color=colors, line=dict(width=0),
                    opacity=[1.0 if v >= 0 else 0.85 for v in df["gain_pct"]]),
        text=[f"{v:+.1f}%" for v in df["gain_pct"]], textposition="outside",
        textfont=dict(color=T.TEXT2, size=11),
        hovertemplate="<b>%{y}</b><br>Return: %{x:.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=T.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="Return per Stock (%)", xaxis_title="Return (%)",
                      **_plotly_base(), height=380)
    return fig

def chart_pl_waterfall(eq):
    df = pd.DataFrame(eq).sort_values("gain_loss")
    total = df["gain_loss"].sum()
    tickers = df["ticker"].tolist() + ["TOTAL"]
    vals    = df["gain_loss"].tolist() + [total]
    colors  = [GREEN if v >= 0 else RED for v in vals]
    colors[-1] = TEAL if total >= 0 else RED
    fig = go.Figure(go.Bar(
        x=tickers, y=vals,
        marker=dict(color=colors, line=dict(width=0),
                    opacity=[0.82]*len(df) + [1.0]),
        text=[f"{'+'if v>=0 else ''}GHS {v:,.0f}" for v in vals], textposition="outside",
        textfont=dict(color=T.TEXT2, size=11),
        hovertemplate="<b>%{x}</b><br>P&L: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=T.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="P&L Contribution per Stock (GHS)", yaxis_title="GHS",
                      **_plotly_base(), height=340)
    return fig

def chart_market_vs_cost(eq):
    df = pd.DataFrame(eq).sort_values("market_value", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Cost Basis", x=df["ticker"], y=df["total_cost"],
                         marker_color=BLUE, opacity=0.75,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Cost</extra>"))
    fig.add_trace(go.Bar(name="Market Value", x=df["ticker"], y=df["market_value"],
                         marker_color=PURPLE, opacity=0.9,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Market</extra>"))
    for _, row in df.iterrows():
        gl = row["gain_pct"]
        fig.add_annotation(
            x=row["ticker"], y=max(row["total_cost"], row["market_value"]),
            text=f"{gl:+.1f}%", showarrow=False, yshift=12,
            font=dict(color=GREEN if gl >= 0 else RED, size=10, family="Inter"),
        )
    fig.update_layout(title="Market Value vs Cost Basis", yaxis_title="GHS",
                      barmode="group", **_plotly_base(), height=380)
    return fig

def chart_allocation_treemap(ps):
    cmap = {"Equities": PURPLE, "Cash": BLUE, "Funds": AMBER, "Fixed Income": TEAL}
    labels, parents, values, colors = [], [], [], []
    for k, v in ps.items():
        if k == "Total" or v["value"] == 0:
            continue
        labels.append(k); parents.append(""); values.append(v["value"])
        colors.append(cmap.get(k, T.MUTED))
    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        marker=dict(colors=colors, line=dict(width=3, color=T.BG)),
        texttemplate="<b>%{label}</b><br>GHS %{value:,.0f}<br>%{percentRoot:.1%}",
        textfont=dict(size=13, family="Inter"),
        hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f}<br>%{percentRoot:.1%}<extra></extra>",
    ))
    layout = {**_plotly_base(), "title": "Portfolio Allocation", "height": 300,
              "margin": dict(l=8, r=8, t=48, b=8)}
    fig.update_layout(**layout)
    return fig

def chart_stock_weight_bar(eq):
    df = pd.DataFrame(eq).sort_values("market_value")
    total = df["market_value"].sum()
    df["weight"] = df["market_value"] / total * 100
    fig = go.Figure(go.Bar(
        x=df["weight"], y=df["ticker"], orientation="h",
        marker=dict(
            color=df["weight"],
            colorscale=[[0, BLUE], [0.4, PURPLE], [1, TEAL]],
            line=dict(width=0),
        ),
        text=[f"{w:.1f}%" for w in df["weight"]], textposition="outside",
        textfont=dict(color=T.TEXT2, size=11),
        customdata=df["market_value"],
        hovertemplate="<b>%{y}</b><br>Weight: %{x:.2f}%<br>GHS %{customdata:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Portfolio Weight by Stock", xaxis_title="Weight (%)",
                      **_plotly_base(), height=340, showlegend=False)
    return fig

def chart_price_comparison(eq):
    df = pd.DataFrame(eq)
    df = df[df["live_price"].notna()].copy()
    if df.empty:
        return None
    df["pct_diff"] = (df["live_price"] - df["statement_price"]) / df["statement_price"] * 100
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Statement Price", x=df["ticker"], y=df["statement_price"],
                         marker_color=AMBER, opacity=0.85,
                         hovertemplate="%{x}<br>Statement: GHS %{y:.4f}<extra></extra>"))
    fig.add_trace(go.Bar(name="Live Price", x=df["ticker"], y=df["live_price"],
                         marker_color=GREEN, opacity=0.9,
                         hovertemplate="%{x}<br>Live: GHS %{y:.4f}<extra></extra>"))
    for _, row in df.iterrows():
        color = GREEN if row["pct_diff"] >= 0 else RED
        fig.add_annotation(x=row["ticker"], y=max(row["statement_price"], row["live_price"]),
                           text=f"{row['pct_diff']:+.1f}%", showarrow=False, yshift=12,
                           font=dict(color=color, size=10))
    fig.update_layout(title="Statement vs Live Price",
                      yaxis_title="GHS per Share", barmode="group", **_plotly_base(), height=320)
    return fig

def chart_cashflow(txs):
    df = pd.DataFrame(txs)
    if df.empty:
        return None
    df["month"] = df["date"].dt.to_period("M")
    m = df.groupby("month").agg(credits=("credit","sum"), debits=("debit","sum")).reset_index()
    m["month_str"] = m["month"].astype(str)
    m["net"] = m["credits"] - m["debits"]
    m["cumnet"] = m["net"].cumsum()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35],
                        vertical_spacing=0.06,
                        subplot_titles=["Monthly Credits & Debits", "Cumulative Net Flow"])
    fig.add_trace(go.Bar(name="Credits", x=m["month_str"], y=m["credits"],
                         marker_color=GREEN, opacity=0.85), row=1, col=1)
    fig.add_trace(go.Bar(name="Debits", x=m["month_str"], y=m["debits"],
                         marker_color=RED, opacity=0.85), row=1, col=1)
    fig.add_trace(go.Scatter(name="Net", x=m["month_str"], y=m["net"],
                             mode="lines+markers", line=dict(color=AMBER, width=2.5),
                             marker=dict(size=6)), row=1, col=1)
    fig.add_trace(go.Bar(name="Cumulative", x=m["month_str"], y=m["cumnet"],
                         marker_color=[GREEN if v >= 0 else RED for v in m["cumnet"]],
                         opacity=0.75, showlegend=False), row=2, col=1)
    layout = {**_plotly_base(), "barmode": "group", "height": 500,
              "xaxis2": dict(tickangle=-30, gridcolor=T.BORDER),
              "yaxis": dict(title="GHS", gridcolor=T.BORDER),
              "yaxis2": dict(title="GHS", gridcolor=T.BORDER)}
    fig.update_layout(**layout)
    return fig

def chart_cumulative(txs, total_value):
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"] = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    profit = total_value - df["cumul"].iloc[-1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        fill="tozeroy", fillcolor=f"rgba(124,111,255,.10)",
        line=dict(color=PURPLE, width=2.5), name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>Invested: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=total_value, line_color=TEAL, line_dash="dash", line_width=2,
                  annotation_text=f" Portfolio Value GHS {total_value:,.0f}",
                  annotation_font=dict(color=TEAL, size=11))
    fig.update_layout(
        title=f"Net Invested vs Portfolio Value  ({'+'if profit>=0 else ''}GHS {profit:,.0f} unrealised)",
        xaxis_title="Date", yaxis_title="GHS", **_plotly_base(), height=340)
    return fig

def chart_breakeven(eq):
    losers = [e for e in eq if e["gain_pct"] < 0]
    if not losers:
        return None
    df = pd.DataFrame(losers)
    price_col = df["live_price"].fillna(df["statement_price"])
    pct_need  = (df["avg_cost"] - price_col) / price_col * 100
    gap_ghs   = (df["avg_cost"] - price_col) * df["qty"]
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Price Gap to Break-even", "GHS Loss to Recover"],
                        specs=[[{"type":"xy"}, {"type":"xy"}]])
    fig.add_trace(go.Bar(name="Current", x=df["ticker"], y=price_col,
                         marker_color=RED, opacity=0.85), row=1, col=1)
    fig.add_trace(go.Bar(name="Break-even", x=df["ticker"], y=df["avg_cost"],
                         marker_color=AMBER, opacity=0.85), row=1, col=1)
    fig.add_trace(go.Scatter(
        name="% Needed", x=df["ticker"], y=pct_need, mode="markers+text", yaxis="y2",
        marker=dict(size=14, color=AMBER, symbol="diamond", line=dict(color=T.BG, width=2)),
        text=[f"+{v:.1f}%" for v in pct_need], textposition="top center",
        textfont=dict(color=AMBER, size=10),
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name="GHS to Recover", x=df["ticker"], y=gap_ghs.abs(),
        marker=dict(color=gap_ghs.abs(), colorscale=[[0, AMBER],[1, RED]], line=dict(width=0)),
        text=[f"GHS {v:,.0f}" for v in gap_ghs.abs()], textposition="outside",
    ), row=1, col=2)
    layout = {**_plotly_base(), "title": "Break-even Analysis — Losing Positions",
              "barmode": "group", "height": 380,
              "yaxis": dict(title="Price (GHS)", gridcolor=T.BORDER),
              "yaxis2": dict(title="% Rally Needed", overlaying="y", side="right",
                             showgrid=False, color=AMBER),
              "yaxis3": dict(title="GHS to Recover", gridcolor=T.BORDER),
              "xaxis2": dict(gridcolor=T.BORDER)}
    fig.update_layout(**layout)
    return fig

def chart_concentration(eq):
    df  = pd.DataFrame(eq)
    tot = df["market_value"].sum()
    w   = df["market_value"] / tot
    hhi = round((w ** 2).sum() * 10000)
    if hhi < 1500:   risk, rc = "Low",      GREEN
    elif hhi < 2500: risk, rc = "Moderate", AMBER
    else:            risk, rc = "High",     RED
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["HHI Concentration Score", "Exposure by Stock"],
                        specs=[[{"type":"indicator"}, {"type":"xy"}]])
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=hhi,
        delta=dict(reference=1500, valueformat=".0f",
                   increasing=dict(color=RED), decreasing=dict(color=GREEN)),
        number=dict(font=dict(color=rc, size=36, family="Inter"), suffix=" HHI"),
        gauge=dict(
            axis=dict(range=[0, 10000], tickcolor=T.MUTED, tickfont=dict(color=T.MUTED, size=9)),
            bar=dict(color=rc, thickness=0.3),
            bgcolor=T.CARD2, bordercolor=T.BORDER,
            steps=[
                dict(range=[0, 1500],    color="rgba(0,229,160,.10)"),
                dict(range=[1500, 2500], color="rgba(255,179,0,.10)"),
                dict(range=[2500,10000], color="rgba(255,63,108,.10)"),
            ],
            threshold=dict(line=dict(color=rc, width=3), thickness=0.8, value=hhi),
        ),
        title=dict(text=f"<b>{risk}</b> Concentration", font=dict(color=rc, size=14)),
    ), row=1, col=1)
    df_s = df.sort_values("market_value", ascending=True)
    ws   = (df_s["market_value"] / tot * 100).values
    fig.add_trace(go.Bar(
        x=ws, y=df_s["ticker"].values, orientation="h",
        marker=dict(color=ws, colorscale=[[0,GREEN],[0.4,AMBER],[1,RED]], line=dict(width=0)),
        text=[f"{v:.1f}%" for v in ws], textposition="outside",
        textfont=dict(color=T.TEXT2, size=11), showlegend=False,
        hovertemplate="<b>%{y}</b>: %{x:.1f}%<extra></extra>",
    ), row=1, col=2)
    layout = {
        "paper_bgcolor": T.BG, "plot_bgcolor": T.CARD,
        "font": dict(color=T.TEXT, family="Inter"),
        "margin": dict(l=16, r=16, t=60, b=16), "height": 380,
        "xaxis2": dict(gridcolor=T.BORDER, title="Weight (%)", tickcolor=T.MUTED),
        "yaxis2": dict(gridcolor=T.BORDER, tickcolor=T.MUTED),
        "hoverlabel": dict(bgcolor=T.CARD2, bordercolor=T.BORDER, font=dict(color=T.TEXT)),
        "legend": dict(bgcolor=T.CARD2, bordercolor=T.BORDER),
    }
    fig.update_layout(**layout)
    return fig, hhi, risk, rc

def chart_sector_donut(eq):
    """Donut chart of holdings by sector tag (from API or 'N/A')."""
    from collections import defaultdict
    buckets = defaultdict(float)
    for e in eq:
        buckets[e.get("sector", "N/A")] += e["market_value"]
    labels = list(buckets.keys())
    values = list(buckets.values())
    palette = [PURPLE, TEAL, GREEN, AMBER, BLUE, RED, PINK, INDIGO]
    colors  = [palette[i % len(palette)] for i in range(len(labels))]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=colors, line=dict(color=T.BG, width=3)),
        texttemplate="%{label}<br><b>%{percent}</b>",
        textfont=dict(size=11, family="Inter"),
        hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f} (%{percent})<extra></extra>",
    ))
    fig.update_layout(title="Holdings by Sector", **_plotly_base(), height=300,
                      margin=dict(l=16, r=16, t=48, b=16))
    return fig

def chart_rolling_return(txs, eq, total_value):
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    df["proxy_value"] = (df["cumul"] * (total_value / df["cumul"].iloc[-1])
                         if df["cumul"].iloc[-1] else df["cumul"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["proxy_value"], mode="lines",
        fill="tozeroy", fillcolor="rgba(0,201,177,.09)",
        line=dict(color=TEAL, width=2.5), name="Est. Portfolio Value",
        hovertemplate="%{x|%b %d, %Y}<br>Est: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        line=dict(color=PURPLE, width=1.5, dash="dot"), name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>Invested: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Estimated Portfolio Value Over Time",
                      xaxis_title="Date", yaxis_title="GHS", **_plotly_base(), height=320)
    return fig

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(
            f"<div style='font-size:.7rem;color:{T.MUTED};font-weight:700;"
            f"text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px;'>"
            f"📡 GSE PRICE ENGINE</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:.78rem;color:{T.TEXT2};line-height:1.65;'>"
            f"<b style='color:{GREEN}'>Layer 1</b> — Bulk live API<br>"
            f"<b style='color:{AMBER}'>Layer 2</b> — Per-ticker API (concurrent)<br>"
            f"<b style='color:{PURPLE}'>Layer 3</b> — Manual override<br>"
            f"<span style='color:{T.MUTED}'>No HTML scraping — never breaks.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.divider()
        if st.button("🔄 Refresh Live Prices", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        st.markdown(
            f"<div style='font-size:.72rem;color:{T.MUTED};line-height:1.7;'>"
            f"IC Portfolio Analyser · Ultra Edition<br>"
            f"Data via dev.kwayisi.org/apis/gse<br>"
            f"For informational purposes only.</div>",
            unsafe_allow_html=True,
        )

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    _inject_css()
    render_sidebar()

    # ── HERO ──────────────────────────────────────────────────────────────────
    cl, ct, cr = st.columns([1, 7, 2])
    with cl:
        st.markdown(
            f"<div style='font-size:3.2rem;padding-top:4px;line-height:1;"
            f"filter:drop-shadow(0 0 24px {PURPLE}88);'>📈</div>",
            unsafe_allow_html=True)
    with ct:
        st.markdown(
            f"<div class='hero-badge'>IC Securities · Ghana Stock Exchange</div>"
            f"<div class='hero'>IC Portfolio Analyser</div>"
            f"<div class='hero-sub'>"
            f"Upload your statement PDF · Live GSE prices via 3-layer JSON API · "
            f"Health score, rebalancing & scenario simulator"
            f"</div>",
            unsafe_allow_html=True)

    # ── UPLOAD ────────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "**📄 Drop your IC Securities Account Statement (PDF)**", type=["pdf"])

    if not uploaded:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        features = [
            ("📊", "Overview & KPIs",
             "Portfolio value, ROI, unrealised gains, Health Score gauge & 8 KPI cards."),
            ("📈", "Performance",
             "Returns per stock, P&L waterfall, market vs cost, live vs statement price."),
            ("⚖️", "Risk & Scenarios",
             "Break-even analysis, HHI gauge, smart rebalance, what-if simulator."),
            ("💸", "Cash Flow & Holdings",
             "Monthly flow charts, cumulative chart, full transaction log + CSV export."),
        ]
        for col, (icon, title, desc) in zip([c1, c2, c3, c4], features):
            with col:
                st.markdown(
                    f"<div class='land-card'><span class='land-icon'>{icon}</span>"
                    f"<div class='land-title'>{title}</div>"
                    f"<div class='land-desc'>{desc}</div></div>",
                    unsafe_allow_html=True)
        st.stop()

    # ── PARSE PDF ─────────────────────────────────────────────────────────────
    with st.spinner("📄 Parsing statement…"):
        data = parse_pdf(uploaded.read())

    eq  = data["equities"]
    txs = data["transactions"]
    ps  = data["portfolio_summary"]

    if not eq:
        st.error("Could not parse equity data — please check the PDF format.")
        st.stop()

    # ── LIVE PRICES ───────────────────────────────────────────────────────────
    tickers = tuple(e["ticker"] for e in eq)
    with st.spinner("📡 Fetching live prices…"):
        live, price_source, price_ts = get_live_prices(tickers)

    eq = inject_live_prices(eq, live)
    n_live = sum(1 for e in eq if e["live_price"] is not None)

    age_sec  = time.time() - price_ts
    age_str  = f"{int(age_sec//60)}m {int(age_sec%60)}s ago"

    if price_source == "live":
        st.success(f"📡 All {n_live} prices live from GSE-API · refreshed {age_str}")
    elif price_source == "partial":
        st.warning(f"📡 {n_live}/{len(eq)} prices live · {len(eq)-n_live} using statement price · {age_str}")
    else:
        st.info("📋 Showing statement prices (GSE-API unavailable) — use manual override below")

    # ── MANUAL OVERRIDE ───────────────────────────────────────────────────────
    with st.expander("✏️ Override prices manually", expanded=False):
        cols = st.columns(min(5, len(eq)))
        overrides = {}
        for i, e in enumerate(eq):
            default = float(e["live_price"] or e["statement_price"])
            val = cols[i % 5].number_input(
                e["ticker"], min_value=0.0, value=default,
                step=0.0001, format="%.4f", key=f"ov_{e['ticker']}")
            if val > 0:
                overrides[e["ticker"]] = val
        if st.button("✅ Apply overrides", type="primary"):
            st.cache_data.clear()
            fake_live = {t: {"price": p2, "change_pct": 0, "change_abs": 0,
                             "pe": None, "div_yield": None, "sector": "N/A"}
                         for t, p2 in overrides.items()}
            eq = inject_live_prices(eq, fake_live)
            n_live = len(eq)
            st.success("Manual prices applied.")

    # ── COMPUTED METRICS ──────────────────────────────────────────────────────
    equities_val  = sum(e["market_value"] for e in eq)
    total_cost    = sum(e["total_cost"]    for e in eq)
    total_gain    = sum(e["gain_loss"]     for e in eq)
    gain_pct      = (total_gain / total_cost * 100) if total_cost else 0
    cash_val      = ps.get("Cash", {}).get("value", 0)
    funds_val     = ps.get("Funds", {}).get("value", 0)
    total_value   = equities_val + cash_val + funds_val
    total_credits = sum(t["credit"] for t in txs)
    total_debits  = sum(t["debit"]  for t in txs)
    net_invested  = total_credits - total_debits
    overall_roi   = ((total_value - net_invested) / net_invested * 100) if net_invested else 0
    winners       = sum(1 for e in eq if e["gain_pct"] >= 0)
    best    = max(eq, key=lambda e: e["gain_pct"])
    worst   = min(eq, key=lambda e: e["gain_pct"])
    biggest = max(eq, key=lambda e: e["market_value"])

    # Diversification: positions contributing > 5%
    portfolio_div = (len([e for e in eq if e["market_value"] / equities_val > 0.05])
                     if equities_val else 0)

    # HHI + Health Score
    if equities_val > 0:
        weights   = [e["market_value"] / equities_val for e in eq]
        hhi       = round(sum(w**2 for w in weights) * 10000)
        div_score = (portfolio_div / len(eq) * 100) if eq else 0
        win_score = (winners / len(eq) * 100) if eq else 0
        roi_score = min(100, max(0, overall_roi + 30))
        health_score = round(
            0.35 * roi_score +
            0.25 * win_score +
            0.20 * div_score +
            0.20 * max(0, 100 - hhi / 100)
        )
        health_score = max(0, min(100, health_score))
    else:
        hhi = 0; health_score = 50

    # Sharpe proxy: mean daily gain / std (approximation)
    gain_pcts = [e["gain_pct"] for e in eq]
    if len(gain_pcts) > 1:
        import statistics
        sharpe_proxy = (sum(gain_pcts) / len(gain_pcts)) / (statistics.stdev(gain_pcts) + 1e-9)
        sharpe_proxy = round(sharpe_proxy, 2)
    else:
        sharpe_proxy = 0.0

    active_month = "N/A"
    if txs:
        tdf = pd.DataFrame(txs)
        tdf["month"] = tdf["date"].dt.to_period("M")
        active_month = str(tdf["month"].value_counts().idxmax())

    # ── CLIENT BAR ────────────────────────────────────────────────────────────
    pill_cls = "live" if n_live == len(eq) else "partial" if n_live else "offline"
    pill_txt = ("✦ All Live" if n_live == len(eq)
                else f"{n_live}/{len(eq)} Live" if n_live else "Statement Prices")
    roi_col = GREEN if overall_roi >= 0 else RED
    gl_col  = GREEN if total_gain  >= 0 else RED
    win_rate_str = f"{winners/len(eq)*100:.0f}%" if eq else "—"

    st.markdown(f"""
    <div class='cbar'>
      <div><div class='cbar-lbl'>Client</div>
           <div class='cbar-val'>{data['client_name']}</div></div>
      <div><div class='cbar-lbl'>Account</div>
           <div class='cbar-acc'>{data['account_number']}</div></div>
      <div><div class='cbar-lbl'>Statement Date</div>
           <div class='cbar-val'>{data['report_date']}</div></div>
      <div><div class='cbar-lbl'>Portfolio Value</div>
           <div class='cbar-val'>GHS {total_value:,.2f}</div></div>
      <div><div class='cbar-lbl'>Overall Return</div>
           <div class='cbar-val' style='color:{roi_col}'>{overall_roi:+.2f}%</div></div>
      <div><div class='cbar-lbl'>Unrealised G/L</div>
           <div class='cbar-val' style='color:{gl_col}'>
             {'+'if total_gain>=0 else ''}GHS {total_gain:,.2f}</div></div>
      <div><div class='cbar-lbl'>Win Rate</div>
           <div class='cbar-val'>{winners}/{len(eq)} ({win_rate_str})</div></div>
      <div><div class='cbar-lbl'>Prices</div>
           <div class='cbar-val'>
             <span class='pill {pill_cls}'>{pill_txt}</span></div></div>
    </div>""", unsafe_allow_html=True)

    # ── TABS ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview",
        "📈 Performance",
        "⚖️ Risk & Scenarios",
        "💸 Cash Flow",
        "📋 Holdings",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — OVERVIEW
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        shdr("Portfolio Summary")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(kpi("Total Portfolio Value",
                            f"GHS {total_value:,.2f}",
                            f"As of {data['report_date']}", "b"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi("Unrealised Gain / Loss",
                            f"<span class='{pn(total_gain)}'>{'+'if total_gain>=0 else ''}GHS {total_gain:,.2f}</span>",
                            f"on GHS {total_cost:,.2f} cost basis",
                            "g" if total_gain >= 0 else "r", badge=gain_pct),
                        unsafe_allow_html=True)
        with c3:
            st.markdown(kpi("Overall ROI",
                            f"<span class='{pn(overall_roi)}'>{overall_roi:+.2f}%</span>",
                            f"Net invested GHS {net_invested:,.2f}",
                            "g" if overall_roi >= 0 else "r"), unsafe_allow_html=True)
        with c4:
            st.markdown(kpi("Sharpe Proxy",
                            f"<span style='color:{'"+GREEN+"' if sharpe_proxy>0 else '"+RED+"'}'>{sharpe_proxy:+.2f}</span>",
                            "Mean return ÷ std dev across holdings", "p"),
                        unsafe_allow_html=True)

        st.markdown("")
        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.markdown(kpi("Cash Balance",
                            f"GHS {cash_val:,.2f}",
                            f"{ps.get('Cash',{}).get('alloc',0):.1f}% of portfolio", "y"),
                        unsafe_allow_html=True)
        with c6:
            st.markdown(kpi("Total Contributions",
                            f"GHS {total_credits:,.2f}",
                            f"{len(txs)} total transactions", "b"), unsafe_allow_html=True)
        with c7:
            st.markdown(kpi("Total Withdrawals",
                            f"GHS {total_debits:,.2f}",
                            f"Net GHS {net_invested:,.2f}", "r"), unsafe_allow_html=True)
        with c8:
            st.markdown(kpi("Winning Positions",
                            f"{winners} / {len(eq)}",
                            f"{winners/len(eq)*100:.0f}% win rate",
                            "g" if winners >= len(eq)//2 else "r"), unsafe_allow_html=True)

        # Health score bar
        st.markdown("---")
        health_bar(health_score)

        # Quick insights
        st.markdown("---")
        shdr("Quick Insights")
        i1, i2, i3, i4, i5, i6 = st.columns(6)
        with i1: st.markdown(insight("🏆","Best Performer",
                                     f"{best['ticker']} {best['gain_pct']:+.1f}%","pos"), unsafe_allow_html=True)
        with i2: st.markdown(insight("📉","Worst Performer",
                                     f"{worst['ticker']} {worst['gain_pct']:+.1f}%","neg"), unsafe_allow_html=True)
        with i3: st.markdown(insight("💎","Largest Position",
                                     f"{biggest['ticker']}<br>GHS {biggest['market_value']:,.0f}"), unsafe_allow_html=True)
        with i4: st.markdown(insight("⚡","Most Active Month", active_month), unsafe_allow_html=True)
        with i5: st.markdown(insight("📊","Diversified Stocks",
                                     f"{portfolio_div} of {len(eq)} >5%"), unsafe_allow_html=True)
        with i6: st.markdown(insight("📡","Live Prices",
                                     f"{n_live}/{len(eq)} fetched",
                                     "pos" if n_live == len(eq) else ""), unsafe_allow_html=True)

        # Today's movers
        movers = sorted([e for e in eq if e.get("change_pct") is not None],
                        key=lambda e: abs(e["change_pct"] or 0), reverse=True)
        if movers:
            st.markdown("---")
            shdr("🚀 Today's Movers")
            mcols = st.columns(min(len(movers), 5))
            for col, e in zip(mcols, movers[:5]):
                with col:
                    st.markdown(mover_card(
                        e["ticker"],
                        e["live_price"] or e["statement_price"],
                        e["change_pct"] or 0,
                        e["change_abs"] or 0,
                    ), unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — PERFORMANCE
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        shdr("Performance Analysis")
        cl, cr = st.columns([3, 2])
        with cl: st.plotly_chart(chart_gain_loss(eq), use_container_width=True)
        with cr: st.plotly_chart(chart_stock_weight_bar(eq), use_container_width=True)

        cl, cr = st.columns([3, 2])
        with cl: st.plotly_chart(chart_market_vs_cost(eq), use_container_width=True)
        with cr: st.plotly_chart(chart_allocation_treemap(ps), use_container_width=True)

        st.plotly_chart(chart_pl_waterfall(eq), use_container_width=True)

        # Sector donut
        cl, cr = st.columns([2, 3])
        with cl: st.plotly_chart(chart_sector_donut(eq), use_container_width=True)
        with cr:
            pc = chart_price_comparison(eq)
            if pc:
                st.plotly_chart(pc, use_container_width=True)
            else:
                st.markdown(
                    f"<div style='text-align:center;color:{T.MUTED};padding:60px 24px;'>"
                    f"Price comparison unavailable — no live prices loaded.</div>",
                    unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — RISK & SCENARIOS
    # ══════════════════════════════════════════════════════════════════════════
    with tab3:
        be = chart_breakeven(eq)
        if be:
            shdr("🎯 Break-even Analysis")
            st.plotly_chart(be, use_container_width=True)
        else:
            st.success("🎉 All positions are currently profitable — no break-even analysis needed.")

        st.markdown("---")
        shdr("⚖️ Concentration Risk (HHI)")
        conc_fig, hhi_val, risk, rc = chart_concentration(eq)
        st.plotly_chart(conc_fig, use_container_width=True)
        st.markdown(
            f"<div style='text-align:center;color:{T.MUTED};font-size:.83rem;margin-top:-8px;'>"
            f"Herfindahl-Hirschman Index: <b style='color:{rc}'>{hhi_val}</b> — "
            f"<b style='color:{rc}'>{risk}</b> concentration &nbsp;·&nbsp;"
            f"<span style='color:{GREEN}'>Low &lt;1500</span> · "
            f"<span style='color:{AMBER}'>Moderate 1500–2500</span> · "
            f"<span style='color:{RED}'>High &gt;2500</span>"
            f"</div>", unsafe_allow_html=True)

        # Smart rebalance
        st.markdown("---")
        shdr("🛠️ Smart Rebalance Engine")
        if hhi_val > 2500:
            st.warning("⚠️ High concentration detected — rebalancing recommended")
            equal_target = 100.0 / len(eq)
            rebal_rows = []
            for e in sorted(eq, key=lambda x: x["market_value"] / equities_val, reverse=True):
                current_wt = e["market_value"] / equities_val * 100
                diff = current_wt - equal_target
                rebal_rows.append({
                    "Ticker":      e["ticker"],
                    "Current Wt": f"{current_wt:.1f}%",
                    "Target Wt":  f"{equal_target:.1f}%",
                    "Action":     (f"📉 Trim {abs(diff):.1f}pp" if diff > 3
                                   else f"📈 Add {abs(diff):.1f}pp" if diff < -3
                                   else "✅ On target"),
                    "Diff (GHS)": f"{'+'if diff<0 else '-'} GHS {abs(diff/100*equities_val):,.0f}",
                })
            st.dataframe(pd.DataFrame(rebal_rows), use_container_width=True, hide_index=True)
        elif hhi_val > 1500:
            st.warning(f"⚠️ Moderate concentration (HHI {hhi_val}) — monitor large positions")
        else:
            st.success(f"✅ Well diversified (HHI {hhi_val}) — no immediate rebalancing needed")

        # What-if simulator
        st.markdown("---")
        shdr("🔮 What-If Scenario Simulator")
        st.caption("Drag sliders to simulate price moves on individual stocks")

        if st.button("↺ Reset all to 0%", key="reset_sim"):
            for e in eq:
                st.session_state[f"sim_{e['ticker']}"] = 0

        rows_of_5 = [eq[i:i+5] for i in range(0, len(eq), 5)]
        sim_mult  = {}
        for row in rows_of_5:
            scols = st.columns(len(row))
            for col, e in zip(scols, row):
                chg = col.slider(e["ticker"], min_value=-50, max_value=150, value=0,
                                 step=1, format="%d%%", key=f"sim_{e['ticker']}")
                sim_mult[e["ticker"]] = 1 + chg / 100

        sim_mv    = sum(e["market_value"] * sim_mult.get(e["ticker"], 1) for e in eq)
        sim_total = sim_mv + cash_val + funds_val
        sim_gain  = sum((e["market_value"] * sim_mult.get(e["ticker"],1)) - e["total_cost"] for e in eq)
        sim_delta = sim_total - total_value
        sim_roi   = ((sim_total - net_invested) / net_invested * 100) if net_invested else 0
        gain_chg  = sim_gain - total_gain

        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.markdown(kpi("Simulated Total",
                            f"GHS {sim_total:,.2f}",
                            f"{'+'if sim_delta>=0 else ''}GHS {sim_delta:,.2f} vs now",
                            "g" if sim_delta >= 0 else "r"), unsafe_allow_html=True)
        with sc2:
            st.markdown(kpi("Simulated Equity G/L",
                            f"<span class='{pn(sim_gain)}'>{'+'if sim_gain>=0 else ''}GHS {sim_gain:,.2f}</span>",
                            f"{(sim_gain/total_cost*100):+.2f}% on cost",
                            "g" if sim_gain >= 0 else "r"), unsafe_allow_html=True)
        with sc3:
            st.markdown(kpi("Simulated ROI",
                            f"<span class='{pn(sim_roi)}'>{sim_roi:+.2f}%</span>",
                            f"Current: {overall_roi:+.2f}%",
                            "g" if sim_roi >= 0 else "r"), unsafe_allow_html=True)
        with sc4:
            st.markdown(kpi("G/L Change",
                            f"<span class='{pn(gain_chg)}'>{'+'if gain_chg>=0 else ''}GHS {gain_chg:,.2f}</span>",
                            "vs current unrealised", "g" if gain_chg >= 0 else "r"),
                        unsafe_allow_html=True)

        sim_df = pd.DataFrame([{
            "ticker":    e["ticker"],
            "current":   e["market_value"],
            "simulated": e["market_value"] * sim_mult.get(e["ticker"], 1),
        } for e in eq]).sort_values("simulated", ascending=False)
        fig_sim = go.Figure()
        fig_sim.add_trace(go.Bar(name="Current", x=sim_df["ticker"], y=sim_df["current"],
                                 marker_color=PURPLE, opacity=0.7))
        fig_sim.add_trace(go.Bar(name="Simulated", x=sim_df["ticker"], y=sim_df["simulated"],
                                 marker=dict(
                                     color=[GREEN if s > c else RED
                                            for s, c in zip(sim_df["simulated"], sim_df["current"])],
                                     opacity=0.9)))
        fig_sim.update_layout(title="Current vs Simulated Market Value",
                              yaxis_title="GHS", barmode="group", **_plotly_base(), height=320)
        st.plotly_chart(fig_sim, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — CASH FLOW
    # ══════════════════════════════════════════════════════════════════════════
    with tab4:
        shdr("Cash Flow & History")
        cf = chart_cashflow(txs)
        if cf:
            st.plotly_chart(cf, use_container_width=True)

        cl, cr = st.columns([3, 2])
        with cl:
            cumul = chart_rolling_return(txs, eq, total_value)
            if cumul:
                st.plotly_chart(cumul, use_container_width=True)
        with cr:
            tx_df2 = pd.DataFrame(txs)
            if not tx_df2.empty:
                tx_df2["amount"] = tx_df2["credit"] + tx_df2["debit"]
                grp = tx_df2.groupby("type")["amount"].sum().reset_index().sort_values("amount", ascending=False)
                cmap_t = {"Buy": BLUE, "Sell": AMBER, "Credit": GREEN, "Withdrawal": RED, "Other": T.MUTED}
                fig_tt = go.Figure(go.Bar(
                    x=grp["type"], y=grp["amount"],
                    marker_color=[cmap_t.get(t, T.MUTED) for t in grp["type"]],
                    text=[f"GHS {v:,.0f}" for v in grp["amount"]], textposition="outside",
                ))
                fig_tt.update_layout(title="Volume by Transaction Type",
                                     yaxis_title="GHS", **_plotly_base(), height=320)
                st.plotly_chart(fig_tt, use_container_width=True)

        # Flow averages
        tx_df3 = pd.DataFrame(txs)
        if not tx_df3.empty:
            tx_df3["month"]    = tx_df3["date"].dt.to_period("M")
            n_months           = tx_df3["month"].nunique()
            avg_credit_monthly = total_credits / n_months if n_months else 0
            avg_debit_monthly  = total_debits  / n_months if n_months else 0
            st.markdown("---")
            shdr("Flow Averages")
            fa1, fa2, fa3, fa4 = st.columns(4)
            with fa1: st.markdown(kpi("Months Active", str(n_months),
                                      f"{len(txs)} transactions total","b"), unsafe_allow_html=True)
            with fa2: st.markdown(kpi("Avg Monthly Credit",
                                      f"GHS {avg_credit_monthly:,.2f}","per active month","g"),
                                  unsafe_allow_html=True)
            with fa3: st.markdown(kpi("Avg Monthly Debit",
                                      f"GHS {avg_debit_monthly:,.2f}","per active month","r"),
                                  unsafe_allow_html=True)
            with fa4: st.markdown(kpi("Net Flow",
                                      f"GHS {net_invested:,.2f}","total net invested","t"),
                                  unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — HOLDINGS
    # ══════════════════════════════════════════════════════════════════════════
    with tab5:
        shdr("Equity Positions")
        pos_rows = []
        for e in sorted(eq, key=lambda x: x["market_value"], reverse=True):
            wt = e["market_value"] / equities_val * 100 if equities_val else 0
            pos_rows.append({
                "Ticker":      e["ticker"],
                "Sector":      e.get("sector", "N/A"),
                "Qty":         f"{e['qty']:,.0f}",
                "Avg Cost":    f"{e['avg_cost']:.4f}",
                "Stmt Price":  f"{e['statement_price']:.4f}",
                "Live Price":  f"{e['live_price']:.4f}" if e["live_price"] else "—",
                "Today Δ%":   f"{e['change_pct']:+.2f}%" if e.get("change_pct") is not None else "—",
                "P/E":         f"{e['pe']:.1f}x"        if e.get("pe") else "—",
                "Div Yield":   f"{e['div_yield']:.2f}%"  if e.get("div_yield") else "—",
                "Weight":      f"{wt:.1f}%",
                "Cost Basis":  f"GHS {e['total_cost']:,.2f}",
                "Mkt Value":   f"GHS {e['market_value']:,.2f}",
                "Gain/Loss":   f"{'+'if e['gain_loss']>=0 else ''}GHS {e['gain_loss']:,.2f}",
                "Return %":    f"{e['gain_pct']:+.1f}%",
                "Status":      "✅ Profit" if e["gain_pct"] >= 0 else f"🔴 Loss",
            })
        df_pos = pd.DataFrame(pos_rows)

        def _style_row(row):
            s = [""] * len(row)
            for col in ["Gain/Loss", "Return %"]:
                if col in row.index:
                    idx = list(row.index).index(col)
                    s[idx] = (f"color:{GREEN};font-weight:700"
                              if "+" in str(row[col]) else f"color:{RED};font-weight:700")
            return s

        st.dataframe(df_pos.style.apply(_style_row, axis=1),
                     use_container_width=True, hide_index=True)

        # CSV exports
        st.markdown("---")
        dl1, dl2 = st.columns(2)
        with dl1:
            csv_hold = df_pos.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Holdings CSV", csv_hold,
                f"IC_holdings_{data['account_number']}_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv", use_container_width=True)
        with dl2:
            tx_export = pd.DataFrame(txs)
            if not tx_export.empty:
                csv_tx = tx_export.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Transaction Log CSV", csv_tx,
                    f"IC_transactions_{data['account_number']}_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv", use_container_width=True)

        # Transaction history
        st.markdown("---")
        shdr("Transaction History")
        tx_df = pd.DataFrame(txs).sort_values("date", ascending=False)
        emoji = {"Buy":"🔵","Sell":"🟡","Credit":"🟢","Withdrawal":"🔴","Other":"⚪"}
        tx_df["Type"] = tx_df["type"].map(lambda t: f"{emoji.get(t,'⚪')} {t}")

        cf1, cf2, cf3 = st.columns([2, 2, 3])
        with cf1:
            filt = st.multiselect("Type", options=list(tx_df["Type"].unique()),
                                  default=list(tx_df["Type"].unique()),
                                  label_visibility="collapsed")
        with cf2:
            date_range = st.date_input(
                "Range",
                value=(tx_df["date"].min().date() if not tx_df.empty else datetime.now().date(),
                       tx_df["date"].max().date() if not tx_df.empty else datetime.now().date()),
                label_visibility="collapsed")
        with cf3:
            srch = st.text_input("Search", placeholder="🔍 Search description…",
                                 label_visibility="collapsed")

        view = tx_df[tx_df["Type"].isin(filt)]
        if len(date_range) == 2:
            s, e2 = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
            view = view[(view["date"] >= s) & (view["date"] <= e2)]
        if srch:
            view = view[view["description"].str.contains(srch, case=False, na=False)]

        view_show = view[["date_str","Type","description","credit","debit"]].rename(columns={
            "date_str":"Date","description":"Description",
            "credit":"Credit (GHS)","debit":"Debit (GHS)"})
        view_show["Credit (GHS)"] = view_show["Credit (GHS)"].apply(
            lambda v: f"+{v:,.2f}" if v > 0 else "—")
        view_show["Debit (GHS)"] = view_show["Debit (GHS)"].apply(
            lambda v: f"-{v:,.2f}" if v > 0 else "—")
        view_show["Description"] = view_show["Description"].str[:100]
        st.caption(f"Showing {len(view_show):,} of {len(tx_df):,} transactions")
        st.dataframe(view_show, use_container_width=True, hide_index=True, height=440)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
    ts_display = datetime.fromtimestamp(price_ts).strftime("%H:%M:%S") if price_ts else "—"
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                flex-wrap:wrap;gap:12px;padding:6px 4px 20px;
                font-size:.76rem;color:{T.MUTED};">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:1.1rem;">📈</span>
        <span><b style='color:{PURPLE}'>IC Portfolio Analyser</b> · Ultra Edition · 
              Built for IC Securities Ghana</span>
      </div>
      <div style="display:flex;gap:18px;align-items:center;">
        <span>Prices via
          <a href='https://dev.kwayisi.org/apis/gse/' target='_blank'
             style='color:{PURPLE};text-decoration:none;font-weight:700;'>
             dev.kwayisi.org/apis/gse
          </a>
        </span>
        <span style="color:{T.BORDER2};">|</span>
        <span>Last fetch: {ts_display}</span>
        <span style="color:{T.BORDER2};">|</span>
        <span>For informational purposes only</span>
      </div>
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()