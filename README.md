# NMC Harmonizer (National Material Code Harmonizer)

> **AI-Powered Cross-CPSE Material Harmonization & Inventory Consolidation Platform**  
> *Built for the Smart India Hackathon (SIH)*

---

## 📌 Executive Overview

In major Indian Central Public Sector Enterprises (CPSEs)—such as **IOCL, BPCL, HPCL, ONGC, and GAIL**—identical or functionally equivalent physical materials (e.g., fasteners, valves, pipes, structural steel) are often cataloged under disparate item codes, naming conventions, abbreviations, and unit descriptions. This fragmentation leads to:
- **Redundant procurement** and duplicate purchasing tenders.
- **Inflated inventory holding costs** due to lack of visibility across sister CPSEs.
- **Slow emergency maintenance**, where one plant faces stockouts while another nearby warehouse has surplus stock.

**NMC Harmonizer** is a production-grade prototype that automatically identifies identical and near-duplicate material items across CPSE catalogs, explains the AI reasoning transparently, and unifies them under a standardized **Common Material Code (CMC)** (`NMC-<CAT>-<SEQ>`) while **strictly preserving legacy CPSE codes** for 100% ERP traceability and audit compliance.

---

## 🌟 Key Features

1. **Deterministic Normalization & Rule-Based Attribute Extraction**:
   - Expands abbreviations (`SS`, `STL` &rarr; `Stainless Steel`, `CS` &rarr; `Carbon Steel`, `HEX` &rarr; `Hexagonal`, `BRG` &rarr; `Bearing`, `VLV` &rarr; `Valve`).
   - Unifies units and dimension syntax (`16mm × 50mm`, `M16-50`, `M16 X 50` &rarr; standardized metrics).
   - Extracts structured dimensions (thread, diameter, length, schedule, pressure rating, grade) reliably without depending on slow, expensive, or hallucination-prone cloud LLMs.

2. **Dense Semantic Embeddings + FAISS Vector Retrieval**:
   - Encodes descriptions using a local, CPU-optimized `all-MiniLM-L6-v2` model (`sentence-transformers`).
   - Scalable top-$K$ candidate search via FAISS (`IndexFlatIP` over L2-normalized vectors) avoids the $O(N^2)$ all-pairs bottleneck, searching thousands of items in milliseconds.

3. **Specification-Aware Multi-Component Scorer**:
   - Combines semantic similarity (40%), material match (20%), dimension match (15%), category match (10%), specification match (10%), and UOM match (5%).
   - **Hard Dimensional Conflict Prevention**: Any dimensional discrepancy (e.g., 50mm length vs. 80mm length) applies strict mathematical penalties and triggers a `Specification Conflict` flag, preventing false merges even when semantic descriptions look identical.

4. **N-Way Multi-CPSE Grouping & Connected Components**:
   - Automatically clusters mutually-matching items from 3 or more CPSEs into a single candidate group.
   - Computes cluster-wide consistency and confidence scores.

5. **Configurable Confidence Thresholds & Auto-Approval**:
   - Fully adjustable thresholds via UI settings or `weights.yaml`:
     - **Auto-Approval Threshold**: Matches exceeding confidence (default: 95%) can be auto-approved to accelerate processing.
     - **Review Threshold**: Pairs between 75% and 95% flagged for human review.
     - **Rejection Threshold**: Pairs below 75% marked as non-equivalent.

6. **Explainable AI (XAI) Transparency**:
   - Detailed plain-language breakdown showing `✓ Same` or `✗ Differs` for every attribute (Material, Thread, Diameter, Length, Rating, Specification, Unit of Measure).

7. **Custom Data Upload & Comprehensive Data Export**:
   - **Data Ingestion**: Upload custom multi-sheet Excel workbooks (`.xlsx`) or single CSV files directly from the UI with schema validation and preview.
   - **Data Export**: Export unified master catalogs, CPSE mapping tables, ground truth validation reports, and inventory summaries to Excel (`.xlsx`) or CSV at any time.

8. **Human-in-the-Loop Governance**:
   - Role-based permissions (`Admin`, `Procurement Officer`, `Auditor / Viewer`).
   - Officers can **Approve**, **Reject** (with mandatory reason log), or **Modify** proposed codes before finalizing.

9. **Enterprise Inventory & Financial Impact Analytics**:
   - Aggregates available physical stock across all CPSE warehouses.
   - Highlights duplicate inventory holdings and calculates estimated working capital release and avoidable procurement expenditure (*Prototype Estimates*).

