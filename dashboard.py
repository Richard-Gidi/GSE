"""
IC Securities Portfolio Analyser — ELITE EDITION v3.0 (March 2026)

Upgrades from v2.0:
  • Complete visual redesign — obsidian-gold premium theme
  • Fraunces display font + Epilogue body + DM Mono for all numeric data
  • NEW Analytics tab: Sharpe Ratio, Max Drawdown, ENP, Volatility, Risk/Return Matrix
  • Monthly Cash Flow Calendar Heatmap
  • Portfolio Drawdown chart from cumulative peak
  • Risk / Return bubble scatter (weight × return, sized by market value)
  • Sector Performance grouped comparison chart
  • Estimated Dividend Yield per Stock
  • Position Sizer / Target-Weight calculator in Holdings tab
  • Holding period detection from Buy transactions
  • Enhanced Smart Alerts with deeper pattern detection
  • Holdings tab: sector filter, better sort, improved progress bars
  • Flow Quality Score in Cash Flow tab
  • All KPI numbers rendered in DM Mono for premium data-display feel
  • Improved CSV export with all computed fields including sector

Install:
    pip install streamlit plotly pdfplumber pandas numpy requests beautifulsoup4 lxml
Run:
    streamlit run akwasi_v3.py
"""

import base64, io, re, warnings
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pdfplumber
import streamlit as st
import requests

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IC Portfolio Analyser",
    page_icon="₵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# THEME — OBSIDIAN × GOLD
# ─────────────────────────────────────────────────────────────────────────────
_DARK = SimpleNamespace(
    BG      = "#04060f",
    CARD    = "#08091e",
    CARD2   = "#0c1028",
    BORDER  = "#141838",
    BORDER2 = "#1c2248",
    TEXT    = "#eef0fa",
    TEXT2   = "#8898c8",
    MUTED   = "#424870",
    SHADOW  = "rgba(0,0,0,0.75)",
    name    = "dark",
)

GOLD    = "#e8b438"   # primary — Ghana gold
GOLD2   = "#c0901e"   # deep gold
EMERALD = "#00d485"   # gains / positive
RUBY    = "#ff3960"   # losses / negative
AZURE   = "#0ea5e9"   # info / blue
VIOLET  = "#7c5cfa"   # secondary accent
TEAL    = "#06b6d4"   # tertiary accent
AMBER   = "#f59e0b"   # warning
ROSE    = "#f43f7e"   # highlight
INDIGO  = "#6366f1"   # extra accent
SLATE   = "#64748b"   # neutral


def th():
    return _DARK


def T():
    """Base Plotly layout dict for all charts."""
    p = th()
    return dict(
        paper_bgcolor = p.BG,
        plot_bgcolor  = p.CARD,
        font          = dict(color=p.TEXT2, family="'DM Mono', 'Courier New', monospace", size=11),
        xaxis         = dict(gridcolor=p.BORDER, zerolinecolor=p.BORDER2,
                             tickcolor=p.MUTED, tickfont=dict(color=p.MUTED)),
        yaxis         = dict(gridcolor=p.BORDER, zerolinecolor=p.BORDER2,
                             tickcolor=p.MUTED, tickfont=dict(color=p.MUTED)),
        margin        = dict(l=16, r=16, t=52, b=16),
        legend        = dict(bgcolor=p.CARD2, bordercolor=p.BORDER, borderwidth=1,
                             font=dict(color=p.TEXT2, family="Epilogue, sans-serif")),
        hoverlabel    = dict(bgcolor=p.CARD2, bordercolor=p.BORDER2,
                             font=dict(color=p.TEXT, family="'DM Mono', monospace")),
        title         = dict(font=dict(color=p.TEXT, family="'Epilogue', sans-serif",
                                       size=14, weight=600), x=0.01),
    )


def apply_theme():
    p = th()
    # Radial ambient glows
    bg = (
        f"radial-gradient(ellipse at 15% 5%, {GOLD}0d 0%, transparent 45%),"
        f"radial-gradient(ellipse at 88% 92%, {VIOLET}12 0%, transparent 45%),"
        f"radial-gradient(ellipse at 50% 50%, {AZURE}06 0%, transparent 70%),"
        f"{p.BG}"
    )
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;0,9..144,900;1,9..144,200;1,9..144,400&family=Epilogue:wght@300;400;500;600;700;800;900&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300;1,400&display=swap');

/* ── BASE ─────────────────────────────────────────────── */
html,body,[class*="css"]{{
  font-family:'Epilogue','Segoe UI',system-ui,-apple-system,sans-serif;
}}
.stApp,[data-testid="stAppViewContainer"]{{
  background:{bg}!important;min-height:100vh;
}}
[data-testid="stHeader"],[data-testid="stToolbar"]{{
  background:rgba(4,6,15,0.6)!important;backdrop-filter:blur(20px);
  border-bottom:1px solid {p.BORDER}!important;
}}
section[data-testid="stSidebar"]{{
  background:rgba(8,9,30,0.97)!important;
  border-right:1px solid {p.BORDER}!important;
  backdrop-filter:blur(24px);
}}
.block-container{{
  color:{p.TEXT};padding-top:1.5rem!important;max-width:1500px;
}}

/* ── KPI CARDS ────────────────────────────────────────── */
.kpi{{
  position:relative;background:rgba(8,9,30,0.85);
  backdrop-filter:blur(20px);border-radius:16px;
  padding:20px 22px 16px;
  border:1px solid {p.BORDER};
  margin-bottom:6px;
  transition:transform .25s cubic-bezier(.34,1.56,.64,1),box-shadow .25s ease,border-color .25s;
  box-shadow:0 4px 24px {p.SHADOW};overflow:hidden;
}}
.kpi::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,{GOLD},{GOLD2},{AMBER});
  border-radius:16px 16px 0 0;
}}
.kpi.g::before{{ background:linear-gradient(90deg,{EMERALD},{TEAL}); }}
.kpi.r::before{{ background:linear-gradient(90deg,{RUBY},{AMBER}); }}
.kpi.y::before{{ background:linear-gradient(90deg,{AMBER},{GOLD}); }}
.kpi.b::before{{ background:linear-gradient(90deg,{AZURE},{VIOLET}); }}
.kpi.t::before{{ background:linear-gradient(90deg,{TEAL},{EMERALD}); }}
.kpi.pk::before{{ background:linear-gradient(90deg,{ROSE},{VIOLET}); }}
.kpi.vi::before{{ background:linear-gradient(90deg,{VIOLET},{INDIGO}); }}
.kpi-glow{{
  position:absolute;top:-40px;right:-40px;
  width:100px;height:100px;
  background:radial-gradient({GOLD}18,transparent 70%);
  border-radius:50%;pointer-events:none;
}}
.kpi.g .kpi-glow{{ background:radial-gradient({EMERALD}12,transparent 70%); }}
.kpi.r .kpi-glow{{ background:radial-gradient({RUBY}12,transparent 70%); }}
.kpi:hover{{
  transform:translateY(-4px) scale(1.01);
  box-shadow:0 16px 40px {p.SHADOW};
  border-color:{GOLD}40;
}}
.kpi-icon{{font-size:1.5rem;float:right;margin-top:2px;opacity:0.18;line-height:1;}}
.kpi-lbl{{
  font-size:.65rem;color:{p.MUTED};text-transform:uppercase;
  letter-spacing:.12em;margin-bottom:12px;font-weight:700;
  font-family:'Epilogue',sans-serif;
}}
.kpi-val{{
  font-size:1.55rem;font-weight:500;color:{p.TEXT};
  line-height:1.15;letter-spacing:-.01em;
  font-family:'DM Mono','Courier New',monospace;
}}
.kpi-sub{{
  font-size:.73rem;color:{p.MUTED};margin-top:8px;line-height:1.45;
  font-family:'Epilogue',sans-serif;
}}
.kpi-delta{{
  display:inline-flex;align-items:center;gap:3px;
  font-size:.7rem;font-weight:600;padding:3px 9px;
  border-radius:20px;margin-top:8px;letter-spacing:.03em;
  font-family:'DM Mono',monospace;
}}
.kpi-delta.pos{{background:rgba(0,212,133,0.12);color:{EMERALD};border:1px solid rgba(0,212,133,0.22);}}
.kpi-delta.neg{{background:rgba(255,57,96,0.12);color:{RUBY};border:1px solid rgba(255,57,96,0.22);}}

/* ── INSIGHT BOXES ────────────────────────────────────── */
.ibox{{
  background:rgba(8,9,30,0.75);backdrop-filter:blur(12px);
  border:1px solid {p.BORDER};border-radius:14px;
  padding:18px 12px 16px;text-align:center;height:100%;
  transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s;
  box-shadow:0 2px 12px {p.SHADOW};position:relative;overflow:hidden;
}}
.ibox::after{{
  content:'';position:absolute;bottom:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,{GOLD}40,transparent);
  opacity:0;transition:opacity .2s;
}}
.ibox:hover{{transform:translateY(-3px);box-shadow:0 10px 28px {p.SHADOW};}}
.ibox:hover::after{{opacity:1;}}
.ibox-icon{{font-size:1.9rem;line-height:1;filter:drop-shadow(0 2px 6px {p.SHADOW});}}
.ibox-lbl{{
  font-size:.62rem;color:{p.MUTED};text-transform:uppercase;
  letter-spacing:.1em;margin:10px 0 5px;font-weight:700;
  font-family:'Epilogue',sans-serif;
}}
.ibox-val{{font-size:.9rem;font-weight:500;color:{p.TEXT};font-family:'DM Mono',monospace;}}

/* ── MOVER CARDS ──────────────────────────────────────── */
.mover{{
  background:rgba(8,9,30,0.8);backdrop-filter:blur(12px);
  border:1px solid {p.BORDER};border-radius:14px;padding:16px 14px;
  text-align:center;box-shadow:0 2px 12px {p.SHADOW};
  transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s;
  position:relative;overflow:hidden;
}}
.mover.top-mover{{border-color:{GOLD}55;}}
.mover.top-mover::before{{
  content:'TOP MOVER';position:absolute;top:7px;right:8px;
  font-size:.55rem;font-weight:800;letter-spacing:.1em;
  color:{GOLD};font-family:'Epilogue',sans-serif;
  background:rgba(232,180,56,0.12);padding:2px 6px;border-radius:6px;
  border:1px solid {GOLD}30;
}}
.mover:hover{{transform:translateY(-4px);box-shadow:0 12px 32px {p.SHADOW};border-color:{GOLD}40;}}
.mover-tick{{
  font-size:.68rem;font-weight:800;color:{p.MUTED};text-transform:uppercase;
  letter-spacing:.1em;background:{p.CARD2};display:inline-block;
  padding:2px 10px;border-radius:8px;margin-bottom:8px;
  font-family:'Epilogue',sans-serif;
}}
.mover-price{{
  font-size:1.45rem;font-weight:400;color:{p.TEXT};margin:4px 0;
  font-family:'DM Mono',monospace;letter-spacing:-.01em;
}}
.mover-chg{{
  font-size:.82rem;font-weight:600;padding:3px 12px;
  border-radius:12px;display:inline-block;font-family:'DM Mono',monospace;
}}
.mover-chg.pos{{background:rgba(0,212,133,0.12);color:{EMERALD};}}
.mover-chg.neg{{background:rgba(255,57,96,0.12);color:{RUBY};}}

/* ── SECTION HEADERS ──────────────────────────────────── */
.shdr{{
  display:flex;align-items:center;gap:10px;font-size:.95rem;
  font-weight:700;color:{p.TEXT};margin:22px 0 16px;letter-spacing:-.01em;
  font-family:'Epilogue',sans-serif;
}}
.shdr::before{{
  content:'';display:inline-block;width:3px;height:18px;
  background:linear-gradient(180deg,{GOLD},{AMBER});
  border-radius:4px;flex-shrink:0;
}}

/* ── CLIENT BAR ───────────────────────────────────────── */
.cbar{{
  background:rgba(8,9,30,0.88);backdrop-filter:blur(20px);
  border:1px solid {p.BORDER};border-radius:16px;
  padding:16px 28px;display:flex;justify-content:space-between;
  align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:16px;
  box-shadow:0 4px 24px {p.SHADOW};position:relative;overflow:hidden;
}}
.cbar::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,{GOLD}80,{AMBER}60,transparent);
}}
.cbar-item{{display:flex;flex-direction:column;gap:4px;}}
.cbar-lbl{{
  font-size:.6rem;color:{p.MUTED};text-transform:uppercase;
  letter-spacing:.12em;font-weight:800;font-family:'Epilogue',sans-serif;
}}
.cbar-val{{
  font-size:.92rem;font-weight:400;color:{p.TEXT};
  font-family:'DM Mono',monospace;
}}
.cbar-acc{{
  font-size:.95rem;font-weight:500;
  background:linear-gradient(135deg,{GOLD},{AMBER});
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;font-family:'DM Mono',monospace;
}}

