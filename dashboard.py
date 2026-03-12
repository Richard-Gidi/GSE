"""
IC Securities Portfolio Analyser
Install:  pip install streamlit plotly pdfplumber pandas requests beautifulsoup4 lxml
Run:      streamlit run akwasi.py
"""

import base64, io, re, warnings
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pdfplumber
import streamlit as st

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IC Portfolio Analyser",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# THEME SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
_DARK = SimpleNamespace(
    BG="#0d0f18", CARD="#161929", CARD2="#1e2235",
    BORDER="#252840", BORDER2="#2e3355",
    TEXT="#e8eaf6", TEXT2="#c5c9e0", MUTED="#8892b0",
    SHADOW="rgba(0,0,0,0.4)",
    name="dark",
)
_LIGHT = SimpleNamespace(
    BG="#f0f2fa", CARD="#ffffff", CARD2="#f7f8fd",
    BORDER="#dde1f2", BORDER2="#c8cde8",
    TEXT="#1a1d2e", TEXT2="#3d4166", MUTED="#6b7280",
    SHADOW="rgba(100,110,180,0.12)",
    name="light",
)

# Accent colours — same in both themes
PURPLE = "#6c63ff"
GREEN  = "#00d68f"
RED    = "#ff3d71"
AMBER  = "#ffaa00"
BLUE   = "#0095ff"
TEAL   = "#00c9b1"


def th() -> SimpleNamespace:
    """Return current theme palette."""
    return _DARK if st.session_state.get("theme", "dark") == "dark" else _LIGHT


def T() -> dict:
    """Plotly layout base — resolved from current theme."""
    p = th()
    return dict(
        paper_bgcolor=p.BG, plot_bgcolor=p.CARD,
        font=dict(color=p.TEXT, family="Segoe UI, system-ui", size=12),
        xaxis=dict(gridcolor=p.BORDER, zerolinecolor=p.BORDER, tickcolor=p.MUTED),
        yaxis=dict(gridcolor=p.BORDER, zerolinecolor=p.BORDER, tickcolor=p.MUTED),
        margin=dict(l=16, r=16, t=48, b=16),
        legend=dict(bgcolor=p.CARD2, bordercolor=p.BORDER, borderwidth=1,
                    font=dict(color=p.TEXT)),
        hoverlabel=dict(bgcolor=p.CARD2, bordercolor=p.BORDER,
                        font=dict(color=p.TEXT, family="Segoe UI")),
    )


def apply_theme():
    """Inject CSS for current theme. Call once per render inside main()."""
    p = th()
    is_dark = p.name == "dark"

    # Background grid pattern for dark mode only
    bg_pattern = (
        f"radial-gradient(ellipse at 20% 10%, {PURPLE}18 0%, transparent 50%),"
        f"radial-gradient(ellipse at 80% 80%, {TEAL}12 0%, transparent 50%),"
        f"{p.BG}"
    ) if is_dark else p.BG

    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ══════════════════════════════════════════════
   BASE
══════════════════════════════════════════════ */
html, body, [class*="css"] {{
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
}}
.stApp, [data-testid="stAppViewContainer"] {{
    background: {bg_pattern} !important;
    min-height: 100vh;
}}
[data-testid="stHeader"], [data-testid="stToolbar"] {{
    background: transparent !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}}
section[data-testid="stSidebar"] {{
    background: {'rgba(22,25,41,0.97)' if is_dark else 'rgba(255,255,255,0.97)'} !important;
    border-right: 1px solid {p.BORDER} !important;
    backdrop-filter: blur(20px);
}}
.block-container {{
    color: {p.TEXT};
    padding-top: 2rem !important;
    max-width: 1400px;
}}
hr {{
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, {p.BORDER}, transparent) !important;
    margin: 24px 0 !important;
}}

