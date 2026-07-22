"""
app.py
======
AI EPC Intelligence Platform - unified enterprise frontend.

Single-file Streamlit application. Imports and calls the existing backend
modules directly (no intermediate interface/wrapper layer):

    AI_Assistant.assistant
    Compliance_Checker.compliance_checker
    Schedule_Risk_Prediction.schedule_risk_prediction
    Supply_Chain_Tracker.supply_chain_tracker
    Quality_Assurance.*

Run with:  streamlit run app.py
"""

import os
import sys
import json
import importlib
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import subprocess
import sys

scripts = [
    "AI_Assistant/build_rag_database.py",
    "Compliance_Checker/compliance_checker.py",
    "Schedule_Risk_Prediction/schedule_risk_prediction.py",
    "Supply_Chain_Tracker/supply_chain_tracker.py",
    "Quality_Assurance/sensors/sensor_analyzer.py",
    "Quality_Assurance/vision/detect_defect.py",
    "Quality_Assurance/reports/report_generator.py",
]

for script in scripts:
    subprocess.run([sys.executable, script], check=True)

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

PROJECT_DATA_ROOT = str(BASE_DIR / "project_data")
COMPLIANCE_OUT = BASE_DIR / "Compliance_Checker"
QA_REPORTS_DIR = BASE_DIR / "module5" / "reports"

# ---------------------------------------------------------------------------
# BACKEND IMPORTS (direct - no interface layer)
# Each is wrapped defensively so a missing dependency, missing dataset, or
# missing API key degrades a single panel instead of crashing the platform.
# ---------------------------------------------------------------------------
COMPLIANCE_OK, COMPLIANCE_ERR = True, ""
try:
    from Compliance_Checker.compliance_checker import run_compliance_check
except Exception as e:
    COMPLIANCE_OK, COMPLIANCE_ERR = False, str(e)
# SAFE IMPORT FOR SCHEDULE RISK PREDICTOR
SCHEDULE_OK, SCHEDULE_ERR = True, ""
try:
    from Schedule_Risk_Predictor.schedule_risk_prediction import ScheduleRiskPredictor
except Exception as e:
    # Fallback to direct file loading if python path fails
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("schedule_risk_prediction", str(BASE_DIR / "Schedule_Risk_Predictor" / "schedule_risk_prediction.py"))
        srp_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(srp_mod)
        ScheduleRiskPredictor = srp_mod.ScheduleRiskPredictor
    except Exception as inner_e:
        SCHEDULE_OK, SCHEDULE_ERR = False, str(inner_e)

SUPPLY_OK, SUPPLY_ERR = True, ""
try:
    from Supply_Chain_Tracker.supply_chain_tracker import SupplyChainTracker
except Exception as e:
    SUPPLY_OK, SUPPLY_ERR = False, str(e)

QA_SENSOR_OK = True
try:
    from Quality_Assurance.sensors.sensor_analyzer import analyze_sensor_data
except Exception:
    QA_SENSOR_OK = False

QA_VISION_OK = True
try:
    from Quality_Assurance.vision.detect_defect import detect as run_defect_detection
except Exception:
    QA_VISION_OK = False

QA_HELPER_OK = True
try:
    from Quality_Assurance.utils.helper import calculate_risk_score
except Exception:
    QA_HELPER_OK = False

QA_REPORT_OK = True
try:
    from Quality_Assurance.reports.report_generator import generate_report
except Exception:
    QA_REPORT_OK = False

# Module 5 Pipeline Automation Imports
QA_PIPELINE_OK = True
try:
    from Quality_Assurance.vision.generate_defect_images import generate_images as run_image_gen
    from Quality_Assurance.vision.prepare_dataset import process_dataset_main
    from Quality_Assurance.vision.train_yolo import train_yolo_model
except Exception:
    QA_PIPELINE_OK = False


# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI EPC Intelligence Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# GLOBAL CSS - dark glassmorphism enterprise theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root{
  --bg:#07111F; --sidebar:#0F172A; --card:#111827; --card-hover:#172554;
  --blue:#2563EB; --purple:#8B5CF6; --green:#22C55E; --orange:#F59E0B;
  --red:#EF4444; --cyan:#06B6D4; --yellow:#FACC15;
  --text:#F8FAFC; --text-dim:#94A3B8; --border:rgba(148,163,184,0.14);
}