/* ── HERO ─────────────────────────────────────────────── */
.hero{{
  font-size:2.8rem;font-weight:600;line-height:1.05;
  letter-spacing:-.05em;
  background:linear-gradient(135deg,{p.TEXT} 0%,{GOLD} 55%,{AMBER} 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;font-family:'Fraunces','Georgia',serif;
}}
.hero-sub{{
  color:{p.MUTED};font-size:.9rem;margin-top:8px;line-height:1.65;
  font-weight:400;font-family:'Epilogue',sans-serif;
}}
.hero-badge{{
  display:inline-block;background:rgba(232,180,56,0.1);
  color:{GOLD};border:1px solid rgba(232,180,56,0.25);
  font-size:.65rem;font-weight:800;padding:3px 11px;border-radius:10px;
  letter-spacing:.09em;text-transform:uppercase;margin-bottom:10px;
  font-family:'Epilogue',sans-serif;
}}

/* ── TABS ─────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"]{{
  background:rgba(8,9,30,0.85)!important;backdrop-filter:blur(16px)!important;
  border-radius:12px!important;padding:5px!important;
  border:1px solid {p.BORDER}!important;gap:2px;
  box-shadow:0 2px 16px {p.SHADOW};
}}
[data-testid="stTabs"] [role="tab"]{{
  border-radius:9px!important;color:{p.MUTED}!important;
  font-weight:600!important;font-size:.82rem!important;
  padding:8px 18px!important;transition:all .18s ease!important;
  border:none!important;letter-spacing:.01em;
  font-family:'Epilogue',sans-serif!important;
}}
[data-testid="stTabs"] [role="tab"]:hover{{
  color:{p.TEXT}!important;background:{p.CARD2}!important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{{
  background:linear-gradient(135deg,rgba(232,180,56,0.18),rgba(232,180,56,0.08))!important;
  color:{GOLD}!important;
  box-shadow:0 2px 12px rgba(232,180,56,0.2),inset 0 0 0 1px rgba(232,180,56,0.3)!important;
}}

/* ── FILE UPLOAD ──────────────────────────────────────── */
[data-testid="stFileUploadDropzone"]{{
  background:rgba(8,9,30,0.75)!important;
  border:2px dashed {GOLD}40!important;border-radius:16px!important;
  padding:36px!important;transition:all .2s!important;backdrop-filter:blur(12px);
}}
[data-testid="stFileUploadDropzone"]:hover{{
  border-color:{GOLD}80!important;
  background:rgba(232,180,56,0.04)!important;
}}

/* ── DATAFRAMES ───────────────────────────────────────── */
[data-testid="stDataFrame"]{{
  border-radius:12px!important;overflow:hidden;
  border:1px solid {p.BORDER}!important;
  box-shadow:0 2px 16px {p.SHADOW};
}}
.js-plotly-plot{{
  border-radius:14px!important;overflow:hidden;
  border:1px solid {p.BORDER};
  box-shadow:0 2px 20px {p.SHADOW};
}}
[data-testid="stExpander"]{{
  background:rgba(8,9,30,0.75)!important;
  border:1px solid {p.BORDER}!important;
  border-radius:12px!important;backdrop-filter:blur(12px);
}}
[data-testid="stExpander"] summary{{
  font-weight:700!important;color:{p.TEXT}!important;
  font-family:'Epilogue',sans-serif!important;
}}

/* ── PILLS & BADGES ───────────────────────────────────── */
.pill{{
  display:inline-flex;align-items:center;gap:4px;
  padding:3px 11px;border-radius:18px;font-size:.7rem;
  font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  font-family:'Epilogue',sans-serif;
}}
.pill.live{{background:rgba(0,212,133,0.12);color:{EMERALD};border:1px solid rgba(0,212,133,0.25);}}
.pill.warn{{background:rgba(245,158,11,0.12);color:{AMBER};border:1px solid rgba(245,158,11,0.25);}}
.pill.info{{background:rgba(14,165,233,0.12);color:{AZURE};border:1px solid rgba(14,165,233,0.25);}}
.pill.gold{{background:rgba(232,180,56,0.12);color:{GOLD};border:1px solid rgba(232,180,56,0.25);}}
.sec-badge{{
  display:inline-block;padding:2px 8px;border-radius:7px;
  font-size:.63rem;font-weight:700;letter-spacing:.04em;
  background:rgba(124,92,250,0.12);color:{VIOLET};
  border:1px solid rgba(124,92,250,0.22);
  font-family:'Epilogue',sans-serif;
}}

/* ── ALERTS ───────────────────────────────────────────── */
.abox{{
  border-radius:12px;padding:14px 18px;margin-bottom:9px;
  border-left:3px solid;font-size:.84rem;line-height:1.65;
  font-family:'Epilogue',sans-serif;
}}
.abox.warn{{background:rgba(245,158,11,0.07);border-color:{AMBER};color:{p.TEXT2};}}
.abox.danger{{background:rgba(255,57,96,0.07);border-color:{RUBY};color:{p.TEXT2};}}
.abox.ok{{background:rgba(0,212,133,0.07);border-color:{EMERALD};color:{p.TEXT2};}}
.abox.info{{background:rgba(14,165,233,0.07);border-color:{AZURE};color:{p.TEXT2};}}
.abox-title{{font-weight:800;margin-bottom:4px;font-size:.88rem;color:{p.TEXT};}}

/* ── PROGRESS BARS ────────────────────────────────────── */
.prog-wrap{{background:{p.CARD2};border-radius:6px;height:7px;overflow:hidden;margin-top:3px;}}
.prog-bar{{height:7px;border-radius:6px;transition:width .7s cubic-bezier(.34,1.56,.64,1);}}

/* ── LANDING CARDS ────────────────────────────────────── */
.land-card{{
  background:rgba(8,9,30,0.8);backdrop-filter:blur(16px);
  border:1px solid {p.BORDER};border-radius:18px;padding:28px 20px;
  text-align:center;
  transition:transform .28s cubic-bezier(.34,1.56,.64,1),box-shadow .28s,border-color .28s;
  box-shadow:0 4px 24px {p.SHADOW};height:100%;position:relative;overflow:hidden;
}}
.land-card::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,{GOLD}60,transparent);
  opacity:0;transition:opacity .25s;
}}
.land-card:hover{{
  transform:translateY(-6px) scale(1.01);
  box-shadow:0 20px 48px {p.SHADOW};border-color:{GOLD}40;
}}
.land-card:hover::before{{opacity:1;}}
.land-icon{{font-size:2.4rem;margin-bottom:12px;display:block;}}
.land-title{{
  font-size:.98rem;font-weight:800;color:{p.TEXT};margin-bottom:7px;
  font-family:'Epilogue',sans-serif;
}}
.land-desc{{font-size:.78rem;color:{p.MUTED};line-height:1.65;}}

/* ── STAT ROW ─────────────────────────────────────────── */
.stat-row{{
  display:flex;justify-content:space-between;padding:8px 0;
  border-bottom:1px solid {p.BORDER};font-size:.82rem;
}}
.stat-row:last-child{{border-bottom:none;}}
.stat-lbl{{color:{p.MUTED};font-family:'Epilogue',sans-serif;}}
.stat-val{{
  color:{p.TEXT};font-weight:500;font-family:'DM Mono',monospace;
}}

/* ── MISC ─────────────────────────────────────────────── */
.rich-divider{{
  height:1px;
  background:linear-gradient(90deg,transparent,{GOLD}30,{AMBER}20,transparent);
  border:none;margin:28px 0;
}}
.pos{{color:{EMERALD}!important;font-weight:600;}}
.neg{{color:{RUBY}!important;font-weight:600;}}
.gold{{color:{GOLD}!important;}}

*::-webkit-scrollbar{{width:5px;height:5px;}}
*::-webkit-scrollbar-track{{background:{p.BG};}}
*::-webkit-scrollbar-thumb{{background:{p.BORDER2};border-radius:3px;}}
*::-webkit-scrollbar-thumb:hover{{background:{GOLD};}}
::selection{{background:{GOLD}30;color:{p.TEXT};}}

/* Number formatting in Streamlit metrics */
[data-testid="stMetricValue"]{{
  font-family:'DM Mono',monospace!important;font-size:1.4rem!important;
}}
</style>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# GSE SECTOR MAP
# ─────────────────────────────────────────────────────────────────────────────
GSE_SECTORS = {
    "GCB":"Banking","CAL":"Banking","EGL":"Banking","SCB":"Banking",
    "SOGEGH":"Banking","ADB":"Banking","ACCESS":"Banking","RBGH":"Banking",
    "ABSA":"Banking","FIDELITY":"Banking","HFC":"Banking","NTHBNK":"Banking",
    "NIB":"Banking","UNIBANK":"Banking","BSIC":"Banking",
    "MTNGH":"Telecom","SAMBA":"Telecom",
    "TOTAL":"Oil & Gas","GOIL":"Oil & Gas",
    "FML":"Food & Bev","GGBL":"Beverages","TBL":"Beverages","FAN":"Food & Bev",
    "UNIL":"Consumer","PBC":"Agriculture","OTUMFUO":"Agriculture",
    "ANGLOGOLD":"Mining",
    "SPL":"Manufacturing","BOPP":"Manufacturing","CPC":"Manufacturing",
    "CLYD":"Insurance","SIC":"Insurance","ENTERPRISE":"Insurance",
    "CMLT":"Insurance","HAP":"Insurance","HORDS":"Insurance","STARASS":"Insurance",
    "DOCK":"Transport","PKL":"Transport","TRANSOL":"Transport",
    "GWEB":"Technology",
}

SECTOR_COLORS = {
    "Banking":VIOLET,"Telecom":TEAL,"Oil & Gas":AMBER,"Food & Bev":EMERALD,
    "Beverages":AZURE,"Consumer":ROSE,"Agriculture":"#84cc16",
    "Mining":"#94a3b8","Manufacturing":INDIGO,"Insurance":"#f97316",
    "Transport":"#22d3ee","Technology":"#ec4899","Other":SLATE,
}


def get_sector(ticker):
    return GSE_SECTORS.get(ticker.upper(), "Other")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────
_ICONS = {"":"📊","b":"💼","g":"📈","r":"📉","y":"💰","t":"🌊","pk":"🌸","vi":"🔮"}


def kpi(label, value, sub="", cls="", delta=None, icon=None):
    delta_html = ""
    if delta is not None:
        dc  = "pos" if delta >= 0 else "neg"
        arr = "▲" if delta >= 0 else "▼"
        delta_html = f"<div class='kpi-delta {dc}'>{arr} {abs(delta):.2f}%</div>"
    sub_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    ico = icon or _ICONS.get(cls, "📊")
    return (
        f"<div class='kpi {cls}'>"
        f"<div class='kpi-glow'></div>"
        f"<span class='kpi-icon'>{ico}</span>"
        f"<div class='kpi-lbl'>{label}</div>"
        f"<div class='kpi-val'>{value}</div>"
        f"{sub_html}{delta_html}</div>"
    )


def insight(icon, label, value, cls=""):
    return (
        f"<div class='ibox'><div class='ibox-icon'>{icon}</div>"
        f"<div class='ibox-lbl'>{label}</div>"
        f"<div class='ibox-val {cls}'>{value}</div></div>"
    )


def mover_card(ticker, price, chg, chga, is_top=False):
    cls  = "pos" if chg >= 0 else "neg"
    arr  = "▲" if chg >= 0 else "▼"
    sec  = get_sector(ticker)
    top_cls = " top-mover" if is_top else ""
    return (
        f"<div class='mover{top_cls}'>"
        f"<div class='mover-tick'>{ticker}</div>"
        f"<div style='font-size:.6rem;margin:-4px 0 6px;'><span class='sec-badge'>{sec}</span></div>"
        f"<div class='mover-price'>GHS {price:.4f}</div>"
        f"<div class='mover-chg {cls}'>{arr} {abs(chg):.2f}%</div>"
        f"<div style='font-size:.7rem;color:#424870;margin-top:5px;font-family:DM Mono,monospace;'>"
        f"Δ {chga:+.4f}</div></div>"
    )


def shdr(text, sub=None):
    p = th()
    sub_part = (f"<span style='font-size:.76rem;font-weight:400;opacity:.5;margin-left:8px;"
                f"font-family:Epilogue,sans-serif;'>{sub}</span>") if sub else ""
    st.markdown(f"<div class='shdr'>{text}{sub_part}</div>", unsafe_allow_html=True)


def alert_box(title, body, cls="info"):
    icons = {"warn":"⚠️","danger":"🚨","ok":"✅","info":"ℹ️","gold":"✦"}
    return (
        f"<div class='abox {cls}'>"
        f"<div class='abox-title'>{icons.get(cls,'')} {title}</div>"
        f"{body}</div>"
    )


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
    if re.search(r"\bBought\b", desc, re.I): return "Buy"
    if re.search(r"\bSold\b",   desc, re.I): return "Sell"
    if re.search(r"Dividend|Div\b", desc, re.I): return "Dividend"
    if re.search(r"Contribution|Funding|Deposit", desc, re.I): return "Credit"
    if re.search(r"Withdrawal|Transfer.*Payout", desc, re.I): return "Withdrawal"
    return "Other"