/* ══════════════════════════════════════════════
   KPI CARDS  — glass + gradient top-border
══════════════════════════════════════════════ */
.kpi {{
    position: relative;
    background: {'rgba(22,25,41,0.8)' if is_dark else 'rgba(255,255,255,0.9)'};
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-radius: 18px;
    padding: 22px 24px 18px;
    border: 1px solid {p.BORDER};
    margin-bottom: 6px;
    transition: transform .22s cubic-bezier(.34,1.56,.64,1), box-shadow .22s ease;
    box-shadow: 0 4px 20px {p.SHADOW};
    overflow: hidden;
}}
.kpi::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, {PURPLE}, {TEAL});
    border-radius: 18px 18px 0 0;
}}
.kpi.g::before {{ background: linear-gradient(90deg, {GREEN}, {TEAL}); }}
.kpi.r::before {{ background: linear-gradient(90deg, {RED}, {AMBER}); }}
.kpi.y::before {{ background: linear-gradient(90deg, {AMBER}, #ff9500); }}
.kpi.b::before {{ background: linear-gradient(90deg, {BLUE}, {PURPLE}); }}
.kpi.t::before {{ background: linear-gradient(90deg, {TEAL}, {GREEN}); }}
.kpi::after {{
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 140px; height: 140px;
    background: {'rgba(108,99,255,0.04)' if is_dark else 'rgba(108,99,255,0.03)'};
    border-radius: 50%;
    pointer-events: none;
}}
.kpi:hover {{
    transform: translateY(-4px) scale(1.01);
    box-shadow: 0 12px 32px {p.SHADOW};
    border-color: {PURPLE}55;
}}
.kpi-icon {{
    font-size: 1.6rem;
    float: right;
    margin-top: -2px;
    opacity: 0.2;
    line-height: 1;
}}
.kpi-lbl {{
    font-size: .68rem;
    color: {p.MUTED};
    text-transform: uppercase;
    letter-spacing: .1em;
    margin-bottom: 10px;
    font-weight: 600;
}}
.kpi-val {{
    font-size: 1.6rem;
    font-weight: 800;
    color: {p.TEXT};
    line-height: 1.15;
    letter-spacing: -.02em;
}}
.kpi-sub {{
    font-size: .76rem;
    color: {p.MUTED};
    margin-top: 8px;
    line-height: 1.4;
}}
.kpi-delta {{
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: .72rem;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 20px;
    margin-top: 8px;
    letter-spacing: .02em;
}}
.kpi-delta.pos {{
    background: {'rgba(0,214,143,0.15)' if is_dark else 'rgba(0,214,143,0.12)'};
    color: {GREEN};
    border: 1px solid {'rgba(0,214,143,0.25)' if is_dark else 'rgba(0,214,143,0.2)'};
}}
.kpi-delta.neg {{
    background: {'rgba(255,61,113,0.15)' if is_dark else 'rgba(255,61,113,0.12)'};
    color: {RED};
    border: 1px solid {'rgba(255,61,113,0.25)' if is_dark else 'rgba(255,61,113,0.2)'};
}}

/* ══════════════════════════════════════════════
   INSIGHT BOXES
══════════════════════════════════════════════ */
.ibox {{
    background: {'rgba(22,25,41,0.7)' if is_dark else 'rgba(255,255,255,0.85)'};
    backdrop-filter: blur(12px);
    border: 1px solid {p.BORDER};
    border-radius: 16px;
    padding: 18px 14px 16px;
    text-align: center;
    height: 100%;
    transition: transform .22s cubic-bezier(.34,1.56,.64,1), box-shadow .22s;
    box-shadow: 0 2px 10px {p.SHADOW};
    position: relative;
    overflow: hidden;
}}
.ibox::after {{
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, {PURPLE}55, transparent);
    opacity: 0;
    transition: opacity .2s;
}}
.ibox:hover {{ transform: translateY(-3px); box-shadow: 0 8px 24px {p.SHADOW}; }}
.ibox:hover::after {{ opacity: 1; }}
.ibox-icon {{
    font-size: 2rem;
    line-height: 1;
    filter: drop-shadow(0 2px 4px {p.SHADOW});
}}
.ibox-lbl {{
    font-size: .65rem;
    color: {p.MUTED};
    text-transform: uppercase;
    letter-spacing: .09em;
    margin: 10px 0 5px;
    font-weight: 600;
}}
.ibox-val  {{
    font-size: .95rem;
    font-weight: 700;
    color: {p.TEXT};
    letter-spacing: -.01em;
}}

/* ══════════════════════════════════════════════
   MOVER CARDS
══════════════════════════════════════════════ */
.mover {{
    background: {'rgba(22,25,41,0.75)' if is_dark else 'rgba(255,255,255,0.9)'};
    backdrop-filter: blur(12px);
    border: 1px solid {p.BORDER};
    border-radius: 16px;
    padding: 16px 14px;
    text-align: center;
    box-shadow: 0 2px 10px {p.SHADOW};
    transition: transform .22s cubic-bezier(.34,1.56,.64,1), box-shadow .22s;
    position: relative;
    overflow: hidden;
}}
.mover:hover {{
    transform: translateY(-4px);
    box-shadow: 0 10px 28px {p.SHADOW};
    border-color: {PURPLE}55;
}}
.mover-tick {{
    font-size: .7rem;
    font-weight: 700;
    color: {p.MUTED};
    text-transform: uppercase;
    letter-spacing: .08em;
    background: {p.CARD2};
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    margin-bottom: 8px;
}}
.mover-price {{
    font-size: 1.5rem;
    font-weight: 800;
    color: {p.TEXT};
    margin: 4px 0;
    letter-spacing: -.02em;
}}
.mover-chg   {{
    font-size: .85rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
    display: inline-block;
}}
.mover-chg.pos {{
    background: {'rgba(0,214,143,0.15)' if is_dark else 'rgba(0,214,143,0.1)'};
    color: {GREEN};
}}
.mover-chg.neg {{
    background: {'rgba(255,61,113,0.15)' if is_dark else 'rgba(255,61,113,0.1)'};
    color: {RED};
}}

/* ══════════════════════════════════════════════
   SECTION HEADERS
══════════════════════════════════════════════ */
.shdr {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1rem;
    font-weight: 700;
    color: {p.TEXT};
    margin: 20px 0 18px;
    letter-spacing: -.01em;
}}
.shdr::before {{
    content: '';
    display: inline-block;
    width: 4px;
    height: 20px;
    background: linear-gradient(180deg, {PURPLE}, {TEAL});
    border-radius: 4px;
    flex-shrink: 0;
}}

/* ══════════════════════════════════════════════
   CLIENT BAR
══════════════════════════════════════════════ */
.cbar {{
    background: {'rgba(22,25,41,0.8)' if is_dark else 'rgba(255,255,255,0.9)'};
    backdrop-filter: blur(16px);
    border: 1px solid {p.BORDER};
    border-radius: 18px;
    padding: 18px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;
    box-shadow: 0 4px 20px {p.SHADOW};
    position: relative;
    overflow: hidden;
}}
.cbar::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, {PURPLE}, {TEAL}, {GREEN});
}}
.cbar-item {{
    display: flex;
    flex-direction: column;
    gap: 4px;
}}
.cbar-lbl  {{
    font-size: .65rem;
    color: {p.MUTED};
    text-transform: uppercase;
    letter-spacing: .1em;
    font-weight: 600;
}}
.cbar-val  {{
    font-size: 1rem;
    font-weight: 700;
    color: {p.TEXT};
    letter-spacing: -.01em;
}}
.cbar-acc  {{
    font-size: .95rem;
    font-weight: 700;
    background: linear-gradient(135deg, {PURPLE}, {TEAL});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}

/* ══════════════════════════════════════════════
   HERO SECTION
══════════════════════════════════════════════ */
.hero-wrap {{
    padding: 8px 0 4px;
}}
.hero {{
    font-size: 2.6rem;
    font-weight: 900;
    line-height: 1.05;
    letter-spacing: -.04em;
    background: linear-gradient(135deg, {PURPLE} 0%, {TEAL} 60%, {GREEN} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}
.hero-sub {{
    color: {p.MUTED};
    font-size: .95rem;
    margin-top: 8px;
    line-height: 1.6;
    font-weight: 400;
}}
.hero-badge {{
    display: inline-block;
    background: {'rgba(108,99,255,0.15)' if is_dark else 'rgba(108,99,255,0.1)'};
    color: {PURPLE};
    border: 1px solid {'rgba(108,99,255,0.3)' if is_dark else 'rgba(108,99,255,0.25)'};
    font-size: .7rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
    letter-spacing: .06em;
    text-transform: uppercase;
    margin-bottom: 10px;
}}

/* ══════════════════════════════════════════════
   TABS
══════════════════════════════════════════════ */
[data-testid="stTabs"] [role="tablist"] {{
    background: {'rgba(22,25,41,0.8)' if is_dark else 'rgba(255,255,255,0.9)'} !important;
    backdrop-filter: blur(12px) !important;
    border-radius: 14px !important;
    padding: 5px !important;
    border: 1px solid {p.BORDER} !important;
    gap: 3px;
    box-shadow: 0 2px 12px {p.SHADOW};
}}
[data-testid="stTabs"] [role="tab"] {{
    border-radius: 10px !important;
    color: {p.MUTED} !important;
    font-weight: 600 !important;
    font-size: .88rem !important;
    padding: 9px 20px !important;
    transition: all .18s ease !important;
    border: none !important;
    letter-spacing: .01em;
}}
[data-testid="stTabs"] [role="tab"]:hover {{
    color: {p.TEXT} !important;
    background: {p.CARD2} !important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    background: linear-gradient(135deg, {PURPLE}, #5a52e8) !important;
    color: white !important;
    box-shadow: 0 4px 12px {'rgba(108,99,255,0.4)' if is_dark else 'rgba(108,99,255,0.25)'} !important;
}}

/* ══════════════════════════════════════════════
   UPLOAD ZONE
══════════════════════════════════════════════ */
[data-testid="stFileUploadDropzone"] {{
    background: {'rgba(22,25,41,0.7)' if is_dark else 'rgba(255,255,255,0.8)'} !important;
    border: 2px dashed {PURPLE}55 !important;
    border-radius: 18px !important;
    padding: 40px !important;
    transition: all .2s !important;
    backdrop-filter: blur(12px);
}}
[data-testid="stFileUploadDropzone"]:hover {{
    border-color: {PURPLE}bb !important;
    background: {'rgba(108,99,255,0.05)' if is_dark else 'rgba(108,99,255,0.03)'} !important;
}}

/* ══════════════════════════════════════════════
   DATAFRAMES
══════════════════════════════════════════════ */
[data-testid="stDataFrame"] {{
    border-radius: 14px !important;
    overflow: hidden;
    border: 1px solid {p.BORDER} !important;
    box-shadow: 0 2px 12px {p.SHADOW};
}}

/* ══════════════════════════════════════════════
   PLOTLY CHARTS
══════════════════════════════════════════════ */
.js-plotly-plot {{
    border-radius: 16px !important;
    overflow: hidden;
    border: 1px solid {p.BORDER};
    box-shadow: 0 2px 16px {p.SHADOW};
}}

/* ══════════════════════════════════════════════
   EXPANDER
══════════════════════════════════════════════ */
[data-testid="stExpander"] {{
    background: {'rgba(22,25,41,0.7)' if is_dark else 'rgba(255,255,255,0.8)'} !important;
    border: 1px solid {p.BORDER} !important;
    border-radius: 14px !important;
    backdrop-filter: blur(12px);
}}
[data-testid="stExpander"] summary {{
    font-weight: 600 !important;
    color: {p.TEXT} !important;
}}

/* ══════════════════════════════════════════════
   PILLS & BADGES
══════════════════════════════════════════════ */
.pill {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: .75rem;
    font-weight: 700;
    letter-spacing: .04em;
    text-transform: uppercase;
}}
.pill.live   {{
    background: {'rgba(0,214,143,0.15)' if is_dark else 'rgba(0,214,143,0.1)'};
    color: {GREEN};
    border: 1px solid {'rgba(0,214,143,0.3)' if is_dark else 'rgba(0,214,143,0.25)'};
}}
.pill.warn   {{
    background: {'rgba(255,170,0,0.15)' if is_dark else 'rgba(255,170,0,0.1)'};
    color: {AMBER};
    border: 1px solid {'rgba(255,170,0,0.3)' if is_dark else 'rgba(255,170,0,0.25)'};
}}
.pill.info   {{
    background: {'rgba(0,149,255,0.15)' if is_dark else 'rgba(0,149,255,0.1)'};
    color: {BLUE};
    border: 1px solid {'rgba(0,149,255,0.3)' if is_dark else 'rgba(0,149,255,0.25)'};
}}

/* ══════════════════════════════════════════════
   LANDING PAGE CARDS
══════════════════════════════════════════════ */
.land-card {{
    background: {'rgba(22,25,41,0.75)' if is_dark else 'rgba(255,255,255,0.88)'};
    backdrop-filter: blur(16px);
    border: 1px solid {p.BORDER};
    border-radius: 20px;
    padding: 32px 22px;
    text-align: center;
    transition: transform .25s cubic-bezier(.34,1.56,.64,1), box-shadow .25s, border-color .25s;
    box-shadow: 0 4px 20px {p.SHADOW};
    height: 100%;
    position: relative;
    overflow: hidden;
}}
.land-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, {PURPLE}, {TEAL});
    opacity: 0;
    transition: opacity .25s;
}}
.land-card:hover {{
    transform: translateY(-6px) scale(1.01);
    box-shadow: 0 16px 40px {p.SHADOW};
    border-color: {PURPLE}55;
}}
.land-card:hover::before {{ opacity: 1; }}
.land-icon {{
    font-size: 2.8rem;
    margin-bottom: 14px;
    display: block;
    filter: drop-shadow(0 4px 8px {p.SHADOW});
}}
.land-title {{
    font-size: 1.05rem;
    font-weight: 800;
    color: {p.TEXT};
    margin-bottom: 8px;
    letter-spacing: -.01em;
}}
.land-desc  {{
    font-size: .82rem;
    color: {p.MUTED};
    line-height: 1.6;
}}

