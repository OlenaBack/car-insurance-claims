# Assignment 1 – Plan: Structured Extraction Service (Car Insurance Claims)

Deadlines: checkpoint (steps 1–2) **24 Oct**, final (steps 1–4) **27 Oct 23:59**.

## 1. Decisions

| Topic | Decision | Rationale |
| --- | --- | --- |
| Domain | Car insurance accident claims | Course project topic (Insurance). |
| Hosted model | Gemini via API (free tier) | Free allowance; supports structured output. |
| Local model | Ollama `qwen2.5:3b` (fallback `llama3.2:3b`, upgrade `qwen2.5:7b` if RAM allows) | Strong JSON adherence, runs on a laptop. |
| Language / runtime | Python 3.11+ (venv has 3.13), `python main.py` | Spec: one-command run. |
| Schema | Pydantic v2 | Validation + JSON Schema export for structured output. |
| Secrets | `.env` (ignored), `.env.example` committed | Spec requirement. |
| Out of scope | UI, deployment, fine-tuning | Explicitly not required. |

## 2. Data hypothesis (H1)

A hybrid dataset gives a more honest benchmark than either source alone.

- **Cleanlab/insurance-claims-extraction** (30 rows): naturally messy emails, nested ground truth, some null fields. Auto claims (~1/3) form the core golden set; license unclear, so cite and document.
- **itamarcohen/insurance_car_Qfiles (QCAR)** (~10k rows, MIT, synthetic): car-specific columns (`accident_type`, `severity`, `fault`, `weather_conditions`, ...) and a clean `accident_description`. Needs noise injection (typos, truncation, dropped details, mixed-language phrases).
- **Test in report:** compare per-field accuracy/validity on the Cleanlab subset vs the noised-QCAR subset, and check whether the model ranking is the same on both.
- **Risks:** different label schemas (needs mapping), unclear Cleanlab license, noise is our own transformation (document seed and method). Cleanlab Auto claims lack labels for weather, severity and fault, so Cleanlab golden items must be hand-labelled against our schema.

**Data evidence (QCAR, 400 sampled rows):** the free-text `accident_description` mentions the label values at these rates: city 69%, car make 68%, year 61%, colour 52%, weather 52%, severity wording 34%; plate number 0%, coverage type 0%, exact damage amount 9%, injuries 20%, police 14%. The schema is therefore built only from fields that are both labelled and recoverable from the text.

## 3. Schema (Pydantic v2) – must satisfy the assignment contract

Contract: **≥ 6 fields, ≥ 1 enum, ≥ 1 nested object or list** (Step 1, 2 pts).

| Field | Type (QCAR source column) | Contract element |
| --- | --- | --- |
| `location_city` | str \| null (`location_city`) | field 1 |
| `accident_type` | **enum**: rear-end collision, reversing collision, parking lot scrape, head-on at junction, lane-change sideswipe, side collision at intersection, chain collision, pedestrian-area incident (`accident_type`) | field 2, **enum** |
| `severity` | **enum**: minor, moderate, severe (`severity`) | field 3, **enum** |
| `fault` | **enum**: reporter_at_fault, other_party_at_fault, shared_fault, undetermined (`fault`) | field 4, **enum** |
| `weather_conditions` | **enum**: clear, night-clear, cloudy, foggy, wet road, rainy (`weather_conditions`) | field 5, **enum** |
| `time_of_day` | **enum**: morning, afternoon, evening, night, null (derived from the hour of `accident_timestamp`) | field 6, **enum** |
| `vehicle` | **nested object**: `make` (str \| null), `color` (str \| null), `year` (int \| null) (`car_make`, `car_color`, `manufacture_year`) | **nested object** |
| `other_vehicles` | **list of nested objects**: `make` (str \| null), `color` (str \| null); empty list if none are mentioned. No QCAR column, so labels are **hand-written** for the golden set (draft labels are empty) | **list** |

Total: 8 top-level fields (minimum 6), 5 enums, 1 nested object and 1 list of objects. Decision (2026-10-14): `other_vehicles` is included and hand-labelled.

Excluded because the data does not support them: `claim_id` (a new claim has none), `policy_number`, `plate_number` and `coverage_type` (0% in text), `estimated_damage` (9% in text), `injuries_reported`, `police_report_number` (no labels in QCAR), `driver_name` and `driver_city` (personal data), `insurance_company` (known by the insurer).

Rules: missing information is `null`, never invented. Labels come from the QCAR columns; Cleanlab items are hand-labelled to this schema.

## 4. Data pipeline

1. Download both sources into `data/raw/` (script, reproducible, pinned).
2. Map Cleanlab Auto claims and QCAR columns to our schema (`data/mapping`).
3. Build `data/texts.jsonl` (≥30 texts: ~10 Cleanlab + ~20 noised QCAR, mixed lengths/languages).
4. Hand-verify 10 as `data/golden.jsonl` (mix of both sources, include missing fields).
5. Keep no real personal data (all sources synthetic).

## 5. Implementation steps (mapped to rubric)

**Step 1 – Schema + baseline (6 pts)**
- `src/extraction/schema.py`; `prompts/extract_v1.md`.
- Gemini client with structured output, timeout, retry with backoff.
- Process all texts; write `results/<run>/...jsonl`.

**Step 2 – Second model + measurements (8 pts)** *(checkpoint 24 Oct)*
- Shared `LLMClient` interface (Gemini, Ollama).
- `config.yaml`: model, `temperature`, `top_p`; ≥2 configs (e.g. 0.0 vs 0.7).
- Metrics: per-field accuracy on golden, % valid, latency p50/p95, cost per 1,000 docs (tokens × price; local = 0 plus note).

**Step 3 – Versioning + validation (8 pts)**
- `prompts/` with `v1`, `v2` files and `CHANGELOG.md` (what/why).
- Validate each response; one repair attempt; else `status=failed`.
- Log model, prompt version, sampling params per result.

**Step 4 – Report (6 pts)**
- `REPORT.md`: model × prompt × config table with all metrics, 3–5 error analyses, production choice + conditions to revisit, H1 conclusion.

**Repo quality (2 pts):** README with setup, `.env.example`, `python main.py`, no keys in code.

## 6. Prerequisites checklist

- [ ] Gemini API key (in `.env`)
- [ ] Ollama installed; `ollama pull qwen2.5:3b`
- [ ] Check laptop RAM (decides 3b vs 7b)
- [ ] `pip install -e ".[dev]"` (add `google-genai`, `pydantic`, `python-dotenv`, `pyyaml`, `datasets`)

## 7. Timeline

| Date | Goal |
| --- | --- |
| 14–16 Oct | Prerequisites, schema, data pipeline, golden set |
| 17–20 Oct | Step 1 baseline on Gemini |
| 21–24 Oct | Step 2: Ollama + metrics → post checkpoint |
| 25–26 Oct | Step 3 (prompt v2, validation, logging); Q&A feedback |
| 26–27 Oct | Step 4 report, README polish, submit |

## 8. Decisions and open questions

Decided (2026-10-14):
- Schema confirmed with `other_vehicles` (hand-labelled list); see section 3.
- Gemini: a Flash-class model on the free tier; the model ID goes in `config/config.yaml` once seen in AI Studio. Cost estimate about $1.10 per 1,000 documents at about $0.75 / $3.75 per 1M input / output tokens (Flash-class list price, to be re-checked when computing the cost metric).

Open:
- Exact noise recipe and language mix (the current recipe is implemented in the data batches; needs sign-off).
- Hand-label `other_vehicles` for the 10 golden documents (draft labels are empty).