def fmt_ghs(v, places=2):
    """Format a GHS value with DM Mono style."""
    return f"GHS {v:,.{places}f}"


# ─────────────────────────────────────────────────────────────────────────────
# LIVE PRICES
# ─────────────────────────────────────────────────────────────────────────────
def _parse_gse_api(data, tickers):
    norm_to_orig = {_normalize(t): t for t in tickers}
    wanted, results = set(norm_to_orig), {}
    for item in data:
        sym = _normalize(item.get("name", ""))
        if sym not in wanted:
            continue
        price = _to_float(item.get("price"))
        if not price or price <= 0:
            continue
        chg  = _to_float(item.get("change", 0))
        prev = price - chg if chg else price
        results[norm_to_orig[sym]] = {
            "price": price,
            "change_abs": chg,
            "change_pct": round((chg / prev * 100) if prev else 0.0, 2),
        }
    return results


def _parse_afx_html(html, tickers):
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
            hdrs = [th_tag.get_text(strip=True) for th_tag in tbl.find_all("th")]
            if "Ticker" in hdrs and "Price" in hdrs:
                table = tbl
                break
    if not table:
        return {}
    headers    = [th_tag.get_text(strip=True) for th_tag in table.find_all("th")]
    ticker_idx = headers.index("Ticker")
    price_idx  = headers.index("Price")
    change_idx = headers.index("Change") if "Change" in headers else None
    for tr in table.find("tbody").find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) <= price_idx:
            continue
        sym   = _normalize(cells[ticker_idx].get_text(strip=True))
        if sym not in wanted:
            continue
        price = _to_float(cells[price_idx].get_text(strip=True))
        if not price or price <= 0:
            continue
        chg  = (_to_float(cells[change_idx].get_text(strip=True)) or 0.0
                if change_idx and len(cells) > change_idx else 0.0)
        prev = price - chg
        results[norm_to_orig[sym]] = {
            "price": price,
            "change_abs": chg,
            "change_pct": round((chg / prev * 100) if prev else 0.0, 2),
        }
    return results


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_live(tickers):
    try:
        r = requests.get("https://dev.kwayisi.org/apis/gse/live",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            return _parse_gse_api(r.json(), tickers)
    except Exception:
        pass
    try:
        r = requests.get("https://afx.kwayisi.org/gse/",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=10, verify=False)
        if r.status_code == 200:
            return _parse_afx_html(r.text, tickers)
    except Exception:
        pass
    return {}


def get_live_prices(tickers):
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
def parse_pdf(pdf_bytes):
    equities, transactions, portfolio_summary, funds_data = [], [], {}, {}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = full_text.split("\n")

    for i, line in enumerate(lines):
        if "Total Value" in line and "Allocation" in line:
            for l in lines[i+1:i+10]:
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
        r"IC Liquidity\s+([\d,\.]+)\s+-([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)",
        full_text)
    if m:
        funds_data = {
            "name": "IC Liquidity",
            "invested": float(m.group(1).replace(",", "")),
            "redeemed": float(m.group(2).replace(",", "")),
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
                "ticker": m.group(1),
                "qty": qty,
                "avg_cost": cost,
                "statement_price": float(m.group(5)),
                "live_price": None,
                "market_value": mv,
                "total_cost": tc,
                "gain_loss": gl,
                "gain_pct": (gl / tc * 100) if tc else 0,
                "sector": get_sector(m.group(1)),
            })

    for line in lines:
        line = line.strip()
        dm   = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.*)", line)
        if not dm:
            continue
        date_str, rest = dm.group(1), dm.group(2).strip()
        nums = re.findall(r"-?[\d,]+\.\d{2}", rest)
        if len(nums) >= 2:
            try:
                credit = float(nums[-2].replace(",", ""))
                debit  = float(nums[-1].replace(",", ""))
                desc   = rest[: rest.rfind(nums[-2])].strip()
                ttype  = tx_type(desc)
                transactions.append({
                    "date": datetime.strptime(date_str, "%d/%m/%Y"),
                    "date_str": date_str,
                    "description": desc,
                    "credit": credit if credit > 0 else 0,
                    "debit":  abs(debit) if debit < 0 else 0,
                    "type":   ttype,
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
        "equities": equities, "transactions": transactions,
        "portfolio_summary": portfolio_summary, "funds": funds_data,
        "client_name":    _field("Client Name:"),
        "account_number": _field("Account Number:"),
        "report_date":    _field("Report Date:"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# INJECT LIVE PRICES
# ─────────────────────────────────────────────────────────────────────────────
def inject_live_prices(equities, live):
    out = []
    for e in equities:
        e = e.copy()
        if e["ticker"] in live:
            lp = live[e["ticker"]]["price"]
            mv = e["qty"] * lp
            gl = mv - e["total_cost"]
            e.update({
                "live_price": lp, "market_value": mv, "gain_loss": gl,
                "gain_pct": (gl / e["total_cost"] * 100) if e["total_cost"] else 0,
                "change_pct": live[e["ticker"]]["change_pct"],
                "change_abs": live[e["ticker"]]["change_abs"],
            })
        else:
            e["live_price"] = e["change_pct"] = e["change_abs"] = None
        out.append(e)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────────────────────
def compute_metrics(eq, txs, ps):
    equities_val = sum(e["market_value"] for e in eq)
    total_cost   = sum(e["total_cost"]   for e in eq)
    total_gain   = sum(e["gain_loss"]    for e in eq)
    gain_pct     = (total_gain / total_cost * 100) if total_cost else 0
    cash_val     = ps.get("Cash",  {}).get("value", 0)
    funds_val    = ps.get("Funds", {}).get("value", 0)
    total_value  = equities_val + cash_val + funds_val

    net_contributions  = sum(t["credit"] for t in txs if t["type"] == "Credit")
    net_withdrawals    = sum(t["debit"]  for t in txs if t["type"] == "Withdrawal")
    net_invested       = net_contributions - net_withdrawals
    total_credits_all  = sum(t["credit"] for t in txs)
    total_debits_all   = sum(t["debit"]  for t in txs)
    overall_roi        = ((total_value - net_invested) / net_invested * 100) if net_invested > 0 else 0
    dividend_income    = sum(t["credit"] for t in txs if t["type"] == "Dividend")

    cagr = None
    funding_txs = [t for t in txs if t["type"] == "Credit"]
    if funding_txs and net_invested > 0 and total_value > 0:
        first_date = min(t["date"] for t in funding_txs)
        years = (datetime.now() - first_date).days / 365.25
        if years >= 0.1:
            cagr = ((total_value / net_invested) ** (1.0 / years) - 1) * 100

    weights = [e["market_value"] / equities_val for e in eq] if equities_val else []
    hhi     = round(sum(w**2 for w in weights) * 10000) if weights else 0

    sectors_used = len(set(e["sector"] for e in eq))
    winners      = sum(1 for e in eq if e["gain_pct"] >= 0)
    n            = len(eq)
    div_score    = (len([e for e in eq if e["market_value"]/equities_val > 0.05]) / n * 100) if n and equities_val else 0
    win_score    = (winners / n * 100) if n else 0
    roi_score    = min(100, max(0, overall_roi + 30))
    conc_score   = max(0, 100 - hhi / 100)
    sec_score    = min(100, sectors_used / max(1, n) * 100 * 3)
    health_score = round(0.30*roi_score + 0.20*win_score + 0.15*div_score + 0.20*conc_score + 0.15*sec_score)
    health_score = max(0, min(100, health_score))

    active_month = "N/A"
    if txs:
        _tdf = pd.DataFrame(txs)
        _tdf["month"] = _tdf["date"].dt.to_period("M")
        active_month  = str(_tdf["month"].value_counts().idxmax())

    best    = max(eq, key=lambda e: e["gain_pct"])
    worst   = min(eq, key=lambda e: e["gain_pct"])
    biggest = max(eq, key=lambda e: e["market_value"])

    return dict(
        equities_val=equities_val, total_cost=total_cost, total_gain=total_gain,
        gain_pct=gain_pct, cash_val=cash_val, funds_val=funds_val,
        total_value=total_value, net_invested=net_invested,
        net_contributions=net_contributions, net_withdrawals=net_withdrawals,
        total_credits_all=total_credits_all, total_debits_all=total_debits_all,
        overall_roi=overall_roi, cagr=cagr, dividend_income=dividend_income,
        hhi=hhi, health_score=health_score, winners=winners,
        active_month=active_month, best=best, worst=worst, biggest=biggest,
        sectors_used=sectors_used,
    )


def compute_advanced_metrics(eq, txs, m):
    """
    Sharpe (approximate), Max Drawdown, ENP, Volatility, Consistency,
    Dividend Yield, Holding Periods.
    Risk-free rate: Ghana 91-day T-bill ~18% p.a. (approximate)
    """
    RF_RATE = 18.0  # %

    # Portfolio volatility (cross-sectional dispersion of returns)
    if eq and m["equities_val"]:
        returns = [e["gain_pct"] for e in eq]
        weights = [e["market_value"] / m["equities_val"] for e in eq]
        w_mean  = sum(r*w for r, w in zip(returns, weights))
        var     = sum(w*(r - w_mean)**2 for r, w in zip(returns, weights))
        port_vol = var**0.5
    else:
        port_vol = 0.0

    cagr_v = m.get("cagr") or 0.0
    sharpe  = (cagr_v - RF_RATE) / port_vol if port_vol > 1e-6 else None

    # Max drawdown from cumulative cash-flow series
    max_dd = 0.0
    if txs:
        df = pd.DataFrame(txs).sort_values("date")
        df["net"]   = df["credit"] - df["debit"]
        df["cumul"] = df["net"].cumsum()
        peak = df["cumul"].cummax()
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.where(peak > 0, (df["cumul"] - peak) / peak * 100, 0.0)
        max_dd = float(np.min(dd))

    # ENP — effective number of positions
    enp = round(10000 / m["hhi"], 1) if m["hhi"] > 0 else float(len(eq))

    # Consistency — % stocks within ±5% of cost
    near_flat = sum(1 for e in eq if e["gain_pct"] > -5)
    consistency = near_flat / len(eq) * 100 if eq else 0

    # Dividend yield
    div_yield_cost   = m["dividend_income"] / m["total_cost"]   * 100 if m["total_cost"]   else 0
    div_yield_market = m["dividend_income"] / m["equities_val"] * 100 if m["equities_val"] else 0

    # Holding period: find earliest Buy tx per ticker
    holding_periods = {}
    buy_txs = [t for t in txs if t["type"] == "Buy"]
    for e in eq:
        matches = [t for t in buy_txs if e["ticker"] in t["description"].upper()]
        if matches:
            first_buy = min(t["date"] for t in matches)
            days = (datetime.now() - first_buy).days
            holding_periods[e["ticker"]] = days
    avg_holding = int(np.mean(list(holding_periods.values()))) if holding_periods else None

    return dict(
        sharpe=sharpe, max_dd=max_dd, enp=enp, port_vol=port_vol,
        consistency=consistency, div_yield_cost=div_yield_cost,
        div_yield_market=div_yield_market, rf_rate=RF_RATE,
        holding_periods=holding_periods, avg_holding=avg_holding,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def chart_gain_loss(eq):
    p   = th()
    df  = pd.DataFrame(eq).sort_values("gain_pct")
    clr = [EMERALD if v >= 0 else RUBY for v in df["gain_pct"]]
    fig = go.Figure(go.Bar(
        x=df["gain_pct"], y=df["ticker"], orientation="h",
        marker=dict(color=clr, opacity=0.85, line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df["gain_pct"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        hovertemplate="<b>%{y}</b><br>Return: %{x:.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="Return per Stock (%)", xaxis_title="Return (%)", **T(), height=380)
    return fig


def chart_performance_attribution(eq, equities_val):
    p  = th()
    df = pd.DataFrame(eq).copy()
    df["contribution_pct"] = (df["gain_loss"] / equities_val * 100) if equities_val else 0
    df = df.sort_values("contribution_pct")
    clr = [EMERALD if v >= 0 else RUBY for v in df["contribution_pct"]]
    fig = go.Figure(go.Bar(
        x=df["contribution_pct"], y=df["ticker"], orientation="h",
        marker=dict(color=clr, opacity=0.85, line=dict(width=0)),
        text=[f"{v:+.2f}%" for v in df["contribution_pct"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        customdata=df["gain_loss"],
        hovertemplate="<b>%{y}</b><br>Contribution: %{x:+.2f}%<br>P&L: GHS %{customdata:,.2f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(
        title="Performance Attribution — % contribution of each stock to portfolio P&L",
        xaxis_title="Contribution (% of equity value)", **T(), height=380)
    return fig


def chart_sector_donut(eq):
    p      = th()
    df     = pd.DataFrame(eq)
    sec_df = df.groupby("sector")["market_value"].sum().reset_index().sort_values("market_value", ascending=False)
    total  = sec_df["market_value"].sum()
    sec_df["pct"] = sec_df["market_value"] / total * 100
    clr = [SECTOR_COLORS.get(s, p.MUTED) for s in sec_df["sector"]]
    fig = go.Figure(go.Pie(
        labels=sec_df["sector"], values=sec_df["market_value"], hole=0.62,
        marker=dict(colors=clr, line=dict(color=p.BG, width=3)),
        texttemplate="<b>%{label}</b><br>%{percent:.1%}",
        textfont=dict(size=11, family="Epilogue"),
        hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f}<br>%{percent:.1%}<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        title="Sector Allocation",
        annotations=[dict(text=f"<b>{len(sec_df)}</b><br><span style='font-size:9px'>Sectors</span>",
                          x=0.5, y=0.5, font=dict(size=18, color=p.TEXT, family="DM Mono"), showarrow=False)],
        **T(), height=340)
    return fig


def chart_sector_performance(eq):
    """Grouped bar: sector → market value, cost, total gain."""
    p  = th()
    df = pd.DataFrame(eq)
    sg = df.groupby("sector").agg(
        mv =("market_value","sum"),
        tc =("total_cost","sum"),
        gl =("gain_loss","sum"),
    ).reset_index().sort_values("mv", ascending=False)
    sg["ret"] = sg["gl"] / sg["tc"] * 100
    clr = [SECTOR_COLORS.get(s, p.MUTED) for s in sg["sector"]]
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Market Value vs Cost by Sector",
                                        "Sector Return (%)"],
                        column_widths=[0.6, 0.4])
    fig.add_trace(go.Bar(name="Cost Basis", x=sg["sector"], y=sg["tc"],
                         marker_color=AZURE, opacity=0.65), row=1, col=1)
    fig.add_trace(go.Bar(name="Market Value", x=sg["sector"], y=sg["mv"],
                         marker_color=GOLD, opacity=0.9), row=1, col=1)
    bar_clr = [EMERALD if v >= 0 else RUBY for v in sg["ret"]]
    fig.add_trace(go.Bar(name="Return %", x=sg["sector"], y=sg["ret"],
                         marker=dict(color=bar_clr, opacity=0.85),
                         text=[f"{v:+.1f}%" for v in sg["ret"]], textposition="outside",
                         textfont=dict(size=10, family="DM Mono", color=p.TEXT2),
                         showlegend=False), row=1, col=2)
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", row=1, col=2)
    layout = {**T(), "barmode":"group", "height":360,
              "xaxis": dict(tickangle=-20, gridcolor=p.BORDER),
              "xaxis2":dict(tickangle=-20, gridcolor=p.BORDER),
              "yaxis": dict(title="GHS", gridcolor=p.BORDER),
              "yaxis2":dict(title="Return (%)", gridcolor=p.BORDER)}
    fig.update_layout(**layout)
    return fig


def chart_portfolio_efficiency(eq):
    p  = th()
    df = pd.DataFrame(eq).copy()
    df["efficiency"] = df["gain_loss"] / df["total_cost"].replace(0, 1) * 100
    df = df.sort_values("efficiency")
    clr = [EMERALD if v >= 0 else RUBY for v in df["efficiency"]]
    fig = go.Figure(go.Bar(
        x=df["efficiency"], y=df["ticker"], orientation="h",
        marker=dict(color=clr, opacity=0.85, line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df["efficiency"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        customdata=df["gain_loss"],
        hovertemplate="<b>%{y}</b><br>Efficiency: %{x:+.1f}%<br>P&L: GHS %{customdata:,.2f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="Portfolio Efficiency — Gain / GHS Invested (%)",
                      xaxis_title="ROI (%)", **T(), height=360)
    return fig


def chart_risk_return_scatter(eq, equities_val):
    """Bubble: x=weight, y=return, size=market value, colour=sector."""
    p  = th()
    df = pd.DataFrame(eq).copy()
    df["weight"] = df["market_value"] / equities_val * 100 if equities_val else 0
    equal_w = 100 / len(eq) if eq else 10
    fig = go.Figure()
    for sector in df["sector"].unique():
        sub = df[df["sector"] == sector]
        fig.add_trace(go.Scatter(
            x=sub["weight"], y=sub["gain_pct"],
            mode="markers+text", name=sector,
            marker=dict(
                size = sub["market_value"] / sub["market_value"].max() * 40 + 12,
                color = SECTOR_COLORS.get(sector, p.MUTED),
                opacity = 0.82,
                line = dict(color=p.BG, width=2),
            ),
            text=sub["ticker"],
            textposition="top center",
            textfont=dict(size=9, color=p.TEXT2, family="Epilogue"),
            customdata=sub[["market_value","gain_loss","sector"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Sector: %{customdata[2]}<br>"
                "Weight: %{x:.1f}%<br>"
                "Return: %{y:+.1f}%<br>"
                "Market Value: GHS %{customdata[0]:,.2f}<br>"
                "P&L: GHS %{customdata[1]:+,.2f}"
                "<extra></extra>"
            ),
        ))
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.add_vline(x=equal_w, line_color=GOLD, line_dash="dot", line_width=1,
                  annotation_text=f" Equal weight ({equal_w:.1f}%)",
                  annotation_font=dict(color=GOLD, size=9, family="DM Mono"))
    # Quadrant labels
    for txt, ax, ay in [("High weight\nHigh return", 0.92, 0.95),
                         ("Low weight\nHigh return", 0.05, 0.95),
                         ("High weight\nLow return", 0.92, 0.05),
                         ("Low weight\nLow return", 0.05, 0.05)]:
        fig.add_annotation(
            xref="paper", yref="paper", x=ax, y=ay,
            text=txt.replace("\n","<br>"),
            showarrow=False,
            font=dict(size=8, color=p.MUTED, family="Epilogue"),
            align="center", opacity=0.6,
        )
    fig.update_layout(
        title="Risk / Return Matrix — Bubble size = Market Value",
        xaxis_title="Portfolio Weight (%)",
        yaxis_title="Return (%)",
        **T(), height=440,
    )
    return fig


def chart_pl_waterfall(eq):
    p     = th()
    df    = pd.DataFrame(eq).sort_values("gain_loss")
    total = df["gain_loss"].sum()
    tickers = df["ticker"].tolist() + ["TOTAL"]
    vals    = df["gain_loss"].tolist() + [total]
    clr     = [EMERALD if v >= 0 else RUBY for v in vals]
    clr[-1] = GOLD if total >= 0 else RUBY
    fig = go.Figure(go.Bar(
        x=tickers, y=vals,
        marker=dict(color=clr, opacity=[0.8]*len(df) + [1.0], line=dict(width=0)),
        text=[f"{'+'if v>=0 else ''}GHS {v:,.0f}" for v in vals],
        textposition="outside", textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        hovertemplate="<b>%{x}</b><br>P&L: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(title="P&L Contribution per Stock (GHS)", yaxis_title="GHS", **T(), height=340)
    return fig


def chart_market_vs_cost(eq):
    p  = th()
    df = pd.DataFrame(eq).sort_values("market_value", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Cost Basis", x=df["ticker"], y=df["total_cost"],
                         marker_color=AZURE, opacity=0.7,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Cost</extra>"))
    fig.add_trace(go.Bar(name="Market Value", x=df["ticker"], y=df["market_value"],
                         marker_color=GOLD, opacity=0.9,
                         hovertemplate="%{x}: GHS %{y:,.2f}<extra>Market</extra>"))
    for _, row in df.iterrows():
        gl = row["gain_pct"]
        fig.add_annotation(
            x=row["ticker"], y=max(row["total_cost"], row["market_value"]),
            text=f"{gl:+.1f}%", showarrow=False, yshift=12,
            font=dict(color=EMERALD if gl >= 0 else RUBY, size=9, family="DM Mono"),
        )
    fig.update_layout(title="Market Value vs Cost Basis", yaxis_title="GHS",
                      barmode="group", **T(), height=380)
    return fig


def chart_allocation_treemap(ps):
    p    = th()
    cmap = {"Equities":VIOLET,"Cash":AZURE,"Funds":GOLD,"Fixed Income":TEAL}
    labels, parents, values, clr = [], [], [], []
    for k, v in ps.items():
        if k == "Total" or v["value"] == 0:
            continue
        labels.append(k); parents.append(""); values.append(v["value"])
        clr.append(cmap.get(k, p.MUTED))
    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        marker=dict(colors=clr, line=dict(width=3, color=p.BG)),
        texttemplate="<b>%{label}</b><br>GHS %{value:,.0f}<br>%{percentRoot:.1%}",
        textfont=dict(size=12, family="Epilogue"),
        hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f}<br>%{percentRoot:.1%}<extra></extra>",
    ))
    fig.update_layout(title="Asset Class Allocation", height=300,
                      **{**T(), "margin":dict(l=8,r=8,t=48,b=8)})
    return fig


def chart_drawdown(txs, total_value):
    """Drawdown from cumulative cash-flow peak — proxy for portfolio drawdown."""
    p  = th()
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    # Scale to portfolio value
    if df["cumul"].iloc[-1] > 0:
        df["scaled"] = df["cumul"] * (total_value / df["cumul"].iloc[-1])
    else:
        df["scaled"] = df["cumul"]
    peak = df["scaled"].cummax()
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak > 0, (df["scaled"] - peak) / peak * 100, 0.0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=dd, mode="lines",
        fill="tozeroy", fillcolor=f"rgba(255,57,96,0.10)",
        line=dict(color=RUBY, width=2), name="Drawdown",
        hovertemplate="%{x|%b %d %Y}<br>Drawdown: %{y:.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(
        title="Portfolio Drawdown (%) from Peak",
        xaxis_title="Date", yaxis_title="Drawdown (%)",
        **T(), height=300)
    return fig


def chart_monthly_cashflow_heatmap(txs):
    """Calendar-grid heatmap: net cash flow by month × year."""
    p  = th()
    if not txs:
        return None
    df = pd.DataFrame(txs)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["net"]   = df["credit"] - df["debit"]
    pivot = df.groupby(["year","month"])["net"].sum().reset_index()
    pivot = pivot.pivot(index="year", columns="month", values="net").fillna(0)

    months = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
    z_vals = []
    y_vals = []
    for yr in sorted(pivot.index, reverse=True):
        row = [float(pivot.loc[yr, col]) if col in pivot.columns else 0 for col in range(1,13)]
        z_vals.append(row)
        y_vals.append(str(yr))

    fig = go.Figure(go.Heatmap(
        z=z_vals, x=months, y=y_vals,
        colorscale=[[0, RUBY], [0.5, p.CARD2], [1, EMERALD]],
        zmid=0,
        text=[[f"GHS {v:+,.0f}" if v != 0 else "—" for v in row] for row in z_vals],
        texttemplate="%{text}",
        textfont=dict(size=9, family="DM Mono"),
        hovertemplate="<b>%{y} %{x}</b><br>Net Flow: GHS %{z:+,.2f}<extra></extra>",
        showscale=True,
        colorbar=dict(
            tickfont=dict(color=p.TEXT2, size=9, family="DM Mono"),
            outlinecolor=p.BORDER, outlinewidth=1,
            title=dict(text="GHS", font=dict(color=p.MUTED, size=9)),
        ),
    ))
    fig.update_layout(
        title="Monthly Net Cash Flow Calendar",
        xaxis=dict(side="top", gridcolor=p.BORDER, tickcolor=p.MUTED,
                   tickfont=dict(color=p.TEXT2, family="Epilogue")),
        yaxis=dict(gridcolor=p.BORDER, tickcolor=p.MUTED,
                   tickfont=dict(color=p.TEXT2, family="DM Mono")),
        **{**T(), "margin":dict(l=16,r=16,t=80,b=16)},
        height=max(200, len(y_vals)*50 + 90),
    )
    return fig


def chart_cashflow(txs):
    p  = th()
    df = pd.DataFrame(txs)
    if df.empty:
        return None
    df["month"] = df["date"].dt.to_period("M")
    m  = df.groupby("month").agg(credits=("credit","sum"), debits=("debit","sum")).reset_index()
    m["month_str"] = m["month"].astype(str)
    m["net"]    = m["credits"] - m["debits"]
    m["cumnet"] = m["net"].cumsum()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65,0.35],
                        vertical_spacing=0.06,
                        subplot_titles=["Monthly Credits & Debits","Cumulative Net Flow"])
    fig.add_trace(go.Bar(name="Credits", x=m["month_str"], y=m["credits"],
                         marker_color=EMERALD, opacity=0.8), row=1, col=1)
    fig.add_trace(go.Bar(name="Debits",  x=m["month_str"], y=m["debits"],
                         marker_color=RUBY,    opacity=0.8), row=1, col=1)
    fig.add_trace(go.Scatter(name="Net", x=m["month_str"], y=m["net"],
                             mode="lines+markers",
                             line=dict(color=GOLD, width=2.5),
                             marker=dict(size=5, color=GOLD)), row=1, col=1)
    net_clr = [EMERALD if v >= 0 else RUBY for v in m["cumnet"]]
    fig.add_trace(go.Bar(name="Cumulative", x=m["month_str"], y=m["cumnet"],
                         marker_color=net_clr, opacity=0.72, showlegend=False), row=2, col=1)
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1, row=1, col=1)
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1, row=2, col=1)
    layout = {**T(), "barmode":"group", "height":500,
              "xaxis2":dict(tickangle=-30, gridcolor=p.BORDER),
              "yaxis" :dict(title="GHS", gridcolor=p.BORDER),
              "yaxis2":dict(title="GHS", gridcolor=p.BORDER)}
    fig.update_layout(**layout)
    return fig


def chart_cumulative(txs, total_value):
    p  = th()
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    profit = total_value - df["cumul"].iloc[-1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        fill="tozeroy", fillcolor=f"rgba(232,180,56,0.08)",
        line=dict(color=GOLD, width=2.5), name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>Invested: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=total_value, line_color=EMERALD, line_dash="dash", line_width=2,
                  annotation_text=f" Portfolio Value GHS {total_value:,.0f}",
                  annotation_font=dict(color=EMERALD, size=10, family="DM Mono"))
    fig.update_layout(
        title=f"Net Invested vs Current Value ({'+'if profit>=0 else ''}GHS {profit:,.0f} unrealised)",
        xaxis_title="Date", yaxis_title="GHS", **T(), height=320)
    return fig


def chart_breakeven(eq):
    p      = th()
    losers = [e for e in eq if e["gain_pct"] < 0]
    if not losers:
        return None
    df = pd.DataFrame(losers)
    pc = df["live_price"].fillna(df["statement_price"])
    pct_need = (df["avg_cost"] - pc) / pc * 100
    gap_ghs  = (df["avg_cost"] - pc) * df["qty"]
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Price Gap to Break-even","GHS Loss to Recover"],
                        specs=[[{"type":"xy"},{"type":"xy"}]])
    fig.add_trace(go.Bar(name="Current Price", x=df["ticker"], y=pc,
                         marker_color=RUBY, opacity=0.8), row=1, col=1)
    fig.add_trace(go.Bar(name="Break-even",    x=df["ticker"], y=df["avg_cost"],
                         marker_color=GOLD,    opacity=0.8), row=1, col=1)
    fig.add_trace(go.Scatter(
        name="% Rally Needed", x=df["ticker"], y=pct_need, yaxis="y2",
        mode="markers+text",
        marker=dict(size=13, color=AMBER, symbol="diamond",
                    line=dict(color=p.BG, width=2)),
        text=[f"+{v:.1f}%" for v in pct_need], textposition="top center",
        textfont=dict(color=AMBER, size=9, family="DM Mono"),
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name="GHS to Recover", x=df["ticker"], y=gap_ghs.abs(),
        marker=dict(color=gap_ghs.abs(),
                    colorscale=[[0,GOLD],[1,RUBY]], line=dict(width=0)),
        text=[f"GHS {v:,.0f}" for v in gap_ghs.abs()], textposition="outside",
        textfont=dict(size=9, family="DM Mono"),
    ), row=1, col=2)
    layout = {**T(), "title":"Break-even Analysis — Losing Positions",
              "barmode":"group", "height":380,
              "yaxis" :dict(title="Price (GHS)", gridcolor=p.BORDER),
              "yaxis2":dict(title="% Rally Needed", overlaying="y", side="right",
                            showgrid=False, color=AMBER,
                            tickfont=dict(color=AMBER, family="DM Mono")),
              "yaxis3":dict(title="GHS to Recover", gridcolor=p.BORDER),
              "xaxis2":dict(gridcolor=p.BORDER)}
    fig.update_layout(**layout)
    return fig


def chart_concentration(eq):
    p   = th()
    df  = pd.DataFrame(eq)
    tot = df["market_value"].sum()
    w   = df["market_value"] / tot
    hhi = round((w**2).sum() * 10000)
    if hhi < 1500: risk, rc = "Low",      EMERALD
    elif hhi < 2500: risk, rc = "Moderate", AMBER
    else:            risk, rc = "High",     RUBY
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["HHI Concentration Score","Exposure by Stock"],
                        specs=[[{"type":"indicator"},{"type":"xy"}]])
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta", value=hhi,
        delta=dict(reference=1500, valueformat=".0f",
                   increasing=dict(color=RUBY), decreasing=dict(color=EMERALD)),
        number=dict(font=dict(color=rc, size=34, family="DM Mono"), suffix=" HHI"),
        gauge=dict(
            axis=dict(range=[0,10000], tickcolor=p.MUTED,
                      tickfont=dict(color=p.MUTED, size=8, family="DM Mono")),
            bar=dict(color=rc, thickness=0.28),
            bgcolor=p.CARD2, bordercolor=p.BORDER,
            steps=[dict(range=[0,1500],   color="rgba(0,212,133,0.1)"),
                   dict(range=[1500,2500], color="rgba(245,158,11,0.1)"),
                   dict(range=[2500,10000],color="rgba(255,57,96,0.1)")],
            threshold=dict(line=dict(color=rc, width=3), thickness=0.8, value=hhi),
        ),
        title=dict(text=f"<b>{risk}</b> Concentration",
                   font=dict(color=rc, size=13, family="Epilogue")),
    ), row=1, col=1)
    df_s     = df.sort_values("market_value", ascending=True)
    ws       = (df_s["market_value"] / tot * 100).values
    sec_clr  = [SECTOR_COLORS.get(s, p.MUTED) for s in df_s["sector"]]
    fig.add_trace(go.Bar(
        x=ws, y=df_s["ticker"].values, orientation="h",
        marker=dict(color=sec_clr, line=dict(width=0), opacity=0.85),
        text=[f"{v:.1f}%" for v in ws], textposition="outside",
        textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        customdata=df_s["sector"].values,
        hovertemplate="<b>%{y}</b>: %{x:.1f}%<br>Sector: %{customdata}<extra></extra>",
        showlegend=False,
    ), row=1, col=2)
    layout = {
        "paper_bgcolor":p.BG, "plot_bgcolor":p.CARD,
        "font":dict(color=p.TEXT2, family="DM Mono"),
        "margin":dict(l=16,r=16,t=60,b=16), "height":380,
        "xaxis2":dict(gridcolor=p.BORDER, title="Weight (%)", tickcolor=p.MUTED),
        "yaxis2":dict(gridcolor=p.BORDER, tickcolor=p.MUTED),
        "hoverlabel":dict(bgcolor=p.CARD2, bordercolor=p.BORDER, font=dict(color=p.TEXT)),
        "legend":dict(bgcolor=p.CARD2, bordercolor=p.BORDER),
        "title":dict(font=dict(color=p.TEXT, family="Epilogue", size=14), x=0.01),
    }
    fig.update_layout(**layout)
    return fig, hhi, risk, rc


def chart_dividend_timeline(txs):
    p      = th()
    div_txs = [t for t in txs if t["type"] == "Dividend"]
    if not div_txs:
        return None
    df = pd.DataFrame(div_txs)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    mg = df.groupby("month")["credit"].sum().reset_index()
    fig = go.Figure(go.Bar(
        x=mg["month"], y=mg["credit"],
        marker=dict(color=TEAL, opacity=0.85, line=dict(width=0)),
        text=[f"GHS {v:,.2f}" for v in mg["credit"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=9, family="DM Mono"),
        hovertemplate="%{x}<br>Dividends: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Dividend Income by Month", yaxis_title="GHS", **T(), height=280)
    return fig


def chart_rolling_return(txs, total_value):
    p  = th()
    df = pd.DataFrame(txs).sort_values("date")
    if df.empty:
        return None
    df["net"]   = df["credit"] - df["debit"]
    df["cumul"] = df["net"].cumsum()
    scale = total_value / df["cumul"].iloc[-1] if df["cumul"].iloc[-1] else 1
    df["proxy_value"] = df["cumul"] * scale
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["proxy_value"], mode="lines",
        fill="tozeroy", fillcolor="rgba(6,182,212,0.08)",
        line=dict(color=TEAL, width=2.5), name="Est. Portfolio Value",
        hovertemplate="%{x|%b %d, %Y}<br>Est. Value: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul"], mode="lines",
        line=dict(color=GOLD, width=1.5, dash="dot"), name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>Invested: GHS %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Estimated Portfolio Value Over Time",
                      xaxis_title="Date", yaxis_title="GHS", **T(), height=320)
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
                         marker_color=AMBER, opacity=0.8))
    fig.add_trace(go.Bar(name="Live Price",      x=df["ticker"], y=df["live_price"],
                         marker_color=EMERALD,   opacity=0.9))
    for _, row in df.iterrows():
        c = EMERALD if row["pct_diff"] >= 0 else RUBY
        fig.add_annotation(x=row["ticker"], y=max(row["statement_price"], row["live_price"]),
                           text=f"{row['pct_diff']:+.1f}%", showarrow=False, yshift=12,
                           font=dict(color=c, size=9, family="DM Mono"))
    fig.update_layout(title="Statement vs Live Price", yaxis_title="GHS per Share",
                      barmode="group", **T(), height=320)
    return fig


def chart_stock_weight(eq):
    p  = th()
    df = pd.DataFrame(eq).sort_values("market_value")
    tot= df["market_value"].sum()
    df["weight"] = df["market_value"] / tot * 100
    fig = go.Figure(go.Bar(
        x=df["weight"], y=df["ticker"], orientation="h",
        marker=dict(color=df["weight"],
                    colorscale=[[0,AZURE],[0.4,VIOLET],[1,GOLD]],
                    line=dict(width=0)),
        text=[f"{w:.1f}%" for w in df["weight"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        customdata=df["market_value"],
        hovertemplate="<b>%{y}</b><br>Weight: %{x:.2f}%<br>GHS %{customdata:,.2f}<extra></extra>",
    ))
    fig.update_layout(title="Portfolio Weight by Stock", xaxis_title="Weight (%)",
                      **T(), height=340, showlegend=False)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SMART ALERTS
# ─────────────────────────────────────────────────────────────────────────────
def generate_alerts(eq, m, txs):
    alerts = []
    ev     = m["equities_val"]

    for e in eq:
        wt = e["market_value"] / ev * 100 if ev else 0
        if wt > 30:
            alerts.append(("danger", f"Extreme Concentration: {e['ticker']}",
                f"{e['ticker']} is {wt:.1f}% of equities — far above the 30% danger threshold. "
                f"A single adverse event could cause significant portfolio damage."))
        elif wt > 20:
            alerts.append(("warn", f"High Concentration: {e['ticker']}",
                f"{e['ticker']} is {wt:.1f}% of the equity book. Consider trimming to below 15%."))

    big_losers = [e for e in eq if e["gain_pct"] < -20]
    if big_losers:
        names = ", ".join(e["ticker"] for e in big_losers)
        alerts.append(("warn","Deep Losses > 20%",
            f"{names} are down more than 20% from cost basis. Re-evaluate the investment thesis "
            f"or establish stop-loss levels."))

    # Cash drag
    if m["total_value"] and m["cash_val"] / m["total_value"] > 0.25:
        alerts.append(("info","High Cash Drag",
            f"Cash represents {m['cash_val']/m['total_value']*100:.1f}% of the portfolio. "
            f"Idle cash erodes real returns in a high-inflation environment."))

    # Sector over-exposure
    sec_df = pd.DataFrame(eq).groupby("sector")["market_value"].sum()
    if ev:
        for sec, val in sec_df.items():
            if val / ev > 0.60:
                alerts.append(("warn", f"Sector Over-exposure: {sec}",
                    f"{sec} stocks represent {val/ev*100:.1f}% of equity holdings. "
                    f"Add cross-sector diversification to reduce idiosyncratic risk."))

    # Win rate
    if m["winners"] / len(eq) < 0.40:
        alerts.append(("warn","Low Win Rate",
            f"Only {m['winners']}/{len(eq)} positions are profitable. "
            f"Review underperformers for potential rebalancing opportunities."))

    # Single-sector portfolio
    if m["sectors_used"] == 1:
        alerts.append(("danger","Single-Sector Portfolio",
            "All equity positions are in the same sector. "
            "You have zero sector diversification — any sector-wide shock is fully absorbed."))

    # Only few sectors for large portfolio
    if m["sectors_used"] < 3 and len(eq) >= 5:
        alerts.append(("warn","Limited Sector Diversification",
            f"Only {m['sectors_used']} sectors across {len(eq)} holdings. "
            f"Consider adding exposure to Banking, Telecom, or Oil & Gas to broaden the base."))

    if not alerts:
        alerts.append(("ok","Portfolio Health: Good",
            "No critical concentration issues detected. Win rate is acceptable and sector "
            "diversification is reasonable. Continue monitoring quarterly."))

    return alerts


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    p = th()
    with st.sidebar:
        st.markdown(
            f"<div style='font-size:.7rem;color:{p.MUTED};font-weight:800;"
            f"text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;"
            f"font-family:Epilogue,sans-serif;'>📡 Live GSE Prices</div>",
            unsafe_allow_html=True)
        st.success("✅ GSE-API (dev.kwayisi.org) + afx fallback")
        if st.button("🔄 Refresh Prices", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
        if "pdf_name" in st.session_state:
            st.caption(f"📄 {st.session_state['pdf_name']}")
            if st.button("🗑️ Clear Statement", use_container_width=True):
                st.session_state.pop("pdf_data", None)
                st.session_state.pop("pdf_name", None)
                st.rerun()
        st.divider()
        st.markdown(
            f"<div style='font-size:.7rem;color:{p.MUTED};line-height:1.7;"
            f"font-family:Epilogue,sans-serif;'>"
            f"<b style='color:{GOLD};'>IC Portfolio Analyser v3.0</b><br>"
            f"Elite Edition · March 2026<br>"
            f"For informational purposes only.</div>",
            unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    apply_theme()
    render_sidebar()
    p = th()

    # ── Header ───────────────────────────────────────────────────────────────
    cl, ct, cr = st.columns([1, 7, 2])
    with cl:
        st.markdown(
            f"<div style='font-size:3.2rem;padding-top:4px;line-height:1;"
            f"filter:drop-shadow(0 0 24px {GOLD}60);'>₵</div>",
            unsafe_allow_html=True)
    with ct:
        st.markdown(
            f"<div class='hero-badge'>IC Securities · Ghana Stock Exchange</div>"
            f"<div class='hero'>IC Portfolio Analyser</div>"
            f"<div class='hero-sub'>"
            f"Upload your statement · Live GSE prices · Analytics · Health score · Sector risk"
            f"</div>",
            unsafe_allow_html=True)

    # ── Upload / persist ──────────────────────────────────────────────────────
    uploaded = st.file_uploader("**📄 Drop your IC Securities Account Statement (PDF)**",
                                type=["pdf"])
    if uploaded is not None:
        new_bytes = uploaded.read()
        if st.session_state.get("pdf_name") != uploaded.name or "pdf_data" not in st.session_state:
            with st.spinner("📄 Parsing statement…"):
                st.session_state["pdf_data"] = parse_pdf(new_bytes)
                st.session_state["pdf_name"] = uploaded.name

    if "pdf_data" not in st.session_state:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        cols = st.columns(6)
        features = [
            ("📊","Overview & KPIs",   "Value, ROI, CAGR, Health Score & Smart Alerts."),
            ("📈","Performance",        "Attribution, P&L waterfall, sector charts."),
            ("🔬","Analytics",          "Sharpe, MaxDD, ENP, Risk/Return Matrix."),
            ("⚖️","Risk & Scenarios",   "HHI, break-even analysis, What-If simulator."),
            ("💸","Cash Flow",          "Monthly flows, dividends, heatmap."),
            ("📋","Holdings",           "Position detail, sizer, CSV export."),
        ]
        for col, (icon, title, desc) in zip(cols, features):
            with col:
                st.markdown(
                    f"<div class='land-card'><span class='land-icon'>{icon}</span>"
                    f"<div class='land-title'>{title}</div>"
                    f"<div class='land-desc'>{desc}</div></div>",
                    unsafe_allow_html=True)
        st.stop()

    data = st.session_state["pdf_data"]
    eq   = data["equities"]
    txs  = data["transactions"]
    ps   = data["portfolio_summary"]

    if uploaded is None:
        st.info(f"📄 Using loaded statement: **{st.session_state.get('pdf_name', 'unknown')}** "
                f"— upload a new file above to switch.", icon="📋")

    if not eq:
        st.error("Could not parse equity data from this PDF. Please check the document format.")
        st.session_state.pop("pdf_data", None)
        st.session_state.pop("pdf_name", None)
        st.stop()

    # ── Live prices ───────────────────────────────────────────────────────────
    tickers = tuple(e["ticker"] for e in eq)
    live    = get_live_prices(tickers)
    eq      = inject_live_prices(eq, live)
    n_live  = sum(1 for e in eq if e["live_price"] is not None)

    if   n_live == len(eq): st.success(f"📡 All {n_live} live prices loaded from GSE-API")
    elif n_live:             st.warning(f"📡 {n_live}/{len(eq)} live prices · statement price used for the rest")
    else:                    st.info("📋 Showing statement prices (GSE-API unavailable)")

    # ── Manual price override ─────────────────────────────────────────────────
    with st.expander("✏️ Override prices manually", expanded=False):
        ov_cols   = st.columns(5)
        overrides = {}
        for i, e in enumerate(eq):
            default = float(e["live_price"] or e["statement_price"])
            val = ov_cols[i % 5].number_input(
                e["ticker"], min_value=0.0, value=default,
                step=0.01, format="%.4f", key=f"ov_{e['ticker']}")
            if val > 0:
                overrides[e["ticker"]] = val
        if st.button("✅ Apply prices", type="primary"):
            st.cache_data.clear()
            eq = inject_live_prices(
                eq, {t: {"price": pv, "change_pct":0, "change_abs":0}
                     for t, pv in overrides.items()})
            n_live = len(eq)
            st.success("Applied.")

    # ── Compute metrics ───────────────────────────────────────────────────────
    m  = compute_metrics(eq, txs, ps)
    am = compute_advanced_metrics(eq, txs, m)

    # ── Client bar ────────────────────────────────────────────────────────────
    pp_cls = "live" if n_live == len(eq) else "warn" if n_live else "info"
    pp_txt = ("✦ All Live" if n_live == len(eq)
              else f"{n_live}/{len(eq)} Live" if n_live else "Statement")
    roi_c  = EMERALD if m["overall_roi"] >= 0 else RUBY
    gl_c   = EMERALD if m["total_gain"]  >= 0 else RUBY
    cagr_s = (f"<span style='color:{'{'}{EMERALD if (m['cagr'] or 0) >= 0 else RUBY}{'}'}'>"
              f"{m['cagr']:+.2f}%</span>" if m["cagr"] is not None else "—")
    st.markdown(f"""
<div class='cbar'>
  <div class='cbar-item'><div class='cbar-lbl'>Client</div>
    <div class='cbar-val'>{data['client_name']}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Account</div>
    <div class='cbar-acc'>{data['account_number']}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Statement Date</div>
    <div class='cbar-val'>{data['report_date']}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Portfolio Value</div>
    <div class='cbar-val'>GHS {m['total_value']:,.2f}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>ROI (net cash)</div>
    <div class='cbar-val' style='color:{roi_c}'>{m['overall_roi']:+.2f}%</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>CAGR</div>
    <div class='cbar-val'>{cagr_s}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Unrealised G/L</div>
    <div class='cbar-val' style='color:{gl_c}'>{'+'if m['total_gain']>=0 else ''}GHS {m['total_gain']:,.2f}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Win Rate</div>
    <div class='cbar-val'>{m['winners']}/{len(eq)} ({m['winners']/len(eq)*100:.0f}%)</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Prices</div>
    <div class='cbar-val'><span class='pill {pp_cls}'>{pp_txt}</span></div></div>
</div>""", unsafe_allow_html=True)

    # ── TABS ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Overview",
        "📈 Performance",
        "🔬 Analytics",
        "⚖️ Risk & Scenarios",
        "💸 Cash Flow",
        "📋 Holdings",
    ])

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1 — OVERVIEW
    # ═══════════════════════════════════════════════════════════════════════════
    with tab1:
        shdr("Portfolio Summary")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(kpi("Total Portfolio Value",
                f"GHS {m['total_value']:,.2f}",
                f"As of {data['report_date']}", "b"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi("Unrealised Gain / Loss",
                f"<span class='{pn(m['total_gain'])}'>{'+'if m['total_gain']>=0 else ''}GHS {m['total_gain']:,.2f}</span>",
                f"on GHS {m['total_cost']:,.2f} cost basis",
                "g" if m["total_gain"] >= 0 else "r",
                delta=m["gain_pct"]), unsafe_allow_html=True)
        with c3:
            st.markdown(kpi("Overall ROI",
                f"<span class='{pn(m['overall_roi'])}'>{m['overall_roi']:+.2f}%</span>",
                f"vs GHS {m['net_invested']:,.2f} net invested",
                "g" if m["overall_roi"] >= 0 else "r", icon="📐"), unsafe_allow_html=True)
        with c4:
            cd = f"<span class='{pn(m['cagr'] or 0)}'>{m['cagr']:+.2f}%</span>" if m["cagr"] else "—"
            st.markdown(kpi("CAGR", cd,
                "Annualised return" if m["cagr"] else "Insufficient history",
                "t" if (m["cagr"] or 0) >= 0 else "r", icon="📅"), unsafe_allow_html=True)

        st.markdown("")
        c5, c6, c7, c8 = st.columns(4)
        with c5:
            hc = EMERALD if m["health_score"] >= 75 else AMBER if m["health_score"] >= 50 else RUBY
            st.markdown(kpi("Health Score",
                f"<span style='color:{hc}'>{m['health_score']}</span><span style='font-size:.9rem;color:{p.MUTED};'>/100</span>",
                "ROI · Win Rate · Diversification · Concentration · Sectors",
                "t" if m["health_score"] >= 75 else "y"), unsafe_allow_html=True)
        with c6:
            st.markdown(kpi("Cash Balance",
                f"GHS {m['cash_val']:,.2f}",
                f"{ps.get('Cash',{}).get('alloc',0):.1f}% of portfolio", "y"), unsafe_allow_html=True)
        with c7:
            st.markdown(kpi("Dividend Income",
                f"GHS {m['dividend_income']:,.2f}",
                "Total dividends received", "pk", icon="🌸"), unsafe_allow_html=True)
        with c8:
            st.markdown(kpi("Winning Positions",
                f"{m['winners']} / {len(eq)}",
                f"{m['winners']/len(eq)*100:.0f}% win rate",
                "g" if m["winners"] >= len(eq)//2 else "r"), unsafe_allow_html=True)

        # Smart Alerts
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("🚨 Smart Alerts")
        alerts = generate_alerts(eq, m, txs)
        for cls, title, body in alerts:
            st.markdown(alert_box(title, body, cls), unsafe_allow_html=True)

        # Quick Insights
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("Quick Insights")
        i1, i2, i3, i4, i5, i6 = st.columns(6)
        with i1: st.markdown(insight("🏆","Best Performer",
            f"{m['best']['ticker']} {m['best']['gain_pct']:+.1f}%","pos"), unsafe_allow_html=True)
        with i2: st.markdown(insight("📉","Worst Performer",
            f"{m['worst']['ticker']} {m['worst']['gain_pct']:+.1f}%","neg"), unsafe_allow_html=True)
        with i3: st.markdown(insight("💎","Largest Position",
            f"{m['biggest']['ticker']} · GHS {m['biggest']['market_value']:,.0f}"), unsafe_allow_html=True)
        with i4: st.markdown(insight("🏭","Sectors Held",
            f"{m['sectors_used']} active"), unsafe_allow_html=True)
        with i5: st.markdown(insight("⚡","Most Active Month", m["active_month"]), unsafe_allow_html=True)
        with i6: st.markdown(insight("📡","Live Prices",
            f"{n_live} / {len(eq)} fetched","pos" if n_live==len(eq) else ""), unsafe_allow_html=True)

        # Today's Movers
        movers = sorted([e for e in eq if e.get("change_pct") is not None],
                        key=lambda e: abs(e["change_pct"] or 0), reverse=True)
        if movers:
            st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
            shdr("🚀 Today's Movers")
            mcols = st.columns(min(len(movers), 5))
            for i, (col, e) in enumerate(zip(mcols, movers[:5])):
                with col:
                    st.markdown(mover_card(
                        e["ticker"],
                        e["live_price"] or e["statement_price"],
                        e["change_pct"] or 0,
                        e["change_abs"] or 0,
                        is_top=(i == 0),
                    ), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2 — PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════════════
    with tab2:
        shdr("Performance Analysis")
        cl, cr = st.columns([3, 2])
        with cl: st.plotly_chart(chart_gain_loss(eq), use_container_width=True)
        with cr: st.plotly_chart(chart_sector_donut(eq), use_container_width=True)

        st.plotly_chart(chart_performance_attribution(eq, m["equities_val"]),
                        use_container_width=True)

        # Sector performance
        st.plotly_chart(chart_sector_performance(eq), use_container_width=True)

        cl, cr = st.columns([3, 2])
        with cl: st.plotly_chart(chart_market_vs_cost(eq), use_container_width=True)
        with cr: st.plotly_chart(chart_allocation_treemap(ps), use_container_width=True)

        st.plotly_chart(chart_portfolio_efficiency(eq), use_container_width=True)
        st.plotly_chart(chart_pl_waterfall(eq), use_container_width=True)

        pc = chart_price_comparison(eq)
        if pc:
            st.plotly_chart(pc, use_container_width=True)

        # Sector table
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("Sector Breakdown Table")
        sec_rows = []
        for sector, grp in pd.DataFrame(eq).groupby("sector"):
            smv  = grp["market_value"].sum()
            stc  = grp["total_cost"].sum()
            sgl  = grp["gain_loss"].sum()
            sec_rows.append({
                "Sector":           sector,
                "Stocks":           ", ".join(grp["ticker"].tolist()),
                "# Stocks":         len(grp),
                "Market Value":     f"GHS {smv:,.2f}",
                "Cost Basis":       f"GHS {stc:,.2f}",
                "Gain/Loss":        f"{'+'if sgl>=0 else ''}GHS {sgl:,.2f}",
                "Sector Return":    f"{(sgl/stc*100 if stc else 0):+.1f}%",
                "Portfolio Weight": f"{(smv/m['equities_val']*100 if m['equities_val'] else 0):.1f}%",
            })
        st.dataframe(pd.DataFrame(sec_rows), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 3 — ANALYTICS (NEW)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab3:
        shdr("Advanced Analytics",
             f"Risk-free rate: {am['rf_rate']:.0f}% (Ghana 91-day T-bill, approx.)")

        # Top-row KPIs
        a1, a2, a3, a4, a5 = st.columns(5)
        with a1:
            if am["sharpe"] is not None:
                sc   = EMERALD if am["sharpe"] >= 1 else AMBER if am["sharpe"] >= 0 else RUBY
                sval = f"<span style='color:{sc}'>{am['sharpe']:+.2f}</span>"
                ssub = ("Excellent" if am["sharpe"] >= 2 else
                        "Good"      if am["sharpe"] >= 1 else
                        "Below RF"  if am["sharpe"] < 0  else "Adequate")
            else:
                sval, ssub = "—", "Insufficient data"
            st.markdown(kpi("Sharpe Ratio (approx)", sval,
                f"Risk-adj. return · {ssub}",
                "g" if (am["sharpe"] or 0) >= 1 else "y" if (am["sharpe"] or 0) >= 0 else "r",
                icon="⚡"), unsafe_allow_html=True)
        with a2:
            mdc = AMBER if am["max_dd"] > -15 else RUBY
            st.markdown(kpi("Max Drawdown",
                f"<span style='color:{mdc}'>{am['max_dd']:.2f}%</span>",
                "From cumulative flow peak", "r", icon="📉"), unsafe_allow_html=True)
        with a3:
            st.markdown(kpi("Effective Positions",
                f"{am['enp']:.1f}",
                f"ENP = 1 / HHI · of {len(eq)} holdings", "b", icon="🎯"), unsafe_allow_html=True)
        with a4:
            vc = AMBER if am["port_vol"] > 20 else EMERALD
            st.markdown(kpi("Cross-sectional Vol",
                f"<span style='color:{vc}'>{am['port_vol']:.1f}%</span>",
                "Return dispersion across stocks", "vi", icon="📊"), unsafe_allow_html=True)
        with a5:
            cc = EMERALD if am["consistency"] >= 70 else AMBER if am["consistency"] >= 50 else RUBY
            st.markdown(kpi("Consistency Score",
                f"<span style='color:{cc}'>{am['consistency']:.0f}%</span>",
                "Stocks within −5% of cost", "t", icon="🎯"), unsafe_allow_html=True)

        st.markdown("")
        b1, b2, b3 = st.columns(3)
        with b1:
            dyc = EMERALD if am["div_yield_cost"] >= 3 else AMBER
            st.markdown(kpi("Dividend Yield on Cost",
                f"<span style='color:{dyc}'>{am['div_yield_cost']:.2f}%</span>",
                "Div income / cost basis", "pk", icon="🌸"), unsafe_allow_html=True)
        with b2:
            dym = EMERALD if am["div_yield_market"] >= 3 else AMBER
            st.markdown(kpi("Dividend Yield on MV",
                f"<span style='color:{dym}'>{am['div_yield_market']:.2f}%</span>",
                "Div income / market value", "t", icon="💎"), unsafe_allow_html=True)
        with b3:
            if am["avg_holding"] is not None:
                hp_str = (f"{am['avg_holding'] // 365}y {(am['avg_holding'] % 365)//30}m"
                          if am["avg_holding"] >= 365
                          else f"{am['avg_holding'] // 30}m {am['avg_holding'] % 30}d")
                st.markdown(kpi("Avg Holding Period", hp_str,
                    "Estimated from buy transactions", "b", icon="⏱️"), unsafe_allow_html=True)
            else:
                st.markdown(kpi("Avg Holding Period", "—",
                    "No buy transactions detected", "b", icon="⏱️"), unsafe_allow_html=True)

        # Risk / Return scatter
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("Risk / Return Matrix",
             "Bubble size = Market Value · Vertical line = equal weight")
        st.plotly_chart(chart_risk_return_scatter(eq, m["equities_val"]),
                        use_container_width=True)

        # Portfolio drawdown
        dd_fig = chart_drawdown(txs, m["total_value"])
        if dd_fig:
            st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
            shdr("Portfolio Drawdown from Peak")
            st.plotly_chart(dd_fig, use_container_width=True)

        # Monthly cash-flow heatmap
        hm_fig = chart_monthly_cashflow_heatmap(txs)
        if hm_fig:
            st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
            shdr("Monthly Net Cash Flow Calendar",
                 "Green = net inflow · Red = net outflow")
            st.plotly_chart(hm_fig, use_container_width=True)

        # Per-stock analytics table
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("Per-Stock Analytics")
        ana_rows = []
        for e in sorted(eq, key=lambda x: x["market_value"], reverse=True):
            wt  = e["market_value"] / m["equities_val"] * 100 if m["equities_val"] else 0
            eff = e["gain_loss"] / e["total_cost"] * 100 if e["total_cost"] else 0
            hp  = am["holding_periods"].get(e["ticker"])
            hp_s= (f"{hp//365}y {(hp%365)//30}m" if hp and hp >= 365
                   else f"{hp//30}m" if hp else "—")
            ana_rows.append({
                "Ticker":         e["ticker"],
                "Sector":         e["sector"],
                "Weight %":       f"{wt:.1f}%",
                "Return %":       f"{e['gain_pct']:+.1f}%",
                "Efficiency ROI": f"{eff:+.1f}%",
                "Contribution":   f"{e['gain_loss']/m['equities_val']*100:+.2f}%" if m["equities_val"] else "—",
                "Holding Period": hp_s,
                "Status":         "✅ Profit" if e["gain_pct"] >= 0 else "🔴 Loss",
            })
        st.dataframe(pd.DataFrame(ana_rows), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 4 — RISK & SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════════
    with tab4:
        # Break-even
        be = chart_breakeven(eq)
        if be:
            shdr("🎯 Break-even Analysis")
            st.plotly_chart(be, use_container_width=True)
        else:
            st.success("🎉 All positions are currently profitable — no break-even analysis needed.")

        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("⚖️ Concentration Risk (HHI)")
        conc_fig, hhi_val, risk_lbl, rc = chart_concentration(eq)
        st.plotly_chart(conc_fig, use_container_width=True)
        st.markdown(
            f"<div style='text-align:center;color:{p.MUTED};font-size:.82rem;margin-top:-8px;"
            f"font-family:DM Mono,monospace;'>"
            f"HHI: <b style='color:{rc}'>{hhi_val}</b> — "
            f"<b style='color:{rc}'>{risk_lbl}</b> concentration &nbsp;·&nbsp;"
            f"<span style='color:{EMERALD}'>Low &lt;1500</span> · "
            f"<span style='color:{AMBER}'>Moderate 1500–2500</span> · "
            f"<span style='color:{RUBY}'>High &gt;2500</span>"
            f"</div>", unsafe_allow_html=True)

        # Rebalance recommendations
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("🛠️ Rebalance Recommendations")
        if hhi_val > 2500:
            st.warning("⚠️ High concentration — consider the adjustments below:")
        else:
            st.success("✅ Concentration within acceptable range. Fine-tuning suggestions below.")

        ev    = m["equities_val"]
        n     = len(eq)
        equal = 100 / n if n else 10
        rec_rows = []
        for e in sorted(eq, key=lambda x: x["market_value"] / ev, reverse=True):
            wt = e["market_value"] / ev * 100 if ev else 0
            if   wt > 20:           action = f"🔴 Trim → target 10–15% (currently {wt:.1f}%)"
            elif wt < 3 and e["gain_pct"] >= 0: action = f"🟢 Consider adding — only {wt:.1f}%"
            elif e["gain_pct"] < -15: action = f"🟡 Review thesis — {e['gain_pct']:+.1f}% return"
            else:                   action = f"✅ Hold — {wt:.1f}% (target ~{equal:.1f}%)"
            rec_rows.append({
                "Ticker": e["ticker"], "Sector": e["sector"],
                "Current Weight": f"{wt:.1f}%",
                "Equal-weight Target": f"{equal:.1f}%",
                "Return": f"{e['gain_pct']:+.1f}%",
                "Recommendation": action,
            })
        st.dataframe(pd.DataFrame(rec_rows), use_container_width=True, hide_index=True)

        # What-If Simulator
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("🔮 What-If Scenario Simulator")
        st.caption("Adjust sliders to simulate price moves on each position")
        rows_of_5 = [eq[i:i+5] for i in range(0, len(eq), 5)]
        sim_mult  = {}
        for row in rows_of_5:
            sc = st.columns(len(row))
            for col, e in zip(sc, row):
                chg = col.slider(e["ticker"], min_value=-50, max_value=150,
                                 value=0, step=1, format="%d%%", key=f"sim_{e['ticker']}")
                sim_mult[e["ticker"]] = 1 + chg / 100

        sim_mv    = sum(e["market_value"] * sim_mult.get(e["ticker"], 1) for e in eq)
        sim_total = sim_mv + m["cash_val"] + m["funds_val"]
        sim_gain  = sum((e["market_value"] * sim_mult.get(e["ticker"],1)) - e["total_cost"] for e in eq)
        sim_delta = sim_total - m["total_value"]
        sim_roi   = ((sim_total - m["net_invested"]) / m["net_invested"] * 100) if m["net_invested"] else 0

        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.markdown(kpi("Simulated Total Value",
                f"GHS {sim_total:,.2f}",
                f"{'+'if sim_delta>=0 else ''}GHS {sim_delta:,.2f} vs now",
                "g" if sim_delta >= 0 else "r"), unsafe_allow_html=True)
        with sc2:
            st.markdown(kpi("Simulated G/L",
                f"<span class='{pn(sim_gain)}'>{'+'if sim_gain>=0 else ''}GHS {sim_gain:,.2f}</span>",
                f"{(sim_gain/m['total_cost']*100):+.2f}% on cost",
                "g" if sim_gain >= 0 else "r"), unsafe_allow_html=True)
        with sc3:
            st.markdown(kpi("Simulated ROI",
                f"<span class='{pn(sim_roi)}'>{sim_roi:+.2f}%</span>",
                f"Current: {m['overall_roi']:+.2f}%",
                "g" if sim_roi >= 0 else "r"), unsafe_allow_html=True)
        with sc4:
            gchg = sim_gain - m["total_gain"]
            st.markdown(kpi("G/L Change",
                f"<span class='{pn(gchg)}'>{'+'if gchg>=0 else ''}GHS {gchg:,.2f}</span>",
                "vs current unrealised G/L",
                "g" if gchg >= 0 else "r"), unsafe_allow_html=True)

        sim_df = pd.DataFrame([{
            "ticker":    e["ticker"],
            "current":   e["market_value"],
            "simulated": e["market_value"] * sim_mult.get(e["ticker"], 1),
        } for e in eq]).sort_values("simulated", ascending=False)
        fig_sim = go.Figure()
        fig_sim.add_trace(go.Bar(name="Current", x=sim_df["ticker"], y=sim_df["current"],
                                 marker_color=VIOLET, opacity=0.65))
        fig_sim.add_trace(go.Bar(name="Simulated", x=sim_df["ticker"], y=sim_df["simulated"],
                                 marker=dict(
                                     color=[EMERALD if s > c else RUBY
                                            for s, c in zip(sim_df["simulated"], sim_df["current"])],
                                     opacity=0.9)))
        fig_sim.update_layout(title="Current vs Simulated Market Value",
                              yaxis_title="GHS", barmode="group", **T(), height=320)
        st.plotly_chart(fig_sim, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 5 — CASH FLOW
    # ═══════════════════════════════════════════════════════════════════════════
    with tab5:
        shdr("Cash Flow & History")
        cf = chart_cashflow(txs)
        if cf:
            st.plotly_chart(cf, use_container_width=True)

        div_chart = chart_dividend_timeline(txs)
        if div_chart:
            shdr("💎 Dividend Income Timeline")
            st.plotly_chart(div_chart, use_container_width=True)

        cl, cr = st.columns([3, 2])
        with cl:
            cml = chart_cumulative(txs, m["total_value"])
            if cml: st.plotly_chart(cml, use_container_width=True)
        with cr:
            rl = chart_rolling_return(txs, m["total_value"])
            if rl: st.plotly_chart(rl, use_container_width=True)

        # Tx type volume chart
        tx_df2 = pd.DataFrame(txs)
        if not tx_df2.empty:
            tx_df2["amount"] = tx_df2["credit"] + tx_df2["debit"]
            grp = tx_df2.groupby("type")["amount"].sum().reset_index().sort_values("amount", ascending=False)
            cmap_t = {"Buy":AZURE,"Sell":AMBER,"Credit":EMERALD,
                      "Withdrawal":RUBY,"Dividend":TEAL,"Other":SLATE}
            fig_tt = go.Figure(go.Bar(
                x=grp["type"], y=grp["amount"],
                marker_color=[cmap_t.get(t, SLATE) for t in grp["type"]],
                marker_opacity=0.85,
                text=[f"GHS {v:,.0f}" for v in grp["amount"]], textposition="outside",
                textfont=dict(size=10, family="DM Mono"),
                hovertemplate="%{x}: GHS %{y:,.2f}<extra></extra>",
            ))
            fig_tt.update_layout(title="Volume by Transaction Type",
                                 yaxis_title="GHS", **T(), height=280)
            st.plotly_chart(fig_tt, use_container_width=True)

        # Flow summary KPIs
        if not tx_df2.empty:
            tx_df2["month"] = tx_df2["date"].dt.to_period("M")
            n_months = tx_df2["month"].nunique()
            # Flow quality score
            buy_vol  = tx_df2[tx_df2["type"]=="Buy"]["amount"].sum()
            sell_vol = tx_df2[tx_df2["type"]=="Sell"]["amount"].sum()
            flow_quality = "Active Investor" if buy_vol > sell_vol * 2 else \
                           "Active Trader"   if sell_vol > buy_vol   else "Balanced"

            st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
            shdr("Flow Summary")
            fa1, fa2, fa3, fa4, fa5 = st.columns(5)
            with fa1: st.markdown(kpi("Months Active", f"{n_months}",
                f"{len(txs)} total transactions", "b"), unsafe_allow_html=True)
            with fa2: st.markdown(kpi("Total Contributions", f"GHS {m['net_contributions']:,.2f}",
                "Cash in", "g"), unsafe_allow_html=True)
            with fa3: st.markdown(kpi("Total Withdrawals", f"GHS {m['net_withdrawals']:,.2f}",
                "Cash out", "r"), unsafe_allow_html=True)
            with fa4: st.markdown(kpi("Net Invested", f"GHS {m['net_invested']:,.2f}",
                "Contributions − Withdrawals", "t"), unsafe_allow_html=True)
            with fa5: st.markdown(kpi("Flow Profile", flow_quality,
                f"Buy vol GHS {buy_vol:,.0f}", "vi", icon="🧭"), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 6 — HOLDINGS
    # ═══════════════════════════════════════════════════════════════════════════
    with tab6:
        shdr("Equity Positions")

        # Filters
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            sectors_avail = sorted(set(e["sector"] for e in eq))
            sel_sectors   = st.multiselect("Filter by Sector", sectors_avail,
                                           default=sectors_avail, label_visibility="collapsed",
                                           placeholder="Filter by sector…")
        with fc2:
            prof_filter = st.selectbox("Profitability", ["All","Profitable","Loss-making"],
                                       label_visibility="collapsed")
        with fc3:
            sort_by = st.selectbox("Sort by", ["Market Value","Return %","Gain/Loss",
                                               "Weight","Ticker"],
                                   label_visibility="collapsed")

        # Build table
        eq_filtered = [e for e in eq if e["sector"] in sel_sectors]
        if prof_filter == "Profitable":   eq_filtered = [e for e in eq_filtered if e["gain_pct"] >= 0]
        elif prof_filter == "Loss-making": eq_filtered = [e for e in eq_filtered if e["gain_pct"] < 0]

        sort_key_map = {
            "Market Value": lambda e: e["market_value"],
            "Return %":     lambda e: e["gain_pct"],
            "Gain/Loss":    lambda e: e["gain_loss"],
            "Weight":       lambda e: e["market_value"],
            "Ticker":       lambda e: e["ticker"],
        }
        eq_filtered = sorted(eq_filtered, key=sort_key_map[sort_by], reverse=(sort_by != "Ticker"))

        pos_rows = []
        for e in eq_filtered:
            wt = e["market_value"] / m["equities_val"] * 100 if m["equities_val"] else 0
            pos_rows.append({
                "Ticker":     e["ticker"],
                "Sector":     e["sector"],
                "Qty":        f"{e['qty']:,.0f}",
                "Avg Cost":   f"{e['avg_cost']:.4f}",
                "Stmt Price": f"{e['statement_price']:.4f}",
                "Live Price": f"{e['live_price']:.4f}" if e["live_price"] else "—",
                "Today Δ%":   f"{e['change_pct']:+.2f}%" if e.get("change_pct") is not None else "—",
                "Weight %":   f"{wt:.1f}%",
                "Cost Basis": f"GHS {e['total_cost']:,.2f}",
                "Market Val": f"GHS {e['market_value']:,.2f}",
                "Gain/Loss":  f"{'+'if e['gain_loss']>=0 else ''}GHS {e['gain_loss']:,.2f}",
                "Return %":   f"{e['gain_pct']:+.1f}%",
                "Status":     "✅ Profit" if e["gain_pct"] >= 0 else f"🔴 −{abs(e['gain_pct']):.1f}%",
            })

        def _style_row(row):
            s  = [""] * len(row)
            ig = list(row.index).index("Gain/Loss")
            ir = list(row.index).index("Return %")
            c  = (f"color:{EMERALD};font-weight:600" if "+" in row["Gain/Loss"]
                  else f"color:{RUBY};font-weight:600")
            s[ig] = s[ir] = c
            return s

        df_pos = pd.DataFrame(pos_rows)
        if not df_pos.empty:
            st.dataframe(df_pos.style.apply(_style_row, axis=1),
                         use_container_width=True, hide_index=True)

        # Progress bars
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("📊 Invested → Market Value Progress")
        for e in sorted(eq_filtered, key=lambda x: x["market_value"], reverse=True):
            prog   = min(1.0, e["market_value"] / e["total_cost"]) if e["total_cost"] else 0
            bc     = EMERALD if e["gain_pct"] >= 0 else RUBY
            lbl    = f"{e['gain_pct']:+.1f}%"
            mv_lbl = f"GHS {e['market_value']:,.2f}"
            wt     = e["market_value"] / m["equities_val"] * 100 if m["equities_val"] else 0
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:.78rem;margin-bottom:2px;align-items:baseline;'>"
                f"<span style='font-weight:700;color:{p.TEXT};font-family:Epilogue,sans-serif;'>"
                f"{e['ticker']} <span class='sec-badge'>{e['sector']}</span></span>"
                f"<span style='font-family:DM Mono,monospace;'>"
                f"<span style='color:{p.MUTED};margin-right:8px;'>{mv_lbl} · {wt:.1f}%</span>"
                f"<span style='color:{bc};font-weight:600;'>{lbl}</span></span></div>"
                f"<div class='prog-wrap'>"
                f"<div class='prog-bar' style='width:{min(100,prog*100):.1f}%;background:{bc};'></div>"
                f"</div><div style='height:10px'></div>",
                unsafe_allow_html=True)

        # Position Sizer
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("🎯 Position Sizer",
             "Enter a target total portfolio size to see required changes per position")
        with st.expander("Open Position Sizer", expanded=False):
            target_total = st.number_input(
                "Target Portfolio Value (GHS)",
                min_value=0.0,
                value=float(m["total_value"]),
                step=1000.0, format="%.2f")
            target_eq_pct = st.slider(
                "Target Equity Allocation (%)",
                min_value=10, max_value=100, value=70, step=5)
            target_eq_val = target_total * target_eq_pct / 100
            strategy = st.selectbox("Weighting Strategy",
                                    ["Equal Weight","Market-cap Weight (keep current)"])

            sizer_rows = []
            for e in sorted(eq, key=lambda x: x["market_value"], reverse=True):
                if strategy == "Equal Weight":
                    target_w   = 1 / len(eq)
                    target_mv  = target_eq_val * target_w
                else:
                    w          = e["market_value"] / m["equities_val"] if m["equities_val"] else 0
                    target_mv  = target_eq_val * w
                delta_ghs  = target_mv - e["market_value"]
                price      = e["live_price"] or e["statement_price"]
                delta_shr  = round(delta_ghs / price) if price else 0
                sizer_rows.append({
                    "Ticker":           e["ticker"],
                    "Current Value":    f"GHS {e['market_value']:,.2f}",
                    "Target Value":     f"GHS {target_mv:,.2f}",
                    "Δ Value":          f"{'+'if delta_ghs>=0 else ''}GHS {delta_ghs:,.2f}",
                    "Shares to Trade":  f"{'+'if delta_shr>=0 else ''}{delta_shr:,} shares",
                    "Action":           ("🟢 Buy" if delta_shr > 0 else
                                         "🔴 Sell" if delta_shr < 0 else "✅ Hold"),
                })
            if sizer_rows:
                st.dataframe(pd.DataFrame(sizer_rows), use_container_width=True, hide_index=True)
                st.caption(
                    f"Target equity allocation: GHS {target_eq_val:,.2f} "
                    f"({target_eq_pct}% of GHS {target_total:,.2f} target)")

        # CSV exports
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        dl1, dl2 = st.columns(2)
        with dl1:
            csv_hold = df_pos.to_csv(index=False).encode("utf-8") if not df_pos.empty else b""
            st.download_button(
                "📥 Download Holdings CSV",
                csv_hold,
                f"IC_holdings_{data['account_number']}_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv", use_container_width=True)
        with dl2:
            tx_export = pd.DataFrame(txs)
            if not tx_export.empty:
                csv_tx = tx_export.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Transaction Log CSV",
                    csv_tx,
                    f"IC_transactions_{data['account_number']}_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv", use_container_width=True)

        # Transaction history
        st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
        shdr("Transaction History")
        tx_df = pd.DataFrame(txs).sort_values("date", ascending=False)
        emojis = {"Buy":"🔵","Sell":"🟡","Credit":"🟢","Withdrawal":"🔴","Dividend":"💎","Other":"⚪"}
        tx_df["Type"] = tx_df["type"].map(lambda t: f"{emojis.get(t,'⚪')} {t}")

        tf1, tf2, tf3 = st.columns([2,2,3])
        with tf1:
            filt = st.multiselect("Type filter", list(tx_df["Type"].unique()),
                                  default=list(tx_df["Type"].unique()),
                                  label_visibility="collapsed")
        with tf2:
            date_range = st.date_input(
                "Date range",
                value=(tx_df["date"].min().date() if not tx_df.empty else datetime.now().date(),
                       tx_df["date"].max().date() if not tx_df.empty else datetime.now().date()),
                label_visibility="collapsed")
        with tf3:
            srch = st.text_input("Search", placeholder="🔍 Search description…",
                                 label_visibility="collapsed")

        view = tx_df[tx_df["Type"].isin(filt)]
        if len(date_range) == 2:
            s, e2 = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
            view  = view[(view["date"] >= s) & (view["date"] <= e2)]
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
        st.dataframe(view_show, use_container_width=True, hide_index=True, height=400)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("<div class='rich-divider'></div>", unsafe_allow_html=True)
    generated = datetime.now().strftime("%d %b %Y · %H:%M")
    st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            flex-wrap:wrap;gap:12px;padding:4px 4px 20px;
            font-size:.75rem;color:{p.MUTED};font-family:Epilogue,sans-serif;">
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:1.1rem;">₵</span>
    <span>
      <b style='color:{GOLD};font-family:Fraunces,serif;font-size:.85rem;'>
        IC Portfolio Analyser</b>
      <span style='color:{p.BORDER2};margin:0 6px;'>·</span>Elite Edition v3.0
    </span>
  </div>
  <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;">
    <span>Generated {generated}</span>
    <span style="color:{p.BORDER2};">|</span>
    <span>Prices: <a href='https://dev.kwayisi.org/apis/gse/' target='_blank'
      style='color:{GOLD};text-decoration:none;font-weight:600;'>
      dev.kwayisi.org/apis/gse</a></span>
    <span style="color:{p.BORDER2};">|</span>
    <span>For informational purposes only</span>
    <span style="color:{p.BORDER2};">|</span>
    <span>Past performance does not guarantee future results</span>
  </div>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()