/* ══════════════════════════════════════════════
   SECTION DIVIDER
══════════════════════════════════════════════ */
.rich-divider {{
    height: 1px;
    background: linear-gradient(90deg, transparent, {PURPLE}44, {TEAL}44, transparent);
    border: none;
    margin: 28px 0;
}}

/* ══════════════════════════════════════════════
   POSITIVE / NEGATIVE
══════════════════════════════════════════════ */
.pos {{ color: {GREEN} !important; font-weight: 700; }}
.neg {{ color: {RED}   !important; font-weight: 700; }}

/* ══════════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════════ */
.sb-label {{
    font-size: .65rem;
    color: {p.MUTED};
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .1em;
    margin-bottom: 10px;
}}
.sb-note {{
    font-size: .75rem;
    color: {p.MUTED};
    line-height: 1.6;
}}

/* ══════════════════════════════════════════════
   SCROLLBAR (dark only)
══════════════════════════════════════════════ */
{'*::-webkit-scrollbar { width: 6px; height: 6px; }' if is_dark else ''}
{'*::-webkit-scrollbar-track { background: ' + p.BG + '; }' if is_dark else ''}
{'*::-webkit-scrollbar-thumb { background: ' + p.BORDER2 + '; border-radius: 3px; }' if is_dark else ''}
{'*::-webkit-scrollbar-thumb:hover { background: ' + PURPLE + '; }' if is_dark else ''}

/* ══════════════════════════════════════════════
   SELECTION
══════════════════════════════════════════════ */
::selection {{
    background: {PURPLE}44;
    color: {p.TEXT};
}}
</style>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
_KPI_ICONS = {"b": "💼", "g": "📈", "r": "📉", "y": "💰", "t": "🌊", "": "📊"}

def kpi(label, value, sub="", cls="", delta=None, icon=None):
    delta_html = ""
    if delta is not None:
        dc    = "pos" if delta >= 0 else "neg"
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = f"<div class='kpi-delta {dc}'>{arrow} {abs(delta):.2f}%</div>"
    sub_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    ico      = icon or _KPI_ICONS.get(cls, "📊")
    return (f"<div class='kpi {cls}'>"
            f"<span class='kpi-icon'>{ico}</span>"
            f"<div class='kpi-lbl'>{label}</div>"
            f"<div class='kpi-val'>{value}</div>"
            f"{sub_html}{delta_html}</div>")


def insight(icon, label, value, cls=""):
    return (f"<div class='ibox'>"
            f"<div class='ibox-icon'>{icon}</div>"
            f"<div class='ibox-lbl'>{label}</div>"
            f"<div class='ibox-val {cls}'>{value}</div></div>")


def mover_card(ticker, price, chg, chga):
    cls   = "pos" if chg >= 0 else "neg"
    arrow = "▲" if chg >= 0 else "▼"
    return (f"<div class='mover'>"
            f"<div class='mover-tick'>{ticker}</div>"
            f"<div class='mover-price'>GHS {price:.4f}</div>"
            f"<div class='mover-chg {cls}'>{arrow} {abs(chg):.2f}%</div>"
            f"<div style='font-size:.75rem;color:#8892b0;margin-top:5px;'>"
            f"Δ {chga:+.4f} GHS</div>"
            f"</div>")


