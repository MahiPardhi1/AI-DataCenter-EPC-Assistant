import os
import sys
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
from google import genai
from google.genai import types
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# gemini-flash-latest is an auto-updating alias, but the Interactions API's
# supported-models table (as of the docs) lists explicit model IDs, so we
# pin to the current flagship Flash model directly to avoid any alias
# mismatch on a newer API surface.
MODEL_NAME = "gemini-3.5-flash"

EQUIPMENT_IDS = ["EQ-GEN-303", "EQ-UPS-101", "EQ-CHILL-202", "EQ-BATT-404", "EQ-CRAH-505"]


def validate_api_key(key):
    """
    Google is transitioning Gemini API keys from the old 'Standard' format
    (AIzaSy..., 39 chars) to the new 'Auth' key format (AQ.Ab..., ~53 chars).
    As of mid-2026, AI Studio issues Auth keys by default -- an AQ.-prefixed
    key is correct and expected, not a mistake. Standard AIzaSy keys still
    work today but are being phased out (unrestricted ones were already
    rejected starting June 19, 2026; all Standard keys stop working in
    September 2026). This check just catches keys that are missing or
    obviously malformed, not the AQ. vs AIza distinction.
    """
    if not key:
        return False, "No GEMINI_API_KEY found in your .env file."
    if not (key.startswith("AQ.") or key.startswith("AIzaSy")):
        return False, (
            f"This doesn't look like a Gemini API key (got {len(key)} chars, starting with "
            f"'{key[:4]}...'). Expected either an Auth key (starts with 'AQ.') or a legacy "
            "Standard key (starts with 'AIzaSy'). Generate one at "
            "https://aistudio.google.com/apikey and put it in your .env file as "
            "GEMINI_API_KEY=..."
        )
    return True, ""


# ---------------------------------------------------------
# CHROMADB CONNECTION
# ---------------------------------------------------------
print("Connecting to local ChromaDB database...")
chroma_client = chromadb.PersistentClient(path="project_data/chroma_db")

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

try:
    collection = chroma_client.get_collection(
        name="project_corpus",
        embedding_function=embedding_fn
    )
except Exception:
    print("ERROR: No 'project_corpus' collection found. Run build_rag_db.py first to build the database.")
    sys.exit(1)


# ---------------------------------------------------------
# RETRIEVAL
# If the question mentions a known Equipment_ID, retrieval is biased toward
# chunks tagged with that ID via a metadata filter, then backfilled with
# plain semantic search -- this stops a generic UPS mention in an unrelated
# file from crowding out the specific asset the person actually asked about.
# ---------------------------------------------------------
def retrieve_context(question, n_results=6):
    mentioned_equipment = [eq for eq in EQUIPMENT_IDS if eq in question.upper().replace(" ", "")]
    # Also catch loose mentions like "the UPS" or "generator" -> map to IDs present in corpus is
    # out of scope for a lightweight keyword pass, so we only filter on explicit IDs typed by the user.

    docs, metas = [], []

    if mentioned_equipment:
        filtered = collection.query(
            query_texts=[question],
            n_results=n_results,
            where={"equipment_id": {"$in": mentioned_equipment}} if len(mentioned_equipment) > 1
                  else {"equipment_id": mentioned_equipment[0]}
        )
        docs.extend(filtered["documents"][0])
        metas.extend(filtered["metadatas"][0])

    remaining = n_results - len(docs)
    if remaining > 0:
        general = collection.query(query_texts=[question], n_results=remaining + len(docs))
        for doc, meta in zip(general["documents"][0], general["metadatas"][0]):
            if doc not in docs:
                docs.append(doc)
                metas.append(meta)
            if len(docs) >= n_results:
                break

    return docs[:n_results], metas[:n_results]


def build_context_block(docs, metas):
    block = ""
    for idx, (doc, meta) in enumerate(zip(docs, metas)):
        block += (
            f"\n--- CHUNK {idx + 1} "
            f"(Source: {meta['source']} | Category: {meta.get('doc_category', 'N/A')} | "
            f"Equipment: {meta.get('equipment_id', 'None')}) ---\n{doc}\n"
        )
    return block


