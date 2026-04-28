# Northwind Triage Agent

Take-home assessment for Avreo: build a customer intent triage agent for Northwind Home Services.

The agent reads one inbound customer message and returns a structured triage decision:

- `category`
- `priority`
- `route_to`
- `draft_reply`
- `needs_human_review`
- `reasoning`

## Approach

This is a single-agent, single-prompt implementation. The SOP, service catalogue, and tone guide are encoded in `agent/prompt.py`, and the model returns a validated `TriageOutput` Pydantic object.

I kept the design intentionally small because the task has a fixed input shape, a fixed output schema, and enough context to fit cleanly in one prompt. A multi-agent setup would add orchestration complexity without improving the core decision quality for this dataset.

## Project Structure

```text
agent/
  prompt.py        # Final system prompt
  schema.py        # Pydantic output schema
  triage.py        # OpenAI call and structured parsing
assets/            # Original assessment materials
data/              # JSON input and benchmark used by the runner
outputs/
  results.json     # Latest scored run across all 20 messages
scripts/
  run_batch.py     # Batch runner and benchmark scoring
  experimental/
    convert_assets_docling.py  # Optional PDF ingestion experiment
WRITEUP.md         # Assessment write-up and self-evaluation
```

## Setup

Requires Python 3.12.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with an OpenAI API key:

```bash
OPENAI_API_KEY=your_api_key_here
```

## Run

Run the agent across all 20 inbound messages and score against the benchmark:

```bash
python scripts/run_batch.py
```

The script writes results to:

```text
outputs/results.json
```

## Optional: Docling PDF Ingestion

The submitted agent does not require Docling. I kept it out of `requirements.txt` so the assessment remains lightweight and reproducible.

I included an optional experiment in `scripts/experimental/convert_assets_docling.py` to show how I would productionize the PDF context ingestion step. It uses Docling to convert the original PDF materials in `assets/` into both raw Docling JSON and compact LLM-friendly JSON.

Optional setup:

```bash
pip install docling
```

Run the experiment:

```bash
python scripts/experimental/convert_assets_docling.py
```

Generated outputs:

```text
assets/converted_json/docling_raw/  # Lossless Docling document JSON
assets/converted_json/llm_context/  # Smaller JSON with markdown, plain text, and sections
```

This is not wired into the main agent on purpose. For a take-home, the fixed prompt is simpler and easier to evaluate. For a production version, Docling would make the SOP/catalogue/tone-guide ingestion auditable and easier to refresh when client documents change.

## Current Score

Latest run in `outputs/results.json`:

| Field | Score | Accuracy |
|---|---:|---:|
| `category` | 20.0 / 20 | 100.0% |
| `priority` | 20.0 / 20 | 100.0% |
| `route_to` | 20.0 / 20 | 100.0% |
| `needs_human_review` | 15.0 / 20 | 75.0% |
| **Strict accuracy** | **15 / 20** | **75.0%** |

See `WRITEUP.md` for the agent design, final prompt, benchmark disagreements, failure analysis, tone assessment, and next-step recommendations.

## Packaging Note

If packaging this folder manually, exclude local-only files and directories such as `.env`, `venv/`, `__pycache__/`, and `.DS_Store`. They are listed in `.gitignore` and are not needed to review or run the submission.