10. **Offline Ground Truth Accuracy Evaluation**:
    - Built-in benchmark evaluating AI predictions against a verified `Ground_Truth` matrix (calculating Precision, Recall, F1-Score, and Conflict Detection Rate).

11. **Immutable Provenance Audit Trail**:
    - Full chronological record of all AI inferences, officer approvals/rejections, configuration edits, and mapping updates.

---

## 🏗️ End-to-End AI Architecture

```text
Raw CPSE Material Records (IOCL, BPCL, HPCL, ONGC, GAIL)
                         │
                         ▼
1. Deterministic Normalization (abbreviations, casing, units)
                         │
                         ▼
2. Attribute Extraction (material, dimensions, thread, pressure rating, UOM)
                         │
                         ▼
3. Hierarchical Classification (category / subcategory)
                         │
                         ▼
4. Dense Vector Embeddings (sentence-transformers: all-MiniLM-L6-v2)
                         │
                         ▼
5. Scalable Candidate Search (FAISS IndexFlatIP — sub-millisecond top-K)
                         │
                         ▼
6. Specification-Aware Multi-Component Scorer
   (Semantic + Material + Dimensions + Spec + Category + UOM)
                         │
                         ├── Dimension mismatch detected? ──► [Specification Conflict Flag]
                         │                                     (Downgraded: Cannot auto-merge)
                         ▼
7. N-Way Connected Component Grouping (Clusters mutually-matching CPSE items)
                         │
                         ▼
8. Threshold Decision Engine
   ├─ Confidence ≥ 95% ────► Auto-Approved (or Queued for Fast-Track Review)
   ├─ 75% ≤ Conf < 95% ────► Flagged for Human Review
   └─ Conf < 75% ──────────► Discarded / No Match
                         │
                         ▼
9. Human-in-the-Loop Review (Approve / Modify / Reject with Reason)
                         │
                         ▼
10. Common Material Code Generation (NMC-<CAT>-<SEQ>)
    + Immutable CPSE Mapping + Provenance Audit Trail
                         │
                         ▼
11. Downstream Services:
    ├─ Cross-CPSE Warehouse Stock Aggregation
    ├─ Duplicate Procurement & Working Capital Release Analytics
    ├─ Natural Language Semantic Material Search
    └─ Excel / CSV Catalog Export
```

---

## 💻 Tech Stack