def shdr(text, sub=None):
    sub_part = (f"<span style='font-size:.78rem;font-weight:400;opacity:.55;"
                f"margin-left:8px;'>{sub}</span>") if sub else ""
    st.markdown(f"<div class='shdr'>{text}{sub_part}</div>", unsafe_allow_html=True)


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
    wanted, results = set(norm_to_orig), {}

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
    try:
        html = base64.b64decode(st.secrets["gse_html_b64"]).decode("utf-8")
        return _parse_afx_html(html, tickers)
    except Exception:
        pass
    html = st.session_state.get("gse_html", "")
    if html:
        return _parse_afx_html(html, tickers)
    return _fetch_live(tickers)


# ─────────────────────────────────────────────────────────────────────────────
# PDF PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse_pdf(pdf_bytes: bytes) -> dict:
    equities, transactions, portfolio_summary, funds_data = [], [], {}, {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = full_text.split("\n")

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

    m = re.search(
        r"IC Liquidity\s+([\d,\.]+)\s+-([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)", full_text)
    if m:
        funds_data = {
            "name": "IC Liquidity",
            "invested":     float(m.group(1).replace(",", "")),
            "redeemed":     float(m.group(2).replace(",", "")),
            "market_value": float(m.group(5)),
        }

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
# CHARTS  — all use T() so they re-render with correct theme
# ─────────────────────────────────────────────────────────────────────────────
def chart_gain_loss(eq):
    p  = th()
    df = pd.DataFrame(eq).sort_values("gain_pct")
    colors = [GREEN if v >= 0 else RED for v in df["gain_pct"]]
    fig = go.Figure(go.Bar(
        x=df["gain_pct"], y=df["ticker"], orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df["gain_pct"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=11),
        hovertemplate="<b>%{y}</b><br>Return: %{x:.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="Return per Stock (%)", xaxis_title="Return (%)", **T(), height=380)
    return fig


def chart_pl_waterfall(eq):
    p     = th()
    df    = pd.DataFrame(eq).sort_values("gain_loss")
    total = df["gain_loss"].sum()
    tickers = df["ticker"].tolist() + ["TOTAL"]
    vals    = df["gain_loss"].tolist() + [total]
    colors  = [GREEN if v >= 0 else RED for v in vals]
    # Make TOTAL bar stand out
    colors[-1] = TEAL if total >= 0 else RED

    fig = go.Figure(go.Bar(
        x=tickers, y=vals,
        marker=dict(color=colors, line=dict(width=0),
                    opacity=[0.85]*len(df) + [1.0]),
        text=[f"{'+'if v>=0 else ''}GHS {v:,.0f}" for v in vals],
        textposition="outside",
        textfont=dict(color=p.TEXT2, size=11),
        hovertemplate="<b>%{x}</b><br>P&L: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="P&L Contribution per Stock (GHS)", yaxis_title="GHS",
                      **T(), height=340)
    return fig


def chart_market_vs_cost(eq):
    p  = th()
    df = pd.DataFrame(eq).sort_values("market_value", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Cost Basis",   x=df["ticker"], y=df["total_cost"],
                         marker_color=BLUE, opacity=0.8,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Cost</extra>"))
    fig.add_trace(go.Bar(name="Market Value", x=df["ticker"], y=df["market_value"],
                         marker_color=PURPLE, opacity=0.9,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Market</extra>"))
    # Annotate % gain/loss above bars
    for _, row in df.iterrows():
        gl = row["gain_pct"]
        fig.add_annotation(
            x=row["ticker"], y=max(row["total_cost"], row["market_value"]),
            text=f"{gl:+.1f}%", showarrow=False, yshift=12,
            font=dict(color=GREEN if gl >= 0 else RED, size=10, family="Segoe UI"),
        )
    fig.update_layout(title="Market Value vs Cost Basis (with Return %)", yaxis_title="GHS",
                      barmode="group", **T(), height=380)
    return fig


def chart_allocation_treemap(ps):
    p    = th()
    cmap = {"Equities": PURPLE, "Cash": BLUE, "Funds": AMBER, "Fixed Income": TEAL}
    labels, parents, values, colors = [], [], [], []
    for k, v in ps.items():
        if k == "Total" or v["value"] == 0:
            continue
        labels.append(k)
        parents.append("")
        values.append(v["value"])
        colors.append(cmap.get(k, p.MUTED))
    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        marker=dict(colors=colors, line=dict(width=3, color=p.BG)),
        texttemplate="<b>%{label}</b><br>GHS %{value:,.0f}<br>%{percentRoot:.1%}",
        textfont=dict(size=13, family="Segoe UI"),
        hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f}<br>%{percentRoot:.1%}<extra></extra>",
    ))
    layout = {**T(), "title": "Portfolio Allocation", "height": 300,
              "margin": dict(l=8, r=8, t=48, b=8)}
    fig.update_layout(**layout)
    return fig


def chart_stock_weight_bar(eq):
    p     = th()
    df    = pd.DataFrame(eq).sort_values("market_value")
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
        textfont=dict(color=p.TEXT2, size=11),
        customdata=df["market_value"],
        hovertemplate="<b>%{y}</b><br>Weight: %{x:.2f}%<br>GHS %{customdata:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Portfolio Weight by Stock", xaxis_title="Weight (%)",
                      **T(), height=340, showlegend=False)
    return fig


def chart_price_comparison(eq):
    p  = th()
    df = pd.DataFrame(eq)
    df = df[df["live_price"].notna()].copy()
    if df.empty:
        return None
    df["pct_diff"] = (df["live_price"] - df["statement_price"]) / df["statement_price"] * 100
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Statement Price", x=df["ticker"], y=df["statement_price"],
                         marker_color=AMBER, opacity=0.85,
                         hovertemplate="%{x}<br>Statement: GHS %{y:.4f}<extra></extra>"))
    fig.add_trace(go.Bar(name="Live Price",      x=df["ticker"], y=df["live_price"],
                         marker_color=GREEN, opacity=0.9,
                         hovertemplate="%{x}<br>Live: GHS %{y:.4f}<extra></extra>"))
    for _, row in df.iterrows():
        color = GREEN if row["pct_diff"] >= 0 else RED
        fig.add_annotation(x=row["ticker"], y=max(row["statement_price"], row["live_price"]),
                           text=f"{row['pct_diff']:+.1f}%", showarrow=False, yshift=12,
                           font=dict(color=color, size=10))
    fig.update_layout(title="Statement vs Live Price (% change annotated)",
                      yaxis_title="GHS per Share", barmode="group", **T(), height=320)
    return fig


def chart_cashflow(txs):
    p  = th()
    df = pd.DataFrame(txs)
    if df.empty:
        return None
    df["month"] = df["date"].dt.to_period("M")
    m = df.groupby("month").agg(credits=("credit","sum"), debits=("debit","sum")).reset_index()
    m["month_str"] = m["month"].astype(str)
    m["net"]       = m["credits"] - m["debits"]
    m["cumnet"]    = m["net"].cumsum()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35],
                        vertical_spacing=0.06,
                        subplot_titles=["Monthly Credits & Debits", "Cumulative Net Flow"])
    fig.add_trace(go.Bar(name="Credits", x=m["month_str"], y=m["credits"],
                         marker_color=GREEN, opacity=0.85,
                         hovertemplate="%{x}<br>GHS %{y:,.2f}<extra>Credits</extra>"), row=1, col=1)
    fig.add_trace(go.Bar(name="Debits",  x=m["month_str"], y=m["debits"],
                         marker_color=RED, opacity=0.85,
                         hovertemplate="%{x}<br>GHS %{y:,.2f}<extra>Debits</extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(name="Net", x=m["month_str"], y=m["net"],
                             mode="lines+markers", line=dict(color=AMBER, width=2.5),
                             marker=dict(size=6, color=AMBER),
                             hovertemplate="%{x}<br>Net GHS %{y:,.2f}<extra></extra>"), row=1, col=1)
    net_colors = [GREEN if v >= 0 else RED for v in m["cumnet"]]
    fig.add_trace(go.Bar(name="Cumulative Net", x=m["month_str"], y=m["cumnet"],
                         marker_color=net_colors, opacity=0.75, showlegend=False,
                         hovertemplate="%{x}<br>Cumul. GHS %{y:,.2f}<extra></extra>"), row=2, col=1)
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1, row=1, col=1)
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1, row=2, col=1)
    layout = {**T(), "barmode": "group", "height": 500,
              "xaxis2": dict(tickangle=-30, gridcolor=p.BORDER),
              "yaxis":  dict(title="GHS", gridcolor=p.BORDER),
              "yaxis2": dict(title="GHS", gridcolor=p.BORDER)}
    fig.update_layout(**layout)
    return fig


