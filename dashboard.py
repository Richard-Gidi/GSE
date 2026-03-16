"""
IC Securities Portfolio Analyser — ELITE EDITION v4.0 (March 2026)

NEW in v4:
  ★ Multi-Statement Portfolio Timeline  — upload all past statements; see your real
      equity curve, position evolution, and month-on-month value changes over time.
  ★ Real Returns vs Ghana Inflation     — every return shown in both nominal and
      real (CPI-adjusted) terms. At 23%+ inflation many "gains" are real losses.
  ★ GSE Composite Index Benchmark       — portfolio alpha vs the GSE-CI fetched live.
  ★ Fee Impact Analyser                 — estimates every GHS paid to IC/SEC/GhSE
      across all buy & sell transactions. Shows the compounded drag over time.
  ★ Dividend DRIP Simulator             — what your portfolio would be worth today
      had you reinvested every dividend back into the paying stock.
  ★ Goals & Projection Engine           — set a target wealth figure; projection
      engine shows expected date at current CAGR + optimistic/pessimistic bands.
  ★ Statement Diff View                 — load two statements and instantly see
      every new position, exited position, and weight change.
  ★ Downloadable HTML Report            — one-click full-portfolio report styled
      for printing / saving as PDF from the browser.

Install:
    pip install streamlit plotly pdfplumber pandas numpy requests beautifulsoup4 lxml fpdf2
Run:
    streamlit run akwasi_v4.py
"""

import base64, io, re, warnings, json
from datetime import datetime, timedelta
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
    BG="#04060f", CARD="#08091e", CARD2="#0c1028",
    BORDER="#141838", BORDER2="#1c2248",
    TEXT="#eef0fa", TEXT2="#8898c8", MUTED="#424870",
    SHADOW="rgba(0,0,0,0.75)", name="dark",
)
GOLD="#e8b438"; GOLD2="#c0901e"; EMERALD="#00d485"; RUBY="#ff3960"
AZURE="#0ea5e9"; VIOLET="#7c5cfa"; TEAL="#06b6d4"; AMBER="#f59e0b"
ROSE="#f43f7e"; INDIGO="#6366f1"; SLATE="#64748b"

def th(): return _DARK

# ── Safe layout builder — NEVER pass these keys directly alongside **T() ────
# title, xaxis, yaxis, font, paper_bgcolor, plot_bgcolor, margin, legend, hoverlabel
def T(title=None, xt=None, yt=None):
    p  = th()
    tf = dict(color=p.MUTED, size=11, family="'DM Mono','Courier New',monospace")
    xax = dict(gridcolor=p.BORDER, zerolinecolor=p.BORDER2,
               tickcolor=p.MUTED, tickfont=dict(color=p.MUTED))
    yax = dict(gridcolor=p.BORDER, zerolinecolor=p.BORDER2,
               tickcolor=p.MUTED, tickfont=dict(color=p.MUTED))
    if xt: xax["title"] = dict(text=xt, font=tf)
    if yt: yax["title"] = dict(text=yt, font=tf)
    td = dict(font=dict(color=p.TEXT, family="'Epilogue',sans-serif", size=14), x=0.01)
    if title: td["text"] = title
    return dict(
        paper_bgcolor=p.BG, plot_bgcolor=p.CARD,
        font=dict(color=p.TEXT2, family="'DM Mono','Courier New',monospace", size=11),
        xaxis=xax, yaxis=yax,
        margin=dict(l=16, r=16, t=52, b=16),
        legend=dict(bgcolor=p.CARD2, bordercolor=p.BORDER, borderwidth=1,
                    font=dict(color=p.TEXT2, family="Epilogue,sans-serif")),
        hoverlabel=dict(bgcolor=p.CARD2, bordercolor=p.BORDER2,
                        font=dict(color=p.TEXT, family="'DM Mono',monospace")),
        title=td,
    )

# ─────────────────────────────────────────────────────────────────────────────
# GHANA CPI — annual headline inflation rates (Bank of Ghana / GSS)
# ─────────────────────────────────────────────────────────────────────────────
GHANA_CPI = {
    2016: 15.4, 2017: 11.8, 2018: 9.8, 2019: 7.9,
    2020: 10.4, 2021: 12.6, 2022: 31.5, 2023: 23.2,
    2024: 22.4, 2025: 18.0,
}

def real_return(nominal_pct, years, cpi_year=None):
    """Convert nominal return to approximate real return using Ghana CPI."""
    if years <= 0: return None
    avg_cpi = 0.0
    now_yr  = datetime.now().year
    for y in range(max(2016, now_yr - max(1, int(years))), now_yr + 1):
        avg_cpi += GHANA_CPI.get(y, 18.0)
    avg_cpi /= max(1, int(years))
    # Fisher equation: real = ((1 + nominal/100) / (1 + cpi/100) - 1) * 100
    real = ((1 + nominal_pct / 100) / (1 + avg_cpi / 100) - 1) * 100
    return round(real, 2), round(avg_cpi, 1)

# ─────────────────────────────────────────────────────────────────────────────
# IC SECURITIES FEE SCHEDULE (approximate, 2024)
# ─────────────────────────────────────────────────────────────────────────────
IC_FEES = {
    "IC Brokerage":    0.0150,   # 1.50%
    "SEC Levy":        0.0030,   # 0.30%
    "GhSE Levy":       0.0005,   # 0.05%
    "CSDR Levy":       0.0010,   # 0.10%
    "VAT (on broker)": 0.0000,   # 21.9% of brokerage — simplified to 0 for display
}
TOTAL_FEE_RATE = sum(IC_FEES.values())  # ~1.95%

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
def get_sector(t): return GSE_SECTORS.get(t.upper(), "Other")

# ─────────────────────────────────────────────────────────────────────────────
# THEME CSS
# ─────────────────────────────────────────────────────────────────────────────
def apply_theme():
    p = th()
    bg = (f"radial-gradient(ellipse at 15% 5%,{GOLD}0d 0%,transparent 45%),"
          f"radial-gradient(ellipse at 88% 92%,{VIOLET}12 0%,transparent 45%),"
          f"radial-gradient(ellipse at 50% 50%,{AZURE}06 0%,transparent 70%),"
          f"{p.BG}")
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;0,9..144,900;1,9..144,200&family=Epilogue:wght@300;400;500;600;700;800;900&family=DM+Mono:wght@300;400;500&display=swap');
html,body,[class*="css"]{{font-family:'Epilogue','Segoe UI',system-ui,sans-serif;}}
.stApp,[data-testid="stAppViewContainer"]{{background:{bg}!important;min-height:100vh;}}
[data-testid="stHeader"],[data-testid="stToolbar"]{{background:rgba(4,6,15,0.6)!important;backdrop-filter:blur(20px);border-bottom:1px solid {p.BORDER}!important;}}
section[data-testid="stSidebar"]{{background:rgba(8,9,30,0.97)!important;border-right:1px solid {p.BORDER}!important;backdrop-filter:blur(24px);}}
.block-container{{color:{p.TEXT};padding-top:1.5rem!important;max-width:1500px;}}

.kpi{{position:relative;background:rgba(8,9,30,0.85);backdrop-filter:blur(20px);border-radius:16px;padding:20px 22px 16px;border:1px solid {p.BORDER};margin-bottom:6px;transition:transform .25s cubic-bezier(.34,1.56,.64,1),box-shadow .25s,border-color .25s;box-shadow:0 4px 24px {p.SHADOW};overflow:hidden;}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,{GOLD},{GOLD2},{AMBER});border-radius:16px 16px 0 0;}}
.kpi.g::before{{background:linear-gradient(90deg,{EMERALD},{TEAL});}}
.kpi.r::before{{background:linear-gradient(90deg,{RUBY},{AMBER});}}
.kpi.y::before{{background:linear-gradient(90deg,{AMBER},{GOLD});}}
.kpi.b::before{{background:linear-gradient(90deg,{AZURE},{VIOLET});}}
.kpi.t::before{{background:linear-gradient(90deg,{TEAL},{EMERALD});}}
.kpi.pk::before{{background:linear-gradient(90deg,{ROSE},{VIOLET});}}
.kpi.vi::before{{background:linear-gradient(90deg,{VIOLET},{INDIGO});}}
.kpi.re::before{{background:linear-gradient(90deg,{RUBY},{ROSE});}}
.kpi-glow{{position:absolute;top:-40px;right:-40px;width:100px;height:100px;background:radial-gradient({GOLD}18,transparent 70%);border-radius:50%;pointer-events:none;}}
.kpi.g .kpi-glow{{background:radial-gradient({EMERALD}12,transparent 70%);}}
.kpi.r .kpi-glow,.kpi.re .kpi-glow{{background:radial-gradient({RUBY}12,transparent 70%);}}
.kpi:hover{{transform:translateY(-4px) scale(1.01);box-shadow:0 16px 40px {p.SHADOW};border-color:{GOLD}40;}}
.kpi-icon{{font-size:1.5rem;float:right;margin-top:2px;opacity:0.18;line-height:1;}}
.kpi-lbl{{font-size:.65rem;color:{p.MUTED};text-transform:uppercase;letter-spacing:.12em;margin-bottom:12px;font-weight:700;font-family:'Epilogue',sans-serif;}}
.kpi-val{{font-size:1.55rem;font-weight:500;color:{p.TEXT};line-height:1.15;font-family:'DM Mono','Courier New',monospace;}}
.kpi-sub{{font-size:.73rem;color:{p.MUTED};margin-top:8px;line-height:1.45;font-family:'Epilogue',sans-serif;}}
.kpi-delta{{display:inline-flex;align-items:center;gap:3px;font-size:.7rem;font-weight:600;padding:3px 9px;border-radius:20px;margin-top:8px;font-family:'DM Mono',monospace;}}
.kpi-delta.pos{{background:rgba(0,212,133,0.12);color:{EMERALD};border:1px solid rgba(0,212,133,0.22);}}
.kpi-delta.neg{{background:rgba(255,57,96,0.12);color:{RUBY};border:1px solid rgba(255,57,96,0.22);}}

.ibox{{background:rgba(8,9,30,0.75);backdrop-filter:blur(12px);border:1px solid {p.BORDER};border-radius:14px;padding:18px 12px 16px;text-align:center;height:100%;transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s;box-shadow:0 2px 12px {p.SHADOW};}}
.ibox:hover{{transform:translateY(-3px);box-shadow:0 10px 28px {p.SHADOW};}}
.ibox-icon{{font-size:1.9rem;line-height:1;}}
.ibox-lbl{{font-size:.62rem;color:{p.MUTED};text-transform:uppercase;letter-spacing:.1em;margin:10px 0 5px;font-weight:700;font-family:'Epilogue',sans-serif;}}
.ibox-val{{font-size:.9rem;font-weight:500;color:{p.TEXT};font-family:'DM Mono',monospace;}}

.mover{{background:rgba(8,9,30,0.8);backdrop-filter:blur(12px);border:1px solid {p.BORDER};border-radius:14px;padding:16px 14px;text-align:center;box-shadow:0 2px 12px {p.SHADOW};transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s;position:relative;overflow:hidden;}}
.mover.top-mover{{border-color:{GOLD}55;}}
.mover.top-mover::before{{content:'TOP MOVER';position:absolute;top:7px;right:8px;font-size:.55rem;font-weight:800;letter-spacing:.1em;color:{GOLD};font-family:'Epilogue',sans-serif;background:rgba(232,180,56,0.12);padding:2px 6px;border-radius:6px;border:1px solid {GOLD}30;}}
.mover:hover{{transform:translateY(-4px);box-shadow:0 12px 32px {p.SHADOW};border-color:{GOLD}40;}}
.mover-tick{{font-size:.68rem;font-weight:800;color:{p.MUTED};text-transform:uppercase;letter-spacing:.1em;background:{p.CARD2};display:inline-block;padding:2px 10px;border-radius:8px;margin-bottom:8px;font-family:'Epilogue',sans-serif;}}
.mover-price{{font-size:1.45rem;font-weight:400;color:{p.TEXT};margin:4px 0;font-family:'DM Mono',monospace;}}
.mover-chg{{font-size:.82rem;font-weight:600;padding:3px 12px;border-radius:12px;display:inline-block;font-family:'DM Mono',monospace;}}
.mover-chg.pos{{background:rgba(0,212,133,0.12);color:{EMERALD};}}
.mover-chg.neg{{background:rgba(255,57,96,0.12);color:{RUBY};}}

.shdr{{display:flex;align-items:center;gap:10px;font-size:.95rem;font-weight:700;color:{p.TEXT};margin:22px 0 16px;font-family:'Epilogue',sans-serif;}}
.shdr::before{{content:'';display:inline-block;width:3px;height:18px;background:linear-gradient(180deg,{GOLD},{AMBER});border-radius:4px;flex-shrink:0;}}

.cbar{{background:rgba(8,9,30,0.88);backdrop-filter:blur(20px);border:1px solid {p.BORDER};border-radius:16px;padding:16px 28px;display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:16px;box-shadow:0 4px 24px {p.SHADOW};position:relative;overflow:hidden;}}
.cbar::before{{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,{GOLD}80,{AMBER}60,transparent);}}
.cbar-item{{display:flex;flex-direction:column;gap:4px;}}
.cbar-lbl{{font-size:.6rem;color:{p.MUTED};text-transform:uppercase;letter-spacing:.12em;font-weight:800;font-family:'Epilogue',sans-serif;}}
.cbar-val{{font-size:.92rem;font-weight:400;color:{p.TEXT};font-family:'DM Mono',monospace;}}
.cbar-acc{{font-size:.95rem;font-weight:500;background:linear-gradient(135deg,{GOLD},{AMBER});-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-family:'DM Mono',monospace;}}

.hero{{font-size:2.8rem;font-weight:600;line-height:1.05;letter-spacing:-.05em;background:linear-gradient(135deg,{p.TEXT} 0%,{GOLD} 55%,{AMBER} 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-family:'Fraunces','Georgia',serif;}}
.hero-sub{{color:{p.MUTED};font-size:.9rem;margin-top:8px;line-height:1.65;font-weight:400;font-family:'Epilogue',sans-serif;}}
.hero-badge{{display:inline-block;background:rgba(232,180,56,0.1);color:{GOLD};border:1px solid rgba(232,180,56,0.25);font-size:.65rem;font-weight:800;padding:3px 11px;border-radius:10px;letter-spacing:.09em;text-transform:uppercase;margin-bottom:10px;font-family:'Epilogue',sans-serif;}}

[data-testid="stTabs"] [role="tablist"]{{background:rgba(8,9,30,0.85)!important;backdrop-filter:blur(16px)!important;border-radius:12px!important;padding:5px!important;border:1px solid {p.BORDER}!important;gap:2px;box-shadow:0 2px 16px {p.SHADOW};}}
[data-testid="stTabs"] [role="tab"]{{border-radius:9px!important;color:{p.MUTED}!important;font-weight:600!important;font-size:.82rem!important;padding:8px 18px!important;transition:all .18s ease!important;border:none!important;font-family:'Epilogue',sans-serif!important;}}
[data-testid="stTabs"] [role="tab"]:hover{{color:{p.TEXT}!important;background:{p.CARD2}!important;}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{{background:linear-gradient(135deg,rgba(232,180,56,0.18),rgba(232,180,56,0.08))!important;color:{GOLD}!important;box-shadow:0 2px 12px rgba(232,180,56,0.2),inset 0 0 0 1px rgba(232,180,56,0.3)!important;}}

[data-testid="stFileUploadDropzone"]{{background:rgba(8,9,30,0.75)!important;border:2px dashed {GOLD}40!important;border-radius:16px!important;padding:36px!important;backdrop-filter:blur(12px);}}
[data-testid="stFileUploadDropzone"]:hover{{border-color:{GOLD}80!important;background:rgba(232,180,56,0.04)!important;}}
[data-testid="stDataFrame"]{{border-radius:12px!important;overflow:hidden;border:1px solid {p.BORDER}!important;box-shadow:0 2px 16px {p.SHADOW};}}
.js-plotly-plot{{border-radius:14px!important;overflow:hidden;border:1px solid {p.BORDER};box-shadow:0 2px 20px {p.SHADOW};}}
[data-testid="stExpander"]{{background:rgba(8,9,30,0.75)!important;border:1px solid {p.BORDER}!important;border-radius:12px!important;}}
[data-testid="stExpander"] summary{{font-weight:700!important;color:{p.TEXT}!important;font-family:'Epilogue',sans-serif!important;}}

.pill{{display:inline-flex;align-items:center;gap:4px;padding:3px 11px;border-radius:18px;font-size:.7rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;font-family:'Epilogue',sans-serif;}}
.pill.live{{background:rgba(0,212,133,0.12);color:{EMERALD};border:1px solid rgba(0,212,133,0.25);}}
.pill.warn{{background:rgba(245,158,11,0.12);color:{AMBER};border:1px solid rgba(245,158,11,0.25);}}
.pill.info{{background:rgba(14,165,233,0.12);color:{AZURE};border:1px solid rgba(14,165,233,0.25);}}
.pill.gold{{background:rgba(232,180,56,0.12);color:{GOLD};border:1px solid rgba(232,180,56,0.25);}}
.pill.ruby{{background:rgba(255,57,96,0.12);color:{RUBY};border:1px solid rgba(255,57,96,0.25);}}
.sec-badge{{display:inline-block;padding:2px 8px;border-radius:7px;font-size:.63rem;font-weight:700;background:rgba(124,92,250,0.12);color:{VIOLET};border:1px solid rgba(124,92,250,0.22);font-family:'Epilogue',sans-serif;}}

.abox{{border-radius:12px;padding:14px 18px;margin-bottom:9px;border-left:3px solid;font-size:.84rem;line-height:1.65;font-family:'Epilogue',sans-serif;}}
.abox.warn{{background:rgba(245,158,11,0.07);border-color:{AMBER};color:{p.TEXT2};}}
.abox.danger{{background:rgba(255,57,96,0.07);border-color:{RUBY};color:{p.TEXT2};}}
.abox.ok{{background:rgba(0,212,133,0.07);border-color:{EMERALD};color:{p.TEXT2};}}
.abox.info{{background:rgba(14,165,233,0.07);border-color:{AZURE};color:{p.TEXT2};}}
.abox-title{{font-weight:800;margin-bottom:4px;font-size:.88rem;color:{p.TEXT};}}

.prog-wrap{{background:{p.CARD2};border-radius:6px;height:7px;overflow:hidden;margin-top:3px;}}
.prog-bar{{height:7px;border-radius:6px;transition:width .7s cubic-bezier(.34,1.56,.64,1);}}

.land-card{{background:rgba(8,9,30,0.8);backdrop-filter:blur(16px);border:1px solid {p.BORDER};border-radius:18px;padding:28px 20px;text-align:center;transition:transform .28s cubic-bezier(.34,1.56,.64,1),box-shadow .28s,border-color .28s;box-shadow:0 4px 24px {p.SHADOW};height:100%;position:relative;overflow:hidden;}}
.land-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,{GOLD}60,transparent);opacity:0;transition:opacity .25s;}}
.land-card:hover{{transform:translateY(-6px) scale(1.01);box-shadow:0 20px 48px {p.SHADOW};border-color:{GOLD}40;}}
.land-card:hover::before{{opacity:1;}}
.land-icon{{font-size:2.4rem;margin-bottom:12px;display:block;}}
.land-title{{font-size:.98rem;font-weight:800;color:{p.TEXT};margin-bottom:7px;font-family:'Epilogue',sans-serif;}}
.land-desc{{font-size:.78rem;color:{p.MUTED};line-height:1.65;}}