# ---------------------------------------------------------
# GEMINI CLIENT (new unified google-genai SDK)
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "You are an expert lead data center commissioning manager and AI project assistant "
    "for an EPC (Engineering, Procurement, Construction) data center project. "
    "Answer the user's question using ONLY the provided document chunks below -- never invent facts. "
    "For every factual claim or data point, cite the source file in square brackets exactly as given "
    "in the chunk metadata (e.g. [UPS_Specs.pdf]). If multiple chunks support a claim, cite all of them. "
    "If the provided context does not contain the answer, say plainly that the project documents do not "
    "specify this, rather than guessing. "
    "If you notice a numeric conflict between chunks (e.g. a client spec threshold vs a vendor's actual "
    "test result), explicitly flag the discrepancy and cite both sources -- this is often the most "
    "important thing for the user to know.\n\n"
    "FORMATTING RULES -- follow these exactly, the output is rendered as Markdown in a terminal:\n"
    "- Open with ONE short plain sentence directly answering the question. No heading, no bold, on its own line.\n"
    "- Then, if there is more than one distinct fact to report, use a bullet list with short bold labels "
    "  (e.g. '- **Equipment ID:** EQ-CRAH-505'), one fact per bullet, each ending with its citation(s).\n"
    "- Bold ONLY the label or the single key value in a bullet -- never bold a whole sentence or paragraph.\n"
    "- Do not nest bullets, do not use headings (#), and do not use tables.\n"
    "- Keep the whole answer under 150 words unless the user explicitly asks for more detail."
)

# Keep a pointer to the last interaction so the server can retain
# conversation history for us via previous_interaction_id -- no need to
# manually re-stitch prior Q&A text into every prompt.
last_interaction_id = None


def ask_knowledge_assistant(user_question):
    global last_interaction_id
    print(f"\nSearching database for: '{user_question}'...")
    docs, metas = retrieve_context(user_question)

    if not docs:
        print("No matching context found in your database.")
        return

    context_block = build_context_block(docs, metas)
    full_prompt = (
        f"RELEVANT PROJECT DATA CONTEXT:\n{context_block}\n\n"
        f"USER QUESTION: {user_question}\n\nYOUR CITED ANSWER:"
    )

    print("Thinking (Gemini processing)...")
    try:
        kwargs = dict(
            model=MODEL_NAME,
            input=full_prompt,
            system_instruction=SYSTEM_INSTRUCTION,
        )
        if last_interaction_id:
            kwargs["previous_interaction_id"] = last_interaction_id

        interaction = client.interactions.create(**kwargs)
        answer_text = interaction.output_text
        last_interaction_id = interaction.id

        console.print()
        console.print(Panel(
            Markdown(answer_text),
            title="Assistant Response",
            border_style="cyan",
            padding=(1, 2),
        ))

        unique_sources = sorted(set(meta["source"] for meta in metas))
        sources_md = "\n".join(f"- {source}" for source in unique_sources)
        console.print(Panel(
            Markdown(sources_md),
            title="Sources Retrieved",
            border_style="dim",
            padding=(0, 2),
        ))

    except Exception as e:
        console.print(f"[bold red]Gemini API Error:[/bold red] {e}")


def summarize_source(filename_fragment):
    """Bonus feature: pulls every chunk belonging to a specific source file
    and asks Gemini for a clean summary -- directly serves the 'document
    summarization' requirement of Module 1, not just Q&A."""
    all_data = collection.get()
    matched_docs = [
        doc for doc, meta in zip(all_data["documents"], all_data["metadatas"])
        if filename_fragment.lower() in meta["source"].lower()
    ]

    if not matched_docs:
        print(f"No document matching '{filename_fragment}' found in the database.")
        return

    matched_docs.sort()  # rough chunk-order approximation
    combined_text = "\n".join(matched_docs)
    prompt = (
        "Summarize the following project document in 4-6 concise bullet points, "
        "highlighting any specific numbers, thresholds, dates, or equipment IDs mentioned:\n\n"
        f"{combined_text}\n\nSUMMARY:"
    )

    print(f"\nSummarizing {len(matched_docs)} chunk(s) from files matching '{filename_fragment}'...")
    try:
        interaction = client.interactions.create(model=MODEL_NAME, input=prompt, store=False)
        console.print()
        console.print(Panel(
            Markdown(interaction.output_text),
            title=f"Summary: {filename_fragment}",
            border_style="green",
            padding=(1, 2),
        ))
    except Exception as e:
        console.print(f"[bold red]Gemini API Error:[/bold red] {e}")


# ---------------------------------------------------------
# INTERACTIVE TERMINAL LOOP
# ---------------------------------------------------------
if __name__ == "__main__":
    valid, message = validate_api_key(GEMINI_API_KEY)
    if not valid:
        print(f"ERROR: {message}")
        sys.exit(1)

    print("\nAI Project Knowledge Assistant is online!")
    print("Commands:")
    print("  Ask any project question directly")
    print("  'summarize <filename fragment>' -> summarizes a specific document")
    print("  'exit' or 'quit' -> closes the assistant\n")

    while True:
        query = input("Ask a project question: ").strip()
        if query.lower() in ("exit", "quit"):
            print("Closing assistant. Good luck with the demo!")
            break
        if not query:
            continue
        if query.lower().startswith("summarize "):
            summarize_source(query[len("summarize "):].strip())
        else:
            ask_knowledge_assistant(query)