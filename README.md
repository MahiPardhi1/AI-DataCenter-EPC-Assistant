# 🏢 CortexEPC — AI-Powered Data Centre EPC Project Intelligence Platform

**One relational dataset. Five AI modules. A single source of truth for a data centre build.**

> Project ID: `PRJ-MUM-2026` · Domain: EPC (Engineering, Procurement & Construction) for hyperscale data centres · Built for [Hackathon Name / Track]

---

## 1. The Problem

India's data centre capacity is projected to scale from **~900 MW to 2,700+ MW by 2027**, but **67% of EPC projects run over schedule** — not because the engineering is hard, but because the *information* is scattered. A single project generates:

- Technical specs and design requirements from the client
- Vendor datasheets, quotations, and manuals
- Engineering drawings across electrical, mechanical, HVAC, and floor plans
- RFIs, meeting minutes, inspection sign-offs
- A Primavera-style master schedule that keeps slipping
- Multi-tier supply chain and shipment telemetry
- Commissioning reports and real-time sensor streams
- Hundreds of site inspection photos

None of it talks to each other. A generator shipment delay sitting in a logistics spreadsheet has no automatic link to the critical-path activity it's about to blow through. A vendor's UPS efficiency number in a 40-page PDF submittal never gets checked against the client's spec until someone manually does it, usually too late.

**CortexEPC unifies all of it under one relational backbone — `Project_ID`, `Equipment_ID`, `Vendor_ID`, `Activity_ID` — and layers AI on top to answer, predict, and recommend, instead of just storing.**

---

## 2. What's Actually Built

This is an honest status table — everything marked ✅ **Implemented** runs end-to-end today on the dataset in this repo and is covered by automated tests. Everything marked 🧩 **Data-ready** has its full data pipeline built (CSVs, PDFs, ground-truth labels, images) but the AI logic on top is scoped for the next build phase.

| # | Module | Status | What it does |
|---|--------|--------|---------------|
| 1 | 💬 AI Project Knowledge Assistant (RAG) | ✅ Implemented | Chat over the entire project corpus with cited answers |
| 2 | ⚖️ AI Compliance Checker | 🧩 Data-ready | Requirements register + vendor compliance ground truth generated; automated checker is next |
| 3 | 📅 AI Schedule Risk Predictor | ✅ Implemented | Cascading delay prediction, critical path, recovery actions |
| 4 | 🚚 AI Supply Chain Tracker | ✅ Implemented | Delay detection against float, risk scoring, alternate vendor recommender |
| 5 | 🧪 AI Commissioning QA Copilot | 🧩 Data-ready | Synthetic defect images + labelled bounding boxes generated for a CV model; detection pipeline is next |

Modules 3 and 4 each ship with a dedicated `pytest` suite built on deterministic fixtures (not the random dataset generator), so every number the module reports — cascade math, float exhaustion, risk bands — is verified against a hand-computed expected answer.

---

## 3. Architecture

```
                        ┌─────────────────────────────┐
                        │   project_data/  (10 folders) │
                        │  Client docs · Vendor docs ·   │
                        │  Drawings · RFIs · Inspections │
                        │  Schedule · Supply Chain ·      │
                        │  Commissioning · Images ·       │
                        │  Sensor Streams · Compliance KB │
                        └───────────────┬─────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                          │
    ┌─────────▼─────────┐   ┌───────────▼───────────┐   ┌──────────▼──────────┐
    │  build_rag_        │   │  schedule_risk_         │   │  supply_chain_       │
    │  database.py        │   │  predictor.py            │   │  tracker.py           │
    │  → ChromaDB vector   │   │  → cascade delay engine  │   │  → risk + recommender │
    │    store (Module 1)  │   │    (Module 3)            │   │    (Module 4)          │
    └─────────┬─────────┘   └───────────┬───────────┘   └──────────┬──────────┘
              │                         │                          │
    ┌─────────▼─────────┐   ┌───────────▼───────────┐   ┌──────────▼──────────┐
    │   assistant.py       │   │  schedule_dashboard.html│   │ supply_chain_          │
    │   (Gemini + RAG        │   │  + .json export         │   │ dashboard.html          │
    │   terminal chat)        │   │                          │   │  + .json export         │
    └─────────────────────┘   └─────────────────────────┘   └───────────────────────┘
```