/* diff table colours */
.diff-new{{color:{EMERALD};font-weight:700;}}
.diff-exit{{color:{RUBY};font-weight:700;}}
.diff-up{{color:{TEAL};}}
.diff-dn{{color:{AMBER};}}

.rich-divider{{height:1px;background:linear-gradient(90deg,transparent,{GOLD}30,{AMBER}20,transparent);border:none;margin:28px 0;}}
.pos{{color:{EMERALD}!important;font-weight:600;}}
.neg{{color:{RUBY}!important;font-weight:600;}}
*::-webkit-scrollbar{{width:5px;height:5px;}}
*::-webkit-scrollbar-track{{background:{p.BG};}}
*::-webkit-scrollbar-thumb{{background:{p.BORDER2};border-radius:3px;}}
*::-webkit-scrollbar-thumb:hover{{background:{GOLD};}}
::selection{{background:{GOLD}30;color:{p.TEXT};}}
</style>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
_ICONS = {"":"📊","b":"💼","g":"📈","r":"📉","y":"💰","t":"🌊","pk":"🌸","vi":"🔮","re":"🔥"}

def kpi(label, value, sub="", cls="", delta=None, icon=None):
    d_html = ""
    if delta is not None:
        dc = "pos" if delta >= 0 else "neg"
        d_html = f"<div class='kpi-delta {dc}'>{'▲' if delta>=0 else '▼'} {abs(delta):.2f}%</div>"
    s_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    ico = icon or _ICONS.get(cls, "📊")
    return (f"<div class='kpi {cls}'><div class='kpi-glow'></div>"
            f"<span class='kpi-icon'>{ico}</span>"
            f"<div class='kpi-lbl'>{label}</div><div class='kpi-val'>{value}</div>"
            f"{s_html}{d_html}</div>")

def insight(icon, label, value, cls=""):
    return (f"<div class='ibox'><div class='ibox-icon'>{icon}</div>"
            f"<div class='ibox-lbl'>{label}</div>"
            f"<div class='ibox-val {cls}'>{value}</div></div>")

def mover_card(ticker, price, chg, chga, is_top=False):
    cls = "pos" if chg >= 0 else "neg"
    arr = "▲" if chg >= 0 else "▼"
    top = " top-mover" if is_top else ""
    return (f"<div class='mover{top}'>"
            f"<div class='mover-tick'>{ticker}</div>"
            f"<div style='font-size:.6rem;margin:-4px 0 6px;'>"
            f"<span class='sec-badge'>{get_sector(ticker)}</span></div>"
            f"<div class='mover-price'>GHS {price:.4f}</div>"
            f"<div class='mover-chg {cls}'>{arr} {abs(chg):.2f}%</div>"
            f"<div style='font-size:.7rem;color:#424870;margin-top:5px;font-family:DM Mono,monospace;'>"
            f"Δ {chga:+.4f}</div></div>")

def shdr(text, sub=None):
    p = th()
    s = (f"<span style='font-size:.76rem;font-weight:400;opacity:.5;margin-left:8px;"
         f"font-family:Epilogue,sans-serif;'>{sub}</span>") if sub else ""
    st.markdown(f"<div class='shdr'>{text}{s}</div>", unsafe_allow_html=True)

def alert_box(title, body, cls="info"):
    icons = {"warn":"⚠️","danger":"🚨","ok":"✅","info":"ℹ️","gold":"✦"}
    return (f"<div class='abox {cls}'>"
            f"<div class='abox-title'>{icons.get(cls,'')} {title}</div>"
            f"{body}</div>")

def pn(v): return "pos" if v >= 0 else "neg"
def _normalize(s): return re.sub(r"[^A-Z0-9]", "", s.upper())
def _to_float(val):
    try:
        f = float(re.sub(r"[^\d.\-]", "", str(val).replace(",", "")))
        return f if f == f else None
    except: return None

def tx_type(desc):
    if re.search(r"\bBought\b", desc, re.I): return "Buy"
    if re.search(r"\bSold\b",   desc, re.I): return "Sell"
    if re.search(r"Dividend|Div\b", desc, re.I): return "Dividend"
    if re.search(r"Contribution|Funding|Deposit", desc, re.I): return "Credit"
    if re.search(r"Withdrawal|Transfer.*Payout", desc, re.I): return "Withdrawal"
    return "Other"


# ─────────────────────────────────────────────────────────────────────────────
# LIVE PRICES
# ─────────────────────────────────────────────────────────────────────────────
def _parse_gse_api(data, tickers):
    n2o = {_normalize(t): t for t in tickers}
    wanted, out = set(n2o), {}
    for item in data:
        sym = _normalize(item.get("name", ""))
        if sym not in wanted: continue
        price = _to_float(item.get("price"))
        if not price or price <= 0: continue
        chg  = _to_float(item.get("change", 0))
        prev = price - chg if chg else price
        out[n2o[sym]] = {"price": price, "change_abs": chg,
                         "change_pct": round((chg/prev*100) if prev else 0.0, 2)}
    return out

def _parse_afx_html(html, tickers):
    from bs4 import BeautifulSoup
    n2o = {_normalize(t): t for t in tickers}
    wanted, out = set(n2o), {}
    soup  = BeautifulSoup(html, "html.parser")
    table = None
    div   = soup.find("div", class_="t")
    if div: table = div.find("table")
    if not table:
        for tbl in soup.find_all("table"):
            hdrs = [h.get_text(strip=True) for h in tbl.find_all("th")]
            if "Ticker" in hdrs and "Price" in hdrs: table = tbl; break
    if not table: return {}
    headers    = [h.get_text(strip=True) for h in table.find_all("th")]
    ti = headers.index("Ticker"); pi = headers.index("Price")
    ci = headers.index("Change") if "Change" in headers else None
    for tr in table.find("tbody").find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) <= pi: continue
        sym   = _normalize(cells[ti].get_text(strip=True))
        if sym not in wanted: continue
        price = _to_float(cells[pi].get_text(strip=True))
        if not price or price <= 0: continue
        chg  = (_to_float(cells[ci].get_text(strip=True)) or 0.0
                if ci and len(cells) > ci else 0.0)
        prev = price - chg
        out[n2o[sym]] = {"price": price, "change_abs": chg,
                         "change_pct": round((chg/prev*100) if prev else 0.0, 2)}
    return out

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_live(tickers):
    try:
        r = requests.get("https://dev.kwayisi.org/apis/gse/live",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code == 200: return _parse_gse_api(r.json(), tickers)
    except: pass
    try:
        r = requests.get("https://afx.kwayisi.org/gse/",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=10, verify=False)
        if r.status_code == 200: return _parse_afx_html(r.text, tickers)
    except: pass
    return {}

def get_live_prices(tickers):
    try:
        html = base64.b64decode(st.secrets["gse_html_b64"]).decode("utf-8")
        return _parse_afx_html(html, tickers)
    except: pass
    return _fetch_live(tickers)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_gse_index():
    """Fetch GSE Composite Index latest value from kwayisi."""
    try:
        r = requests.get("https://dev.kwayisi.org/apis/gse/live",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            for item in data:
                if "GSE" in str(item.get("name","")).upper() or "INDEX" in str(item.get("name","")).upper():
                    return _to_float(item.get("price")), str(item.get("name",""))
    except: pass
    return None, None


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
                        "value": float(m.group(2).replace(",","")), "alloc": float(m.group(3))}
                m2 = re.match(r"([\d,\.]+)\s+100\.00", l.strip())
                if m2: portfolio_summary["Total"] = float(m2.group(1).replace(",",""))

    m = re.search(r"IC Liquidity\s+([\d,\.]+)\s+-([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)", full_text)
    if m:
        funds_data = {"name":"IC Liquidity","invested":float(m.group(1).replace(",","")),
                      "redeemed":float(m.group(2).replace(",","")),"market_value":float(m.group(5))}

    eq_pat = re.compile(r"^([A-Z]{2,8})\s+(GH[A-Z0-9]+|TG[A-Z0-9]+)\s+([\d,\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d,\.]+)")
    for line in lines:
        m = eq_pat.match(line.strip())
        if m:
            qty=float(m.group(3).replace(",","")); cost=float(m.group(4))
            tc=qty*cost; mv=float(m.group(6).replace(",","")); gl=mv-tc
            equities.append({"ticker":m.group(1),"qty":qty,"avg_cost":cost,
                             "statement_price":float(m.group(5)),"live_price":None,
                             "market_value":mv,"total_cost":tc,"gain_loss":gl,
                             "gain_pct":(gl/tc*100) if tc else 0,"sector":get_sector(m.group(1))})

    for line in lines:
        line = line.strip()
        dm = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.*)", line)
        if not dm: continue
        date_str, rest = dm.group(1), dm.group(2).strip()
        nums = re.findall(r"-?[\d,]+\.\d{2}", rest)
        if len(nums) >= 2:
            try:
                credit=float(nums[-2].replace(",","")); debit=float(nums[-1].replace(",",""))
                desc=rest[:rest.rfind(nums[-2])].strip(); ttype=tx_type(desc)
                transactions.append({"date":datetime.strptime(date_str,"%d/%m/%Y"),
                    "date_str":date_str,"description":desc,
                    "credit":credit if credit>0 else 0,
                    "debit":abs(debit) if debit<0 else 0,"type":ttype})
            except: pass

    def _field(label):
        m = re.search(re.escape(label)+r"\s*(.+)", full_text)
        if not m: return ""
        v = m.group(1).strip().split("\n")[0].strip()
        return re.split(r"\s{3,}|\s+(?:Report Date|Account Number|Address|Report Currency):", v)[0].strip()

    return {"equities":equities,"transactions":transactions,
            "portfolio_summary":portfolio_summary,"funds":funds_data,
            "client_name":_field("Client Name:"),"account_number":_field("Account Number:"),
            "report_date":_field("Report Date:")}


# ─────────────────────────────────────────────────────────────────────────────
# INJECT LIVE PRICES
# ─────────────────────────────────────────────────────────────────────────────
def inject_live_prices(equities, live):
    out = []
    for e in equities:
        e = e.copy()
        if e["ticker"] in live:
            lp=live[e["ticker"]]["price"]; mv=e["qty"]*lp; gl=mv-e["total_cost"]
            e.update({"live_price":lp,"market_value":mv,"gain_loss":gl,
                      "gain_pct":(gl/e["total_cost"]*100) if e["total_cost"] else 0,
                      "change_pct":live[e["ticker"]]["change_pct"],
                      "change_abs":live[e["ticker"]]["change_abs"]})
        else:
            e["live_price"]=e["change_pct"]=e["change_abs"]=None
        out.append(e)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────────────────────
def compute_metrics(eq, txs, ps):
    ev=sum(e["market_value"] for e in eq); tc=sum(e["total_cost"] for e in eq)
    tg=sum(e["gain_loss"] for e in eq); gp=(tg/tc*100) if tc else 0
    cv=ps.get("Cash",{}).get("value",0); fv=ps.get("Funds",{}).get("value",0)
    tv=ev+cv+fv
    nc=sum(t["credit"] for t in txs if t["type"]=="Credit")
    nw=sum(t["debit"]  for t in txs if t["type"]=="Withdrawal")
    ni=nc-nw
    roi=((tv-ni)/ni*100) if ni>0 else 0
    div=sum(t["credit"] for t in txs if t["type"]=="Dividend")
    cagr=None; funding_txs=[t for t in txs if t["type"]=="Credit"]
    years=0.0
    if funding_txs and ni>0 and tv>0:
        first=min(t["date"] for t in funding_txs)
        years=(datetime.now()-first).days/365.25
        if years>=0.1: cagr=((tv/ni)**(1.0/years)-1)*100
    weights=[e["market_value"]/ev for e in eq] if ev else []
    hhi=round(sum(w**2 for w in weights)*10000) if weights else 0
    su=len(set(e["sector"] for e in eq)); winners=sum(1 for e in eq if e["gain_pct"]>=0)
    n=len(eq)
    hs=max(0,min(100,round(
        0.30*min(100,max(0,roi+30))+
        0.20*(winners/n*100 if n else 0)+
        0.15*(len([e for e in eq if ev and e["market_value"]/ev>0.05])/n*100 if n and ev else 0)+
        0.20*max(0,100-hhi/100)+
        0.15*min(100,su/max(1,n)*100*3))))
    active_month="N/A"
    if txs:
        _tdf=pd.DataFrame(txs); _tdf["month"]=_tdf["date"].dt.to_period("M")
        active_month=str(_tdf["month"].value_counts().idxmax())
    best=max(eq,key=lambda e:e["gain_pct"]); worst=min(eq,key=lambda e:e["gain_pct"])
    biggest=max(eq,key=lambda e:e["market_value"])
    return dict(ev=ev,tc=tc,tg=tg,gp=gp,cv=cv,fv=fv,tv=tv,ni=ni,nc=nc,nw=nw,
                roi=roi,cagr=cagr,div=div,hhi=hhi,hs=hs,winners=winners,
                active_month=active_month,best=best,worst=worst,biggest=biggest,
                su=su,years=years)

def compute_advanced(eq, txs, m):
    RF=18.0
    if eq and m["ev"]:
        rets=[e["gain_pct"] for e in eq]; ws=[e["market_value"]/m["ev"] for e in eq]
        wm=sum(r*w for r,w in zip(rets,ws)); var=sum(w*(r-wm)**2 for r,w in zip(rets,ws))
        vol=var**0.5
    else: vol=0.0
    cagr=m.get("cagr") or 0.0
    sharpe=(cagr-RF)/vol if vol>1e-6 else None
    max_dd=0.0
    if txs:
        df=pd.DataFrame(txs).sort_values("date")
        df["net"]=df["credit"]-df["debit"]; df["cumul"]=df["net"].cumsum()
        peak=df["cumul"].cummax()
        with np.errstate(divide="ignore",invalid="ignore"):
            dd=np.where(peak>0,(df["cumul"]-peak)/peak*100,0.0)
        max_dd=float(np.min(dd))
    enp=round(10000/m["hhi"],1) if m["hhi"]>0 else float(len(eq))
    consistency=sum(1 for e in eq if e["gain_pct"]>-5)/len(eq)*100 if eq else 0
    dyc=m["div"]/m["tc"]*100 if m["tc"] else 0
    dym=m["div"]/m["ev"]*100 if m["ev"] else 0
    holding_periods={}
    buy_txs=[t for t in txs if t["type"]=="Buy"]
    for e in eq:
        matches=[t for t in buy_txs if e["ticker"] in t["description"].upper()]
        if matches:
            holding_periods[e["ticker"]]=(datetime.now()-min(t["date"] for t in matches)).days
    avg_holding=int(np.mean(list(holding_periods.values()))) if holding_periods else None
    return dict(sharpe=sharpe,max_dd=max_dd,enp=enp,vol=vol,consistency=consistency,
                dyc=dyc,dym=dym,rf=RF,holding_periods=holding_periods,avg_holding=avg_holding)