def chart_cumulative(txs, total_value):
    p  = th()
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    profit      = total_value - df["cumul"].iloc[-1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        fill="tozeroy", fillcolor=f"rgba(108,99,255,0.10)",
        line=dict(color=PURPLE, width=2.5), name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>Invested: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=total_value, line_color=TEAL, line_dash="dash", line_width=2,
                  annotation_text=f"  Portfolio Value  GHS {total_value:,.0f}",
                  annotation_font=dict(color=TEAL, size=11))
    fig.update_layout(
        title=f"Net Invested vs Current Value  "
              f"({'+'if profit>=0 else ''}GHS {profit:,.0f} unrealised)",
        xaxis_title="Date", yaxis_title="GHS", **T(), height=340)
    return fig


def chart_breakeven(eq):
    p      = th()
    losers = [e for e in eq if e["gain_pct"] < 0]
    if not losers:
        return None
    df        = pd.DataFrame(losers)
    price_col = df["live_price"].fillna(df["statement_price"])
    pct_need  = (df["avg_cost"] - price_col) / price_col * 100
    gap_ghs   = (df["avg_cost"] - price_col) * df["qty"]

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Price Gap to Break-even", "GHS Loss to Recover"],
                        specs=[[{"type":"xy"}, {"type":"xy"}]])
    fig.add_trace(go.Bar(name="Current Price",    x=df["ticker"], y=price_col,
                         marker_color=RED, opacity=0.85,
                         hovertemplate="%{x}<br>GHS %{y:.4f}<extra>Current</extra>"), row=1, col=1)
    fig.add_trace(go.Bar(name="Break-even",       x=df["ticker"], y=df["avg_cost"],
                         marker_color=AMBER, opacity=0.85,
                         hovertemplate="%{x}<br>GHS %{y:.4f}<extra>Break-even</extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(
        name="% Rally Needed", x=df["ticker"], y=pct_need,
        mode="markers+text", yaxis="y2",
        marker=dict(size=14, color=AMBER, symbol="diamond", line=dict(color=p.BG, width=2)),
        text=[f"+{v:.1f}%" for v in pct_need], textposition="top center",
        textfont=dict(color=AMBER, size=10),
        hovertemplate="%{x}: +%{y:.1f}% needed<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name="GHS to Recover", x=df["ticker"], y=gap_ghs.abs(),
        marker=dict(color=gap_ghs.abs(),
                    colorscale=[[0, AMBER],[1, RED]],
                    line=dict(width=0)),
        text=[f"GHS {v:,.0f}" for v in gap_ghs.abs()], textposition="outside",
        hovertemplate="%{x}: need GHS %{y:,.2f} recovery<extra></extra>",
    ), row=1, col=2)

    layout = {**T(), "title": "Break-even Analysis — Losing Positions",
              "barmode": "group", "height": 380,
              "yaxis":  dict(title="Price (GHS)", gridcolor=p.BORDER),
              "yaxis2": dict(title="% Rally Needed", overlaying="y", side="right",
                             showgrid=False, color=AMBER),
              "yaxis3": dict(title="GHS to Recover", gridcolor=p.BORDER),
              "xaxis2": dict(gridcolor=p.BORDER),
              "showlegend": True}
    fig.update_layout(**layout)
    return fig


def chart_concentration(eq):
    p   = th()
    df  = pd.DataFrame(eq)
    tot = df["market_value"].sum()
    w   = df["market_value"] / tot
    hhi = round((w ** 2).sum() * 10000)

    if hhi < 1500:   risk, rc = "Low",      GREEN
    elif hhi < 2500: risk, rc = "Moderate", AMBER
    else:            risk, rc = "High",      RED

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["HHI Concentration Score", "Exposure by Stock"],
                        specs=[[{"type":"indicator"}, {"type":"xy"}]])

    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=hhi,
        delta=dict(reference=1500, valueformat=".0f",
                   increasing=dict(color=RED), decreasing=dict(color=GREEN)),
        number=dict(font=dict(color=rc, size=36, family="Segoe UI"), suffix=" HHI"),
        gauge=dict(
            axis=dict(range=[0, 10000], tickcolor=p.MUTED,
                      tickfont=dict(color=p.MUTED, size=9)),
            bar=dict(color=rc, thickness=0.3),
            bgcolor=p.CARD2,
            bordercolor=p.BORDER,
            steps=[
                dict(range=[0,    1500], color="rgba(0,214,143,0.12)"),
                dict(range=[1500, 2500], color="rgba(255,170,0,0.12)"),
                dict(range=[2500,10000], color="rgba(255,61,113,0.12)"),
            ],
            threshold=dict(line=dict(color=rc, width=3), thickness=0.8, value=hhi),
        ),
        title=dict(text=f"<b>{risk}</b> Concentration", font=dict(color=rc, size=14)),
    ), row=1, col=1)

    df_s = df.sort_values("market_value", ascending=True)
    ws   = (df_s["market_value"] / tot * 100).values
    fig.add_trace(go.Bar(
        x=ws, y=df_s["ticker"].values, orientation="h",
        marker=dict(color=ws, colorscale=[[0, GREEN],[0.4, AMBER],[1, RED]],
                    line=dict(width=0)),
        text=[f"{v:.1f}%" for v in ws], textposition="outside",
        textfont=dict(color=p.TEXT2, size=11),
        hovertemplate="<b>%{y}</b>: %{x:.1f}%<extra></extra>",
        showlegend=False,
    ), row=1, col=2)

    layout = {
        "paper_bgcolor": p.BG, "plot_bgcolor": p.CARD,
        "font": dict(color=p.TEXT, family="Segoe UI"),
        "margin": dict(l=16, r=16, t=60, b=16), "height": 380,
        "xaxis2": dict(gridcolor=p.BORDER, title="Weight (%)", tickcolor=p.MUTED),
        "yaxis2": dict(gridcolor=p.BORDER, tickcolor=p.MUTED),
        "hoverlabel": dict(bgcolor=p.CARD2, bordercolor=p.BORDER, font=dict(color=p.TEXT)),
        "legend": dict(bgcolor=p.CARD2, bordercolor=p.BORDER),
    }
    fig.update_layout(**layout)
    return fig, hhi, risk, rc


