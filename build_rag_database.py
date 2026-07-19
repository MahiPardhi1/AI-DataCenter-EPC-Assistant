import os
import pandas as pd
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract
import chromadb
from chromadb.utils import embedding_functions

# ---------------------------------------------------------
# WINDOWS PREREQUISITE PATHS
# Update these to match your local installation locations
# ---------------------------------------------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\bin"

EQUIPMENT_IDS = ["EQ-GEN-303", "EQ-UPS-101", "EQ-CHILL-202", "EQ-BATT-404", "EQ-CRAH-505"]

# ---------------------------------------------------------
# LOCAL CHROMADB SETUP
# ---------------------------------------------------------
print("Initializing local ChromaDB filing cabinet...")
chroma_client = chromadb.PersistentClient(path="project_data/chroma_db")

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

collection = chroma_client.get_or_create_collection(
    name="project_corpus",
    embedding_function=embedding_fn
)


# ---------------------------------------------------------
# FOLDER -> METADATA MAPPING
# Turns your directory structure into real, queryable metadata instead of
# just a filename string. This is what lets the assistant later answer
# things like "what do our vendor quotations say" or "summarize the HVAC
# drawings" by filtering on doc_category / discipline, not just keyword
# matching inside chunk text.
# ---------------------------------------------------------
def classify_path(file_path):
    parts = file_path.replace("\\", "/").split("/")
    doc_category = "General"
    discipline = "General"

    if "01_Client_Documents" in parts:
        doc_category = "Client_" + (parts[parts.index("01_Client_Documents") + 1] if len(parts) > parts.index("01_Client_Documents") + 1 else "Document")
    elif "02_Vendor_Documents" in parts:
        doc_category = "Vendor_" + (parts[parts.index("02_Vendor_Documents") + 1] if len(parts) > parts.index("02_Vendor_Documents") + 1 else "Document")
    elif "03_Engineering_Drawings" in parts:
        doc_category = "Drawing"
        discipline = parts[parts.index("03_Engineering_Drawings") + 1] if len(parts) > parts.index("03_Engineering_Drawings") + 1 else "General"
    elif "04_RFIs_Meeting_Minutes" in parts:
        doc_category = "RFI_MeetingMinutes"
    elif "05_Inspection_Reports" in parts:
        doc_category = "Inspection_Report"
    elif "06_Project_Schedule" in parts:
        doc_category = "Schedule"
    elif "07_Supply_Chain_Data" in parts:
        doc_category = "Supply_Chain"
    elif "08_Commissioning_Reports" in parts:
        doc_category = "Commissioning_Report"
    elif "10_Sensor_Readings" in parts:
        doc_category = "Sensor_Telemetry"

    return doc_category, discipline


# ---------------------------------------------------------
# SMART FILE PARSERS
# ---------------------------------------------------------
def extract_text_from_pdf(file_path):
    """Extracts text normally; falls back to OCR if the PDF is scanned."""
    text = ""
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if len(text.strip()) < 100:
            print(f"   -> Scanned PDF detected. Running OCR on: {os.path.basename(file_path)}")
            text = ""
            images = convert_from_path(file_path, poppler_path=POPPLER_PATH)
            for i, image in enumerate(images):
                ocr_page = pytesseract.image_to_string(image)
                text += f"\n[Page {i + 1} OCR Start]\n" + ocr_page
    except Exception as e:
        print(f"   ERROR reading PDF {file_path}: {e}")
    return text


def convert_csv_to_sentences(file_path):
    """Converts spreadsheet rows into descriptive sentences for semantic search."""
    text = ""
    try:
        df = pd.read_csv(file_path)
        filename = os.path.basename(file_path)
        for idx, row in df.iterrows():
            row_info = f"In file {filename}, record line {idx + 1}: "
            row_details = ", ".join([f"{col} is '{val}'" for col, val in row.items() if pd.notna(val)])
            text += row_info + row_details + ".\n"
    except Exception as e:
        print(f"   ERROR parsing CSV {file_path}: {e}")
    return text


# ---------------------------------------------------------
# CHUNKING ENGINE
# ---------------------------------------------------------
def slice_into_chunks(text, chunk_size=600, overlap=100):
    """Slices text into overlapping word-based chunks."""
    words = text.split()
    if not words:
        return []
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i: i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break
        i += (chunk_size - overlap)
    return chunks


def find_equipment_ids(text):
    """Returns ALL equipment IDs mentioned in a chunk, not just the first one --
    a chunk discussing a clash between two pieces of equipment should be
    retrievable under either ID."""
    found = [eq for eq in EQUIPMENT_IDS if eq in text]
    return ",".join(found) if found else "None"


# ---------------------------------------------------------
# MAIN PROCESSING LOOP
# ---------------------------------------------------------
print("\nScanning project folders for data...")
supported_extensions = (".pdf", ".csv")
global_id_counter = 0
files_processed = 0
files_skipped = 0

BATCH_SIZE = 64
batch_docs, batch_metas, batch_ids = [], [], []


def flush_batch():
    global batch_docs, batch_metas, batch_ids
    if batch_docs:
        collection.add(documents=batch_docs, metadatas=batch_metas, ids=batch_ids)
        batch_docs, batch_metas, batch_ids = [], [], []


for root, dirs, files in os.walk("project_data"):
    if "chroma_db" in root:
        continue
    for file in files:
        if not file.endswith(supported_extensions):
            continue

        file_path = os.path.join(root, file)
        print(f"Processing: {file_path}")

        if file.endswith(".pdf"):
            raw_text = extract_text_from_pdf(file_path)
        else:
            raw_text = convert_csv_to_sentences(file_path)

        if not raw_text.strip():
            print(f"   -> No extractable text, skipping: {file}")
            files_skipped += 1
            continue

        doc_category, discipline = classify_path(file_path)
        text_chunks = slice_into_chunks(raw_text)

        for index, chunk in enumerate(text_chunks):
            batch_docs.append(chunk)
            batch_metas.append({
                "source": os.path.basename(file_path),
                "relative_path": file_path.replace("\\", "/"),
                "chunk_index": index,
                "equipment_id": find_equipment_ids(chunk),
                "doc_category": doc_category,
                "discipline": discipline,
            })
            batch_ids.append(f"id_{global_id_counter}")
            global_id_counter += 1

            if len(batch_docs) >= BATCH_SIZE:
                flush_batch()

        files_processed += 1

flush_batch()

print(f"\nDone. {files_processed} files embedded, {files_skipped} skipped (no extractable text).")
print(f"Total chunks loaded into ChromaDB: {global_id_counter}")