# ─────────────────────────────────────────────────────────────────────────────
# FEE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
def compute_fees(txs):
    """Estimate total brokerage / levy fees paid on all buy and sell transactions."""
    rows = []
    total_fees = 0.0
    for t in txs:
        if t["type"] not in ("Buy","Sell"): continue
        vol = t["credit"] + t["debit"]
        fee_breakdown = {k: vol*v for k,v in IC_FEES.items()}
        total = sum(fee_breakdown.values())
        total_fees += total
        rows.append({"date": t["date"], "type": t["type"],
                     "volume": vol, "est_fees": total, **fee_breakdown})
    return rows, total_fees


# ─────────────────────────────────────────────────────────────────────────────
# DRIP SIMULATOR
# ─────────────────────────────────────────────────────────────────────────────
def simulate_drip(eq, txs, m):
    """
    Estimate portfolio value if every dividend had been reinvested at the price
    prevailing on the ex-div date (approximated as statement price for that ticker).
    """
    div_txs = [t for t in txs if t["type"] == "Dividend"]
    if not div_txs:
        return None, 0.0

    # Map ticker → current price for reinvestment
    price_map = {e["ticker"]: (e["live_price"] or e["statement_price"]) for e in eq}
    avg_price = np.mean(list(price_map.values())) if price_map else 1.0

    # For each dividend, estimate shares that would have been bought
    extra_value = 0.0
    drip_rows   = []
    for t in div_txs:
        div_amt = t["credit"]
        # Try to guess ticker from description
        guessed_ticker = None
        for ticker in price_map:
            if ticker in t["description"].upper():
                guessed_ticker = ticker
                break
        price = price_map.get(guessed_ticker, avg_price) if guessed_ticker else avg_price
        shares_bought = div_amt / price if price else 0
        current_value = shares_bought * price
        extra_value  += current_value
        drip_rows.append({"date":t["date"],"amount":div_amt,
                          "guessed_ticker":guessed_ticker or "?",
                          "price_at_reinvest":round(price,4),
                          "extra_shares":round(shares_bought,4),
                          "current_value":round(current_value,2)})

    return drip_rows, extra_value


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-STATEMENT TIMELINE
# ─────────────────────────────────────────────────────────────────────────────
def build_timeline(all_statements):
    """
    Given a list of parsed statement dicts (sorted by report_date),
    build a timeline DataFrame: date, total_value, equities_val, cash_val,
    gain_loss, net_invested, roi.
    """
    rows = []
    for s in all_statements:
        eq  = s["equities"]
        ps  = s["portfolio_summary"]
        txs = s["transactions"]
        ev  = sum(e["market_value"] for e in eq)
        cv  = ps.get("Cash",{}).get("value",0)
        fv  = ps.get("Funds",{}).get("value",0)
        tv  = ev + cv + fv
        tc  = sum(e["total_cost"] for e in eq)
        tg  = sum(e["gain_loss"] for e in eq)
        nc  = sum(t["credit"] for t in txs if t["type"]=="Credit")
        nw  = sum(t["debit"]  for t in txs if t["type"]=="Withdrawal")
        ni  = nc - nw
        roi = (tv-ni)/ni*100 if ni>0 else 0
        # Parse date
        try:
            dt = datetime.strptime(s["report_date"], "%d/%m/%Y")
        except:
            try: dt = datetime.strptime(s["report_date"], "%B %d, %Y")
            except: dt = datetime.now()
        rows.append({"date":dt,"label":s["report_date"],"total_value":tv,
                     "equities_val":ev,"cash_val":cv,"funds_val":fv,
                     "total_cost":tc,"gain_loss":tg,"net_invested":ni,"roi":roi,
                     "n_stocks":len(eq)})
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df["mom_change"] = df["total_value"].diff()
    df["mom_pct"]    = df["total_value"].pct_change()*100
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STATEMENT DIFF
# ─────────────────────────────────────────────────────────────────────────────
def diff_statements(old_s, new_s):
    old_eq = {e["ticker"]: e for e in old_s["equities"]}
    new_eq = {e["ticker"]: e for e in new_s["equities"]}
    old_ev = sum(e["market_value"] for e in old_s["equities"])
    new_ev = sum(e["market_value"] for e in new_s["equities"])
    rows = []
    all_tickers = set(old_eq) | set(new_eq)
    for t in sorted(all_tickers):
        if t in new_eq and t not in old_eq:
            e = new_eq[t]
            wt = e["market_value"]/new_ev*100 if new_ev else 0
            rows.append({"Ticker":t,"Status":"🟢 NEW","Sector":e["sector"],
                         "Old Weight":"—","New Weight":f"{wt:.1f}%",
                         "Qty Change":f"+{e['qty']:,.0f}",
                         "Value Change":f"+GHS {e['market_value']:,.2f}",
                         "Return":f"{e['gain_pct']:+.1f}%"})
        elif t in old_eq and t not in new_eq:
            e = old_eq[t]
            rows.append({"Ticker":t,"Status":"🔴 EXITED","Sector":e["sector"],
                         "Old Weight":f"{e['market_value']/old_ev*100:.1f}%" if old_ev else "—",
                         "New Weight":"—","Qty Change":f"-{e['qty']:,.0f}",
                         "Value Change":f"-GHS {e['market_value']:,.2f}",
                         "Return":f"{e['gain_pct']:+.1f}%"})
        else:
            oe=old_eq[t]; ne=new_eq[t]
            old_wt=oe["market_value"]/old_ev*100 if old_ev else 0
            new_wt=ne["market_value"]/new_ev*100 if new_ev else 0
            mv_chg=ne["market_value"]-oe["market_value"]
            qty_chg=ne["qty"]-oe["qty"]
            if abs(mv_chg) < 0.01 and abs(qty_chg) < 0.01:
                status = "➡️ UNCHANGED"
            elif new_wt > old_wt:
                status = "⬆️ INCREASED"
            else:
                status = "⬇️ REDUCED"
            rows.append({"Ticker":t,"Status":status,"Sector":ne["sector"],
                         "Old Weight":f"{old_wt:.1f}%","New Weight":f"{new_wt:.1f}%",
                         "Qty Change":f"{qty_chg:+,.0f}",
                         "Value Change":f"{'+'if mv_chg>=0 else ''}GHS {mv_chg:,.2f}",
                         "Return":f"{ne['gain_pct']:+.1f}%"})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def project_portfolio(current_value, cagr_pct, target_value, years_max=20):
    """Return DataFrame of projected values with optimistic / pessimistic bands."""
    if cagr_pct <= 0 or current_value <= 0: return None
    base   = cagr_pct / 100
    bull   = base * 1.4
    bear   = base * 0.6
    rows   = []
    yr     = 0
    for yr in np.arange(0, years_max + 0.25, 0.25):
        rows.append({
            "years": yr,
            "date": datetime.now() + timedelta(days=yr*365.25),
            "base":  current_value * (1+base)**yr,
            "bull":  current_value * (1+bull)**yr,
            "bear":  current_value * (1+bear)**yr,
        })
    df = pd.DataFrame(rows)
    # Find when base crosses target — coerce to plain Python datetime so
    # Plotly add_vline never receives a pandas Timestamp (causes TypeError)
    hits = df[df["base"] >= target_value]
    if not hits.empty:
        raw = hits.iloc[0]["date"]
        hit_date = raw.to_pydatetime() if hasattr(raw, "to_pydatetime") else raw
    else:
        hit_date = None
    return df, hit_date


