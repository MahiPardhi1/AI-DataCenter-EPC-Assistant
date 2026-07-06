# 🏢 AI-Powered Data Centre EPC Project Intelligence Platform

## 📌 Project Overview
India is in the middle of an unprecedented data centre construction boom, with national capacity projected to scale from 900 MW to over 2,700 MW by 2027. However, 67% of data centre EPC (Engineering, Procurement, and Construction) projects experience severe overruns due to information fragmentation across disconnected systems. 

This platform unifies unstructured technical specifications, structured project schedules, live supply chain logs, and field commissioning telemetry into a living intelligence layer. By automating cross-system compliance and predictive risk handling, it eliminates manual coordination effort, matching the engineering complexity of hyperscale infrastructure.

---

## 🧠 Core Modules

### 💬 Module 1: AI Project Knowledge Assistant (RAG + LLM)
* **Purpose:** Acts as a centralized knowledge conversational layer over the entire project corpus.
* **Features:** 
  * Semantic document search with granular source citations across all file types.
  * Automated summarization of dense, multi-page technical manuals and design requirements.
  * Cross-referencing of Request for Information (RFI) logs and meeting minutes.

### ⚖️ Module 2: AI Compliance Checker
* **Purpose:** Automatically verifies alignment between client-mandated specifications and vendor equipment submittals before materials arrive on-site.
* **Features:**
  * Multi-document comparison using advanced OCR and NLP parsing models[cite: 1].
  * Automated deviation and mismatch detection (e.g., flagging minor efficiency drops or voltage mismatches)[cite: 1].
  * Risk scoring metrics paired with AI-generated mitigation and corrective action plans[cite: 1].

### 📅 Module 3: AI Schedule Risk Predictor
* **Purpose:** Analyzes project master schedules to predict critical path overruns weeks in advance[cite: 1].
* **Features:**
  * Dynamic critical path calculation and task dependency mapping[cite: 1].
  * Impact modeling that scales delay forecasting based on current upstream activity constraints[cite: 1].
  * Generates actionable schedule recovery strategies instead of simple static alerts[cite: 1].

### 🚚 Module 4: AI Supply Chain Tracker
* **Purpose:** Monitors high-value long-lead equipment shipments and flags downstream procurement vulnerabilities[cite: 1].
* **Features:**
  * Real-time transit telemetry analysis and port customs hold identification[cite: 1].
  * Relational mapping linking material delays directly to schedule activity float windows[cite: 1].
  * Automated recommendation system for alternative pre-vetted suppliers[cite: 1].

### 🧪 Module 5: AI Commissioning Quality Assurance Copilot
* **Purpose:** Streamlines final testing sequences (Levels 1–5) and guarantees Tier III/IV verification standards[cite: 1].
* **Features:**
  * Multi-modal fault detection analyzing real-time SCADA sensor streams and electrical load data[cite: 1].
  * Computer Vision installation checking to identify physical panel damages or wiring defects[cite: 1].
  * Automated punch-list logging and commissioning documentation package assembly[cite: 1].

---

## 🛠️ Technology Stack
* **Document Parsing & OCR:** PyPDF2, pdfplumber, Tesseract OCR
* **Natural Language Processing & Core AI:** LangChain, LlamaIndex, OpenAI API / Google Gemini Pro
* **Vector Architecture:** ChromaDB / FAISS (Vector Space Embeddings)
* **Data Infrastructure:** Knowledge Graph Network (Neo4j / NetworkX), Pandas Dataframes
* **Computer Vision:** OpenCV, PyTorch / YOLOv8 (Image Feature Extraction)
* **Predictive Engine:** NumPy, Scikit-Learn (Time-Series Anomaly Detection & Float Modeling)
* **Frontend Dashboard:** Streamlit / Next.js

---

## 📁 Interconnected Dataset Architecture
The project workspace uses a highly unified directory structure connected through a relational primary key backbone (`Project_ID`, `Equipment_ID`, `Vendor_ID`)[cite: 1]:

```text
project_data/
├── 01_Client_Documents/          # Technical Specifications & Design Criteria[cite: 1]
├── 02_Vendor_Documents/          # Data sheets, Quotations, & Equipment Manuals[cite: 1]
├── 03_Engineering_Drawings/       # Single-Line Diagrams & HVAC Layout Layouts[cite: 1]
├── 04_RFIs_Meeting_Minutes/       # Closed & Open Site Communication Records[cite: 1]
├── 05_Inspection_Reports/         # Structural & Installation Sign-off Logs[cite: 1]
├── 06_Project_Schedule/           # Master Primavera P6 Baseline Deliverables[cite: 1]
├── 07_Supply_Chain_Data/          # Multi-tier Material tracking and Vendor Master Profiles[cite: 1]
├── 08_Commissioning_Reports/      # Level 5 Integrated Systems Testing Scripts[cite: 1]
├── 09_Equipment_Images/           # Real-World Visual Site Inspection Verification Photos[cite: 1]
└── 10_Sensor_Readings/            # Real-Time Generator & UPS Load Test Stream Data[cite: 1]