html, body, [class*="css"]{ font-family:'Inter',sans-serif; }
#MainMenu, footer, header{ visibility:hidden; }
.stApp{ background:radial-gradient(circle at 10% 0%, #0B1626 0%, #07111F 55%, #05090F 100%); color:var(--text); }
.block-container{ padding-top:1.1rem; padding-bottom:2rem; max-width:1400px; }

::-webkit-scrollbar{ width:9px; height:9px; }
::-webkit-scrollbar-track{ background:transparent; }
::-webkit-scrollbar-thumb{ background:linear-gradient(180deg,var(--blue),var(--purple)); border-radius:8px; }

section[data-testid="stSidebar"]{
  background:linear-gradient(180deg,var(--sidebar) 0%, #0A1220 100%);
  border-right:1px solid var(--border);
}
section[data-testid="stSidebar"] .block-container{ padding-top:1.2rem; }

/* Sidebar nav buttons */
.stButton>button{
  width:100%; text-align:left; background:transparent; color:var(--text-dim);
  border:1px solid transparent; border-radius:10px; padding:0.55rem 0.9rem;
  font-weight:500; font-size:0.92rem; transition:all .15s ease;
}
.stButton>button:hover{
  background:rgba(37,99,235,0.12); color:var(--text); border-color:rgba(37,99,235,0.35);
  transform:translateX(2px);
}
.nav-active > button{
  background:linear-gradient(90deg, rgba(37,99,235,0.22), rgba(139,92,246,0.10));
  color:var(--text) !important; border:1px solid rgba(37,99,235,0.45) !important;
  font-weight:600;
}

/* Primary gradient buttons */
button[kind="primary"]{
  background:linear-gradient(135deg,var(--blue),var(--purple)) !important;
  border:none !important; box-shadow:0 6px 20px rgba(37,99,235,0.35); font-weight:600 !important;
}

/* Header bar */
.top-header{
  background:linear-gradient(120deg, rgba(37,99,235,0.18), rgba(139,92,246,0.12) 60%, rgba(6,182,212,0.10));
  border:1px solid var(--border); border-radius:18px; padding:1.4rem 1.8rem;
  margin-bottom:1.4rem; backdrop-filter:blur(18px);
}
.top-header h1{ font-size:1.55rem; font-weight:800; margin:0; letter-spacing:-0.02em; }
.top-header p{ color:var(--text-dim); margin:0.2rem 0 0 0; font-size:0.88rem; }

/* Glass cards */
.glass-card{
  background:rgba(17,24,39,0.65); border:1px solid var(--border); border-radius:16px;
  padding:1.25rem 1.4rem; backdrop-filter:blur(12px); transition:all .18s ease;
}
.glass-card:hover{ border-color:rgba(37,99,235,0.4); background:rgba(23,37,84,0.55); transform:translateY(-2px); }

/* KPI cards */
.kpi-card{
  background:rgba(17,24,39,0.7); border:1px solid var(--border); border-radius:16px;
  padding:1.1rem 1.3rem; position:relative; overflow:hidden; transition:all .2s ease;
}
.kpi-card:hover{ transform:translateY(-3px); border-color:var(--accent,#2563EB); box-shadow:0 10px 30px rgba(0,0,0,0.35); }
.kpi-card .kpi-icon{ font-size:1.4rem; }
.kpi-card .kpi-label{ color:var(--text-dim); font-size:0.76rem; text-transform:uppercase; letter-spacing:0.06em; margin-top:0.4rem;}
.kpi-card .kpi-value{ font-size:1.9rem; font-weight:800; margin-top:0.15rem; }
.kpi-card .kpi-trend{ font-size:0.78rem; margin-top:0.3rem; font-weight:600; }

/* Badges */
.badge{ display:inline-block; padding:0.18rem 0.65rem; border-radius:999px; font-size:0.74rem; font-weight:700; letter-spacing:0.02em;}
.badge-green{ background:rgba(34,197,94,0.15); color:#4ADE80; border:1px solid rgba(34,197,94,0.35); }
.badge-orange{ background:rgba(245,158,11,0.15); color:#FBBF24; border:1px solid rgba(245,158,11,0.35); }
.badge-red{ background:rgba(239,68,68,0.15); color:#F87171; border:1px solid rgba(239,68,68,0.35); }
.badge-blue{ background:rgba(37,99,235,0.15); color:#60A5FA; border:1px solid rgba(37,99,235,0.35); }
.badge-cyan{ background:rgba(6,182,212,0.15); color:#22D3EE; border:1px solid rgba(6,182,212,0.35); }

/* AI hero */
.ai-hero{
  background:linear-gradient(135deg, rgba(37,99,235,0.16), rgba(139,92,246,0.14));
  border:1px solid rgba(37,99,235,0.35); border-radius:22px; padding:2rem 2.2rem;
  margin-bottom:1.4rem; backdrop-filter:blur(20px);
}
.ai-hero h2{ font-size:1.3rem; font-weight:800; margin-bottom:0.2rem; }
.ai-hero p{ color:var(--text-dim); font-size:0.9rem; margin-bottom:1rem; }

/* Section title */
.section-title{ font-size:1.05rem; font-weight:700; margin:1.1rem 0 0.6rem 0; color:var(--text); }
.subtle{ color:var(--text-dim); font-size:0.85rem; }

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]>div{
  background:rgba(255,255,255,0.04) !important; border:1px solid var(--border) !important;
  color:var(--text) !important; border-radius:10px !important;
}
[data-testid="stMetric"]{
  background:rgba(17,24,39,0.6); border:1px solid var(--border); border-radius:14px; padding:0.8rem 1rem;
}
hr{ border-color:var(--border); }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "hero_query" not in st.session_state:
    st.session_state.hero_query = ""
if "checklist" not in st.session_state:
    st.session_state.checklist = {}
if "resolved_alerts" not in st.session_state:
    st.session_state.resolved_alerts = set()


# ---------------------------------------------------------------------------
# BACKEND DATA ACCESSORS (cached)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_schedule_predictor():
    if not SCHEDULE_OK:
        return None
    try:
        return ScheduleRiskPredictor(PROJECT_DATA_ROOT).load_data()
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def get_supply_tracker():
    if not SUPPLY_OK:
        return None
    try:
        return SupplyChainTracker(PROJECT_DATA_ROOT).load_data()
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=300)
def get_compliance_df():
    for candidate in ("compliance_report_complete.csv", "compliance_report.csv"):
        p = COMPLIANCE_OUT / candidate
        if p.exists():
            try:
                return pd.read_csv(p)
            except Exception:
                pass
    return None


@st.cache_resource(show_spinner=False)
def _load_ai_assistant():
    try:
        module = importlib.import_module("AI_Assistant.assistant")
    except SystemExit:
        return {"ok": False, "err": "RAG database not found. Run build_rag_database.py first.", "mod": None}
    except Exception as e:
        return {"ok": False, "err": str(e), "mod": None}

    try:
        ok, msg = module.validate_api_key(module.GEMINI_API_KEY)
    except Exception as e:
        return {"ok": False, "err": str(e), "mod": module}
    if not ok:
        return {"ok": False, "err": msg, "mod": module}
    return {"ok": True, "err": "", "mod": module}


def run_ai_query(question: str):
    state = _load_ai_assistant()
    if not state["ok"]:
        return None, [], state["err"]
    module = state["mod"]
    try:
        docs, metas = module.retrieve_context(question)
        if not docs:
            return "The project documents do not contain information relevant to this question.", [], ""
        context_block = module.build_context_block(docs, metas)
        full_prompt = (
            f"RELEVANT PROJECT DATA CONTEXT:\n{context_block}\n\n"
            f"USER QUESTION: {question}\n\nYOUR CITED ANSWER:"
        )
        interaction = module.client.interactions.create(
            model=module.MODEL_NAME,
            input=full_prompt,
            system_instruction=module.SYSTEM_INSTRUCTION,
        )
        sources = sorted(set(m["source"] for m in metas))
        return interaction.output_text, sources, ""
    except Exception as e:
        return None, [], str(e)


# ---------------------------------------------------------------------------
# SMALL UI HELPERS
# ---------------------------------------------------------------------------
NAV_ITEMS = [
    ("Dashboard", "🏠"),
    ("AI Knowledge Assistant", "🤖"),
    ("Compliance Checker", "✅"),
    ("Schedule Risk Predictor", "📅"),
    ("Supply Chain Tracker", "🚚"),
    ("Commissioning QA", "🧪"),
    ("Alerts", "🔔"),
    ("Settings", "⚙️"),
]


def page_header(icon, title, description, accent="#2563EB", show_search=True):
    crumb = f"AI EPC Platform / {title}"
    st.markdown(f"""
    <div class="top-header" style="border-color:{accent}55;">
      <div class="subtle" style="margin-bottom:0.35rem;">{crumb}</div>
      <h1>{icon} &nbsp;{title}</h1>
      <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)

    if show_search:
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        with c1:
            st.text_input("Search", placeholder=f"Search within {title}...", label_visibility="collapsed", key=f"search_{title}")
    else:
        c2, c3, c4 = st.columns([1, 1, 1])

    with c2:
        if st.button("🔄 Refresh", key=f"refresh_{title}", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
    with c3:
        st.button("⬇️ Export", key=f"export_{title}", use_container_width=True)
    with c4:
        st.button("⚡ Quick Actions", key=f"qa_{title}", use_container_width=True)
    st.write("")


def kpi_card(col, icon, label, value, trend, color):
    with col:
        st.markdown(f"""
        <div class="kpi-card" style="--accent:{color};">
          <div class="kpi-icon">{icon}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{value}</div>
          <div class="kpi-trend" style="color:{color};">{trend}</div>
        </div>
        """, unsafe_allow_html=True)


def empty_state(message, hint=""):
    st.markdown(f"""
    <div class="glass-card" style="text-align:center; padding:2.2rem;">
      <div style="font-size:1.6rem;">📶</div>
      <div style="font-weight:600; margin-top:0.4rem;">{message}</div>
      <div class="subtle" style="margin-top:0.2rem;">{hint}</div>
    </div>
    """, unsafe_allow_html=True)


def badge(label, kind="blue"):
    return f'<span class="badge badge-{kind}">{label}</span>'


def compliance_badge_kind(label):
    return {
        "Compliant": "green",
        "Partial Compliance": "orange",
        "Missing Information": "orange",
        "Non-Compliant": "red",
    }.get(str(label), "blue")


def risk_badge_kind(label):
    l = str(label).upper()
    if "HIGH" in l or "CRITICAL" in l:
        return "red"
    if "MEDIUM" in l:
        return "orange"
    return "green"


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:0.6rem; padding:0.4rem 0.2rem 1rem 0.2rem;">
      <div style="font-size:1.6rem;">⚡</div>
      <div>
        <div style="font-weight:800; font-size:1.05rem; line-height:1.1;">AI EPC Platform</div>
        <div class="subtle" style="font-size:0.72rem;">Data Center Intelligence</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.selectbox("Project", ["PRJ-MUM-2026 — Data Center EPC"], label_visibility="collapsed")
    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    for name, icon in NAV_ITEMS:
        active = st.session_state.page == name
        wrapper_class = "nav-active" if active else ""
        st.markdown(f'<div class="{wrapper_class}">', unsafe_allow_html=True)
        if st.button(f"{icon}  {name}", key=f"nav_{name}", use_container_width=True):
            st.session_state.page = name
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex; align-items:center; gap:0.6rem; padding:0.3rem 0.2rem;">
      <div style="width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#2563EB,#8B5CF6);
                  display:flex;align-items:center;justify-content:center;font-weight:700;">MB</div>
      <div>
        <div style="font-size:0.85rem; font-weight:600;">Mahi</div>
        <div class="subtle" style="font-size:0.72rem;">Commissioning Team</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PAGE: DASHBOARD
# ---------------------------------------------------------------------------
def render_dashboard():
    st.markdown("""
    <div class="top-header">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6rem;">
        <div>
          <h1>AI EPC Intelligence Platform</h1>
          <p>AI-powered Intelligence for Data Center EPC Delivery</p>
        </div>
        <div style="display:flex; gap:0.6rem; align-items:center;">
          <span class="badge badge-blue">🔔 3</span>
          <span class="badge badge-cyan">PRJ-MUM-2026</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="ai-hero">
      <h2>🤖 AI Command Center</h2>
      <p>Ask anything about compliance, schedule, supply chain, or commissioning — grounded in your project documents.</p>
    </div>
    """, unsafe_allow_html=True)

    chips = [
        "Why is commissioning delayed?",
        "Show compliance issues",
        "Summarize today's project",
        "Which shipment is delayed?",
        "Show critical risks",
        "Analyze vendor documents",
    ]
    chip_cols = st.columns(len(chips))
    for c, chip_text in zip(chip_cols, chips):
        with c:
            if st.button(chip_text, key=f"chip_{chip_text}", use_container_width=True):
                st.session_state.hero_query = chip_text

    query = st.text_input(
        "Ask", value=st.session_state.hero_query,
        placeholder="Ask anything about your project...", label_visibility="collapsed",
        key="hero_input",
    )
    analyze = st.button("⚡ Analyze", type="primary", use_container_width=False)

    if analyze and query.strip():
        with st.spinner("Analyzing across knowledge base, compliance, schedule, and supply chain..."):
            answer, sources, err = run_ai_query(query.strip())
        if err:
            st.warning(f"AI Assistant unavailable: {err}")
        elif answer:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("**Executive Summary**")
            st.markdown(answer)
            if sources:
                st.markdown("**Source Citations**")
                st.markdown(" ".join(badge(s, "blue") for s in sources), unsafe_allow_html=True)
            st.markdown("**Quick Actions**")
            qc = st.columns(5)
            labels = ["Open Compliance", "Open Schedule", "Open Supply Chain", "Open QA", "Open AI Assistant"]
            targets = ["Compliance Checker", "Schedule Risk Predictor", "Supply Chain Tracker", "Commissioning QA", "AI Knowledge Assistant"]
            for col, label, target in zip(qc, labels, targets):
                with col:
                    if st.button(label, key=f"qa_go_{label}"):
                        st.session_state.page = target
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Executive Overview</div>', unsafe_allow_html=True)

    comp_df = get_compliance_df()
    compliance_score = None
    if comp_df is not None and len(comp_df):
        compliance_score = round(100 * (comp_df["Compliance_Label"] == "Compliant").mean(), 1)

    srp = get_schedule_predictor()
    schedule_summary = None
    if srp is not None:
        try:
            schedule_summary = srp.dashboard_summary()
        except Exception:
            schedule_summary = None

    tracker = get_supply_tracker()
    supply_summary = None
    if tracker is not None:
        try:
            supply_summary = tracker.dashboard_summary()
        except Exception:
            supply_summary = None

    critical_alerts = 0
    if comp_df is not None:
        critical_alerts += int((comp_df["Compliance_Label"] == "Non-Compliant").sum())
    if schedule_summary:
        critical_alerts += schedule_summary.get("schedule_breaches", 0)
    if supply_summary:
        critical_alerts += supply_summary.get("schedule_breaches", 0)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    kpi_card(k1, "💚", "Project Health",
             "Good" if critical_alerts == 0 else ("Watch" if critical_alerts < 3 else "At Risk"),
             "Composite score", "#22C55E" if critical_alerts == 0 else "#F59E0B")
    kpi_card(k2, "✅", "Compliance Score",
             f"{compliance_score}%" if compliance_score is not None else "N/A",
             "vs. requirements register", "#22C55E")
    kpi_card(k3, "📅", "Schedule Risk",
             f"{schedule_summary['activities_at_risk']} at risk" if schedule_summary else "N/A",
             f"of {schedule_summary['total_activities']} activities" if schedule_summary else "no data", "#F59E0B")
    kpi_card(k4, "🧪", "Quality Score",
             "N/A", "QA module active", "#06B6D4")
    kpi_card(k5, "🏗️", "Commissioning Progress",
             f"{supply_summary['on_time_pct']}%" if supply_summary else "N/A",
             "on-time delivery rate", "#8B5CF6")
    kpi_card(k6, "🚨", "Critical Alerts",
             str(critical_alerts), "requires attention", "#EF4444")

    st.write("")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown('<div class="section-title">Schedule Risk Distribution</div>', unsafe_allow_html=True)
        if srp is not None:
            try:
                risk_df = srp.risk_prediction()
                dist = risk_df["Risk_Level"].value_counts().reset_index()
                dist.columns = ["Risk_Level", "Count"]
                fig = px.bar(dist, x="Risk_Level", y="Count", color="Risk_Level",
                             color_discrete_map={"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#22C55E"})
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font_color="#F8FAFC", height=320, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                empty_state("Schedule risk data unavailable", str(e))
        else:
            empty_state("Schedule module not connected", SCHEDULE_ERR or "Could not load schedule files.")

    with col_right:
        st.markdown('<div class="section-title">Compliance Breakdown</div>', unsafe_allow_html=True)
        if comp_df is not None:
            dist = comp_df["Compliance_Label"].value_counts().reset_index()
            dist.columns = ["Label", "Count"]
            fig = px.pie(dist, names="Label", values="Count", hole=0.55,
                         color="Label", color_discrete_map={
                             "Compliant": "#22C55E", "Partial Compliance": "#F59E0B",
                             "Non-Compliant": "#EF4444", "Missing Information": "#94A3B8"})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#F8FAFC", height=320, showlegend=True,
                               legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig, use_container_width=True)
        else:
            empty_state("No compliance report found", "Run a check from the Compliance Checker page.")


# ---------------------------------------------------------------------------
# PAGE: AI KNOWLEDGE ASSISTANT
# ---------------------------------------------------------------------------
def render_ai_assistant():
    page_header("🤖", "AI Knowledge Assistant",
                 "Ask project questions grounded in your engineering, vendor, and schedule documents.", "#2563EB")

    ai_state = _load_ai_assistant()
    if not ai_state["ok"]:
        empty_state("AI Assistant is offline", ai_state["err"])
        return

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                st.markdown(" ".join(badge(s, "blue") for s in msg["sources"]), unsafe_allow_html=True)

    suggestions = ["What is the UPS efficiency spec?", "Summarize the chiller vendor datasheet",
                   "Any RFIs open on electrical scope?", "What's the generator transfer time requirement?"]
    sc = st.columns(len(suggestions))
    for col, s in zip(sc, suggestions):
        with col:
            if st.button(s, key=f"sugg_{s}", use_container_width=True):
                st.session_state["_pending_prompt"] = s

    prompt = st.chat_input("Ask a project question...")
    if "_pending_prompt" in st.session_state and not prompt:
        prompt = st.session_state.pop("_pending_prompt")

    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.spinner("Retrieving context and generating answer..."):
            answer, sources, err = run_ai_query(prompt)
        if err:
            answer = f"Sorry, I hit an error reaching the AI backend: {err}"
            sources = []
        st.session_state.chat_history.append({"role": "assistant", "content": answer, "sources": sources})
        st.rerun()


# ---------------------------------------------------------------------------
# PAGE: COMPLIANCE CHECKER
# ---------------------------------------------------------------------------
def render_compliance():
    page_header("✅", "Compliance Checker",
                 "Vendor documentation vs. client requirements, automatically cross-checked.", "#22C55E")

    if not COMPLIANCE_OK:
        empty_state("Compliance module not available", COMPLIANCE_ERR)
        return

    top = st.columns([1, 1, 3])
    with top[0]:
        run_clicked = st.button("▶ Run Full Compliance Check", type="primary", use_container_width=True)
    with top[1]:
        st.file_uploader("Upload vendor doc (drag & drop)", type=["pdf"], label_visibility="collapsed")

    if run_clicked:
        out_path = COMPLIANCE_OUT / "compliance_report.csv"
        with st.spinner("Extracting vendor documents..."):
            try:
                run_compliance_check(PROJECT_DATA_ROOT, str(out_path))
                st.cache_data.clear()
                st.toast("Compliance check complete", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Compliance check failed: {e}")

    df = get_compliance_df()
    if df is None:
        empty_state("No compliance report found yet", "Click 'Run Full Compliance Check' to generate one.")
        return

    score = round(100 * (df["Compliance_Label"] == "Compliant").mean(), 1)
    g1, g2 = st.columns([1, 2])
    with g1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=score,
            title={"text": "Compliance Score"},
            gauge={"axis": {"range": [0, 100]},
                   "bar": {"color": "#22C55E"},
                   "steps": [{"range": [0, 50], "color": "#3F1D1D"},
                             {"range": [50, 80], "color": "#3F331D"},
                             {"range": [80, 100], "color": "#1D3F26"}]}))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#F8FAFC", height=280)
        st.plotly_chart(fig, use_container_width=True)
    with g2:
        heat = df.groupby(["Category", "Compliance_Label"]).size().reset_index(name="Count")
        fig2 = px.density_heatmap(heat, x="Compliance_Label", y="Category", z="Count",
                                   color_continuous_scale="Blues")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#F8FAFC", height=280)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-title">Requirement Comparison</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, height=380)

    st.download_button("⬇️ Download Full Report (CSV)", df.to_csv(index=False).encode(),
                        file_name="compliance_report.csv", mime="text/csv")


# ---------------------------------------------------------------------------
# PAGE: SCHEDULE RISK PREDICTOR
# ---------------------------------------------------------------------------
def render_schedule():
    page_header("📅", "Schedule Risk Predictor",
                 "Baseline vs. active schedule analysis, delay prediction, and recovery planning.", "#F59E0B",
                 show_search=False)

    srp = get_schedule_predictor()
    if srp is None:
        empty_state("Schedule module not connected", SCHEDULE_ERR or "Could not load schedule files.")
        return

    try:
        summary = srp.dashboard_summary()
        delays = srp.predict_delays()
        deps = srp.dependency_analysis()
        actions = srp.recommend_recovery_actions()
    except Exception as e:
        empty_state("Could not compute schedule analytics", str(e))
        return

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_card(k1, "📋", "Total Activities", summary["total_activities"], "tracked", "#2563EB")
    kpi_card(k2, "⚠️", "At Risk", summary["activities_at_risk"], "activities flagged", "#F59E0B")
    kpi_card(k3, "🛤️", "Critical Path", summary["critical_path_activities"], "items on critical path", "#8B5CF6")
    kpi_card(k4, "❌", "Breaches", summary["schedule_breaches"], "float exhausted", "#EF4444")
    kpi_card(k5, "⏱️", "Avg Delay", f"{summary['avg_predicted_delay_days']}d", "predicted", "#06B6D4")

    st.write("")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown('<div class="section-title">Predicted Delay vs. Remaining Float</div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_bar(x=delays["Activity_ID"], y=delays["Predicted_Delay_Days"], name="Predicted Delay (days)", marker_color="#F59E0B")
        fig.add_bar(x=delays["Activity_ID"], y=delays["Float_Remaining_Days"], name="Float Remaining (days)", marker_color="#2563EB")
        fig.update_layout(barmode="group", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#F8FAFC", height=380, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<div class="section-title">Delay Probability</div>', unsafe_allow_html=True)
        avg_delay = summary["avg_predicted_delay_days"]
        fig2 = go.Figure(go.Indicator(mode="gauge+number", value=avg_delay,
                                       title={"text": "Avg predicted delay (days)"},
                                       gauge={"axis": {"range": [0, max(10, avg_delay * 2)]},
                                              "bar": {"color": "#F59E0B"}}))
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#F8FAFC", height=380)
        st.plotly_chart(fig2, use_container_width=True)

    tab1, tab2 = st.tabs(["Dependency Analysis", "Recommended Recovery Actions"])
    with tab1:
        st.dataframe(deps, use_container_width=True)
    with tab2:
        for _, r in actions.iterrows():
            kind = risk_badge_kind(r["Risk_Level"])
            st.markdown(f"""
            <div class="glass-card" style="margin-bottom:0.5rem;">
              {badge(r['Risk_Level'], kind)} &nbsp;<b>{r['Activity_ID']}</b> — {r['Activity_Name']}
              <div class="subtle" style="margin-top:0.3rem;">{r['Recommended_Actions']}</div>
            </div>
            """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PAGE: SUPPLY CHAIN TRACKER
# ---------------------------------------------------------------------------
def render_supply_chain():
    page_header("🚚", "Supply Chain Tracker",
                 "Equipment delivery status, delay detection, and alternate supplier recommendations.", "#8B5CF6")

    tracker = get_supply_tracker()
    if tracker is None:
        empty_state("Supply chain module not connected", SUPPLY_ERR or "Could not load supply-chain files.")
        return

    try:
        summary = tracker.dashboard_summary()
        deliveries = tracker.track_deliveries()
        delays = tracker.detect_delays()
        risk = tracker.risk_analysis()
        recs = tracker.recommend_alternatives()
    except Exception as e:
        empty_state("Could not compute supply chain analytics", str(e))
        return

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_card(k1, "📦", "Total Equipment", summary["total_equipment"], "tracked", "#2563EB")
    kpi_card(k2, "⏳", "Delayed", summary["delayed_shipments"], "shipments", "#F59E0B")
    kpi_card(k3, "❌", "Breaches", summary["schedule_breaches"], "schedule critical", "#EF4444")
    kpi_card(k4, "⚠️", "High Risk", summary["high_risk_items"], "vendor items", "#F59E0B")
    kpi_card(k5, "✅", "On-Time %", f"{summary['on_time_pct']}%", "delivery rate", "#22C55E")

    st.write("")
    st.markdown('<div class="section-title">Shipment ETA Timeline</div>', unsafe_allow_html=True)
    try:
        fig = px.bar(deliveries.sort_values("Days_Delayed", ascending=False),
                     x="Equipment_ID", y="Days_Delayed", color="Current_Transit_Status",
                     hover_data=["Vendor_ID", "Origin_Hub", "Est_Arrival_Date"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#F8FAFC", height=340)
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.dataframe(deliveries, use_container_width=True)

    tab1, tab2, tab3 = st.tabs(["Delay Detection", "Risk Analysis", "Alternative Suppliers"])
    with tab1:
        st.dataframe(delays, use_container_width=True)
    with tab2:
        st.dataframe(risk, use_container_width=True)
    with tab3:
        for _, r in recs.iterrows():
            st.markdown(f"""
            <div class="glass-card" style="margin-bottom:0.5rem;">
              <b>{r['Equipment_ID']}</b> — {r.get('Equipment_Name','')}<br/>
              Current: {badge(r['Current_Vendor'], 'blue')} {badge(r['Current_Risk_Level'], risk_badge_kind(r['Current_Risk_Level']))}
              → Recommended: {badge(r['Recommended_Alternate'], 'green')}
              <div class="subtle" style="margin-top:0.3rem;">{r['Rationale']}</div>
            </div>
            """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PAGE: COMMISSIONING QA (Integrated Pipeline Control Center)
# ---------------------------------------------------------------------------
def render_qa():
    page_header("🧪", "Commissioning QA",
                 "Visual defect detection, sensor telemetry analysis, model training pipeline, and automated QA reporting.", "#06B6D4")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Image Analysis", 
        "Sensor Analysis", 
        "Pipeline Orchestrator", 
        "Testing Checklist", 
        "Generated Reports"
    ])

    with tab1:
        st.markdown('<div class="section-title">Equipment Defect Detection</div>', unsafe_allow_html=True)
        img = st.file_uploader("Upload equipment photo", type=["jpg", "jpeg", "png"])
        if img is not None:
            st.image(img, caption="Uploaded image", use_container_width=True)
            if not QA_VISION_OK:
                empty_state("Vision model not available", "Quality_Assurance.vision.detect_defect could not be imported.")
            else:
                if st.button("Run Defect Detection", type="primary"):
                    from PIL import Image
                    
                    # 1. Convert uploaded file directly to a PIL Image
                    image_obj = Image.open(img)
                    
                    with st.spinner("Running YOLO defect detection..."):
                        try:
                            # 2. Pass the image object AND the original filename 
                            run_defect_detection(image_obj, filename_override=img.name)
                            st.success("Detection complete - see Generated Reports tab.")
                        except Exception as e:
                            st.error(f"Detection failed: {e}")

    with tab2:
        st.markdown('<div class="section-title">Sensor Telemetry Analysis</div>', unsafe_allow_html=True)
        sensor_csv = st.file_uploader("Upload sensor readings CSV", type=["csv"], key="sensor_csv")
        if sensor_csv is not None:
            if not QA_SENSOR_OK:
                empty_state("Sensor analyzer not available", "Quality_Assurance.sensors.sensor_analyzer could not be imported.")
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    tmp.write(sensor_csv.getbuffer())
                    tmp_path = tmp.name
                try:
                    result = analyze_sensor_data(tmp_path)
                    cols = st.columns(3)
                    cols[0].metric("Voltage", result.get("Voltage"), result.get("Voltage_Status"))
                    cols[1].metric("Current", result.get("Current"), result.get("Current_Status"))
                    cols[2].metric("Temperature", result.get("Temperature"), result.get("Temperature_Status"))
                except Exception as e:
                    st.error(f"Sensor analysis failed: {e}")

    with tab3:
        st.markdown('<div class="section-title">⚙️ End-to-End Pipeline Orchestrator</div>', unsafe_allow_html=True)
        st.markdown("Execute data generation, dataset preparation, and YOLO model training directly from the UI.")
        
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            if st.button("1. Generate Synthetic Images", use_container_width=True):
                with st.spinner("Generating defect samples & annotations..."):
                    try:
                        import Quality_Assurance.vision.generate_defect_images as gen_mod
                        st.success("Synthetic images generated successfully!")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col_p2:
            if st.button("2. Prepare YOLO Dataset", use_container_width=True):
                with st.spinner("Splitting train/val and converting boxes..."):
                    try:
                        import Quality_Assurance.vision.prepare_dataset as prep_mod
                        st.success("Dataset prepared for YOLO!")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col_p3:
            if st.button("3. Train YOLOv8 Model", type="primary", use_container_width=True):
                with st.spinner("Training model (this may take a few minutes)..."):
                    try:
                        import Quality_Assurance.vision.train_yolo as train_mod
                        st.success("Model training complete! Weights saved.")
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab4:
        st.markdown('<div class="section-title">Commissioning Testing Checklist</div>', unsafe_allow_html=True)
        checklist_items = [
            "UPS load bank test completed",
            "Generator transfer test (ATS) verified",
            "Chiller performance test within design target",
            "Battery autonomy test passed",
            "CRAH thermal balancing complete",
            "All punch-list items closed",
        ]
        for item in checklist_items:
            st.session_state.checklist[item] = st.checkbox(item, value=st.session_state.checklist.get(item, False))
        done = sum(st.session_state.checklist.values())
        st.progress(done / len(checklist_items))
        st.caption(f"{done}/{len(checklist_items)} items complete")

    with tab5:
        st.markdown('<div class="section-title">Generated Commissioning Reports</div>', unsafe_allow_html=True)
        if QA_REPORTS_DIR.exists():
            reports = sorted(QA_REPORTS_DIR.glob("*_report.txt"))
            if reports:
                for r in reports:
                    with open(r, "r") as f:
                        content = f.read()
                    with st.expander(r.name):
                        st.text(content)
                        st.download_button("Download", content, file_name=r.name, key=f"dl_{r.name}")
            else:
                empty_state("No reports generated yet", "Run a defect detection to generate one.")
        else:
            empty_state("Reports directory not found", str(QA_REPORTS_DIR))


# ---------------------------------------------------------------------------
# PAGE: ALERTS
# ---------------------------------------------------------------------------
def render_alerts():
    page_header("🔔", "Alerts", "Unified notification center across compliance, schedule, and supply chain.", "#EF4444")

    alerts = []
    comp_df = get_compliance_df()
    if comp_df is not None:
        for _, r in comp_df[comp_df["Compliance_Label"] != "Compliant"].iterrows():
            sev = "Critical" if r["Compliance_Label"] == "Non-Compliant" else "Medium"
            alerts.append({"id": f"COMP-{r['Requirement_ID']}", "severity": sev,
                            "message": f"{r['Requirement_ID']} ({r['Equipment_ID']}): {r['Rationale']}"})

    srp = get_schedule_predictor()
    if srp is not None:
        try:
            for _, r in srp.risk_prediction().iterrows():
                if r["Risk_Level"] != "LOW":
                    sev = "Critical" if r["Risk_Level"] == "HIGH" else "Medium"
                    alerts.append({"id": f"SCHED-{r['Activity_ID']}", "severity": sev,
                                    "message": f"{r['Activity_ID']} predicted delay {r['Predicted_Delay_Days']}d, float remaining {r['Float_Remaining_Days']}d"})
        except Exception:
            pass

    tracker = get_supply_tracker()
    if tracker is not None:
        try:
            for _, r in tracker.risk_analysis().iterrows():
                if r["Risk_Level"] != "LOW":
                    sev = "Critical" if r["Risk_Level"] == "HIGH" else "Medium"
                    alerts.append({"id": f"SUPPLY-{r['Equipment_ID']}", "severity": sev,
                                    "message": f"{r['Equipment_ID']} vendor risk {r.get('Vendor_Risk_Tier','-')}, delayed {r.get('Days_Delayed',0)}d"})
        except Exception:
            pass

    tabs = st.tabs(["Critical", "Medium", "Resolved"])
    with tabs[0]:
        crit = [a for a in alerts if a["severity"] == "Critical" and a["id"] not in st.session_state.resolved_alerts]
        if not crit:
            st.success("No critical alerts.")
        for a in crit:
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f'{badge("CRITICAL","red")} <b>{a["id"]}</b><div class="subtle">{a["message"]}</div>', unsafe_allow_html=True)
            with c2:
                if st.button("Resolve", key=f"res_{a['id']}"):
                    st.session_state.resolved_alerts.add(a["id"])
                    st.rerun()
    with tabs[1]:
        med = [a for a in alerts if a["severity"] == "Medium" and a["id"] not in st.session_state.resolved_alerts]
        if not med:
            st.success("No medium alerts.")
        for a in med:
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f'{badge("MEDIUM","orange")} <b>{a["id"]}</b><div class="subtle">{a["message"]}</div>', unsafe_allow_html=True)
            with c2:
                if st.button("Resolve", key=f"res_{a['id']}"):
                    st.session_state.resolved_alerts.add(a["id"])
                    st.rerun()
    with tabs[2]:
        resolved = [a for a in alerts if a["id"] in st.session_state.resolved_alerts]
        if not resolved:
            st.info("No resolved alerts yet.")
        for a in resolved:
            st.markdown(f'{badge("RESOLVED","green")} <b>{a["id"]}</b><div class="subtle">{a["message"]}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PAGE: SETTINGS
# ---------------------------------------------------------------------------
def render_settings():
    page_header("⚙️", "Settings", "Project configuration, theme, and system information.", "#94A3B8")

    st.markdown('<div class="section-title">Project Configuration</div>', unsafe_allow_html=True)
    st.text_input("Project Data Root", value=PROJECT_DATA_ROOT, disabled=True)
    st.text_input("Project Name", value="PRJ-MUM-2026 — Data Center EPC Delivery", disabled=True)

    st.markdown('<div class="section-title">Theme</div>', unsafe_allow_html=True)
    st.radio("Appearance", ["Dark (Enterprise)"], index=0, horizontal=True)

    st.markdown('<div class="section-title">Module Status</div>', unsafe_allow_html=True)
    statuses = [
        ("Compliance Checker", COMPLIANCE_OK, COMPLIANCE_ERR),
        ("Schedule Risk Predictor", SCHEDULE_OK, SCHEDULE_ERR),
        ("Supply Chain Tracker", SUPPLY_OK, SUPPLY_ERR),
        ("QA Sensor Analyzer", QA_SENSOR_OK, ""),
        ("QA Vision Detector", QA_VISION_OK, ""),
        ("QA Pipeline Orchestrator", QA_PIPELINE_OK, ""),
    ]
    for name, ok, err in statuses:
        kind = "green" if ok else "red"
        label = "ONLINE" if ok else "OFFLINE"
        st.markdown(f'{badge(label, kind)} &nbsp; **{name}** {"— " + err if err else ""}', unsafe_allow_html=True)

    st.markdown('<div class="section-title">System Information</div>', unsafe_allow_html=True)
    st.code(f"Python: {sys.version.split()[0]}\nStreamlit: {st.__version__}\nBase directory: {BASE_DIR}", language="text")


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------
ROUTES = {
    "Dashboard": render_dashboard,
    "AI Knowledge Assistant": render_ai_assistant,
    "Compliance Checker": render_compliance,
    "Schedule Risk Predictor": render_schedule,
    "Supply Chain Tracker": render_supply_chain,
    "Commissioning QA": render_qa,
    "Alerts": render_alerts,
    "Settings": render_settings,
}

ROUTES.get(st.session_state.page, render_dashboard)()