def chart_rolling_return(txs, eq, total_value):
    """Monthly portfolio value proxy from cumulative net invested + unrealised gain spread."""
    p  = th()
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    # Spread the current unrealised gain evenly across timeline as a proxy
    total_cost  = sum(e["total_cost"] for e in eq)
    total_gain  = sum(e["gain_loss"]  for e in eq)
    df["proxy_value"] = df["cumul"] * (total_value / df["cumul"].iloc[-1]) if df["cumul"].iloc[-1] else df["cumul"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["proxy_value"], mode="lines",
        fill="tozeroy", fillcolor=f"rgba(0,201,177,0.10)",
        line=dict(color=TEAL, width=2.5), name="Est. Portfolio Value",
        hovertemplate="%{x|%b %d, %Y}<br>Est. Value: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        line=dict(color=PURPLE, width=1.5, dash="dot"), name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>Invested: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Estimated Portfolio Value Over Time",
                      xaxis_title="Date", yaxis_title="GHS", **T(), height=320)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    p       = th()
    is_dark = p.name == "dark"

    with st.sidebar:
        # Theme toggle
        st.markdown(f"<div style='font-size:.75rem;color:{p.MUTED};font-weight:600;"
                    f"text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;'>"
                    f"APPEARANCE</div>", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            dark_style = f"background:{PURPLE};color:white;" if is_dark else f"background:{p.CARD2};color:{p.MUTED};"
            if st.button("🌙  Dark", use_container_width=True, key="sb_dark"):
                st.session_state["theme"] = "dark"
                st.rerun()
        with col_b:
            light_style = f"background:{PURPLE};color:white;" if not is_dark else f"background:{p.CARD2};color:{p.MUTED};"
            if st.button("☀️  Light", use_container_width=True, key="sb_light"):
                st.session_state["theme"] = "light"
                st.rerun()

        st.divider()

        # GSE Prices
        st.markdown(f"<div style='font-size:.75rem;color:{p.MUTED};font-weight:600;"
                    f"text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;'>"
                    f"📡 GSE PRICES</div>", unsafe_allow_html=True)

        if st.secrets.get("gse_html_b64", ""):
            st.success("✅ Loaded from Streamlit Secrets")
            st.caption("Refresh: update `gse_html_b64` in **Settings → Secrets**.")
        else:
            st.info("Set `gse_html_b64` in Secrets for automatic prices.")
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

        st.divider()
        st.markdown(f"<div style='font-size:.72rem;color:{p.MUTED};line-height:1.6;'>"
                    f"IC Portfolio Analyser<br>"
                    f"Prices via <a href='https://afx.kwayisi.org/gse/' style='color:{PURPLE};'>"
                    f"afx.kwayisi.org</a><br>"
                    f"For informational purposes only."
                    f"</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "dark"

    apply_theme()
    render_sidebar()

    p = th()

    # ── Header ───────────────────────────────────────────────────────────────
    is_dark = p.name == "dark"
    cl, ct, cr = st.columns([1, 7, 2])
    with cl:
        st.markdown(
            f"<div style='font-size:3.4rem;padding-top:2px;line-height:1;"
            f"filter:drop-shadow(0 0 20px {PURPLE}66);'>📈</div>",
            unsafe_allow_html=True)
    with ct:
        st.markdown(
            f"<div class='hero-badge'>IC Securities · Ghana Stock Exchange</div>"
            f"<div class='hero'>IC Portfolio Analyser</div>"
            f"<div class='hero-sub'>"
            f"Upload your statement · Live GSE prices · Instant analytics"
            f"</div>",
            unsafe_allow_html=True)
    with cr:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🌙  Dark", use_container_width=True, key="hdr_dark",
                         disabled=is_dark):
                st.session_state["theme"] = "dark"; st.rerun()
        with col2:
            if st.button("☀️  Light", use_container_width=True, key="hdr_light",
                         disabled=not is_dark):
                st.session_state["theme"] = "light"; st.rerun()

    st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)

    # ── Upload ────────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "**📄  Drop your IC Securities Account Statement (PDF)**", type=["pdf"])

    if not uploaded:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        features = [
            ("📊", "Overview & KPIs",
             "Portfolio value, ROI, unrealised gains and 8 KPI cards at a glance."),
            ("📈", "Performance Analysis",
             "Returns per stock, P&L waterfall, market vs cost, live price comparison."),
            ("⚖️", "Risk & Scenarios",
             "Break-even analysis, HHI concentration gauge, what-if price simulator."),
            ("💸", "Cash Flow & Holdings",
             "Monthly flow charts, cumulative invested curve, full transaction log."),
        ]
        for col, (icon, title, desc) in zip([c1,c2,c3,c4], features):
            with col:
                st.markdown(
                    f"<div class='land-card'>"
                    f"<span class='land-icon'>{icon}</span>"
                    f"<div class='land-title'>{title}</div>"
                    f"<div class='land-desc'>{desc}</div>"
                    f"</div>", unsafe_allow_html=True)
        st.stop()

    # ── Parse PDF ─────────────────────────────────────────────────────────────
    with st.spinner("📄 Parsing statement..."):
        data = parse_pdf(uploaded.read())

    eq  = data["equities"]
    txs = data["transactions"]
    ps  = data["portfolio_summary"]

    if not eq:
        st.error("Could not parse equity data. Please check the PDF format.")
        st.stop()

    # ── Live prices ───────────────────────────────────────────────────────────
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

    # ── Manual override ───────────────────────────────────────────────────────
    with st.expander("✏️ Override prices manually", expanded=False):
        cols = st.columns(5)
        overrides = {}
        for i, e in enumerate(eq):
            default = float(e["live_price"] or e["statement_price"])
            val = cols[i % 5].number_input(
                e["ticker"], min_value=0.0, value=default,
                step=0.01, format="%.4f", key=f"ov_{e['ticker']}")
            if val > 0:
                overrides[e["ticker"]] = val
        if st.button("✅ Apply prices", type="primary"):
            st.cache_data.clear()
            eq = inject_live_prices(
                eq, {t: {"price":p2,"change_pct":0,"change_abs":0}
                     for t, p2 in overrides.items()})
            n_live = len(eq)
            st.success("Applied.")

    # ── Computed metrics ──────────────────────────────────────────────────────
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
    portfolio_div = len([e for e in eq if e["market_value"] / equities_val > 0.05]) if equities_val else 0

    active_month = "N/A"
    if txs:
        _tdf          = pd.DataFrame(txs)
        _tdf["month"] = _tdf["date"].dt.to_period("M")
        active_month  = str(_tdf["month"].value_counts().idxmax())

    # ── Client bar ────────────────────────────────────────────────────────────
    price_pill_cls = "live" if n_live == len(eq) else "warn" if n_live else "info"
    price_pill_txt = ("✦ All Live" if n_live == len(eq)
                      else f"{n_live}/{len(eq)} Live" if n_live else "Statement Prices")
    win_rate = f"{winners/len(eq)*100:.0f}%" if eq else "—"
    roi_col  = GREEN if overall_roi >= 0 else RED
    gl_col   = GREEN if total_gain  >= 0 else RED
    st.markdown(f"""
    <div class='cbar'>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Client</div>
        <div class='cbar-val'>{data['client_name']}</div>
      </div>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Account</div>
        <div class='cbar-acc'>{data['account_number']}</div>
      </div>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Statement Date</div>
        <div class='cbar-val'>{data['report_date']}</div>
      </div>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Portfolio Value</div>
        <div class='cbar-val'>GHS {total_value:,.2f}</div>
      </div>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Overall Return</div>
        <div class='cbar-val' style='color:{roi_col}'>{overall_roi:+.2f}%</div>
      </div>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Unrealised G/L</div>
        <div class='cbar-val' style='color:{gl_col}'>
          {'+'if total_gain>=0 else ''}GHS {total_gain:,.2f}
        </div>
      </div>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Win Rate</div>
        <div class='cbar-val'>{winners}/{len(eq)} stocks ({win_rate})</div>
      </div>
      <div class='cbar-item'>
        <div class='cbar-lbl'>Prices</div>
        <div class='cbar-val'>
          <span class='pill {price_pill_cls}'>{price_pill_txt}</span>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊  Overview",
        "📈  Performance",
        "⚖️  Risk & Scenarios",
        "💸  Cash Flow",
        "📋  Holdings",
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
                            "g" if total_gain >= 0 else "r",
                            delta=gain_pct), unsafe_allow_html=True)
        with c3:
            st.markdown(kpi("Overall ROI",
                            f"<span class='{pn(overall_roi)}'>{overall_roi:+.2f}%</span>",
                            f"Net invested GHS {net_invested:,.2f}",
                            "g" if overall_roi >= 0 else "r"), unsafe_allow_html=True)
        with c4:
            st.markdown(kpi("Equities Value",
                            f"GHS {equities_val:,.2f}",
                            f"{ps.get('Equities',{}).get('alloc',0):.1f}% of portfolio",
                            ""), unsafe_allow_html=True)

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

        st.markdown("---")
        shdr("Quick Insights")
        i1, i2, i3, i4, i5, i6 = st.columns(6)
        with i1: st.markdown(insight("🏆","Best Performer",
                                     f"{best['ticker']} {best['gain_pct']:+.1f}%", "pos"),
                             unsafe_allow_html=True)
        with i2: st.markdown(insight("📉","Worst Performer",
                                     f"{worst['ticker']} {worst['gain_pct']:+.1f}%", "neg"),
                             unsafe_allow_html=True)
        with i3: st.markdown(insight("💎","Largest Position",
                                     f"{biggest['ticker']} · GHS {biggest['market_value']:,.0f}"),
                             unsafe_allow_html=True)
        with i4: st.markdown(insight("⚡","Most Active Month", active_month),
                             unsafe_allow_html=True)
        with i5: st.markdown(insight("📊","Diversified Stocks",
                                     f"{portfolio_div} of {len(eq)} >5%"),
                             unsafe_allow_html=True)
        with i6: st.markdown(insight("📡","Live Prices",
                                     f"{n_live} / {len(eq)} fetched",
                                     "pos" if n_live==len(eq) else ""),
                             unsafe_allow_html=True)

        # Today's Movers
        movers = sorted([e for e in eq if e.get("change_pct") is not None],
                        key=lambda e: abs(e["change_pct"] or 0), reverse=True)
        if movers:
            st.markdown("---")
            shdr("🚀 Today's Movers")
            mcols = st.columns(min(len(movers), 5))
            for col, e in zip(mcols, movers[:5]):
                with col:
                    st.markdown(mover_card(
                        e["ticker"], e["live_price"],
                        e["change_pct"] or 0, e["change_abs"] or 0),
                        unsafe_allow_html=True)

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

        pc = chart_price_comparison(eq)
        if pc:
            st.plotly_chart(pc, use_container_width=True)
        else:
            st.markdown(
                f"<div style='text-align:center;color:{p.MUTED};padding:24px;'>"
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
        shdr("⚖️ Concentration Risk")
        conc_fig, hhi, risk, rc = chart_concentration(eq)
        st.plotly_chart(conc_fig, use_container_width=True)
        st.markdown(
            f"<div style='text-align:center;color:{p.MUTED};font-size:.85rem;margin-top:-8px;'>"
            f"Herfindahl-Hirschman Index (HHI): <b style='color:{rc}'>{hhi}</b> — "
            f"<b style='color:{rc}'>{risk}</b> concentration &nbsp;·&nbsp; "
            f"<span style='color:{GREEN}'>Low &lt;1500</span> · "
            f"<span style='color:{AMBER}'>Moderate 1500–2500</span> · "
            f"<span style='color:{RED}'>High &gt;2500</span>"
            f"</div>", unsafe_allow_html=True)

        st.markdown("---")
        shdr("🔮 What-If Scenario Simulator")
        st.caption("Drag sliders to simulate price moves and instantly see the portfolio impact.")

        rows_of_5 = [eq[i:i+5] for i in range(0, len(eq), 5)]
        sim_mult  = {}
        for row in rows_of_5:
            scols = st.columns(len(row))
            for col, e in zip(scols, row):
                chg = col.slider(e["ticker"], min_value=-50, max_value=150,
                                 value=0, step=1, format="%d%%",
                                 key=f"sim_{e['ticker']}")
                sim_mult[e["ticker"]] = 1 + chg / 100

        sim_mv    = sum(e["market_value"] * sim_mult.get(e["ticker"], 1) for e in eq)
        sim_total = sim_mv + cash_val + funds_val
        sim_gain  = sum((e["market_value"] * sim_mult.get(e["ticker"],1)) - e["total_cost"] for e in eq)
        sim_delta = sim_total - total_value
        sim_roi   = ((sim_total - net_invested) / net_invested * 100) if net_invested else 0

        st.markdown("")
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.markdown(kpi("Simulated Total Value",
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
            gain_chg = sim_gain - total_gain
            st.markdown(kpi("G/L Change",
                            f"<span class='{pn(gain_chg)}'>{'+'if gain_chg>=0 else ''}GHS {gain_chg:,.2f}</span>",
                            "vs current unrealised G/L",
                            "g" if gain_chg >= 0 else "r"), unsafe_allow_html=True)

        sim_df = pd.DataFrame([{
            "ticker":    e["ticker"],
            "current":   e["market_value"],
            "simulated": e["market_value"] * sim_mult.get(e["ticker"], 1),
        } for e in eq]).sort_values("simulated", ascending=False)
        fig_sim = go.Figure()
        fig_sim.add_trace(go.Bar(name="Current",   x=sim_df["ticker"], y=sim_df["current"],
                                 marker_color=PURPLE, opacity=0.7))
        fig_sim.add_trace(go.Bar(name="Simulated", x=sim_df["ticker"], y=sim_df["simulated"],
                                 marker=dict(
                                     color=[GREEN if s > c else RED
                                            for s, c in zip(sim_df["simulated"], sim_df["current"])],
                                     opacity=0.9)))
        fig_sim.update_layout(title="Current vs Simulated Market Value",
                              yaxis_title="GHS", barmode="group", **T(), height=320)
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
                cmap = {"Buy":BLUE,"Sell":AMBER,"Credit":GREEN,"Withdrawal":RED,"Other":p.MUTED}
                fig_tt = go.Figure(go.Bar(
                    x=grp["type"], y=grp["amount"],
                    marker_color=[cmap.get(t, p.MUTED) for t in grp["type"]],
                    text=[f"GHS {v:,.0f}" for v in grp["amount"]], textposition="outside",
                    hovertemplate="%{x}: GHS %{y:,.2f}<extra></extra>",
                ))
                fig_tt.update_layout(title="Volume by Transaction Type",
                                     yaxis_title="GHS", **T(), height=320)
                st.plotly_chart(fig_tt, use_container_width=True)

        # Summary stats
        tx_df3 = pd.DataFrame(txs)
        if not tx_df3.empty:
            tx_df3["month"] = tx_df3["date"].dt.to_period("M")
            n_months = tx_df3["month"].nunique()
            avg_monthly_credit = total_credits / n_months if n_months else 0
            avg_monthly_debit  = total_debits  / n_months if n_months else 0
            st.markdown("---")
            shdr("Flow Averages")
            fa1, fa2, fa3, fa4 = st.columns(4)
            with fa1: st.markdown(kpi("Months Active", f"{n_months}",
                                      f"{len(txs)} transactions total", "b"), unsafe_allow_html=True)
            with fa2: st.markdown(kpi("Avg Monthly Credit", f"GHS {avg_monthly_credit:,.2f}",
                                      "per active month", "g"), unsafe_allow_html=True)
            with fa3: st.markdown(kpi("Avg Monthly Debit", f"GHS {avg_monthly_debit:,.2f}",
                                      "per active month", "r"), unsafe_allow_html=True)
            with fa4: st.markdown(kpi("Net Flow", f"GHS {net_invested:,.2f}",
                                      "total net invested", "t"), unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — HOLDINGS
    # ══════════════════════════════════════════════════════════════════════════
    with tab5:
        shdr("Equity Positions")
        pos_rows = []
        for e in sorted(eq, key=lambda x: x["market_value"], reverse=True):
            wt = e["market_value"] / equities_val * 100 if equities_val else 0
            pos_rows.append({
                "Ticker":       e["ticker"],
                "Qty":          f"{e['qty']:,.0f}",
                "Avg Cost":     f"{e['avg_cost']:.4f}",
                "Stmt Price":   f"{e['statement_price']:.4f}",
                "Live Price":   f"{e['live_price']:.4f}" if e["live_price"] else "—",
                "Today Δ%":     f"{e['change_pct']:+.2f}%" if e.get("change_pct") is not None else "—",
                "Today ΔGHS":   f"{e['change_abs']:+.4f}" if e.get("change_abs") is not None else "—",
                "Weight %":     f"{wt:.1f}%",
                "Cost Basis":   f"GHS {e['total_cost']:,.2f}",
                "Market Value": f"GHS {e['market_value']:,.2f}",
                "Gain/Loss":    f"{'+'if e['gain_loss']>=0 else ''}GHS {e['gain_loss']:,.2f}",
                "Return %":     f"{e['gain_pct']:+.1f}%",
                "Status":       "✅ Profit" if e["gain_pct"] >= 0 else f"🔴 Need GHS {e['avg_cost']:.4f}",
            })

        df_pos = pd.DataFrame(pos_rows)

        def _style(row):
            s  = [""] * len(row)
            ig = list(row.index).index("Gain/Loss")
            ir = list(row.index).index("Return %")
            c  = (f"color:{GREEN};font-weight:700" if "+" in row["Gain/Loss"]
                  else f"color:{RED};font-weight:700")
            s[ig] = s[ir] = c
            return s

        st.dataframe(df_pos.style.apply(_style, axis=1),
                     use_container_width=True, hide_index=True)

        st.markdown("---")
        shdr("Transaction History")
        tx_df = pd.DataFrame(txs).sort_values("date", ascending=False)
        emoji = {"Buy":"🔵","Sell":"🟡","Credit":"🟢","Withdrawal":"🔴","Other":"⚪"}
        tx_df["Type"] = tx_df["type"].map(lambda t: f"{emoji.get(t,'⚪')} {t}")

        cf1, cf2, cf3 = st.columns([2, 2, 3])
        with cf1:
            filt = st.multiselect("Filter type",
                                   options=list(tx_df["Type"].unique()),
                                   default=list(tx_df["Type"].unique()),
                                   label_visibility="collapsed")
        with cf2:
            date_range = st.date_input("Date range",
                                        value=(tx_df["date"].min().date(),
                                               tx_df["date"].max().date()),
                                        label_visibility="collapsed")
        with cf3:
            srch = st.text_input("Search", placeholder="🔍  Search description...",
                                 label_visibility="collapsed")

        view = tx_df[tx_df["Type"].isin(filt)]
        if len(date_range) == 2:
            start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
            view = view[(view["date"] >= start) & (view["date"] <= end)]
        if srch:
            view = view[view["description"].str.contains(srch, case=False, na=False)]

        view_show = view[["date_str","Type","description","credit","debit"]].rename(columns={
            "date_str":"Date","description":"Description",
            "credit":"Credit (GHS)","debit":"Debit (GHS)"})
        view_show["Credit (GHS)"] = view_show["Credit (GHS)"].apply(
            lambda v: f"+{v:,.2f}" if v > 0 else "—")
        view_show["Debit (GHS)"]  = view_show["Debit (GHS)"].apply(
            lambda v: f"-{v:,.2f}" if v > 0 else "—")
        view_show["Description"]  = view_show["Description"].str[:100]

        st.caption(f"Showing {len(view_show):,} of {len(tx_df):,} transactions")
        st.dataframe(view_show, use_container_width=True, hide_index=True, height=420)

    # ── Rich Footer ───────────────────────────────────────────────────────────
    p2 = th()
    st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                flex-wrap:wrap;gap:12px;padding:8px 4px 16px;
                font-size:.78rem;color:{p2.MUTED};">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:1.2rem;">📈</span>
        <span><b style='color:{PURPLE}'>IC Portfolio Analyser</b> &nbsp;·&nbsp;
        Built for IC Securities Ghana</span>
      </div>
      <div style="display:flex;gap:20px;align-items:center;">
        <span>Prices via
          <a href='https://afx.kwayisi.org/gse/' target='_blank'
             style='color:{PURPLE};text-decoration:none;font-weight:600;'>
             afx.kwayisi.org
          </a>
        </span>
        <span style="color:{p2.BORDER2};">|</span>
        <span>For informational purposes only</span>
        <span style="color:{p2.BORDER2};">|</span>
        <span>Past performance is not indicative of future results</span>
      </div>
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()