Every module reads from the **same** `project_data/` tree and joins on the same relational keys, so a delay discovered by Module 4 automatically feeds into Module 3's cascade model — this is the actual point of the platform, not a UI trick.

---

## 4. Module Deep-Dive

### 💬 Module 1 — AI Project Knowledge Assistant
`build_rag_database.py` + `assistant.py`

- Walks the full `project_data/` tree, extracts text from every PDF (with an **automatic OCR fallback** via Tesseract for scanned documents) and converts every CSV row into a natural-language sentence, so tabular data becomes just as searchable as prose.
- Chunks and embeds everything into a local, persistent **ChromaDB** collection using the `all-MiniLM-L6-v2` sentence-transformer.
- Each chunk is tagged with rich metadata (`source`, `doc_category`, `discipline`, `equipment_id`) derived straight from the folder it came from — this is what lets the assistant answer scoped questions like *"what do the HVAC drawings say"* by filtering on category, not just keyword luck.
- Query-time retrieval is **equipment-aware**: if a question names a known `Equipment_ID` (e.g. `EQ-GEN-303`), retrieval is biased toward chunks tagged with that ID first and backfilled with general semantic search, so a passing UPS mention elsewhere doesn't crowd out the asset the user actually asked about.
- Answers are generated with **Google Gemini** (`gemini-3.5-flash` via the unified `google-genai` SDK) under a strict system prompt: every factual claim must be cited to its source file, numeric conflicts between chunks (e.g. a client spec vs. a vendor's test result) must be explicitly flagged, and unsupported questions get an honest "the documents don't specify this" instead of a guess.
- Conversation continuity is handled server-side via the Interactions API (`previous_interaction_id`), so there's no manual prompt re-stitching.
- Bonus `summarize <filename>` command pulls every chunk from a specific document and produces a clean 4–6 bullet summary.

### 📅 Module 3 — AI Schedule Risk Predictor
`schedule_risk_predictor.py`

- Diffs the **baseline schedule against the active working schedule** to flag any activity whose duration or float has slipped.
- Predicts delay for every activity as **direct delay** (from linked equipment's shipment lateness) **plus inherited delay**, propagated through a declared `{activity: [predecessors]}` dependency graph using a **Kahn's-algorithm topological sort** — so a generator delay correctly cascades to every downstream activity in the correct order, and a bad/cyclic dependency map fails loudly at load time instead of silently corrupting the forecast.
- Computes `Downstream_Blast_Radius` (how many activities would be hit by further slip) and flags critical-path membership.
- Rolls direct + inherited delay, remaining float, and vendor risk tier into a **0–10 composite risk score** and a HIGH/MEDIUM/LOW band.
- Produces **prescriptive recovery actions** (crash the schedule, escalate, fast-track prep work, engage a dual-source vendor) instead of a flat alert — the specific action depends on *why* the activity is at risk (critical path breach vs. cascade hub vs. high-risk vendor).
- Exports a self-contained HTML dashboard (`saple_schedule_dashboard.html` is a real sample run against this repo's dataset) plus a raw JSON payload for any downstream consumer.

### 🚚 Module 4 — AI Supply Chain Tracker
`supply_chain_tracker.py`

- Tracks every equipment shipment against vendor, transit status, and origin hub.
- **Delay detection is float-aware, not a flat threshold**: a 2-day delay on an activity with 8 days of float is a non-event; the same 2-day delay on an activity with 0 float is a live schedule breach. Four bands: `ON_TIME`, `DELAYED - WITHIN FLOAT`, `AT_RISK - FLOAT NEARLY EXHAUSTED`, `CRITICAL_DELAY - SCHEDULE BREACH`.
- Risk-scores every shipment on a 0–10 scale combining vendor risk tier and float exhaustion.
- **Recommends alternate suppliers** from a curated per-category vendor pool, always excluding the current vendor, ranked by risk tier, with a plain-language rationale for each swap.
- Same dual HTML + JSON export pattern as Module 3.

### ⚖️ Module 2 — AI Compliance Checker *(data-ready)*
`fill_data.py` has already generated the full ground truth this module needs to run against:
- `requirements_register.csv` — 13 client requirements across UPS, Chiller, Generator, Battery, and CRAH, each with a computed `Risk_Score` (Criticality × Impact × Probability).
- `remediation_knowledge_base.csv` — known failure modes mapped to suggested corrective actions.
- `compliance_ground_truth.csv` — labelled Compliant / Non-Compliant / Partial Compliance / Missing Information verdicts with client value vs. vendor value and rationale, for every requirement.

The automated OCR/NLP comparison engine that turns this into a live checker is the next build step.

### 🧪 Module 5 — AI Commissioning QA Copilot *(data-ready)*
`fill_images.py` has generated a full labelled dataset for this module:
- Real equipment reference photos for Generator, UPS, Cooling System, Battery Storage, and CRAH units (with a local placeholder fallback if a source image is unreachable, so the dataset never has gaps).
- **Synthetic defect samples** — scorch marks, corrosion, exposed wiring, panel cracks — rendered with exact, known bounding boxes.
- `image_annotations.csv` — ground truth for every image (`Equipment_ID`, `Is_Defect`, `Defect_Class`, `BBox_X/Y/W/H`), ready to train or evaluate a YOLOv8 defect-detection model against.

---

## 5. Tech Stack

| Layer | Choice |
|---|---|
| LLM | Google Gemini (`gemini-3.5-flash`) via `google-genai` |
| Vector store & embeddings | ChromaDB (persistent, local) + `all-MiniLM-L6-v2` sentence-transformer |
| Document parsing / OCR | `pypdf`, `pdf2image`, `pytesseract` |
| Data & relational joins | `pandas` |
| Predictive engine | Custom Python (topological sort for cascade propagation, weighted risk scoring) |
| Synthetic dataset generation | `fpdf2` (PDF specs/drawings), `Pillow` (scanned docs, equipment images, synthetic defects) |
| Terminal UX | `rich` (Markdown-rendered panels for the RAG assistant) |
| Testing | `pytest`, deterministic fixtures (no dependency on the random dataset generator) |
| Frontend dashboard | Static HTML/CSS today (`export_dashboard_html()` in Modules 3 & 4) → **migrating to Streamlit** (see Roadmap) |

---

## 6. Repository Structure

```
.
├── setup_project.py                  # Creates the full project_data/ folder tree
├── fill_data.py                      # Generates PDFs, drawings, schedule, supply chain,
│                                      #   compliance KB, and sensor telemetry CSVs
├── fill_images.py                    # Generates equipment images + synthetic defect samples
│                                      #   + image_annotations.csv ground truth
├── build_rag_database.py             # Module 1: builds the ChromaDB vector store
├── assistant.py                      # Module 1: interactive cited-answer RAG chat
├── schedule_risk_predictor.py        # Module 3: cascade delay + risk engine
├── supply_chain_tracker.py           # Module 4: delivery risk + vendor recommender
├── test_schedule_risk_predictor.py   # Module 3 pytest suite (fixture-based)
├── test_supply_chain_tracker.py      # Module 4 pytest suite (fixture-based)
├── saple_schedule_dashboard.html     # Sample Module 3 dashboard output
├── .gitignore
└── project_data/                     # Generated on first run (see Quickstart) — tracked,
                                       #   not ignored, so the demo dataset ships with the repo
```

---

## 7. Quickstart

### Prerequisites
- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on your PATH (only needed if you regenerate/read scanned PDFs)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) (only needed for Module 1)

### Install
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install pandas chromadb sentence-transformers google-genai python-dotenv rich \
            pypdf pdf2image pytesseract Pillow requests fpdf2 pytest
```

### 1. Generate the dataset
```bash
python setup_project.py     # scaffolds project_data/ folder structure
python fill_data.py         # generates specs, drawings, schedule, supply chain,
                             #   compliance KB, and sensor telemetry
python fill_images.py       # generates equipment photos + synthetic defect samples
```

### 2. Run Module 1 — Knowledge Assistant
```bash
echo "GEMINI_API_KEY=your_key_here" > .env
python build_rag_database.py    # builds the ChromaDB vector store (run once)
python assistant.py             # interactive chat — ask about any document in the corpus
```

### 3. Run Module 3 — Schedule Risk Predictor
```bash
python schedule_risk_predictor.py --data-root project_data --out reports/
# → reports/schedule_dashboard.html + reports/schedule_dashboard.json
```

### 4. Run Module 4 — Supply Chain Tracker
```bash
python supply_chain_tracker.py --data-root project_data --out reports/
# → reports/supply_chain_dashboard.html + reports/supply_chain_dashboard.json
```

### 5. Run the tests
```bash
pytest test_schedule_risk_predictor.py test_supply_chain_tracker.py -v
```

---

## 8. Roadmap

- [ ] **Streamlit frontend** — replace the static HTML exports for Modules 3 & 4, and give Module 1's terminal chat a proper chat UI, all reading from the same `build_dashboard()` JSON payloads that already exist — no backend rework needed.
- [ ] **Module 2 — Compliance Checker**: automated OCR/NLP comparison engine over the already-generated `requirements_register.csv` / `compliance_ground_truth.csv`.
- [ ] **Module 5 — Commissioning QA Copilot**: YOLOv8 defect detector trained/evaluated on the already-labelled `image_annotations.csv` dataset, plus SCADA sensor stream anomaly detection over `10_Sensor_Readings/`.
- [ ] Replace the hand-declared `ACTIVITY_DEPENDENCIES` map in Module 3 with a real predecessor/successor column once the schedule source system exposes one — the cascade engine already consumes it as a pluggable `{activity: [predecessors]}` dict, so no logic changes needed.
- [ ] Wire Module 4's delay detection directly into Module 3's `Days_Delayed` input, so a supply chain event triggers a live schedule re-forecast instead of a separate report.

---

## 9. Why This Matters

Every number in this platform is traceable back to a source row or document — the RAG assistant cites its sources, the schedule predictor shows direct vs. inherited delay separately, and the risk scores are simple, auditable weighted formulas rather than an opaque black box. For an industry where a wrong call costs weeks and crores on a live construction site, **explainability was treated as a feature, not an afterthought.**
## 📂 Project Structure

```text
AI-DataCenter-EPC-Assistant/
│
├── AI_Assistant/
│   ├── assistant.py
│   └── build_rag_database.py
│
├── Compliance_Checker/
│   ├── compliance_checker.py
│   ├── compliance_report.csv
│   ├── compliance_report_complete.csv
│   └── compliance_report_evaluation.csv
│
├── Quality_Assurance/
│   ├── reports/
│   ├── sensors/
│   ├── utils/
│   └── vision/
│
├── Schedule_Risk_Prediction/
│   ├── schedule_dashboard.py
│   ├── schedule_dashboard.html
│   └── schedule_risk_prediction.py
│
├── Supply_Chain_Tracker/
│   ├── supply_chain_dashboard.py
│   ├── supply_chain_dashboard.html
│   └── supply_chain_tracker.py
│
├── project_data/
│   ├── 01_Client_Documents/
│   ├── 02_Vendor_Documents/
│   ├── 03_Engineering_Drawings/
│   ├── 04_RFIs_Meeting_Minutes/
│   ├── 05_Inspection_Reports/
│   ├── 06_Project_Schedule/
│   ├── 07_Supply_Chain_Data/
│   ├── 08_Commissioning_Reports/
│   ├── 09_Compliance_Knowledge_Base/
│   ├── 10_Equipment_Images/
│   ├── 11_Sensor_Readings/
│   └── 12_Quality_Assurance/
│
├── fill_data.py
├── fill_images.py
├── requirements.txt
├── README.md
└── .gitignore
```