- **Application Framework**: [Streamlit](https://streamlit.io/) (clean, interactive, locked-light enterprise portal)
- **Programming Language**: Python 3.10+
- **Machine Learning & NLP**:
  - `sentence-transformers` (`all-MiniLM-L6-v2`)
  - `faiss-cpu` (Facebook AI Similarity Search)
  - `scikit-learn`, `numpy`
- **Data & Storage**:
  - `SQLAlchemy` ORM + SQLite (`nmc_harmonizer.db`)
  - `pandas`, `openpyxl`
- **Visualization & UI**:
  - `altair`, `plotly`
- **Configuration & Testing**:
  - `PyYAML`, `pytest`

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13 installed on your system.
- **100% Free & Open Source**: No OpenAI, Claude, Azure, or cloud API keys needed. Runs completely offline on local CPU.

### 2. Clone the Repository
```bash
git clone https://github.com/ArshChh3tr1/nmc.git
cd nmc-harmonizer
```

### 3. Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

> [!NOTE]
> On the very first run, `sentence-transformers` will automatically download and locally cache the small `all-MiniLM-L6-v2` model (~80 MB). Subsequent runs execute **100% locally and offline**.

---

## 🏃 Running the Application

### Option A: One-Click Launcher (Windows)
Double-click the `run_app.bat` script in the root directory, or run from terminal:
```cmd
run_app.bat
```

### Option B: Streamlit Command
From the project root inside your activated virtual environment:
```bash
python -m streamlit run app/NMC.py
```
*(Alternative entry point: `python -m streamlit run app/main.py`)*

The application dashboard will automatically open in your default browser at:
```
http://localhost:8501
```

---

## 📊 Live SIH Presentation & Demonstration Guide

### Where Demo Data is Stored
The multi-sheet sample dataset containing CPSE records, taxonomy, warehouses, and ground truth is located at:
```
app/data/demo_dataset.xlsx
```

### Recommended Presentation Walkthrough for Evaluators:

1. **Dashboard Overview**:
   - Open `http://localhost:8501` to view high-level CPSE catalog metrics, inventory status, and recent activity logs.
   - The app starts in a clean state to highlight that results are dynamically computed by the AI rather than pre-baked.

2. **Load Data / Custom Upload**:
   - In the sidebar / action bar, click **📥 Load Demo Dataset** (or navigate to **Materials** &rarr; **Upload Custom Data** to upload your own `.xlsx` / `.csv` file).
   - Preview raw CPSE items across IOCL, BPCL, HPCL, ONGC, and GAIL.

3. **Execute AI Harmonization**:
   - Click **🚀 Run AI Harmonization**.
   - Watch the live progress bar as items undergo normalization, dimension extraction, FAISS vector indexing, pairwise scoring, and N-way grouping.

4. **Review AI Harmonization**:
   - Navigate to the **AI Harmonization** tab.
   - **High-Confidence Duplicate Match**:
     - View the matched cluster (e.g., IOCL `IO-FST-48392` *“HEX BOLT SS M16 X 50”* vs. HPCL `HP-FST-18372` *“STAINLESS STEEL HEX BOLT M16-50”*).
     - Expand **🔍 View AI Match Explanation** to see the 99%+ confidence score and attribute-by-attribute checkmarks.
     - Notice items meeting the auto-approval threshold (>95%) can be approved instantly.
   - **Specification Conflict Trap**:
     - Inspect the deliberate edge-case trap: ONGC `ON-FST-77182` (*“HEX BOLT SS M16 X 80”*).
     - Point out how the AI detected the 50mm vs. 80mm length discrepancy, flagged a **Specification Conflict**, and prevented an erroneous merge despite high textual similarity.

5. **Approve & Generate Common Material Code**:
   - Click **✅ Approve Match** &rarr; Assigns standardized code `NMC-FST-0001` and links legacy records while keeping original CPSE codes intact.

6. **Materials Explorer & Semantic Search**:
   - Go to **Materials Explorer**.
   - Test natural-language query: search for `"SS bolt 16 50"` &rarr; retrieved `NMC-FST-0001` with linked CPSE stock.
   - Toggle **Material Relationship Hierarchy** to visualize the interactive branch diagram:
     ```text
                  NMC-FST-0001 (SS Hex Bolt M16x50)
              ┌──────────────────┼──────────────────┐
              ↓                  ↓                  ↓
             IOCL               BPCL               HPCL
         IO-FST-48392       BP-FST-99213       HP-FST-18372
     ```

7. **Cross-CPSE Inventory & Financial Impact**:
   - Visit **Inventory**: View cross-CPSE warehouse availability and duplicate inventory volumes.
   - Check **Procurement Analytics**: View estimated working capital unlock and avoidable purchase order spend.

8. **Export Harmonized Master**:
   - Download the unified material catalog and mapping tables as Excel (`.xlsx`) or CSV for immediate ERP integration.

9. **AI Accuracy Benchmark & Audit Trail**:
   - **Reports**: Show the offline evaluation report comparing model inferences against `Ground_Truth` (demonstrating 100% precision on conflicts).
   - **Audit Trail**: Review immutable log entries with timestamps, user actions, and justifications.

---

## 🧪 Automated Testing

Run the automated test suite with pytest from the project root:

```bash
# Using activated virtual environment
pytest app/tests -v

# Or directly via venv python
.venv\Scripts\python -m pytest app/tests -v
```

### Test Coverage Highlights:
- `test_normalization.py`: Validates abbreviation expansion, unit normalization, and casing across diverse CPSE phrasing.
- `test_attribute_extraction.py`: Tests structured extraction of thread, diameter, length, and specs.
- `test_scoring.py`: Verifies multi-attribute weighted scoring formulas and dynamic YAML config overrides.
- `test_match_classification.py`: Confirms dimension conflicts (e.g. M16×50 vs M16×80) trigger specification conflict flags and prevent duplicate merges.
- `test_end_to_end_pipeline.py`: Tests the full pipeline from raw ingestion to FAISS retrieval, scoring, and code generation.
- `test_grouping_and_auto_approval.py`: Validates N-way multi-CPSE clustering and automatic approval above threshold.
- `test_upload_and_export.py`: Validates custom Excel/CSV file upload parsing, schema validation, and catalog export generation.

---

## 📂 Repository Structure

```text
nmc-harmonizer/
├── app/
│   ├── NMC.py                    # Root entry point launcher
│   ├── main.py                   # Multi-page Streamlit portal orchestrator
│   ├── config.py                 # Configuration loader (weights, taxonomy, normalizers)
│   ├── config/
│   │   ├── weights.yaml          # Configurable scoring weights & confidence thresholds
│   │   ├── taxonomy.yaml         # Industrial categorization & keyword hierarchy
│   │   └── normalization_dict.yaml # Standard abbreviation & unit dictionary
│   ├── database/
│   │   ├── db.py                 # SQLAlchemy engine, session maker, init_db
│   │   ├── models.py             # 10 ORM models enforcing CPSE immutability
│   │   └── seed.py               # Database seeder (users, taxonomy, demo catalog)
│   ├── services/
│   │   ├── normalization/        # Text normalizer & regex attribute extractor
│   │   ├── classification/       # Keyword-driven taxonomy classifier
│   │   ├── embeddings/           # Sentence-transformers embedder & FAISS index
│   │   ├── matching/             # Candidate search, weighted scorer, explainer, N-way grouping
│   │   ├── harmonization/        # Code generator (NMC-<CAT>-<SEQ>) & review service
│   │   ├── analytics/            # Inventory aggregation & financial impact calculations
│   │   ├── audit/                # Provenance audit logger
│   │   ├── ingestion/            # Excel/CSV loader & demo dataset importer
│   │   └── export/               # Catalog, mapping, and report exporter (.xlsx/.csv)
│   ├── ui/                       # 11 Modular Streamlit pages
│   │   ├── overview.py           # Executive dashboard & KPIs
│   │   ├── harmonization.py      # AI matching, explanations & review queue
│   │   ├── materials.py          # Material master, semantic search & custom upload
│   │   ├── inventory.py          # Cross-CPSE stock consolidation
│   │   ├── procurement.py        # Duplicate order detection & savings insights
│   │   ├── alerts.py             # Stockout & surplus rebalance alerts
│   │   ├── reports.py            # AI accuracy benchmark vs. Ground Truth
│   │   ├── audit_trail.py        # Chronological governance logs
│   │   ├── warehouses.py         # CPSE warehouse location registry
│   │   ├── suppliers.py          # Vendor & OEM registry
│   │   ├── settings.py           # Weight configuration & auto-approval sliders
│   │   └── auth.py               # Persona switcher (Admin, Officer, Viewer)
│   ├── utils/                    # Formatting, text cleaning & input validators
│   ├── tests/                    # 7 Comprehensive pytest suites
│   └── data/
│       ├── demo_dataset.xlsx     # 5-sheet demo workbook
│       └── nmc_harmonizer.db     # SQLite runtime database
├── run_app.bat                   # One-click Windows startup script
├── pytest.ini                    # Pytest configuration
├── requirements.txt              # Production dependencies
└── README.md                     # Project documentation
```

---

## 💡 How the AI Works (Non-Technical Explanation)

### 1. The Scaling Challenge
In large industrial enterprises with tens of thousands of material codes across multiple CPSEs, comparing every material against every other material would require billions of comparisons ($O(N^2)$), causing conventional systems to freeze or require expensive supercomputers.

### 2. The Two-Stage Hybrid Solution
- **Stage 1: Fast Candidate Retrieval (FAISS)**  
  Every material description is converted into a high-dimensional mathematical fingerprint (vector embedding) using a compact local language model. Using **FAISS** (Facebook AI Similarity Search), the system instantly filters down thousands of records to the top-20 most likely candidates in milliseconds.
- **Stage 2: Deterministic Engineering Logic**  
  The system never relies on machine learning alone to make procurement decisions. Candidates from Stage 1 pass through strict engineering rule checks:
  - Are dimensions identical? (e.g., $16\text{ mm} = 16\text{ mm}$, but $50\text{ mm} \neq 80\text{ mm}$)
  - Are material grades equivalent? (e.g., Stainless Steel 316 vs. Carbon Steel)
  - Are pressure and temperature ratings compatible?

### 3. Absolute Traceability Guarantee
Existing CPSE material numbers, legacy ERP IDs, and historical procurement records are **never overwritten or deleted**. Harmonization creates an overarching common reference index, ensuring zero disruption to existing SAP/Oracle ERP operations.

---

## 📄 License & Attribution

Developed for the **Smart India Hackathon (SIH)**.  
Free and open-source for public sector enterprise evaluation and deployment.
