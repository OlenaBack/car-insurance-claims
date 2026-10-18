---
name: claims-data-prep
description: Procedure for building the car-insurance claims corpus (QCAR + Cleanlab) - sampling, label mapping, evidence checks and reproducible noise injection. Use when preparing or regenerating data/texts.jsonl.
---

# Claims data preparation

Use this skill whenever the corpus in `data/` must be built or rebuilt. Context is in `docs/assignment-1/PLAN.md`.

## 1. Sources
| Source | Access | Notes |
| --- | --- | --- |
| QCAR `itamarcohen/insurance_car_Qfiles` | `https://datasets-server.huggingface.co/rows?dataset=itamarcohen/insurance_car_Qfiles&config=default&split=train&offset=N&length=100` | ~10k rows, MIT, clean prose, needs noise |
| Cleanlab `Cleanlab/insurance-claims-extraction` | `https://huggingface.co/datasets/Cleanlab/insurance-claims-extraction/resolve/main/insurance_claims_extraction.csv` | 30 rows, already messy, `ground_truth` is a Python-dict string (`ast.literal_eval`), some `policy_details` are `None`, keep Auto claims |

## 2. Label mapping (QCAR column -> schema field)
| Schema field | Source |
| --- | --- |
| `location_city` | `location_city` |
| `accident_type` | `accident_type` (8 values) |
| `severity` | `severity` (minor, moderate, severe) |
| `fault` | `fault` (reporter_at_fault, other_party_at_fault, shared_fault, undetermined) |
| `weather_conditions` | `weather_conditions` (clear, night-clear, cloudy, foggy, wet road, rainy) |
| `time_of_day` | hour of `accident_timestamp`: 05-11 morning, 12-16 afternoon, 17-20 evening, otherwise night |
| `vehicle.make / color / year` | `car_make`, `car_color`, `manufacture_year` |

Never copy `driver_name`, `driver_city`, `plate_number`, `coverage_type`, `insurance_company` or `claim_id`.
Cleanlab: `vehicle.make/year` come from `insured_objects`; weather, severity and fault are unlabelled, so they are `null` with `needs_review`.

## 3. Evidence check and nulling policy
For every document and label, record whether the value is recoverable from the text (informational). Reference rates in QCAR: city 69%, make 68%, year 61%, colour 52%, weather 52%, severity wording 34%.
- **Null only string-matchable fields** (`location_city`, `vehicle.make`, `vehicle.color`, `vehicle.year`) when the value is not in the final text. This produces the intended "missing field" cases.
- **Keep the source label for inferable enums** (`accident_type`, `severity`, `fault`, `weather_conditions`, `time_of_day`). A model is expected to infer them from the story. Nulling them by keyword match is too strict (a first run nulled 40-50% and made the labels useless).
- Drop pool rows with fewer than 3 recoverable labels before sampling.
- `needs_review = true` only when something was nulled or a heuristic strongly contradicts the label.
- Re-run the check after noise is applied.

## 3b. Label-first batch (about 12 docs)
Define the target label JSON first, then write a messy first-person claim that supports exactly those labels. Vary tone (angry, panicked, formal, SMS-style) and length (60-900 chars), include short Russian or Hebrew fragments, and deliberately omit some fields (set those labels to `null`). Cover rare enum values: severe, head-on at junction, chain collision, foggy, wet road, undetermined, shared_fault, pedestrian-area incident. Store in `data/label_first.jsonl`; the script merges it. Caveat: the generator model must differ from the evaluated models, otherwise scores are inflated; report accuracy per source.

## 3c. Stratification
Every value of `accident_type`, `severity`, `fault` and `weather_conditions` must appear at least twice in the corpus, with mixed text lengths (some under 250 chars, some over 900).

## 4. Noise recipes (seeded `random.Random`, 1-3 ops per doc, about 60% of QCAR docs)
| Op | Effect |
| --- | --- |
| `typo` | swap, drop or duplicate letters in a few words |
| `truncation` | cut the last 20-40% of the text |
| `drop_sentence` | remove one sentence |
| `lowercase_no_punct` | lowercase and strip punctuation |
| `abbreviations` | e.g. collision -> coll. |
| `mixed_language` | insert 1-2 short, well-formed Russian or Hebrew phrases (UTF-8) |
| `extra_filler` | add a chatty or irrelevant sentence |

Keep `original_text` and the list of applied `noise_ops`. Leave Cleanlab docs untouched.

## 5. Output contract
- `data/texts.jsonl`, one JSON per line: `id`, `source`, `source_id`, `text`, `original_text`, `noise_ops`, `draft_labels`, `evidence`, `needs_review`, `label_status` (`draft`). Write with `ensure_ascii=False`.
- `data/DATA_REPORT.md`: counts per source, enum distributions, length stats, noise counts, nulled labels per field, replaced docs, data-quality risks.
- The golden set is never produced here; a human verifies 10 documents.

## 6. Batches and CLI
`python .github\skills\claims-data-prep\scripts\prepare_data.py` (defaults reproduce batch 1; all helper scripts for this skill live in its `scripts\` folder). For further batches:
`--qcar-seed N --noise-seed M --out data\batchN --label-first data\batchN\label_first.jsonl --id-prefix bN --exclude-texts data\texts.jsonl data\batch2\texts.jsonl --compare-to data\texts.jsonl data\batch2\texts.jsonl`
- `--exclude-texts` accepts several paths and removes those batches' QCAR `source_id`s from the pool (overlap must be 0).
- `--compare-to` makes the script write the batch comparison into the report (null rates, needs_review, distributions), so regenerating the report does not lose it.
- `--pool-size` (default 2000) sets how many QCAR rows are fetched; keep the default for batches 1 and 2 so they reproduce byte-for-byte. A non-default size caches to `qcar_pool_<N>.jsonl`.
- Use `data\batchN\` per batch, never overwrite earlier batches (check sha256 before and after).
- Cleanlab has only 10 Auto claims, so later batches reuse them; say so in the report.
- Use an id prefix so ids are unique across batches.
- The label-first file is authored fresh for each batch (new scenarios, tones, languages). Allowed fragment languages: Russian, Hebrew, French, Arabic, Hindi, Turkish, Spanish, German, Swahili, Norwegian. The evidence check matches English only, so each fragment must keep the fact (colour, make, year) in English or be paired with it.
- Keyword contradiction flags are heuristics; verify them by hand.
- The same model authors every label-first batch, so report accuracy per source and per batch.
- QCAR has about 10k rows, but only the first `--pool-size` are fetched, and each batch removes 30 of them.

## 7. Checks before finishing
- Re-running the script gives an identical output hash (fixed seeds); earlier batches are unchanged.
- Valid JSON lines, no excluded fields, Russian and Hebrew text intact, stratification met.