# ─────────────────────────────────────────────────────────────────────────────
# HTML REPORT EXPORT
# ─────────────────────────────────────────────────────────────────────────────
def build_html_report(data, eq, txs, ps, m, am):
    p = th()
    ev = m["ev"]
    def row(label, val, color=""):
        c = f"color:{color};" if color else ""
        return f"<tr><td>{label}</td><td style='text-align:right;font-family:monospace;{c}'>{val}</td></tr>"

    stock_rows = ""
    for e in sorted(eq, key=lambda x: x["market_value"], reverse=True):
        wt  = e["market_value"]/ev*100 if ev else 0
        clr = "#00d485" if e["gain_pct"]>=0 else "#ff3960"
        stock_rows += f"""<tr>
          <td><b>{e['ticker']}</b></td>
          <td>{e['sector']}</td>
          <td style='text-align:right'>{e['qty']:,.0f}</td>
          <td style='text-align:right'>{e['avg_cost']:.4f}</td>
          <td style='text-align:right'>{(e['live_price'] or e['statement_price']):.4f}</td>
          <td style='text-align:right;color:{clr}'>{e['gain_pct']:+.1f}%</td>
          <td style='text-align:right'>GHS {e['market_value']:,.2f}</td>
          <td style='text-align:right'>{wt:.1f}%</td>
        </tr>"""

    generated = datetime.now().strftime("%d %B %Y at %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>IC Portfolio Report — {data['client_name']}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@600;900&family=Epilogue:wght@400;600;700&family=DM+Mono:wght@400;500&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#04060f;color:#eef0fa;font-family:'Epilogue',sans-serif;padding:40px;max-width:1100px;margin:0 auto;}}
  h1{{font-family:'Fraunces',serif;font-size:2.4rem;font-weight:600;
      background:linear-gradient(135deg,#eef0fa 0%,#e8b438 55%,#f59e0b 100%);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
      margin-bottom:6px;}}
  h2{{font-family:'Epilogue',sans-serif;font-size:1rem;font-weight:700;color:#e8b438;
      text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid #141838;
      padding-bottom:8px;margin:32px 0 16px;}}
  .badge{{display:inline-block;background:rgba(232,180,56,0.1);color:#e8b438;
          border:1px solid rgba(232,180,56,0.25);font-size:.65rem;font-weight:800;
          padding:3px 11px;border-radius:10px;letter-spacing:.09em;text-transform:uppercase;
          margin-bottom:12px;font-family:'Epilogue',sans-serif;}}
  .meta{{color:#424870;font-size:.8rem;margin-bottom:32px;font-family:'DM Mono',monospace;}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;}}
  .kpi-box{{background:#08091e;border:1px solid #141838;border-radius:12px;padding:16px 18px;}}
  .kpi-label{{font-size:.6rem;color:#424870;text-transform:uppercase;letter-spacing:.1em;
              font-weight:700;margin-bottom:8px;}}
  .kpi-value{{font-size:1.3rem;font-family:'DM Mono',monospace;font-weight:500;color:#eef0fa;}}
  .pos{{color:#00d485;}}.neg{{color:#ff3960;}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem;margin-bottom:16px;}}
  thead th{{background:#0c1028;color:#8898c8;font-size:.65rem;text-transform:uppercase;
            letter-spacing:.08em;padding:10px 12px;text-align:left;border-bottom:1px solid #141838;}}
  tbody tr{{border-bottom:1px solid #0c1028;}}
  tbody tr:hover{{background:#08091e;}}
  tbody td{{padding:9px 12px;color:#eef0fa;font-family:'DM Mono',monospace;font-size:.8rem;}}
  .footer{{margin-top:48px;padding-top:16px;border-top:1px solid #141838;
           font-size:.72rem;color:#424870;display:flex;justify-content:space-between;
           font-family:'Epilogue',sans-serif;}}
  @media print{{body{{background:#fff;color:#000;}}
    h1{{-webkit-text-fill-color:#000;}}
    .kpi-box{{background:#f9f9f9;border-color:#ddd;}}}}
</style>
</head>
<body>
<div class="badge">IC Securities · Ghana Stock Exchange</div>
<h1>IC Portfolio Report</h1>
<div class="meta">
  Client: <b style="color:#eef0fa">{data['client_name']}</b> &nbsp;·&nbsp;
  Account: <b style="color:#e8b438">{data['account_number']}</b> &nbsp;·&nbsp;
  Statement Date: {data['report_date']} &nbsp;·&nbsp;
  Generated: {generated}
</div>

<h2>Portfolio Summary</h2>
<div class="kpi-grid">
  <div class="kpi-box"><div class="kpi-label">Total Value</div>
    <div class="kpi-value">GHS {m['tv']:,.2f}</div></div>
  <div class="kpi-box"><div class="kpi-label">Unrealised G/L</div>
    <div class="kpi-value {'pos' if m['tg']>=0 else 'neg'}">
      {'+'if m['tg']>=0 else ''}GHS {m['tg']:,.2f}</div></div>
  <div class="kpi-box"><div class="kpi-label">ROI (net cash)</div>
    <div class="kpi-value {'pos' if m['roi']>=0 else 'neg'}">{m['roi']:+.2f}%</div></div>
  <div class="kpi-box"><div class="kpi-label">CAGR</div>
    <div class="kpi-value {'pos' if (m['cagr'] or 0)>=0 else 'neg'}">
      {f"{m['cagr']:+.2f}%" if m['cagr'] else '—'}</div></div>
  <div class="kpi-box"><div class="kpi-label">Health Score</div>
    <div class="kpi-value">{m['hs']}/100</div></div>
  <div class="kpi-box"><div class="kpi-label">Win Rate</div>
    <div class="kpi-value">{m['winners']}/{len(eq)} ({m['winners']/len(eq)*100:.0f}%)</div></div>
  <div class="kpi-box"><div class="kpi-label">Dividend Income</div>
    <div class="kpi-value">GHS {m['div']:,.2f}</div></div>
  <div class="kpi-box"><div class="kpi-label">Sharpe Ratio</div>
    <div class="kpi-value">{f"{am['sharpe']:+.2f}" if am['sharpe'] else '—'}</div></div>
</div>

<h2>Holdings ({len(eq)} positions)</h2>
<table>
  <thead><tr>
    <th>Ticker</th><th>Sector</th><th>Qty</th><th>Avg Cost</th>
    <th>Current Price</th><th>Return</th><th>Market Value</th><th>Weight</th>
  </tr></thead>
  <tbody>{stock_rows}</tbody>
</table>

<h2>Asset Allocation</h2>
<table>
  <thead><tr><th>Asset Class</th><th>Value</th><th>Allocation</th></tr></thead>
  <tbody>
    {''.join(f"<tr><td>{k}</td><td>GHS {v['value']:,.2f}</td><td>{v['alloc']:.1f}%</td></tr>" for k,v in ps.items() if k!='Total' and isinstance(v,dict))}
  </tbody>
</table>

<div class="footer">
  <span>IC Portfolio Analyser v4.0 · Elite Edition</span>
  <span>For informational purposes only · Past performance ≠ future results</span>
  <span>Prices via dev.kwayisi.org/apis/gse</span>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# SMART ALERTS
# ─────────────────────────────────────────────────────────────────────────────
def generate_alerts(eq, m, txs):
    alerts = []
    ev = m["ev"]
    for e in eq:
        wt = e["market_value"]/ev*100 if ev else 0
        if wt > 30:
            alerts.append(("danger",f"Extreme Concentration: {e['ticker']}",
                f"{e['ticker']} is {wt:.1f}% of equities — far above the 30% danger threshold."))
        elif wt > 20:
            alerts.append(("warn",f"High Concentration: {e['ticker']}",
                f"{e['ticker']} is {wt:.1f}% of equities. Consider trimming to below 15%."))
    big_losers = [e for e in eq if e["gain_pct"] < -20]
    if big_losers:
        alerts.append(("warn","Deep Losses > 20%",
            f"{', '.join(e['ticker'] for e in big_losers)} — down >20% from cost. Review thesis or set stop-loss levels."))
    if m["tv"] and m["cv"]/m["tv"] > 0.25:
        alerts.append(("info","High Cash Drag",
            f"Cash is {m['cv']/m['tv']*100:.1f}% of portfolio — idle cash erodes real returns at Ghana's inflation rate."))
    sec_df = pd.DataFrame(eq).groupby("sector")["market_value"].sum()
    if ev:
        for sec, val in sec_df.items():
            if val/ev > 0.60:
                alerts.append(("warn",f"Sector Over-exposure: {sec}",
                    f"{sec} is {val/ev*100:.1f}% of equities. Add cross-sector diversification."))
    if m["su"] == 1:
        alerts.append(("danger","Single-Sector Portfolio",
            "All positions are in one sector — zero sector diversification."))
    elif m["su"] < 3 and len(eq) >= 5:
        alerts.append(("warn","Limited Sector Diversification",
            f"Only {m['su']} sectors across {len(eq)} holdings."))
    if m["winners"]/len(eq) < 0.40:
        alerts.append(("warn","Low Win Rate",
            f"Only {m['winners']}/{len(eq)} positions are profitable."))
    # Real return warning
    if m["cagr"] is not None and m["years"] >= 0.5:
        rr = real_return(m["cagr"], m["years"])
        if rr and rr[0] < 0:
            alerts.append(("danger","Negative Real Return",
                f"Your CAGR of {m['cagr']:.1f}% is BELOW Ghana inflation ({rr[1]:.1f}% avg). "
                f"Real return: {rr[0]:+.1f}%. Your wealth is shrinking in real terms."))
        elif rr and rr[0] < 5:
            alerts.append(("warn","Low Real Return",
                f"After ~{rr[1]:.1f}% avg inflation your real CAGR is only {rr[0]:+.1f}%."))
    if not alerts:
        alerts.append(("ok","Portfolio Health: Good",
            "No critical issues detected. Sector diversification and concentration are reasonable."))
    return alerts


# ─────────────────────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def chart_gain_loss(eq):
    p  = th(); df = pd.DataFrame(eq).sort_values("gain_pct")
    clr = [EMERALD if v>=0 else RUBY for v in df["gain_pct"]]
    fig = go.Figure(go.Bar(x=df["gain_pct"], y=df["ticker"], orientation="h",
        marker=dict(color=clr, opacity=0.85, line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df["gain_pct"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        hovertemplate="<b>%{y}</b><br>Return: %{x:.2f}%<extra></extra>"))
    fig.add_vline(x=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(**T(title="Return per Stock (%)", xt="Return (%)"), height=380)
    return fig

def chart_sector_donut(eq):
    p  = th(); df = pd.DataFrame(eq)
    sd = df.groupby("sector")["market_value"].sum().reset_index().sort_values("market_value",ascending=False)
    clr = [SECTOR_COLORS.get(s, p.MUTED) for s in sd["sector"]]
    fig = go.Figure(go.Pie(labels=sd["sector"], values=sd["market_value"], hole=0.62,
        marker=dict(colors=clr, line=dict(color=p.BG, width=3)),
        texttemplate="<b>%{label}</b><br>%{percent:.1%}",
        textfont=dict(size=11, family="Epilogue"),
        hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f}<br>%{percent:.1%}<extra></extra>",
        sort=False))
    layout = T(title="Sector Allocation")
    layout["annotations"] = [dict(
        text=f"<b>{len(sd)}</b><br><span style='font-size:9px'>Sectors</span>",
        x=0.5, y=0.5, font=dict(size=18, color=p.TEXT, family="DM Mono"), showarrow=False)]
    layout["height"] = 340
    fig.update_layout(**layout)
    return fig

def chart_performance_attribution(eq, ev):
    p  = th(); df = pd.DataFrame(eq).copy()
    df["cp"] = (df["gain_loss"]/ev*100) if ev else 0
    df = df.sort_values("cp")
    clr = [EMERALD if v>=0 else RUBY for v in df["cp"]]
    fig = go.Figure(go.Bar(x=df["cp"], y=df["ticker"], orientation="h",
        marker=dict(color=clr, opacity=0.85, line=dict(width=0)),
        text=[f"{v:+.2f}%" for v in df["cp"]], textposition="outside",
        textfont=dict(color=p.TEXT2, size=10, family="DM Mono"),
        customdata=df["gain_loss"],
        hovertemplate="<b>%{y}</b><br>Contribution: %{x:+.2f}%<br>P&L: GHS %{customdata:,.2f}<extra></extra>"))
    fig.add_vline(x=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.update_layout(**T(title="Performance Attribution",
                          xt="Contribution (% of equity value)"), height=380)
    return fig

def chart_sector_performance(eq):
    p  = th(); df = pd.DataFrame(eq)
    sg = df.groupby("sector").agg(mv=("market_value","sum"),tc=("total_cost","sum"),
                                   gl=("gain_loss","sum")).reset_index().sort_values("mv",ascending=False)
    sg["ret"] = sg["gl"]/sg["tc"]*100
    fig = make_subplots(rows=1,cols=2,subplot_titles=["Market Value vs Cost by Sector","Sector Return (%)"],
                        column_widths=[0.6,0.4])
    fig.add_trace(go.Bar(name="Cost Basis",x=sg["sector"],y=sg["tc"],marker_color=AZURE,opacity=0.65),row=1,col=1)
    fig.add_trace(go.Bar(name="Market Value",x=sg["sector"],y=sg["mv"],marker_color=GOLD,opacity=0.9),row=1,col=1)
    bc = [EMERALD if v>=0 else RUBY for v in sg["ret"]]
    fig.add_trace(go.Bar(name="Return %",x=sg["sector"],y=sg["ret"],
        marker=dict(color=bc,opacity=0.85),text=[f"{v:+.1f}%" for v in sg["ret"]],
        textposition="outside",textfont=dict(size=10,family="DM Mono",color=p.TEXT2),
        showlegend=False),row=1,col=2)
    fig.add_hline(y=0,line_color=p.MUTED,line_dash="dash",row=1,col=2)
    layout = {**T(),"barmode":"group","height":360,
              "xaxis":dict(tickangle=-20,gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
              "xaxis2":dict(tickangle=-20,gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
              "yaxis":dict(title=dict(text="GHS"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
              "yaxis2":dict(title=dict(text="Return (%)"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED))}
    fig.update_layout(**layout)
    return fig

def chart_market_vs_cost(eq):
    p  = th(); df = pd.DataFrame(eq).sort_values("market_value",ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Cost Basis",x=df["ticker"],y=df["total_cost"],
                         marker_color=AZURE,opacity=0.7,hovertemplate="%{x}: GHS %{y:,.2f}<extra>Cost</extra>"))
    fig.add_trace(go.Bar(name="Market Value",x=df["ticker"],y=df["market_value"],
                         marker_color=GOLD,opacity=0.9,hovertemplate="%{x}: GHS %{y:,.2f}<extra>Market</extra>"))
    for _,row in df.iterrows():
        gl=row["gain_pct"]
        fig.add_annotation(x=row["ticker"],y=max(row["total_cost"],row["market_value"]),
                           text=f"{gl:+.1f}%",showarrow=False,yshift=12,
                           font=dict(color=EMERALD if gl>=0 else RUBY,size=9,family="DM Mono"))
    fig.update_layout(**T(title="Market Value vs Cost Basis", yt="GHS"), barmode="group", height=380)
    return fig

def chart_pl_waterfall(eq):
    p  = th(); df = pd.DataFrame(eq).sort_values("gain_loss")
    total = df["gain_loss"].sum()
    tickers = df["ticker"].tolist()+["TOTAL"]; vals = df["gain_loss"].tolist()+[total]
    clr = [EMERALD if v>=0 else RUBY for v in vals]; clr[-1] = GOLD if total>=0 else RUBY
    fig = go.Figure(go.Bar(x=tickers,y=vals,
        marker=dict(color=clr,opacity=[0.8]*len(df)+[1.0],line=dict(width=0)),
        text=[f"{'+'if v>=0 else ''}GHS {v:,.0f}" for v in vals],
        textposition="outside",textfont=dict(color=p.TEXT2,size=10,family="DM Mono"),
        hovertemplate="<b>%{x}</b><br>P&L: GHS %{y:,.2f}<extra></extra>"))
    fig.add_hline(y=0,line_color=p.MUTED,line_dash="dash",line_width=1)
    fig.update_layout(**T(title="P&L Contribution per Stock (GHS)", yt="GHS"), height=340)
    return fig

def chart_portfolio_efficiency(eq):
    p  = th(); df = pd.DataFrame(eq).copy()
    df["eff"] = df["gain_loss"]/df["total_cost"].replace(0,1)*100
    df = df.sort_values("eff")
    clr = [EMERALD if v>=0 else RUBY for v in df["eff"]]
    fig = go.Figure(go.Bar(x=df["eff"],y=df["ticker"],orientation="h",
        marker=dict(color=clr,opacity=0.85,line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df["eff"]],textposition="outside",
        textfont=dict(color=p.TEXT2,size=10,family="DM Mono"),
        customdata=df["gain_loss"],
        hovertemplate="<b>%{y}</b><br>Efficiency: %{x:+.1f}%<br>P&L: GHS %{customdata:,.2f}<extra></extra>"))
    fig.add_vline(x=0,line_color=p.MUTED,line_dash="dash",line_width=1)
    fig.update_layout(**T(title="Portfolio Efficiency — Gain / GHS Invested (%)", xt="ROI (%)"), height=360)
    return fig

def chart_risk_return_scatter(eq, ev):
    p  = th(); df = pd.DataFrame(eq).copy()
    df["weight"] = df["market_value"]/ev*100 if ev else 0
    ew = 100/len(eq) if eq else 10
    fig = go.Figure()
    for sector in df["sector"].unique():
        sub = df[df["sector"]==sector]
        fig.add_trace(go.Scatter(x=sub["weight"],y=sub["gain_pct"],
            mode="markers+text",name=sector,
            marker=dict(size=sub["market_value"]/sub["market_value"].max()*40+12,
                        color=SECTOR_COLORS.get(sector,p.MUTED),opacity=0.82,
                        line=dict(color=p.BG,width=2)),
            text=sub["ticker"],textposition="top center",
            textfont=dict(size=9,color=p.TEXT2,family="Epilogue"),
            customdata=sub[["market_value","gain_loss","sector"]].values,
            hovertemplate=("<b>%{text}</b><br>Sector: %{customdata[2]}<br>"
                           "Weight: %{x:.1f}%<br>Return: %{y:+.1f}%<br>"
                           "MV: GHS %{customdata[0]:,.2f}<extra></extra>")))
    fig.add_hline(y=0,line_color=p.MUTED,line_dash="dash",line_width=1)
    fig.add_vline(x=ew,line_color=GOLD,line_dash="dot",line_width=1)
    fig.add_annotation(
        x=ew, y=1, xref='x', yref='paper',
        text=f" Equal weight ({ew:.1f}%)", showarrow=False,
        xanchor='left', yanchor='top',
        font=dict(color=GOLD,size=9,family="DM Mono"))
    fig.update_layout(**T(title="Risk / Return Matrix — Bubble size = Market Value",
                          xt="Portfolio Weight (%)", yt="Return (%)"), height=440)
    return fig

def chart_concentration(eq):
    p  = th(); df = pd.DataFrame(eq)
    tot = df["market_value"].sum(); w = df["market_value"]/tot
    hhi = round((w**2).sum()*10000)
    if hhi<1500: risk,rc="Low",EMERALD
    elif hhi<2500: risk,rc="Moderate",AMBER
    else: risk,rc="High",RUBY
    fig = make_subplots(rows=1,cols=2,subplot_titles=["HHI Concentration Score","Exposure by Stock"],
                        specs=[[{"type":"indicator"},{"type":"xy"}]])
    fig.add_trace(go.Indicator(mode="gauge+number+delta",value=hhi,
        delta=dict(reference=1500,valueformat=".0f",increasing=dict(color=RUBY),decreasing=dict(color=EMERALD)),
        number=dict(font=dict(color=rc,size=34,family="DM Mono"),suffix=" HHI"),
        gauge=dict(axis=dict(range=[0,10000],tickcolor=p.MUTED,tickfont=dict(color=p.MUTED,size=8,family="DM Mono")),
                   bar=dict(color=rc,thickness=0.28),bgcolor=p.CARD2,bordercolor=p.BORDER,
                   steps=[dict(range=[0,1500],color="rgba(0,212,133,0.1)"),
                          dict(range=[1500,2500],color="rgba(245,158,11,0.1)"),
                          dict(range=[2500,10000],color="rgba(255,57,96,0.1)")],
                   threshold=dict(line=dict(color=rc,width=3),thickness=0.8,value=hhi)),
        title=dict(text=f"<b>{risk}</b> Concentration",font=dict(color=rc,size=13,family="Epilogue"))),row=1,col=1)
    df_s = df.sort_values("market_value",ascending=True)
    ws   = (df_s["market_value"]/tot*100).values
    fig.add_trace(go.Bar(x=ws,y=df_s["ticker"].values,orientation="h",
        marker=dict(color=[SECTOR_COLORS.get(s,p.MUTED) for s in df_s["sector"]],line=dict(width=0),opacity=0.85),
        text=[f"{v:.1f}%" for v in ws],textposition="outside",
        textfont=dict(color=p.TEXT2,size=10,family="DM Mono"),
        customdata=df_s["sector"].values,
        hovertemplate="<b>%{y}</b>: %{x:.1f}%<br>Sector: %{customdata}<extra></extra>",
        showlegend=False),row=1,col=2)
    layout = {"paper_bgcolor":p.BG,"plot_bgcolor":p.CARD,"font":dict(color=p.TEXT2,family="DM Mono"),
              "margin":dict(l=16,r=16,t=60,b=16),"height":380,
              "xaxis2":dict(gridcolor=p.BORDER,title=dict(text="Weight (%)"),tickfont=dict(color=p.MUTED)),
              "yaxis2":dict(gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
              "hoverlabel":dict(bgcolor=p.CARD2,bordercolor=p.BORDER,font=dict(color=p.TEXT)),
              "legend":dict(bgcolor=p.CARD2,bordercolor=p.BORDER),
              "title":dict(font=dict(color=p.TEXT,family="Epilogue",size=14),x=0.01)}
    fig.update_layout(**layout)
    return fig, hhi, risk, rc

def chart_breakeven(eq):
    p      = th(); losers=[e for e in eq if e["gain_pct"]<0]
    if not losers: return None
    df = pd.DataFrame(losers); pc = df["live_price"].fillna(df["statement_price"])
    pct_need=(df["avg_cost"]-pc)/pc*100; gap_ghs=(df["avg_cost"]-pc)*df["qty"]
    fig = make_subplots(rows=1,cols=2,subplot_titles=["Price Gap to Break-even","GHS Loss to Recover"],
                        specs=[[{"type":"xy"},{"type":"xy"}]])
    fig.add_trace(go.Bar(name="Current Price",x=df["ticker"],y=pc,marker_color=RUBY,opacity=0.8),row=1,col=1)
    fig.add_trace(go.Bar(name="Break-even",x=df["ticker"],y=df["avg_cost"],marker_color=GOLD,opacity=0.8),row=1,col=1)
    fig.add_trace(go.Scatter(name="% Rally Needed",x=df["ticker"],y=pct_need,yaxis="y2",
        mode="markers+text",marker=dict(size=13,color=AMBER,symbol="diamond",line=dict(color=p.BG,width=2)),
        text=[f"+{v:.1f}%" for v in pct_need],textposition="top center",
        textfont=dict(color=AMBER,size=9,family="DM Mono")),row=1,col=1)
    fig.add_trace(go.Bar(name="GHS to Recover",x=df["ticker"],y=gap_ghs.abs(),
        marker=dict(color=gap_ghs.abs(),colorscale=[[0,GOLD],[1,RUBY]],line=dict(width=0)),
        text=[f"GHS {v:,.0f}" for v in gap_ghs.abs()],textposition="outside",
        textfont=dict(size=9,family="DM Mono")),row=1,col=2)
    layout = {**T(),"title":dict(text="Break-even Analysis",font=dict(color=p.TEXT,family="Epilogue",size=14),x=0.01),
              "barmode":"group","height":380,
              "yaxis":dict(title=dict(text="Price (GHS)"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
              "yaxis2":dict(title=dict(text="% Rally Needed"),overlaying="y",side="right",showgrid=False,
                            color=AMBER,tickfont=dict(color=AMBER,family="DM Mono")),
              "yaxis3":dict(title=dict(text="GHS to Recover"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
              "xaxis2":dict(gridcolor=p.BORDER,tickfont=dict(color=p.MUTED))}
    fig.update_layout(**layout)
    return fig

def chart_cashflow(txs):
    p  = th(); df=pd.DataFrame(txs)
    if df.empty: return None
    df["month"]=df["date"].dt.to_period("M")
    mg=df.groupby("month").agg(credits=("credit","sum"),debits=("debit","sum")).reset_index()
    mg["month_str"]=mg["month"].astype(str); mg["net"]=mg["credits"]-mg["debits"]; mg["cumnet"]=mg["net"].cumsum()
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.65,0.35],vertical_spacing=0.06,
                      subplot_titles=["Monthly Credits & Debits","Cumulative Net Flow"])
    fig.add_trace(go.Bar(name="Credits",x=mg["month_str"],y=mg["credits"],marker_color=EMERALD,opacity=0.8),row=1,col=1)
    fig.add_trace(go.Bar(name="Debits",x=mg["month_str"],y=mg["debits"],marker_color=RUBY,opacity=0.8),row=1,col=1)
    fig.add_trace(go.Scatter(name="Net",x=mg["month_str"],y=mg["net"],mode="lines+markers",
                             line=dict(color=GOLD,width=2.5),marker=dict(size=5,color=GOLD)),row=1,col=1)
    fig.add_trace(go.Bar(name="Cumul",x=mg["month_str"],y=mg["cumnet"],
                         marker_color=[EMERALD if v>=0 else RUBY for v in mg["cumnet"]],
                         opacity=0.72,showlegend=False),row=2,col=1)
    fig.add_hline(y=0,line_color=p.MUTED,line_dash="dash",line_width=1,row=1,col=1)
    fig.add_hline(y=0,line_color=p.MUTED,line_dash="dash",line_width=1,row=2,col=1)
    layout={**T(),"barmode":"group","height":500,
            "xaxis2":dict(tickangle=-30,gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
            "yaxis":dict(title=dict(text="GHS"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
            "yaxis2":dict(title=dict(text="GHS"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED))}
    fig.update_layout(**layout)
    return fig

def chart_dividend_timeline(txs):
    p  = th(); dt=[t for t in txs if t["type"]=="Dividend"]
    if not dt: return None
    df=pd.DataFrame(dt); df["month"]=df["date"].dt.to_period("M").astype(str)
    mg=df.groupby("month")["credit"].sum().reset_index()
    fig=go.Figure(go.Bar(x=mg["month"],y=mg["credit"],
        marker=dict(color=TEAL,opacity=0.85,line=dict(width=0)),
        text=[f"GHS {v:,.2f}" for v in mg["credit"]],textposition="outside",
        textfont=dict(color=p.TEXT2,size=9,family="DM Mono"),
        hovertemplate="%{x}<br>Dividends: GHS %{y:,.2f}<extra></extra>"))
    fig.update_layout(**T(title="Dividend Income by Month", yt="GHS"), height=280)
    return fig

def chart_cumulative(txs, tv):
    p  = th(); df=pd.DataFrame(txs).sort_values("date")
    if df.empty: return None
    df["net"]=df["credit"]-df["debit"]; df["cumul"]=df["net"].cumsum()
    profit=tv-df["cumul"].iloc[-1]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=df["date"],y=df["cumul"],mode="lines",fill="tozeroy",
        fillcolor="rgba(232,180,56,0.08)",line=dict(color=GOLD,width=2.5),name="Net Invested",
        hovertemplate="%{x|%b %d, %Y}<br>Invested: GHS %{y:,.2f}<extra></extra>"))
    fig.add_hline(y=tv,line_color=EMERALD,line_dash="dash",line_width=2)
    fig.add_annotation(
        x=1, y=tv, xref='paper', yref='y',
        text=f" Portfolio Value GHS {tv:,.0f}", showarrow=False,
        xanchor='right', yanchor='bottom',
        font=dict(color=EMERALD,size=10,family="DM Mono"))
    fig.update_layout(**T(title=f"Net Invested vs Current Value ({'+'if profit>=0 else ''}GHS {profit:,.0f} unrealised)",
                          xt="Date",yt="GHS"), height=320)
    return fig

def chart_drawdown(txs, tv):
    p  = th(); df=pd.DataFrame(txs).sort_values("date")
    if df.empty: return None
    df["net"]=df["credit"]-df["debit"]; df["cumul"]=df["net"].cumsum()
    scale=tv/df["cumul"].iloc[-1] if df["cumul"].iloc[-1] else 1
    df["scaled"]=df["cumul"]*scale
    peak=df["scaled"].cummax()
    with np.errstate(divide="ignore",invalid="ignore"):
        dd=np.where(peak>0,(df["scaled"]-peak)/peak*100,0.0)
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=df["date"],y=dd,mode="lines",fill="tozeroy",
        fillcolor="rgba(255,57,96,0.10)",line=dict(color=RUBY,width=2),name="Drawdown",
        hovertemplate="%{x|%b %d %Y}<br>Drawdown: %{y:.2f}%<extra></extra>"))
    fig.add_hline(y=0,line_color=p.MUTED,line_dash="dash",line_width=1)
    fig.update_layout(**T(title="Portfolio Drawdown (%) from Peak",xt="Date",yt="Drawdown (%)"),height=300)
    return fig

def chart_timeline(df_tl):
    """Multi-statement equity curve."""
    p  = th()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_tl["date"],y=df_tl["total_value"],mode="lines+markers",
        name="Total Value",line=dict(color=GOLD,width=3),marker=dict(size=8,color=GOLD,line=dict(color=p.BG,width=2)),
        text=df_tl["label"],hovertemplate="<b>%{text}</b><br>Total: GHS %{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=df_tl["date"],y=df_tl["equities_val"],mode="lines+markers",
        name="Equities",line=dict(color=VIOLET,width=2,dash="dot"),marker=dict(size=6,color=VIOLET),
        hovertemplate="<b>%{x|%b %Y}</b><br>Equities: GHS %{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=df_tl["date"],y=df_tl["net_invested"],mode="lines",
        name="Net Invested",line=dict(color=SLATE,width=1.5,dash="dot"),
        hovertemplate="<b>%{x|%b %Y}</b><br>Net Invested: GHS %{y:,.2f}<extra></extra>"))
    # Shade area between net_invested and total_value
    fig.add_trace(go.Scatter(x=pd.concat([df_tl["date"],df_tl["date"].iloc[::-1]]),
        y=pd.concat([df_tl["total_value"],df_tl["net_invested"].iloc[::-1]]),
        fill="toself",fillcolor="rgba(232,180,56,0.07)",line=dict(width=0),
        name="Unrealised Gain",hoverinfo="skip"))
    fig.update_layout(**T(title="Portfolio Value Over Time — All Statements",xt="Date",yt="GHS"),height=380)
    return fig

def chart_timeline_roi(df_tl):
    """ROI over time from multi-statement."""
    p  = th()
    clr=[EMERALD if v>=0 else RUBY for v in df_tl["roi"]]
    fig=go.Figure(go.Bar(x=df_tl["label"],y=df_tl["roi"],
        marker=dict(color=clr,opacity=0.85,line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in df_tl["roi"]],textposition="outside",
        textfont=dict(color=p.TEXT2,size=10,family="DM Mono"),
        hovertemplate="%{x}<br>ROI: %{y:+.2f}%<extra></extra>"))
    fig.add_hline(y=0,line_color=p.MUTED,line_dash="dash",line_width=1)
    fig.update_layout(**T(title="Portfolio ROI at Each Statement Date",yt="ROI (%)"),height=300)
    return fig

def chart_monthly_heatmap(txs):
    p  = th()
    if not txs: return None
    df=pd.DataFrame(txs); df["year"]=df["date"].dt.year; df["month"]=df["date"].dt.month
    df["net"]=df["credit"]-df["debit"]
    pivot=df.groupby(["year","month"])["net"].sum().reset_index().pivot(index="year",columns="month",values="net").fillna(0)
    months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    z_vals,y_vals=[],[]
    for yr in sorted(pivot.index,reverse=True):
        z_vals.append([float(pivot.loc[yr,col]) if col in pivot.columns else 0 for col in range(1,13)])
        y_vals.append(str(yr))
    fig=go.Figure(go.Heatmap(z=z_vals,x=months,y=y_vals,
        colorscale=[[0,RUBY],[0.5,p.CARD2],[1,EMERALD]],zmid=0,
        text=[[f"GHS {v:+,.0f}" if v!=0 else "—" for v in row] for row in z_vals],
        texttemplate="%{text}",textfont=dict(size=9,family="DM Mono"),
        hovertemplate="<b>%{y} %{x}</b><br>Net: GHS %{z:+,.2f}<extra></extra>",
        showscale=True,colorbar=dict(tickfont=dict(color=p.TEXT2,size=9,family="DM Mono"),
            outlinecolor=p.BORDER,outlinewidth=1,title=dict(text="GHS",font=dict(color=p.MUTED,size=9)))))
    hm_layout = T(title="Monthly Net Cash Flow Calendar")
    hm_layout["margin"] = dict(l=16,r=16,t=80,b=16)
    hm_layout["xaxis"]  = dict(side="top",gridcolor=p.BORDER,tickcolor=p.MUTED,tickfont=dict(color=p.TEXT2,family="Epilogue"))
    hm_layout["yaxis"]  = dict(gridcolor=p.BORDER,tickcolor=p.MUTED,tickfont=dict(color=p.TEXT2,family="DM Mono"))
    hm_layout["height"] = max(200,len(y_vals)*50+90)
    fig.update_layout(**hm_layout)
    return fig

def chart_projection(df_proj, current_value, target_value, hit_date):
    p  = th()
    # Plotly add_vline requires a string x value for date axes — convert everything upfront
    dates_fwd = df_proj["date"].apply(lambda d: d.strftime("%Y-%m-%d")).tolist()
    dates_rev = df_proj["date"].iloc[::-1].apply(lambda d: d.strftime("%Y-%m-%d")).tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates_fwd + dates_rev,
        y=pd.concat([df_proj["bull"], df_proj["bear"].iloc[::-1]]).tolist(),
        fill="toself", fillcolor="rgba(232,180,56,0.08)", line=dict(width=0),
        name="Optimistic–Pessimistic Band", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=dates_fwd, y=df_proj["bull"].tolist(), mode="lines",
        name="Optimistic (+40% CAGR)", line=dict(color=EMERALD, width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=dates_fwd, y=df_proj["bear"].tolist(), mode="lines",
        name="Pessimistic (−40% CAGR)", line=dict(color=RUBY, width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=dates_fwd, y=df_proj["base"].tolist(), mode="lines",
        name="Base (current CAGR)", line=dict(color=GOLD, width=3),
        hovertemplate="%{x}<br>Base: GHS %{y:,.0f}<extra></extra>"))
    fig.add_hline(y=current_value, line_color=VIOLET, line_dash="dash", line_width=1)
    fig.add_annotation(
        x=1, y=current_value, xref='paper', yref='y',
        text=" Current", showarrow=False,
        xanchor='right', yanchor='bottom',
        font=dict(color=VIOLET, size=9, family="DM Mono"))
    fig.add_hline(y=target_value, line_color=GOLD, line_dash="dash", line_width=2)
    fig.add_annotation(
        x=1, y=target_value, xref='paper', yref='y',
        text=f" Target GHS {target_value:,.0f}", showarrow=False,
        xanchor='right', yanchor='bottom',
        font=dict(color=GOLD, size=10, family="DM Mono"))
    if hit_date:
        # add_vline with annotation triggers Plotly's internal _mean() on x values
        # which crashes on date axes (Timestamp arithmetic error).
        # Safe fix: add_shape (no annotation math) + add_annotation separately.
        hit_str = (hit_date.strftime("%Y-%m-%d")
                   if hasattr(hit_date, "strftime")
                   else str(hit_date)[:10])
        hit_label = (hit_date.strftime("%b %Y")
                     if hasattr(hit_date, "strftime")
                     else hit_str[:7])
        fig.add_shape(type="line", x0=hit_str, x1=hit_str, y0=0, y1=1,
                      xref="x", yref="paper",
                      line=dict(color=EMERALD, width=2, dash="dot"))
        fig.add_annotation(x=hit_str, y=1, xref="x", yref="paper",
                           text=f" {hit_label}", showarrow=False,
                           xanchor="left", yanchor="top",
                           font=dict(color=EMERALD, size=10, family="DM Mono"))
    fig.update_layout(**T(title="Wealth Projection Engine", xt="Date", yt="GHS"), height=420)
    return fig

def chart_fees_over_time(fee_rows):
    p  = th()
    df = pd.DataFrame(fee_rows).sort_values("date")
    df["cumul_fees"] = df["est_fees"].cumsum()
    fig = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.5,0.5],
                        vertical_spacing=0.06,subplot_titles=["Fee per Transaction","Cumulative Fees Paid"])
    fig.add_trace(go.Bar(name="Buy fees",x=df[df["type"]=="Buy"]["date"],
                         y=df[df["type"]=="Buy"]["est_fees"],marker_color=AZURE,opacity=0.85),row=1,col=1)
    fig.add_trace(go.Bar(name="Sell fees",x=df[df["type"]=="Sell"]["date"],
                         y=df[df["type"]=="Sell"]["est_fees"],marker_color=AMBER,opacity=0.85),row=1,col=1)
    fig.add_trace(go.Scatter(name="Cumulative",x=df["date"],y=df["cumul_fees"],
        mode="lines+markers",line=dict(color=RUBY,width=2.5),marker=dict(size=5,color=RUBY)),row=2,col=1)
    layout={**T(),"barmode":"overlay","height":480,
            "xaxis2":dict(tickangle=-20,gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
            "yaxis":dict(title=dict(text="GHS fees"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED)),
            "yaxis2":dict(title=dict(text="Cumulative GHS"),gridcolor=p.BORDER,tickfont=dict(color=p.MUTED))}
    fig.update_layout(**layout)
    return fig

def chart_real_vs_nominal(m):
    """Bar chart comparing nominal CAGR vs real CAGR after Ghana inflation."""
    p  = th()
    if m["cagr"] is None or m["years"] < 0.5: return None
    rr = real_return(m["cagr"], m["years"])
    if rr is None: return None
    real_val, avg_cpi = rr
    categories = ["Nominal CAGR", f"Avg Ghana CPI\n({avg_cpi:.1f}%)", "Real CAGR"]
    values     = [m["cagr"], -avg_cpi, real_val]
    clr        = [GOLD, RUBY, EMERALD if real_val >= 0 else RUBY]
    fig = go.Figure(go.Bar(x=categories, y=values,
        marker=dict(color=clr, opacity=0.85, line=dict(width=0)),
        text=[f"{v:+.1f}%" for v in values], textposition="outside",
        textfont=dict(color=p.TEXT2, size=12, family="DM Mono"),
        hovertemplate="%{x}: %{y:+.2f}%<extra></extra>"))
    fig.add_hline(y=0, line_color=p.MUTED, line_dash="dash", line_width=1)
    fig.add_hline(y=avg_cpi, line_color=RUBY, line_dash="dot", line_width=1)
    fig.add_annotation(
        x=1, y=avg_cpi, xref='paper', yref='y',
        text=f" Inflation hurdle {avg_cpi:.1f}%", showarrow=False,
        xanchor='right', yanchor='bottom',
        font=dict(color=RUBY, size=9, family="DM Mono"))
    fig.update_layout(**T(title=f"Nominal vs Real Returns — Ghana CPI {avg_cpi:.1f}% avg",
                          yt="Annual Return (%)"), height=340)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    p = th()
    with st.sidebar:
        st.markdown(f"<div style='font-size:.7rem;color:{p.MUTED};font-weight:800;"
                    f"text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;"
                    f"font-family:Epilogue,sans-serif;'>📡 Live GSE Prices</div>",
                    unsafe_allow_html=True)
        st.success("✅ GSE-API (dev.kwayisi.org) + afx fallback")
        if st.button("🔄 Refresh Prices", use_container_width=True, type="primary"):
            st.cache_data.clear(); st.rerun()
        if "statements" in st.session_state and st.session_state["statements"]:
            stmts = st.session_state["statements"]
            st.markdown(f"<div style='font-size:.72rem;color:{p.MUTED};margin-top:12px;"
                        f"font-family:Epilogue,sans-serif;'>"
                        f"<b style='color:{GOLD}'>{len(stmts)}</b> statement(s) loaded</div>",
                        unsafe_allow_html=True)
            if st.button("🗑️ Clear All Statements", use_container_width=True):
                st.session_state["statements"] = []
                st.rerun()
        st.divider()
        st.markdown(f"<div style='font-size:.7rem;color:{p.MUTED};line-height:1.7;"
                    f"font-family:Epilogue,sans-serif;'>"
                    f"<b style='color:{GOLD};'>IC Portfolio Analyser v4.0</b><br>"
                    f"Elite Edition · March 2026<br>For informational purposes only.</div>",
                    unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    apply_theme()
    render_sidebar()
    p = th()

    if "statements" not in st.session_state:
        st.session_state["statements"] = []

    cl, ct, _ = st.columns([1, 7, 2])
    with cl:
        st.markdown(f"<div style='font-size:3.2rem;padding-top:4px;line-height:1;"
                    f"filter:drop-shadow(0 0 24px {GOLD}60);'>₵</div>",
                    unsafe_allow_html=True)
    with ct:
        st.markdown(f"<div class='hero-badge'>IC Securities · Ghana Stock Exchange</div>"
                    f"<div class='hero'>IC Portfolio Analyser</div>"
                    f"<div class='hero-sub'>"
                    f"Upload one or many statements · Live GSE prices · Real returns · "
                    f"Fees · DRIP · Goals · Timeline"
                    f"</div>", unsafe_allow_html=True)

    # ── Multi-file upload ─────────────────────────────────────────────────────
    uploaded_files = st.file_uploader(
        "**📄 Upload one or multiple IC Securities Statements (PDF)**",
        type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        existing_names = {s["_filename"] for s in st.session_state["statements"]}
        new_count = 0
        for f in uploaded_files:
            if f.name not in existing_names:
                with st.spinner(f"Parsing {f.name}…"):
                    parsed = parse_pdf(f.read())
                    parsed["_filename"] = f.name
                    st.session_state["statements"].append(parsed)
                    new_count += 1
        if new_count:
            st.success(f"✅ Loaded {new_count} new statement(s). Total: {len(st.session_state['statements'])}")

    statements = st.session_state["statements"]

    if not statements:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        cols = st.columns(4)
        features = [
            ("📊","Overview & Alerts","ROI, CAGR, Health Score, smart alerts, real returns vs Ghana CPI."),
            ("📈","Performance","Attribution, waterfall, sector charts, efficiency, live prices."),
            ("🔬","Analytics","Sharpe, MaxDD, ENP, Risk/Return matrix, goals & projection engine."),
            ("⚖️","Risk & Scenarios","HHI, break-even, rebalance recommendations, What-If simulator."),
        ]
        cols2 = st.columns(4)
        features2 = [
            ("💸","Cash Flow","Monthly flows, dividend timeline, DRIP simulator, fee analysis."),
            ("📋","Holdings","Position table, sizer, sector filters, CSV export."),
            ("🕰️","Timeline","Multi-statement portfolio evolution, statement diff view."),
            ("📄","Report","Download a full HTML report styled for printing as PDF."),
        ]
        for col, (icon, title, desc) in zip(cols, features):
            with col:
                st.markdown(f"<div class='land-card'><span class='land-icon'>{icon}</span>"
                            f"<div class='land-title'>{title}</div>"
                            f"<div class='land-desc'>{desc}</div></div>", unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        for col, (icon, title, desc) in zip(cols2, features2):
            with col:
                st.markdown(f"<div class='land-card'><span class='land-icon'>{icon}</span>"
                            f"<div class='land-title'>{title}</div>"
                            f"<div class='land-desc'>{desc}</div></div>", unsafe_allow_html=True)
        st.stop()

    # ── Use most recent statement as primary ──────────────────────────────────
    def sort_key(s):
        try:    return datetime.strptime(s["report_date"], "%d/%m/%Y")
        except:
            try: return datetime.strptime(s["report_date"], "%B %d, %Y")
            except: return datetime.min
    statements_sorted = sorted(statements, key=sort_key)
    data = statements_sorted[-1]   # most recent

    st.info(f"📄 Primary statement: **{data['_filename']}** "
            f"({data['report_date']}) — {len(statements)} total loaded",
            icon="📋")

    eq  = data["equities"]
    txs = data["transactions"]
    ps  = data["portfolio_summary"]

    if not eq:
        st.error("Could not parse equity data. Check the PDF format.")
        st.session_state["statements"] = []
        st.stop()

    # ── Live prices ───────────────────────────────────────────────────────────
    tickers = tuple(e["ticker"] for e in eq)
    live    = get_live_prices(tickers)
    eq      = inject_live_prices(eq, live)
    n_live  = sum(1 for e in eq if e["live_price"] is not None)

    if   n_live == len(eq): st.success(f"📡 All {n_live} live prices loaded from GSE-API")
    elif n_live:             st.warning(f"📡 {n_live}/{len(eq)} live prices · statement price used for rest")
    else:                    st.info("📋 Showing statement prices (GSE-API unavailable)")

    with st.expander("✏️ Override prices manually", expanded=False):
        ov_cols = st.columns(5); overrides = {}
        for i, e in enumerate(eq):
            val = ov_cols[i%5].number_input(e["ticker"], min_value=0.0,
                value=float(e["live_price"] or e["statement_price"]),
                step=0.01, format="%.4f", key=f"ov_{e['ticker']}")
            if val > 0: overrides[e["ticker"]] = val
        if st.button("✅ Apply prices", type="primary"):
            eq = inject_live_prices(eq, {t:{"price":pv,"change_pct":0,"change_abs":0}
                                         for t,pv in overrides.items()})
            n_live = len(eq); st.success("Applied.")

    # ── Compute ───────────────────────────────────────────────────────────────
    m   = compute_metrics(eq, txs, ps)
    am  = compute_advanced(eq, txs, m)
    fee_rows, total_fees = compute_fees(txs)
    drip_rows, drip_value = simulate_drip(eq, txs, m)

    # ── Client bar ────────────────────────────────────────────────────────────
    roi_c = EMERALD if m["roi"]>=0 else RUBY
    gl_c  = EMERALD if m["tg"]>=0  else RUBY
    cagr_s = (f"<span style='color:{EMERALD if (m['cagr'] or 0)>=0 else RUBY}'>"
              f"{m['cagr']:+.2f}%</span>" if m["cagr"] else "—")
    pp_cls = "live" if n_live==len(eq) else "warn" if n_live else "info"
    pp_txt = "✦ All Live" if n_live==len(eq) else f"{n_live}/{len(eq)} Live" if n_live else "Statement"

    # Real return for cbar
    rr_str = "—"
    if m["cagr"] and m["years"] >= 0.5:
        rr = real_return(m["cagr"], m["years"])
        if rr:
            rr_col = EMERALD if rr[0] >= 0 else RUBY
            rr_str = f"<span style='color:{rr_col}'>{rr[0]:+.2f}%</span>"

    st.markdown(f"""
<div class='cbar'>
  <div class='cbar-item'><div class='cbar-lbl'>Client</div>
    <div class='cbar-val'>{data['client_name']}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Account</div>
    <div class='cbar-acc'>{data['account_number']}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Statement Date</div>
    <div class='cbar-val'>{data['report_date']}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Portfolio Value</div>
    <div class='cbar-val'>GHS {m['tv']:,.2f}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>ROI (net cash)</div>
    <div class='cbar-val' style='color:{roi_c}'>{m['roi']:+.2f}%</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>CAGR / Real CAGR</div>
    <div class='cbar-val'>{cagr_s} / {rr_str}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Unrealised G/L</div>
    <div class='cbar-val' style='color:{gl_c}'>{'+'if m['tg']>=0 else ''}GHS {m['tg']:,.2f}</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Win Rate</div>
    <div class='cbar-val'>{m['winners']}/{len(eq)} ({m['winners']/len(eq)*100:.0f}%)</div></div>
  <div class='cbar-item'><div class='cbar-lbl'>Prices</div>
    <div class='cbar-val'><span class='pill {pp_cls}'>{pp_txt}</span></div></div>
</div>""", unsafe_allow_html=True)

    # ── TABS ──────────────────────────────────────────────────────────────────
    tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs([
        "📊 Overview","📈 Performance","🔬 Analytics",
        "⚖️ Risk & Scenarios","💸 Cash Flow","📋 Holdings",
        "🕰️ Timeline","📄 Report",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — OVERVIEW
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        shdr("Portfolio Summary")
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.markdown(kpi("Total Portfolio Value",f"GHS {m['tv']:,.2f}",
            f"As of {data['report_date']}","b"),unsafe_allow_html=True)
        with c2: st.markdown(kpi("Unrealised Gain / Loss",
            f"<span class='{pn(m['tg'])}'>{'+'if m['tg']>=0 else ''}GHS {m['tg']:,.2f}</span>",
            f"on GHS {m['tc']:,.2f} cost basis","g" if m['tg']>=0 else "r",delta=m['gp']),unsafe_allow_html=True)
        with c3: st.markdown(kpi("Overall ROI",
            f"<span class='{pn(m['roi'])}'>{m['roi']:+.2f}%</span>",
            f"vs GHS {m['ni']:,.2f} net invested","g" if m['roi']>=0 else "r",icon="📐"),unsafe_allow_html=True)
        with c4:
            cd = f"<span class='{pn(m['cagr'] or 0)}'>{m['cagr']:+.2f}%</span>" if m["cagr"] else "—"
            st.markdown(kpi("CAGR","Annualised return" and cd,
                "Annualised return" if m["cagr"] else "Insufficient history",
                "t" if (m["cagr"] or 0)>=0 else "r",icon="📅"),unsafe_allow_html=True)

        st.markdown("")
        c5,c6,c7,c8 = st.columns(4)
        with c5:
            hc=EMERALD if m['hs']>=75 else AMBER if m['hs']>=50 else RUBY
            st.markdown(kpi("Health Score",
                f"<span style='color:{hc}'>{m['hs']}</span><span style='font-size:.9rem;color:{p.MUTED};'>/100</span>",
                "ROI · Win Rate · Concentration · Sectors","t" if m['hs']>=75 else "y"),unsafe_allow_html=True)
        with c6: st.markdown(kpi("Cash Balance",f"GHS {m['cv']:,.2f}",
            f"{ps.get('Cash',{}).get('alloc',0):.1f}% of portfolio","y"),unsafe_allow_html=True)
        with c7: st.markdown(kpi("Dividend Income",f"GHS {m['div']:,.2f}",
            "Total dividends received","pk",icon="🌸"),unsafe_allow_html=True)
        with c8: st.markdown(kpi("Winning Positions",f"{m['winners']} / {len(eq)}",
            f"{m['winners']/len(eq)*100:.0f}% win rate","g" if m['winners']>=len(eq)//2 else "r"),unsafe_allow_html=True)

        # Real return highlight
        if m["cagr"] and m["years"] >= 0.5:
            rr = real_return(m["cagr"], m["years"])
            if rr:
                real_val, avg_cpi = rr
                st.markdown("")
                rr1, rr2, rr3, rr4 = st.columns(4)
                with rr1: st.markdown(kpi("Nominal CAGR",f"<span class='{pn(m['cagr'])}'>{m['cagr']:+.2f}%</span>",
                    "Before inflation","y",icon="📈"),unsafe_allow_html=True)
                with rr2: st.markdown(kpi("Ghana Avg Inflation",f"<span style='color:{RUBY}'>{avg_cpi:.1f}%</span>",
                    f"Avg CPI over {m['years']:.1f} yrs","re",icon="🔥"),unsafe_allow_html=True)
                with rr3: st.markdown(kpi("Real CAGR",
                    f"<span class='{pn(real_val)}'>{real_val:+.2f}%</span>",
                    "After Ghana inflation (Fisher)","g" if real_val>=0 else "re",icon="🌡️"),unsafe_allow_html=True)
                with rr4:
                    est_real_gain = m['ni']*((1+real_val/100)**m['years']-1) if m['ni']>0 else 0
                    st.markdown(kpi("Real Wealth Created",
                        f"<span class='{pn(est_real_gain)}'>{'+'if est_real_gain>=0 else ''}GHS {est_real_gain:,.0f}</span>",
                        "Approx. inflation-adjusted gain","g" if est_real_gain>=0 else "re",icon="💡"),unsafe_allow_html=True)

        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🚨 Smart Alerts")
        for cls, title, body in generate_alerts(eq, m, txs):
            st.markdown(alert_box(title, body, cls), unsafe_allow_html=True)

        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("Quick Insights")
        i1,i2,i3,i4,i5,i6 = st.columns(6)
        with i1: st.markdown(insight("🏆","Best Performer",f"{m['best']['ticker']} {m['best']['gain_pct']:+.1f}%","pos"),unsafe_allow_html=True)
        with i2: st.markdown(insight("📉","Worst Performer",f"{m['worst']['ticker']} {m['worst']['gain_pct']:+.1f}%","neg"),unsafe_allow_html=True)
        with i3: st.markdown(insight("💎","Largest Position",f"{m['biggest']['ticker']} · GHS {m['biggest']['market_value']:,.0f}"),unsafe_allow_html=True)
        with i4: st.markdown(insight("🏭","Sectors Held",f"{m['su']} active"),unsafe_allow_html=True)
        with i5: st.markdown(insight("🧾","Est. Fees Paid",f"GHS {total_fees:,.2f}"),unsafe_allow_html=True)
        with i6: st.markdown(insight("🌱","DRIP Upside",f"+GHS {drip_value:,.2f}"),unsafe_allow_html=True)

        movers = sorted([e for e in eq if e.get("change_pct") is not None],
                        key=lambda e:abs(e["change_pct"] or 0),reverse=True)
        if movers:
            st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
            shdr("🚀 Today's Movers")
            mcols = st.columns(min(len(movers),5))
            for i,(col,e) in enumerate(zip(mcols,movers[:5])):
                with col:
                    st.markdown(mover_card(e["ticker"],e["live_price"] or e["statement_price"],
                        e["change_pct"] or 0,e["change_abs"] or 0,is_top=(i==0)),unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — PERFORMANCE
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        shdr("Performance Analysis")
        cl,cr = st.columns([3,2])
        with cl: st.plotly_chart(chart_gain_loss(eq), key="pc_1",use_container_width=True)
        with cr: st.plotly_chart(chart_sector_donut(eq), key="pc_2",use_container_width=True)
        st.plotly_chart(chart_performance_attribution(eq,m["ev"]), key="pc_3",use_container_width=True)
        st.plotly_chart(chart_sector_performance(eq), key="pc_4",use_container_width=True)
        cl,cr = st.columns([3,2])
        with cl: st.plotly_chart(chart_market_vs_cost(eq), key="pc_5",use_container_width=True)
        with cr:
            from plotly.subplots import make_subplots as _msp
            cmap={"Equities":VIOLET,"Cash":AZURE,"Funds":GOLD,"Fixed Income":TEAL}
            labels,parents,values,clr=[],[],[],[]
            for k,v in ps.items():
                if k=="Total" or (isinstance(v,dict) and v["value"]==0): continue
                if isinstance(v,dict):
                    labels.append(k); parents.append(""); values.append(v["value"]); clr.append(cmap.get(k,SLATE))
            if labels:
                fig_tm=go.Figure(go.Treemap(labels=labels,parents=parents,values=values,
                    marker=dict(colors=clr,line=dict(width=3,color=p.BG)),
                    texttemplate="<b>%{label}</b><br>GHS %{value:,.0f}<br>%{percentRoot:.1%}",
                    textfont=dict(size=12,family="Epilogue"),
                    hovertemplate="<b>%{label}</b><br>GHS %{value:,.2f}<br>%{percentRoot:.1%}<extra></extra>"))
                tm_layout=T(title="Asset Class Allocation")
                tm_layout["height"]=300; tm_layout["margin"]=dict(l=8,r=8,t=48,b=8)
                fig_tm.update_layout(**tm_layout)
                st.plotly_chart(fig_tm, key="pc_6",use_container_width=True)
        st.plotly_chart(chart_portfolio_efficiency(eq), key="pc_7",use_container_width=True)
        st.plotly_chart(chart_pl_waterfall(eq), key="pc_8",use_container_width=True)
        # Price comparison
        df_pc=pd.DataFrame(eq); df_pc=df_pc[df_pc["live_price"].notna()].copy()
        if not df_pc.empty:
            df_pc["pct_diff"]=(df_pc["live_price"]-df_pc["statement_price"])/df_pc["statement_price"]*100
            fig_pc=go.Figure()
            fig_pc.add_trace(go.Bar(name="Statement Price",x=df_pc["ticker"],y=df_pc["statement_price"],marker_color=AMBER,opacity=0.8))
            fig_pc.add_trace(go.Bar(name="Live Price",x=df_pc["ticker"],y=df_pc["live_price"],marker_color=EMERALD,opacity=0.9))
            for _,row in df_pc.iterrows():
                c=EMERALD if row["pct_diff"]>=0 else RUBY
                fig_pc.add_annotation(x=row["ticker"],y=max(row["statement_price"],row["live_price"]),
                    text=f"{row['pct_diff']:+.1f}%",showarrow=False,yshift=12,
                    font=dict(color=c,size=9,family="DM Mono"))
            fig_pc.update_layout(**T(title="Statement vs Live Price",yt="GHS per Share"),barmode="group",height=320)
            st.plotly_chart(fig_pc, key="pc_9",use_container_width=True)
        # Sector table
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("Sector Breakdown")
        sec_rows=[]
        for sector,grp in pd.DataFrame(eq).groupby("sector"):
            smv=grp["market_value"].sum(); stc=grp["total_cost"].sum(); sgl=grp["gain_loss"].sum()
            sec_rows.append({"Sector":sector,"Stocks":", ".join(grp["ticker"].tolist()),
                "# Stocks":len(grp),"Market Value":f"GHS {smv:,.2f}","Cost Basis":f"GHS {stc:,.2f}",
                "Gain/Loss":f"{'+'if sgl>=0 else ''}GHS {sgl:,.2f}",
                "Sector Return":f"{(sgl/stc*100 if stc else 0):+.1f}%",
                "Portfolio Weight":f"{(smv/m['ev']*100 if m['ev'] else 0):.1f}%"})
        st.dataframe(pd.DataFrame(sec_rows),use_container_width=True,hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — ANALYTICS
    # ══════════════════════════════════════════════════════════════════════════
    with tab3:
        shdr("Advanced Analytics",f"Risk-free rate: {am['rf']:.0f}% (Ghana 91-day T-bill, approx.)")
        a1,a2,a3,a4,a5=st.columns(5)
        with a1:
            if am["sharpe"] is not None:
                sc=EMERALD if am["sharpe"]>=1 else AMBER if am["sharpe"]>=0 else RUBY
                sval=f"<span style='color:{sc}'>{am['sharpe']:+.2f}</span>"
                ssub="Excellent" if am["sharpe"]>=2 else "Good" if am["sharpe"]>=1 else "Below RF" if am["sharpe"]<0 else "Adequate"
            else: sval,ssub="—","Insufficient data"
            st.markdown(kpi("Sharpe Ratio",sval,f"Risk-adj. return · {ssub}",
                "g" if (am["sharpe"] or 0)>=1 else "y" if (am["sharpe"] or 0)>=0 else "r",icon="⚡"),unsafe_allow_html=True)
        with a2: st.markdown(kpi("Max Drawdown",
            f"<span style='color:{AMBER if am['max_dd']>-15 else RUBY}'>{am['max_dd']:.2f}%</span>",
            "From cumulative flow peak","r",icon="📉"),unsafe_allow_html=True)
        with a3: st.markdown(kpi("Effective Positions",f"{am['enp']:.1f}",
            f"ENP=1/HHI · of {len(eq)} holdings","b",icon="🎯"),unsafe_allow_html=True)
        with a4: st.markdown(kpi("Cross-sectional Vol",
            f"<span style='color:{AMBER if am['vol']>20 else EMERALD}'>{am['vol']:.1f}%</span>",
            "Return dispersion across stocks","vi",icon="📊"),unsafe_allow_html=True)
        with a5: st.markdown(kpi("Consistency",
            f"<span style='color:{EMERALD if am['consistency']>=70 else AMBER if am['consistency']>=50 else RUBY}'>{am['consistency']:.0f}%</span>",
            "Stocks within −5% of cost","t",icon="🎯"),unsafe_allow_html=True)

        # Real returns chart
        rr_fig = chart_real_vs_nominal(m)
        if rr_fig:
            st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
            shdr("🌡️ Real Returns vs Ghana Inflation",
                 "After ~23% avg annual inflation, many nominal gains are real losses")
            st.plotly_chart(rr_fig, key="pc_10",use_container_width=True)

        # Risk / Return scatter
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("Risk / Return Matrix","Bubble size = Market Value")
        st.plotly_chart(chart_risk_return_scatter(eq,m["ev"]), key="pc_11",use_container_width=True)

        # Drawdown
        dd_fig=chart_drawdown(txs,m["tv"])
        if dd_fig:
            st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
            shdr("Portfolio Drawdown from Peak")
            st.plotly_chart(dd_fig, key="pc_12",use_container_width=True)

        # Goals & Projection
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🎯 Goals & Wealth Projection",
             "Based on current CAGR with optimistic (+40%) and pessimistic (−40%) bands")
        if m["cagr"] and m["cagr"] > 0:
            g1,g2,g3 = st.columns(3)
            with g1: target_val = st.number_input("Target Portfolio Value (GHS)",
                min_value=float(m["tv"]),value=float(m["tv"]*2),step=10000.0,format="%.2f")
            with g2: yrs_max = st.slider("Projection horizon (years)",5,30,15)
            with g3: st.markdown(kpi("Current CAGR",
                f"<span class='{pn(m['cagr'])}'>{m['cagr']:+.2f}%</span>",
                "This drives the base projection","t"),unsafe_allow_html=True)
            proj_result = project_portfolio(m["tv"], m["cagr"], target_val, yrs_max)
            if proj_result:
                df_proj, hit_date = proj_result
                st.plotly_chart(chart_projection(df_proj,m["tv"],target_val,hit_date), key="pc_13",use_container_width=True)
                if hit_date:
                    years_to_target = (hit_date - datetime.now()).days / 365.25
                    st.markdown(alert_box(
                        f"Target of GHS {target_val:,.0f} reached",
                        f"At your current CAGR of {m['cagr']:.1f}%, you reach your target in approximately "
                        f"<b>{years_to_target:.1f} years</b> ({hit_date.strftime('%B %Y')}).",
                        "ok"),unsafe_allow_html=True)
                else:
                    st.markdown(alert_box("Target Not Reached in Horizon",
                        f"At {m['cagr']:.1f}% CAGR your portfolio does not reach GHS {target_val:,.0f} "
                        f"within {yrs_max} years. Extend the horizon or increase your contributions.",
                        "warn"),unsafe_allow_html=True)
        else:
            st.info("Insufficient CAGR data for projection. Upload more statements or ensure contribution history is present.")

        # Monthly heatmap
        hm_fig=chart_monthly_heatmap(txs)
        if hm_fig:
            st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
            shdr("Monthly Net Cash Flow Calendar")
            st.plotly_chart(hm_fig, key="pc_14",use_container_width=True)

        # Per-stock analytics table
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("Per-Stock Analytics")
        ana_rows=[]
        for e in sorted(eq,key=lambda x:x["market_value"],reverse=True):
            wt=e["market_value"]/m["ev"]*100 if m["ev"] else 0
            eff=e["gain_loss"]/e["total_cost"]*100 if e["total_cost"] else 0
            hp=am["holding_periods"].get(e["ticker"])
            hp_s=f"{hp//365}y {(hp%365)//30}m" if hp and hp>=365 else f"{hp//30}m" if hp else "—"
            ana_rows.append({"Ticker":e["ticker"],"Sector":e["sector"],
                "Weight %":f"{wt:.1f}%","Return %":f"{e['gain_pct']:+.1f}%",
                "Efficiency ROI":f"{eff:+.1f}%",
                "Contribution":f"{e['gain_loss']/m['ev']*100:+.2f}%" if m["ev"] else "—",
                "Holding Period":hp_s,"Status":"✅ Profit" if e["gain_pct"]>=0 else "🔴 Loss"})
        st.dataframe(pd.DataFrame(ana_rows),use_container_width=True,hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — RISK & SCENARIOS
    # ══════════════════════════════════════════════════════════════════════════
    with tab4:
        be=chart_breakeven(eq)
        if be:
            shdr("🎯 Break-even Analysis")
            st.plotly_chart(be, key="pc_15",use_container_width=True)
        else:
            st.success("🎉 All positions are currently profitable — no break-even analysis needed.")
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("⚖️ Concentration Risk (HHI)")
        cf,hhi_val,risk_lbl,rc=chart_concentration(eq)
        st.plotly_chart(cf, key="pc_16",use_container_width=True)
        st.markdown(f"<div style='text-align:center;color:{p.MUTED};font-size:.82rem;margin-top:-8px;font-family:DM Mono,monospace;'>"
                    f"HHI: <b style='color:{rc}'>{hhi_val}</b> — <b style='color:{rc}'>{risk_lbl}</b> &nbsp;·&nbsp;"
                    f"<span style='color:{EMERALD}'>Low &lt;1500</span> · <span style='color:{AMBER}'>Moderate 1500–2500</span> · <span style='color:{RUBY}'>High &gt;2500</span>"
                    f"</div>",unsafe_allow_html=True)
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🛠️ Rebalance Recommendations")
        if hhi_val>2500: st.warning("⚠️ High concentration — consider the adjustments below:")
        else: st.success("✅ Concentration within acceptable range.")
        ev=m["ev"]; n=len(eq); equal=100/n if n else 10
        rec_rows=[]
        for e in sorted(eq,key=lambda x:x["market_value"]/ev if ev else 0,reverse=True):
            wt=e["market_value"]/ev*100 if ev else 0
            if wt>20:         action=f"🔴 Trim → target 10–15% (currently {wt:.1f}%)"
            elif wt<3 and e["gain_pct"]>=0: action=f"🟢 Consider adding — only {wt:.1f}%"
            elif e["gain_pct"]<-15: action=f"🟡 Review thesis — {e['gain_pct']:+.1f}%"
            else:             action=f"✅ Hold — {wt:.1f}% (target ~{equal:.1f}%)"
            rec_rows.append({"Ticker":e["ticker"],"Sector":e["sector"],
                "Current Weight":f"{wt:.1f}%","Equal-weight Target":f"{equal:.1f}%",
                "Return":f"{e['gain_pct']:+.1f}%","Recommendation":action})
        st.dataframe(pd.DataFrame(rec_rows),use_container_width=True,hide_index=True)
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🔮 What-If Scenario Simulator")
        st.caption("Adjust sliders to simulate price moves on each position")
        sim_mult={}
        for row in [eq[i:i+5] for i in range(0,len(eq),5)]:
            sc=st.columns(len(row))
            for col,e in zip(sc,row):
                chg=col.slider(e["ticker"],min_value=-50,max_value=150,value=0,step=1,format="%d%%",key=f"sim_{e['ticker']}")
                sim_mult[e["ticker"]]=1+chg/100
        sim_mv=sum(e["market_value"]*sim_mult.get(e["ticker"],1) for e in eq)
        sim_total=sim_mv+m["cv"]+m["fv"]
        sim_gain=sum((e["market_value"]*sim_mult.get(e["ticker"],1))-e["total_cost"] for e in eq)
        sim_delta=sim_total-m["tv"]
        sim_roi=((sim_total-m["ni"])/m["ni"]*100) if m["ni"] else 0
        sc1,sc2,sc3,sc4=st.columns(4)
        with sc1: st.markdown(kpi("Simulated Total Value",f"GHS {sim_total:,.2f}",
            f"{'+'if sim_delta>=0 else ''}GHS {sim_delta:,.2f} vs now","g" if sim_delta>=0 else "r"),unsafe_allow_html=True)
        with sc2: st.markdown(kpi("Simulated G/L",
            f"<span class='{pn(sim_gain)}'>{'+'if sim_gain>=0 else ''}GHS {sim_gain:,.2f}</span>",
            f"{(sim_gain/m['tc']*100):+.2f}% on cost","g" if sim_gain>=0 else "r"),unsafe_allow_html=True)
        with sc3: st.markdown(kpi("Simulated ROI",
            f"<span class='{pn(sim_roi)}'>{sim_roi:+.2f}%</span>",
            f"Current: {m['roi']:+.2f}%","g" if sim_roi>=0 else "r"),unsafe_allow_html=True)
        with sc4:
            gchg=sim_gain-m["tg"]
            st.markdown(kpi("G/L Change",
                f"<span class='{pn(gchg)}'>{'+'if gchg>=0 else ''}GHS {gchg:,.2f}</span>",
                "vs current unrealised G/L","g" if gchg>=0 else "r"),unsafe_allow_html=True)
        sim_df=pd.DataFrame([{"ticker":e["ticker"],"current":e["market_value"],
            "simulated":e["market_value"]*sim_mult.get(e["ticker"],1)} for e in eq]).sort_values("simulated",ascending=False)
        fig_sim=go.Figure()
        fig_sim.add_trace(go.Bar(name="Current",x=sim_df["ticker"],y=sim_df["current"],marker_color=VIOLET,opacity=0.65))
        fig_sim.add_trace(go.Bar(name="Simulated",x=sim_df["ticker"],y=sim_df["simulated"],
            marker=dict(color=[EMERALD if s>c else RUBY for s,c in zip(sim_df["simulated"],sim_df["current"])],opacity=0.9)))
        fig_sim.update_layout(**T(title="Current vs Simulated Market Value",yt="GHS"),barmode="group",height=320)
        st.plotly_chart(fig_sim, key="pc_17",use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — CASH FLOW
    # ══════════════════════════════════════════════════════════════════════════
    with tab5:
        shdr("Cash Flow & History")
        cf=chart_cashflow(txs)
        if cf: st.plotly_chart(cf, key="pc_18",use_container_width=True)
        div_c=chart_dividend_timeline(txs)
        if div_c:
            shdr("💎 Dividend Income Timeline")
            st.plotly_chart(div_c, key="pc_19",use_container_width=True)
        cl,cr=st.columns([3,2])
        with cl:
            cml=chart_cumulative(txs,m["tv"])
            if cml: st.plotly_chart(cml, key="pc_20",use_container_width=True)
        with cr:
            df_r=pd.DataFrame(txs).sort_values("date")
            if not df_r.empty:
                df_r["net"]=df_r["credit"]-df_r["debit"]; df_r["cumul"]=df_r["net"].cumsum()
                scale=m["tv"]/df_r["cumul"].iloc[-1] if df_r["cumul"].iloc[-1] else 1
                df_r["proxy"]=df_r["cumul"]*scale
                fig_r=go.Figure()
                fig_r.add_trace(go.Scatter(x=df_r["date"],y=df_r["proxy"],mode="lines",fill="tozeroy",
                    fillcolor="rgba(6,182,212,0.08)",line=dict(color=TEAL,width=2.5),name="Est. Value"))
                fig_r.add_trace(go.Scatter(x=df_r["date"],y=df_r["cumul"],mode="lines",
                    line=dict(color=GOLD,width=1.5,dash="dot"),name="Net Invested"))
                fig_r.update_layout(**T(title="Estimated Portfolio Value Over Time",xt="Date",yt="GHS"),height=320)
                st.plotly_chart(fig_r, key="pc_21",use_container_width=True)

        # DRIP Simulator
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🌱 Dividend Reinvestment (DRIP) Simulator",
             "What your portfolio would be worth had you reinvested every dividend")
        if drip_rows:
            drip_df = pd.DataFrame(drip_rows)
            d1,d2,d3,d4 = st.columns(4)
            with d1: st.markdown(kpi("Total Dividends Received",f"GHS {m['div']:,.2f}",
                "Cash received as dividends","pk",icon="🌸"),unsafe_allow_html=True)
            with d2: st.markdown(kpi("DRIP Extra Value",f"+GHS {drip_value:,.2f}",
                "If dividends had been reinvested","g",icon="🌱"),unsafe_allow_html=True)
            with d3: st.markdown(kpi("DRIP Portfolio Value",f"GHS {m['tv']+drip_value:,.2f}",
                f"+{drip_value/m['tv']*100:.1f}% vs current","t",icon="💰"),unsafe_allow_html=True)
            with d4: st.markdown(kpi("Missed Compounding",
                f"GHS {drip_value:,.2f}",
                "Left on the table by taking cash","re",icon="🔥"),unsafe_allow_html=True)
            st.dataframe(drip_df[["date","guessed_ticker","amount","price_at_reinvest",
                                   "extra_shares","current_value"]].rename(columns={
                "date":"Date","guessed_ticker":"Stock","amount":"Dividend (GHS)",
                "price_at_reinvest":"Price at Reinvest","extra_shares":"Extra Shares","current_value":"Current Value (GHS)"}),
                use_container_width=True,hide_index=True)
        else:
            st.info("No dividend transactions found in this statement.")

        # Fee Analysis
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🧾 Transaction Fee Analysis",
             "Estimated fees on all buy/sell transactions (IC Brokerage + SEC + GhSE + CSDR)")
        if fee_rows:
            fee_df = pd.DataFrame(fee_rows)
            f1,f2,f3,f4 = st.columns(4)
            total_buy_vol  = fee_df[fee_df["type"]=="Buy"]["volume"].sum()
            total_sell_vol = fee_df[fee_df["type"]=="Sell"]["volume"].sum()
            with f1: st.markdown(kpi("Total Est. Fees Paid",f"GHS {total_fees:,.2f}",
                f"{total_fees/(total_buy_vol+total_sell_vol)*100:.2f}% of total volume","re",icon="🧾"),unsafe_allow_html=True)
            with f2: st.markdown(kpi("Buy Fees",f"GHS {fee_df[fee_df['type']=='Buy']['est_fees'].sum():,.2f}",
                f"on GHS {total_buy_vol:,.0f} buy volume","r",icon="📥"),unsafe_allow_html=True)
            with f3: st.markdown(kpi("Sell Fees",f"GHS {fee_df[fee_df['type']=='Sell']['est_fees'].sum():,.2f}",
                f"on GHS {total_sell_vol:,.0f} sell volume","y",icon="📤"),unsafe_allow_html=True)
            with f4: st.markdown(kpi("Fee Drag on Portfolio",
                f"{total_fees/m['tv']*100:.2f}%",
                "Total fees / current portfolio value","vi",icon="🔩"),unsafe_allow_html=True)
            st.plotly_chart(chart_fees_over_time(fee_rows), key="pc_22",use_container_width=True)
            # Fee breakdown table
            fee_breakdown_df = pd.DataFrame({"Fee Component":list(IC_FEES.keys()),
                "Rate":[f"{v*100:.2f}%" for v in IC_FEES.values()],
                "Est. Total Paid":[f"GHS {total_buy_vol*v + total_sell_vol*v:,.2f}"
                                   for v in IC_FEES.values()]})
            st.dataframe(fee_breakdown_df,use_container_width=True,hide_index=True)
        else:
            st.info("No buy/sell transactions found for fee analysis.")

        # Flow summary
        tx_df2=pd.DataFrame(txs)
        if not tx_df2.empty:
            tx_df2["month"]=tx_df2["date"].dt.to_period("M"); n_months=tx_df2["month"].nunique()
            tx_df2["amount"]=tx_df2["credit"]+tx_df2["debit"]
            buy_vol=tx_df2[tx_df2["type"]=="Buy"]["amount"].sum()
            sell_vol=tx_df2[tx_df2["type"]=="Sell"]["amount"].sum()
            fq="Active Investor" if buy_vol>sell_vol*2 else "Active Trader" if sell_vol>buy_vol else "Balanced"
            st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
            shdr("Flow Summary")
            fa1,fa2,fa3,fa4,fa5=st.columns(5)
            with fa1: st.markdown(kpi("Months Active",f"{n_months}",f"{len(txs)} transactions","b"),unsafe_allow_html=True)
            with fa2: st.markdown(kpi("Total Contributions",f"GHS {m['nc']:,.2f}","Cash in","g"),unsafe_allow_html=True)
            with fa3: st.markdown(kpi("Total Withdrawals",f"GHS {m['nw']:,.2f}","Cash out","r"),unsafe_allow_html=True)
            with fa4: st.markdown(kpi("Net Invested",f"GHS {m['ni']:,.2f}","Contributions − Withdrawals","t"),unsafe_allow_html=True)
            with fa5: st.markdown(kpi("Flow Profile",fq,f"Buy vol GHS {buy_vol:,.0f}","vi",icon="🧭"),unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 6 — HOLDINGS
    # ══════════════════════════════════════════════════════════════════════════
    with tab6:
        shdr("Equity Positions")
        fc1,fc2,fc3=st.columns([2,2,2])
        with fc1:
            sel_sectors=st.multiselect("Sector",sorted(set(e["sector"] for e in eq)),
                default=sorted(set(e["sector"] for e in eq)),label_visibility="collapsed",placeholder="Filter by sector…")
        with fc2:
            pf=st.selectbox("Profitability",["All","Profitable","Loss-making"],label_visibility="collapsed")
        with fc3:
            sb=st.selectbox("Sort by",["Market Value","Return %","Gain/Loss","Weight","Ticker"],label_visibility="collapsed")
        eq_f=[e for e in eq if e["sector"] in sel_sectors]
        if pf=="Profitable":    eq_f=[e for e in eq_f if e["gain_pct"]>=0]
        elif pf=="Loss-making": eq_f=[e for e in eq_f if e["gain_pct"]<0]
        sk={"Market Value":lambda e:e["market_value"],"Return %":lambda e:e["gain_pct"],
            "Gain/Loss":lambda e:e["gain_loss"],"Weight":lambda e:e["market_value"],"Ticker":lambda e:e["ticker"]}
        eq_f=sorted(eq_f,key=sk[sb],reverse=(sb!="Ticker"))
        pos_rows=[]
        for e in eq_f:
            wt=e["market_value"]/m["ev"]*100 if m["ev"] else 0
            pos_rows.append({"Ticker":e["ticker"],"Sector":e["sector"],"Qty":f"{e['qty']:,.0f}",
                "Avg Cost":f"{e['avg_cost']:.4f}","Stmt Price":f"{e['statement_price']:.4f}",
                "Live Price":f"{e['live_price']:.4f}" if e["live_price"] else "—",
                "Today Δ%":f"{e['change_pct']:+.2f}%" if e.get("change_pct") is not None else "—",
                "Weight %":f"{wt:.1f}%","Cost Basis":f"GHS {e['total_cost']:,.2f}",
                "Market Val":f"GHS {e['market_value']:,.2f}",
                "Gain/Loss":f"{'+'if e['gain_loss']>=0 else ''}GHS {e['gain_loss']:,.2f}",
                "Return %":f"{e['gain_pct']:+.1f}%","Status":"✅ Profit" if e["gain_pct"]>=0 else f"🔴 −{abs(e['gain_pct']):.1f}%"})
        def _style_row(row):
            s=[""]* len(row); ig=list(row.index).index("Gain/Loss"); ir=list(row.index).index("Return %")
            c=f"color:{EMERALD};font-weight:600" if "+" in row["Gain/Loss"] else f"color:{RUBY};font-weight:600"
            s[ig]=s[ir]=c; return s
        df_pos=pd.DataFrame(pos_rows)
        if not df_pos.empty:
            st.dataframe(df_pos.style.apply(_style_row,axis=1),use_container_width=True,hide_index=True)
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("📊 Invested → Market Value Progress")
        for e in sorted(eq_f,key=lambda x:x["market_value"],reverse=True):
            prog=min(1.0,e["market_value"]/e["total_cost"]) if e["total_cost"] else 0
            bc=EMERALD if e["gain_pct"]>=0 else RUBY
            wt=e["market_value"]/m["ev"]*100 if m["ev"] else 0
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:2px;align-items:baseline;'>"
                f"<span style='font-weight:700;color:{p.TEXT};font-family:Epilogue,sans-serif;'>"
                f"{e['ticker']} <span class='sec-badge'>{e['sector']}</span></span>"
                f"<span style='font-family:DM Mono,monospace;'>"
                f"<span style='color:{p.MUTED};margin-right:8px;'>GHS {e['market_value']:,.2f} · {wt:.1f}%</span>"
                f"<span style='color:{bc};font-weight:600;'>{e['gain_pct']:+.1f}%</span></span></div>"
                f"<div class='prog-wrap'><div class='prog-bar' style='width:{min(100,prog*100):.1f}%;background:{bc};'></div></div>"
                f"<div style='height:10px'></div>",unsafe_allow_html=True)
        # Position sizer
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🎯 Position Sizer")
        with st.expander("Open Position Sizer",expanded=False):
            tt=st.number_input("Target Portfolio Value (GHS)",min_value=0.0,value=float(m["tv"]),step=1000.0,format="%.2f")
            tep=st.slider("Target Equity Allocation (%)",10,100,70,step=5)
            tev=tt*tep/100
            strat=st.selectbox("Strategy",["Equal Weight","Market-cap Weight (keep current)"])
            sr=[]
            for e in sorted(eq,key=lambda x:x["market_value"],reverse=True):
                tmv=tev/len(eq) if strat=="Equal Weight" else tev*(e["market_value"]/m["ev"] if m["ev"] else 0)
                dg=tmv-e["market_value"]; pr=e["live_price"] or e["statement_price"]; ds=round(dg/pr) if pr else 0
                sr.append({"Ticker":e["ticker"],"Current":f"GHS {e['market_value']:,.2f}","Target":f"GHS {tmv:,.2f}",
                    "Δ Value":f"{'+'if dg>=0 else ''}GHS {dg:,.2f}",
                    "Shares to Trade":f"{'+'if ds>=0 else ''}{ds:,} shares",
                    "Action":"🟢 Buy" if ds>0 else "🔴 Sell" if ds<0 else "✅ Hold"})
            if sr: st.dataframe(pd.DataFrame(sr),use_container_width=True,hide_index=True)
        # CSV
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        dl1,dl2=st.columns(2)
        with dl1:
            csv_hold=df_pos.to_csv(index=False).encode("utf-8") if not df_pos.empty else b""
            st.download_button("📥 Download Holdings CSV",csv_hold,
                f"IC_holdings_{data['account_number']}_{datetime.now().strftime('%Y%m%d')}.csv","text/csv",use_container_width=True)
        with dl2:
            tx_ex=pd.DataFrame(txs)
            if not tx_ex.empty:
                st.download_button("📥 Download Transaction Log CSV",tx_ex.to_csv(index=False).encode("utf-8"),
                    f"IC_transactions_{data['account_number']}_{datetime.now().strftime('%Y%m%d')}.csv","text/csv",use_container_width=True)
        # Transaction history
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("Transaction History")
        tx_df=pd.DataFrame(txs).sort_values("date",ascending=False)
        emojis={"Buy":"🔵","Sell":"🟡","Credit":"🟢","Withdrawal":"🔴","Dividend":"💎","Other":"⚪"}
        tx_df["Type"]=tx_df["type"].map(lambda t:f"{emojis.get(t,'⚪')} {t}")
        tf1,tf2,tf3=st.columns([2,2,3])
        with tf1: filt=st.multiselect("Type",list(tx_df["Type"].unique()),default=list(tx_df["Type"].unique()),label_visibility="collapsed")
        with tf2:
            dr=st.date_input("Dates",value=(tx_df["date"].min().date(),tx_df["date"].max().date()),label_visibility="collapsed")
        with tf3: srch=st.text_input("Search",placeholder="🔍 Search description…",label_visibility="collapsed")
        view=tx_df[tx_df["Type"].isin(filt)]
        if len(dr)==2:
            view=view[(view["date"]>=pd.Timestamp(dr[0]))&(view["date"]<=pd.Timestamp(dr[1]))]
        if srch: view=view[view["description"].str.contains(srch,case=False,na=False)]
        vs=view[["date_str","Type","description","credit","debit"]].rename(columns={
            "date_str":"Date","description":"Description","credit":"Credit (GHS)","debit":"Debit (GHS)"})
        vs["Credit (GHS)"]=vs["Credit (GHS)"].apply(lambda v:f"+{v:,.2f}" if v>0 else "—")
        vs["Debit (GHS)"]=vs["Debit (GHS)"].apply(lambda v:f"-{v:,.2f}" if v>0 else "—")
        vs["Description"]=vs["Description"].str[:100]
        st.caption(f"Showing {len(vs):,} of {len(tx_df):,} transactions")
        st.dataframe(vs,use_container_width=True,hide_index=True,height=400)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 7 — TIMELINE
    # ══════════════════════════════════════════════════════════════════════════
    with tab7:
        shdr("Portfolio Timeline",f"{len(statements)} statement(s) loaded")
        if len(statements) < 2:
            st.info("📤 Upload **multiple statements** (one per month/quarter) to unlock the timeline view. "
                    "Each PDF adds a data point to your equity curve.")
        else:
            df_tl = build_timeline(statements_sorted)
            st.plotly_chart(chart_timeline(df_tl), key="pc_23",use_container_width=True)
            cl,cr=st.columns(2)
            with cl: st.plotly_chart(chart_timeline_roi(df_tl), key="pc_24",use_container_width=True)
            with cr:
                # n_stocks over time
                fig_ns=go.Figure(go.Scatter(x=df_tl["date"],y=df_tl["n_stocks"],mode="lines+markers",
                    line=dict(color=VIOLET,width=2.5),marker=dict(size=8,color=VIOLET,line=dict(color=p.BG,width=2)),
                    text=df_tl["label"],hovertemplate="<b>%{text}</b><br>Positions: %{y}<extra></extra>"))
                fig_ns.update_layout(**T(title="Number of Positions Over Time",yt="# Stocks"),height=300)
                st.plotly_chart(fig_ns, key="pc_25",use_container_width=True)

            # M-o-M table
            st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
            shdr("Statement-on-Statement Summary")
            tl_show=df_tl[["label","total_value","equities_val","cash_val","gain_loss","roi","n_stocks","mom_pct"]].copy()
            tl_show.columns=["Date","Total Value (GHS)","Equities (GHS)","Cash (GHS)","Unrealised G/L","ROI (%)","# Stocks","MoM Change (%)"]
            tl_show["Total Value (GHS)"]=tl_show["Total Value (GHS)"].apply(lambda v:f"{v:,.2f}")
            tl_show["Equities (GHS)"]=tl_show["Equities (GHS)"].apply(lambda v:f"{v:,.2f}")
            tl_show["Cash (GHS)"]=tl_show["Cash (GHS)"].apply(lambda v:f"{v:,.2f}")
            tl_show["Unrealised G/L"]=tl_show["Unrealised G/L"].apply(lambda v:f"{'+'if v>=0 else ''}{v:,.2f}")
            tl_show["ROI (%)"]=tl_show["ROI (%)"].apply(lambda v:f"{v:+.2f}%")
            tl_show["MoM Change (%)"]=tl_show["MoM Change (%)"].apply(lambda v:f"{v:+.1f}%" if pd.notna(v) else "—")
            st.dataframe(tl_show,use_container_width=True,hide_index=True)

        # Statement Diff
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("🔍 Statement Diff View",
             "Compare two statements to see exactly what changed")
        if len(statements) < 2:
            st.info("Upload at least 2 statements to use the diff view.")
        else:
            filenames = [s["_filename"] for s in statements_sorted]
            d_col1,d_col2=st.columns(2)
            with d_col1: old_sel=st.selectbox("Older statement",filenames[:-1],index=0)
            with d_col2: new_sel=st.selectbox("Newer statement",filenames[1:],index=len(filenames)-2)
            old_s=next(s for s in statements_sorted if s["_filename"]==old_sel)
            new_s=next(s for s in statements_sorted if s["_filename"]==new_sel)
            diff_df=diff_statements(old_s,new_s)
            if not diff_df.empty:
                new_count  = len(diff_df[diff_df["Status"].str.contains("NEW")])
                exit_count = len(diff_df[diff_df["Status"].str.contains("EXITED")])
                ch_count   = len(diff_df[diff_df["Status"].str.contains("INCREASED|REDUCED")])
                dc1,dc2,dc3=st.columns(3)
                with dc1: st.markdown(kpi("New Positions",str(new_count),"Added between statements","g",icon="🟢"),unsafe_allow_html=True)
                with dc2: st.markdown(kpi("Exited Positions",str(exit_count),"Removed between statements","r",icon="🔴"),unsafe_allow_html=True)
                with dc3: st.markdown(kpi("Changed Positions",str(ch_count),"Weight shifted","b",icon="⬆️"),unsafe_allow_html=True)
                st.dataframe(diff_df,use_container_width=True,hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 8 — REPORT
    # ══════════════════════════════════════════════════════════════════════════
    with tab8:
        shdr("📄 Downloadable Portfolio Report")
        st.markdown(
            f"<div style='background:rgba(8,9,30,0.8);border:1px solid {p.BORDER};border-radius:14px;"
            f"padding:24px 28px;margin-bottom:20px;font-family:Epilogue,sans-serif;'>"
            f"<div style='font-size:1rem;font-weight:700;color:{p.TEXT};margin-bottom:8px;'>"
            f"Generate a full HTML report for this portfolio</div>"
            f"<div style='font-size:.84rem;color:{p.MUTED};line-height:1.7;'>"
            f"The report includes all KPIs, holdings table, asset allocation, and key metrics. "
            f"Open it in your browser and use <b>File → Print → Save as PDF</b> for a professional PDF report card. "
            f"Formatted for both screen and print.</div></div>",
            unsafe_allow_html=True)

        if st.button("⚡ Generate Report", type="primary", use_container_width=False):
            with st.spinner("Building report…"):
                html = build_html_report(data, eq, txs, ps, m, am)
            st.download_button(
                label="📥 Download HTML Report",
                data=html.encode("utf-8"),
                file_name=f"IC_Portfolio_Report_{data['account_number']}_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=False)
            st.success("Report ready! Click the download button above.")

        # Report preview
        st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
        shdr("Report Preview")
        r1,r2=st.columns(2)
        with r1:
            st.markdown(
                f"<div style='background:rgba(8,9,30,0.8);border:1px solid {p.BORDER};border-radius:14px;padding:20px 22px;'>"
                f"<div style='font-size:.65rem;color:{p.MUTED};text-transform:uppercase;letter-spacing:.1em;font-weight:700;margin-bottom:12px;'>Summary</div>",
                unsafe_allow_html=True)
            rows = [
                ("Client",         data["client_name"]),
                ("Account",        data["account_number"]),
                ("Statement Date", data["report_date"]),
                ("Portfolio Value",f"GHS {m['tv']:,.2f}"),
                ("Net Invested",   f"GHS {m['ni']:,.2f}"),
                ("Unrealised G/L", f"{'+'if m['tg']>=0 else ''}GHS {m['tg']:,.2f}"),
                ("ROI",            f"{m['roi']:+.2f}%"),
                ("CAGR",           f"{m['cagr']:+.2f}%" if m['cagr'] else "—"),
                ("Health Score",   f"{m['hs']}/100"),
                ("Sharpe Ratio",   f"{am['sharpe']:+.2f}" if am['sharpe'] else "—"),
                ("Dividend Income",f"GHS {m['div']:,.2f}"),
                ("Est. Fees Paid", f"GHS {total_fees:,.2f}"),
                ("DRIP Upside",    f"+GHS {drip_value:,.2f}"),
                ("Positions",      str(len(eq))),
                ("Win Rate",       f"{m['winners']}/{len(eq)} ({m['winners']/len(eq)*100:.0f}%)"),
                ("Sectors",        str(m['su'])),
            ]
            for label, val in rows:
                st.markdown(
                    f"<div class='stat-row' style='display:flex;justify-content:space-between;padding:7px 0;"
                    f"border-bottom:1px solid {p.BORDER};font-size:.82rem;'>"
                    f"<span style='color:{p.MUTED};font-family:Epilogue,sans-serif;'>{label}</span>"
                    f"<span style='color:{p.TEXT};font-family:DM Mono,monospace;font-weight:500;'>{val}</span>"
                    f"</div>",unsafe_allow_html=True)
            st.markdown("</div>",unsafe_allow_html=True)
        with r2:
            st.plotly_chart(chart_sector_donut(eq), key="pc_26",use_container_width=True)
            st.plotly_chart(chart_pl_waterfall(eq), key="pc_27",use_container_width=True)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("<div class='rich-divider'></div>",unsafe_allow_html=True)
    generated=datetime.now().strftime("%d %b %Y · %H:%M")
    st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;
            padding:4px 4px 20px;font-size:.75rem;color:{p.MUTED};font-family:Epilogue,sans-serif;">
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:1.1rem;">₵</span>
    <span><b style='color:{GOLD};font-family:Fraunces,serif;font-size:.85rem;'>IC Portfolio Analyser</b>
      <span style='color:{p.BORDER2};margin:0 6px;'>·</span>Elite Edition v4.0</span>
  </div>
  <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;">
    <span>Generated {generated}</span>
    <span style="color:{p.BORDER2};">|</span>
    <span>Prices: <a href='https://dev.kwayisi.org/apis/gse/' target='_blank'
      style='color:{GOLD};text-decoration:none;font-weight:600;'>dev.kwayisi.org/apis/gse</a></span>
    <span style="color:{p.BORDER2};">|</span>
    <span>For informational purposes only</span>
    <span style="color:{p.BORDER2};">|</span>
    <span>Past performance does not guarantee future results</span>
  </div>
</div>""",unsafe_allow_html=True)


if __name__ == "__main__":
    main()