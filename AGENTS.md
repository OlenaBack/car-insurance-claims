# AGENTS.md

Guidance for AI agents working in this repository.

## Project
**car-insurance-claims**: an AI system for car-insurance accident claims, built in four stages (extraction, RAG, agent, service). Code is grouped by function, not by assignment; assignment documents live in `docs/<assignment>/`.

Current stage: **Assignment 1 - Structured Extraction Service**. It turns messy claim texts into schema-valid JSON, compares a hosted model (Gemini) with a local model (Ollama, `qwen2.5:3b`), and justifies a production choice with measurements. Requirements: `docs/assignment-1/AI-Engineering-Course-Context-and-Assignment-1-English.md`. Decisions, schema and timeline: `docs/assignment-1/PLAN.md`.

Deadlines: checkpoint (steps 1-2) **24 Oct**, final (steps 1-4) **27 Oct 23:59**.

## Status
- Done: project skeleton, plan, data pipeline, 3 draft data batches (`data/`, `data/batch2/`, `data/batch3/`).
- Not started: schema, LLM clients, metrics, prompts, report. Labels are drafts; the 10-doc **golden set is hand-verified by the human later**.
- Python language server: `python-lsp-server` in `.venv` (dev extra), configured in `.github/lsp.json`; run `/lsp reload` after changes. Ollama and the runtime dependencies are not installed yet.

## Layout
| Path | Purpose |
| --- | --- |
| `main.py` | entry point, `python main.py` (stub) |
| `config/config.yaml` | models, sampling configs, prompt versions, timeout, retries, paths |
| `.env.example` | required keys (`GEMINI_API_KEY`, `OLLAMA_HOST`); real keys go in `.env` |
| `src/common/` | shared: `config.py`, `run_log.py` |
| `src/llm/` | shared model clients: `base.py` (interface), `gemini.py`, `ollama.py` |
| `src/extraction/` | stage 1: `schema.py`, `prompts.py`, `pipeline.py`, `validation.py`, `metrics.py` (docstring-only stubs) |
| later stages | add sibling packages by function, e.g. `retrieval/` (RAG), `agent/`, `service/` |
| `prompts/` | `extract_v1.md` (placeholder), `CHANGELOG.md`; add `extract_vN.md` per version |
| `data/` | texts and drafts; `data/raw/` holds downloads; `batch2/`, `batch3/` are extra batches; `golden.jsonl` comes later |
| `results/` | model outputs (`.gitkeep`) |
| `tests/extraction/` | pytest stubs: `test_schema.py`, `test_validation.py`, `test_metrics.py` (mirror the package layout) |
| `docs/assignment-1/` | requirements and `PLAN.md`; one folder per assignment |
| `README.md`, `REPORT.md` | stubs with TODOs |
| `.github/agents/`, `.github/skills/` | custom agent and skill (see below) |

## Commands
- Python 3.11+ (venv in `.venv`, currently 3.13). Install: `.venv\Scripts\pip install -e ".[dev]"`.
- Tests: `.venv\Scripts\python -m pytest`.
- Target entry point (spec): one command, `python main.py`.
- Build a data batch: see `.github/skills/claims-data-prep/SKILL.md` (section 6).

## Contract: extraction schema (see `docs/assignment-1/PLAN.md` section 3)
`location_city`, `accident_type` (enum), `severity` (enum), `fault` (enum), `weather_conditions` (enum), `time_of_day` (enum), `vehicle {make, color, year}`, `other_vehicles [{make, color}]` (hand-labelled list). Missing information is `null`; never invent values. Do not add `claim_id`, `policy_number`, plate number, coverage type, insurance company or driver data (see PLAN.md for why).

## Rules
- Keys live in `.env`; only `.env.example` is committed. Never put secrets in code, data or docs.
- No real personal data. All data sources are synthetic.
- Every result must log model, prompt version and sampling parameters. Invalid output gets one repair attempt, then `failed`.
- Report accuracy per source (QCAR, Cleanlab, label-first) and per batch; label-first texts were written by Claude, so they can favour related models.
- Never overwrite earlier data batches; record hashes to prove they are unchanged.
- Do not create the golden set or edit its labels without the human.
- Out of scope: UI, deployment, fine-tuning.
- Keep changes small, run the smallest relevant test, and update `docs/assignment-1/PLAN.md` when decisions change.

## Keeping this file current
This is a living document. Update it in the same change whenever any of these happen:
- a step is started or finished (update **Status**)
- the layout, commands or entry point change
- the schema or a decision in `docs/assignment-1/PLAN.md` changes
- a new agent, skill or rule is added

### Update log
| Date | Change |
| --- | --- |
| 2026-10-14 | Created: project, status, layout, schema contract, rules, data-provider agent and skill. |
| 2026-10-14 | Added application boilerplate (folder structure with stubs, config, prompts, tests). |
| 2026-10-14 | Renamed repo to `car-insurance-claims`; regrouped code by function (`src/common/`, `src/llm/`, `src/extraction/`, no inner package folder since it is a single project; imports are `from extraction import ...`); moved assignment docs to `docs/assignment-1/`; recreated `.venv`. |

- Agent `data-provider` (`.github/agents/data-provider.agent.md`): downloads, evaluates and noises claim data.
- Skill `claims-data-prep` (`.github/skills/claims-data-prep/SKILL.md`): the procedure; its helper script `scripts/prepare_data.py` lives in the skill folder. Keep all data-provider helper scripts there.
