"""Build data/texts.jsonl (30 QCAR + 10 Cleanlab + label-first texts, DRAFT labels) and data/DATA_REPORT.md.

Standard library only. Deterministic: QCAR sampling uses Random(--qcar-seed, default 42), noise uses Random(--noise-seed, default 7).
No arguments = batch 1; see parse_args() for the options used to build further batches.
Raw downloads are cached under data/raw/ (delete the folder to re-download).
data/label_first.jsonl is authored by hand (text written to match a target label) and merged as-is.
"""
import argparse
import ast
import csv
import hashlib
import json
import random
import re
import statistics
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"
QCAR_SEED = 42
NOISE_SEED = 7
ID_PREFIX = "doc"
COMPARE = []
POOL_PATH = RAW / "qcar_pool.jsonl"
SAMPLE_PATH = OUT / "raw" / "qcar_sample.jsonl"
CLEANLAB_PATH = RAW / "cleanlab_insurance_claims_extraction.csv"

QCAR_URL = ("https://datasets-server.huggingface.co/rows?dataset=itamarcohen/insurance_car_Qfiles"
            "&config=default&split=train&offset={offset}&length=100")
CLEANLAB_URL = ("https://huggingface.co/datasets/Cleanlab/insurance-claims-extraction/resolve/main/"
                "insurance_claims_extraction.csv")
POOL_SIZE = 2000
N_QCAR = 30
DEFAULT_LABEL_FIRST = ROOT / "data" / "label_first.jsonl"
LABEL_FIRST_PATH = DEFAULT_LABEL_FIRST  # overridden by --label-first
# fields the noise/text can genuinely remove: only these are nulled when absent from the text
STRING_FIELDS = ["location_city", "vehicle.make", "vehicle.color", "vehicle.year"]
N_CLEANLAB_EXPECTED = 10

ACCIDENT_TYPES = ["rear-end collision", "reversing collision", "parking lot scrape", "head-on at junction",
                  "lane-change sideswipe", "side collision at intersection", "chain collision",
                  "pedestrian-area incident"]
SEVERITIES = ["minor", "moderate", "severe"]
FAULTS = ["reporter_at_fault", "other_party_at_fault", "shared_fault", "undetermined"]
WEATHERS = ["clear", "night-clear", "cloudy", "foggy", "wet road", "rainy"]
TIMES = ["morning", "afternoon", "evening", "night"]
LABEL_FIELDS = ["location_city", "accident_type", "severity", "fault", "weather_conditions", "time_of_day",
                "vehicle.make", "vehicle.color", "vehicle.year"]
EVIDENCE_KEYS = ["city", "make", "color", "year", "weather", "time_of_day", "accident_type", "severity", "fault"]
EV_TO_FIELD = {"city": "location_city", "make": "vehicle.make", "color": "vehicle.color", "year": "vehicle.year",
               "weather": "weather_conditions", "time_of_day": "time_of_day", "accident_type": "accident_type",
               "severity": "severity", "fault": "fault"}


# ---------------------------------------------------------------- download
def http_get(url, retries=5):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "prepare-data/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def load_pool():
    # a non-default POOL_SIZE uses its own cache file so the batch-1 pool cache is never rewritten
    global POOL_PATH
    if POOL_SIZE != 2000:
        POOL_PATH = RAW / f"qcar_pool_{POOL_SIZE}.jsonl"
    if POOL_PATH.exists():
        return [json.loads(l) for l in POOL_PATH.read_text(encoding="utf-8").splitlines()]
    rows = []
    for offset in range(0, POOL_SIZE, 100):
        data = json.loads(http_get(QCAR_URL.format(offset=offset)).decode("utf-8"))
        rows.extend(r["row"] for r in data["rows"])
    POOL_PATH.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return rows


def load_cleanlab():
    if not CLEANLAB_PATH.exists():
        CLEANLAB_PATH.write_bytes(http_get(CLEANLAB_URL))
    with open(CLEANLAB_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- evidence
WEATHER_KW = {
    "clear": r"clear|sunny|dry|cloudless|bright",
    "cloudy": r"cloud|overcast|grey|gray",
    "foggy": r"fog|mist|haze",
    "wet road": r"wet|slick|puddle|damp",
    "rainy": r"rain|drizzle|downpour|shower|storm",
}
TIME_KW = {
    "morning": r"morning|dawn|sunrise|breakfast",
    "afternoon": r"afternoon|midday|noon|lunch",
    "evening": r"evening|dusk|sunset|rush hour",
    "night": r"night|midnight|late",
}
TYPE_KW = {
    "rear-end collision": r"rear|from behind|back of|tailgat",
    "reversing collision": r"revers|backing|backed",
    "parking lot scrape": r"parking|scrap|parked",
    "head-on at junction": r"head-on|head on|junction|oncoming",
    "lane-change sideswipe": r"lane|sideswip|merg",
    "side collision at intersection": r"intersection|side|t-bone|crossing",
    "chain collision": r"chain|pile-?up|several cars|multiple (cars|vehicles)|series of",
    "pedestrian-area incident": r"pedestrian|crosswalk|sidewalk|crossing|walkway",
}
SEV_KW = {
    "minor": r"minor|small|slight|light|scratch|superficial|negligible",
    "moderate": r"moderate|noticeable|considerable|visible|dent",
    "severe": r"severe|significant|major|serious|extensive|substantial|total|heavy|badly",
}
FAULT_KW = r"fault|blame|responsib|liab|my mistake|their mistake|failed to yield|ran a red|at fault"


def has(pattern, text):
    return re.search(pattern, text, re.I) is not None


def qcar_evidence(text, row):
    """Booleans: is each gold label value recoverable from the (possibly noised) text?"""
    low = text.lower()
    w = row["weather_conditions"]
    if w == "night-clear":
        weather = has(r"night", low) and has(r"clear|dry|dark", low)
    else:
        weather = has(WEATHER_KW[w], low)
    return {
        "city": row["location_city"].lower() in low,
        "make": row["car_make"].lower() in low,
        "color": has(r"\b" + re.escape(row["car_color"]) + r"\b", low),
        "year": str(row["manufacture_year"]) in text,
        "weather": weather,
        "time_of_day": has(TIME_KW[time_of_day(row["accident_timestamp"])], low),
        "accident_type": has(TYPE_KW[row["accident_type"]], low),
        "severity": has(SEV_KW[row["severity"]], low),
        "fault": has(FAULT_KW, low),
    }


def time_of_day(ts):
    h = int(ts[11:13])
    if 5 <= h <= 11:
        return "morning"
    if 12 <= h <= 16:
        return "afternoon"
    if 17 <= h <= 20:
        return "evening"
    return "night"


# ---------------------------------------------------------------- selection
def select_qcar(pool, rng):
    order = pool[:]
    rng.shuffle(order)
    need = Counter()
    for col, vals in (("accident_type", ACCIDENT_TYPES), ("severity", SEVERITIES), ("fault", FAULTS),
                      ("weather_conditions", WEATHERS)):
        for v in vals:
            need[(col, v)] = 2
    need[("len", "short")] = 4
    need[("len", "long")] = 4

    def keys(r):
        k = [(c, r[c]) for c in ("accident_type", "severity", "fault", "weather_conditions")]
        n = len(r["accident_description"])
        if n < 250:
            k.append(("len", "short"))
        if n > 900:
            k.append(("len", "long"))
        return k

    chosen, used = [], set()
    for i, r in enumerate(order):
        if len(chosen) >= N_QCAR:
            break
        if any(need[k] > 0 for k in keys(r)):
            for k in keys(r):
                if need[k] > 0:
                    need[k] -= 1
            chosen.append(r)
            used.add(i)
    for i, r in enumerate(order):
        if len(chosen) >= N_QCAR:
            break
        if i not in used:
            chosen.append(r)
            used.add(i)
    leftover = [r for i, r in enumerate(order) if i not in used]
    unmet = {k: v for k, v in need.items() if v > 0}
    return chosen, leftover, unmet


# ---------------------------------------------------------------- noise
RU = ["ударили сзади", "это была не моя вина", "небольшая царапина", "машина сильно повреждена",
      "всё произошло быстро", "водитель уехал"]
HE = ["תאונה קלה", "הנזק היה קטן", "הוא פגע בי מאחור", "לא אשמתי", "המשטרה הגיעה", "זה קרה מהר מאוד"]
FILLER = ["Sorry for the long message, I am still a bit shaken up.",
          "By the way, my cousin says I should have taken the other road anyway.",
          "I already called my wife and she is not happy about the whole thing.",
          "Anyway, I hope this reaches the right department, last time it got lost.",
          "Honestly it has been a really long week and the coffee machine at work is also broken.",
          "Please get back to me soon, I can be reached after 6 on most days."]
ABBR = [(r"\bcollision\b", "coll."), (r"\bvehicle\b", "veh."), (r"\bintersection\b", "int."),
        (r"\bapproximately\b", "approx."), (r"\bwith\b", "w/"), (r"\band\b", "&"),
        (r"\bbecause\b", "bc"), (r"\bnumber\b", "no."), (r"\bdamage\b", "dmg"), (r"\bbumper\b", "bmpr")]
NOISE_ORDER = ["drop_sentence", "abbreviations", "extra_filler", "mixed_language", "typo", "truncation",
               "lowercase_no_punct"]


def split_sentences(t):
    return re.split(r"(?<=[.!?])\s+", t)


def op_typo(t, rng):
    words = list(re.finditer(r"[A-Za-z]{5,}", t))
    if not words:
        return t
    picks = sorted(rng.sample(words, min(len(words), rng.randint(3, 5))), key=lambda m: m.start(), reverse=True)
    for m in picks:
        w = m.group()
        i = rng.randrange(1, len(w) - 1)
        kind = rng.choice(["swap", "drop", "dup"])
        if kind == "swap":
            w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
        elif kind == "drop":
            w = w[:i] + w[i + 1:]
        else:
            w = w[:i] + w[i] + w[i:]
        t = t[:m.start()] + w + t[m.end():]
    return t


def op_truncation(t, rng):
    keep = 1 - rng.uniform(0.2, 0.4)
    cut = t[:int(len(t) * keep)]
    return cut.rsplit(" ", 1)[0] if " " in cut else cut


def op_drop_sentence(t, rng):
    s = split_sentences(t)
    if len(s) < 3:
        return t
    del s[rng.randrange(len(s))]
    return " ".join(s)


def op_lowercase_no_punct(t, rng):
    t = t.lower().replace("-", " ")
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def op_abbreviations(t, rng):
    for pat, rep in rng.sample(ABBR, rng.randint(3, 5)):
        t = re.sub(pat, rep, t, flags=re.I)
    return t


def op_mixed_language(t, rng):
    phrases = rng.sample(rng.choice([RU, HE]), rng.randint(1, 2))
    s = split_sentences(t)
    for p in phrases:
        s.insert(rng.randint(0, len(s)), p + ".")
    return " ".join(s)


def op_extra_filler(t, rng):
    f = rng.choice(FILLER)
    return f + " " + t if rng.random() < 0.5 else t + " " + f


NOISE_FUNCS = {"typo": op_typo, "truncation": op_truncation, "drop_sentence": op_drop_sentence,
               "lowercase_no_punct": op_lowercase_no_punct, "abbreviations": op_abbreviations,
               "mixed_language": op_mixed_language, "extra_filler": op_extra_filler}


def add_noise(text, rng):
    ops = rng.sample(list(NOISE_FUNCS), rng.randint(1, 3))
    ops = [o for o in NOISE_ORDER if o in ops]
    for o in ops:
        text = NOISE_FUNCS[o](text, rng)
    return text, ops


# ---------------------------------------------------------------- docs
def blank_labels():
    return {"location_city": None, "accident_type": None, "severity": None, "fault": None,
            "weather_conditions": None, "time_of_day": None,
            "vehicle": {"make": None, "color": None, "year": None}}


def qcar_labels(row):
    return {"location_city": row["location_city"], "accident_type": row["accident_type"],
            "severity": row["severity"], "fault": row["fault"], "weather_conditions": row["weather_conditions"],
            "time_of_day": time_of_day(row["accident_timestamp"]),
            "vehicle": {"make": row["car_make"], "color": row["car_color"], "year": row["manufacture_year"]}}


def null_field(labels, field):
    if field.startswith("vehicle."):
        labels["vehicle"][field.split(".")[1]] = None
    else:
        labels[field] = None


def get_field(labels, field):
    return labels["vehicle"][field.split(".")[1]] if field.startswith("vehicle.") else labels[field]


def cleanlab_doc(row):
    gt = ast.literal_eval(row["ground_truth"])
    pol = gt.get("policy_details") or {}
    if pol.get("coverage_type") != "Auto":
        return None
    labels = blank_labels()
    objs = [o for o in (gt.get("insured_objects") or []) if (o or {}).get("object_type") == "Vehicle"]
    notes = []
    if objs:
        o = objs[0]
        mm = o.get("make_model")
        labels["vehicle"]["make"] = mm.split()[0] if mm else None
        labels["vehicle"]["year"] = o.get("year")
        if len(objs) > 1:
            notes.append("multi_vehicle_policy")
    text = row["claim_text"]
    ev = {k: False for k in EVIDENCE_KEYS}
    if labels["vehicle"]["make"]:
        ev["make"] = labels["vehicle"]["make"].lower() in text.lower()
    if labels["vehicle"]["year"]:
        ev["year"] = str(labels["vehicle"]["year"]) in text
    for f in ("vehicle.make", "vehicle.year"):
        if get_field(labels, f) is not None and not ev[f.split(".")[1]]:
            null_field(labels, f)
    return {"source_id": gt["header"].get("claim_id"), "text": text, "labels": labels, "evidence": ev,
            "notes": notes}


def md_table(counter, order):
    lines = ["| value | count |", "| --- | ---: |"]
    for v in order:
        lines.append(f"| {v} | {counter.get(v, 0)} |")
    lines.append(f"| null | {counter.get(None, 0)} |")
    return "\n".join(lines)


def qcar_contradictions(text, row):
    """Strong keyword contradictions between the text and the kept enum label (informational, sets needs_review)."""
    low = text.lower()
    bad = []
    w = row["weather_conditions"]
    if w in ("clear", "night-clear", "cloudy") and has(r"\bfog|\brain|downpour|drizzle", low):
        bad.append("weather_conditions")
    elif w in ("foggy", "rainy", "wet road") and has(r"sunny|clear sky|cloudless", low):
        bad.append("weather_conditions")
    tod = time_of_day(row["accident_timestamp"])
    others = [t for t in ("morning", "afternoon", "evening") if t != tod and has(r"\b" + t + r"\b", low)]
    if others and not has(TIME_KW[tod], low) and tod != "night":
        bad.append("time_of_day")
    sev = row["severity"]
    if sev == "severe" and has(r"\bminor\b|slight|scratch", low) and not has(SEV_KW["severe"], low):
        bad.append("severity")
    if sev == "minor" and has(r"\bsevere|serious|total loss|extensive|major", low) and not has(SEV_KW["minor"], low):
        bad.append("severity")
    return bad


def load_label_first():
    docs = []
    for line in LABEL_FIRST_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        labels, text, low = r["draft_labels"], r["text"], r["text"].lower()
        v = labels["vehicle"]
        ev = {"city": bool(labels["location_city"]) and labels["location_city"].lower() in low,
              "make": bool(v["make"]) and v["make"].lower() in low,
              "color": bool(v["color"]) and has(r"\b" + re.escape(v["color"]) + r"\b", low),
              "year": v["year"] is not None and str(v["year"]) in text}
        for k in ("weather", "time_of_day", "accident_type", "severity", "fault"):
            ev[k] = labels[EV_TO_FIELD[k]] is not None
        ev = {k: ev[k] for k in EVIDENCE_KEYS}
        for f in STRING_FIELDS:
            assert (get_field(labels, f) is None) or ev[[e for e, x in EV_TO_FIELD.items() if x == f][0]], (r["id"], f)
        docs.append({"source": "label_first", "source_id": r["id"], "text": text, "original_text": text,
                     "noise_ops": [], "draft_labels": labels, "evidence": ev, "needs_review": False,
                     "_ev_orig": ev, "_contra": []})
    return docs


def abs_path(s):
    p = Path(s)
    return p if p.is_absolute() else ROOT / p


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--qcar-seed", type=int, default=42)
    ap.add_argument("--noise-seed", type=int, default=7)
    ap.add_argument("--out", default="data", help="output dir (texts.jsonl, DATA_REPORT.md, raw/qcar_sample.jsonl)")
    ap.add_argument("--label-first", default=str(Path("data") / "label_first.jsonl"))
    ap.add_argument("--id-prefix", default="doc", help="document id prefix: <prefix>-001, ...")
    ap.add_argument("--exclude-texts", nargs="*", default=[], metavar="TEXTS_JSONL",
                    help="earlier texts.jsonl files; their QCAR source_ids are removed from the pool")
    ap.add_argument("--pool-size", type=int, default=2000,
                    help="number of leading QCAR rows fetched into the pool (default 2000; others cache to qcar_pool_<N>.jsonl)")
    ap.add_argument("--compare-to", nargs="*", default=[], metavar="TEXTS_JSONL",
                    help="earlier texts.jsonl files; adds a comparison section (null rates, needs_review, distributions)")
    return ap.parse_args()


def main():
    global OUT, SAMPLE_PATH, LABEL_FIRST_PATH, QCAR_SEED, NOISE_SEED, ID_PREFIX, POOL_SIZE, COMPARE
    args = parse_args()
    POOL_SIZE = args.pool_size
    COMPARE = [abs_path(p) for p in args.compare_to]
    QCAR_SEED, NOISE_SEED, ID_PREFIX = args.qcar_seed, args.noise_seed, args.id_prefix
    OUT = abs_path(args.out)
    LABEL_FIRST_PATH = abs_path(args.label_first)
    SAMPLE_PATH = OUT / "raw" / "qcar_sample.jsonl"
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    pool_all = load_pool()
    cl_rows = load_cleanlab()
    excluded = set()
    for p in args.exclude_texts:
        for line in abs_path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r["source"] == "qcar":
                    excluded.add(r["source_id"])
    pool_all = [r for r in pool_all if r["claim_id"] not in excluded]

    # quality guard: drop pool rows with fewer than 3 of 9 evidence checks passing on the original text
    pool = [r for r in pool_all if sum(qcar_evidence(r["accident_description"], r).values()) >= 3]
    n_filtered = len(pool_all) - len(pool)

    rng = random.Random(QCAR_SEED)
    chosen, _, unmet = select_qcar(pool, rng)
    SAMPLE_PATH.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in chosen), encoding="utf-8")

    nrng = random.Random(NOISE_SEED)
    noisy_idx = set(nrng.sample(range(len(chosen)), round(0.6 * len(chosen))))
    docs = []
    for i, r in enumerate(chosen):
        orig = r["accident_description"]
        text, ops = (add_noise(orig, nrng) if i in noisy_idx else (orig, []))
        labels = qcar_labels(r)
        ev = qcar_evidence(text, r)
        review = False
        for k in ("city", "make", "color", "year"):
            if not ev[k]:
                null_field(labels, EV_TO_FIELD[k])
                review = True
        contra = qcar_contradictions(text, r)
        review = review or bool(contra)
        docs.append({"source": "qcar", "source_id": r["claim_id"], "text": text, "original_text": orig,
                     "noise_ops": ops, "draft_labels": labels, "evidence": ev, "needs_review": review,
                     "_ev_orig": qcar_evidence(orig, r), "_contra": contra})

    cl_docs = [d for d in (cleanlab_doc(row) for row in cl_rows) if d]
    assert len(cl_docs) == N_CLEANLAB_EXPECTED, len(cl_docs)
    for d in cl_docs:
        docs.append({"source": "cleanlab", "source_id": d["source_id"], "text": d["text"],
                     "original_text": d["text"], "noise_ops": [], "draft_labels": d["labels"],
                     "evidence": d["evidence"], "needs_review": True, "_ev_orig": d["evidence"],
                     "_notes": d["notes"], "_contra": []})
    docs.extend(load_label_first())

    assert len(docs) >= 50, len(docs)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "texts.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for n, d in enumerate(docs, 1):
            rec = {"id": f"{ID_PREFIX}-{n:03d}", "source": d["source"], "source_id": d["source_id"], "text": d["text"],
                   "original_text": d["original_text"], "noise_ops": d["noise_ops"],
                   "draft_labels": d["draft_labels"], "evidence": d["evidence"],
                   "needs_review": d["needs_review"], "label_status": "draft"}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    write_report(docs, unmet, n_filtered, len(pool_all))


# counts from the previous run (50 docs: 40 qcar + 10 cleanlab), kept for the BEFORE/AFTER table
BEFORE_NULL = {"fault": 25, "location_city": 23, "severity": 21, "weather_conditions": 19, "accident_type": 18,
               "time_of_day": 18, "vehicle.make": 18, "vehicle.color": 34, "vehicle.year": 20}
BEFORE_DOCS = 50


def _load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _stats(recs):
    """Comparable statistics for a list of records (current docs or a texts.jsonl file)."""
    qc = [r for r in recs if r["source"] == "qcar"]
    lf = [r for r in recs if r["source"] == "label_first"]
    cl = [r for r in recs if r["source"] == "cleanlab"]
    nl = lambda ds, f: sum(1 for r in ds if get_field(r["draft_labels"], f) is None)
    ov = [len(r["original_text"]) for r in qc]
    lfl = [len(r["text"]) for r in lf]
    return {"recs": recs, "qc": qc, "lf": lf, "cl": cl, "nl": nl, "ov": ov, "lfl": lfl}


def comparison_section(docs, sec, n_pool):
    names = [p.parent.name if p.parent.name != "data" else "batch1" for p in COMPARE]
    cur_name = ID_PREFIX
    sets = [(n, _stats(_load_jsonl(p))) for n, p in zip(names, COMPARE)]
    sets.append((cur_name + " (this)", _stats(docs)))
    ids = {n: {r["source_id"] for r in st["qc"]} for n, st in sets}
    cur_ids = ids[cur_name + " (this)"]
    L = [f"## {sec}. Comparison with earlier batches (script-generated)\n"]
    L.append("QCAR source_id overlap of this batch with: " + "; ".join(
        f"{n} **{len(cur_ids & ids[n])}**" for n, _ in sets[:-1]) + f" (pool after exclusion: {n_pool} rows). "
        "Cleanlab: only 10 Auto claims exist, so the **same 10 Cleanlab docs are reused** in every batch "
        "(overlap 10, unavoidable).\n")
    hdr = "| metric | " + " | ".join(n for n, _ in sets) + " |\n| --- | " + " | ".join("---:" for _ in sets) + " |"
    L.append(hdr)
    def row(label, fn):
        L.append(f"| {label} | " + " | ".join(str(fn(st)) for _, st in sets) + " |")
    row("docs (qcar/cleanlab/label_first)", lambda s: f"{len(s['recs'])} ({len(s['qc'])}/{len(s['cl'])}/{len(s['lf'])})")
    row("needs_review total", lambda s: sum(1 for r in s["recs"] if r["needs_review"]))
    row("needs_review QCAR", lambda s: f"{sum(1 for r in s['qc'] if r['needs_review'])}/{len(s['qc'])}")
    for f in STRING_FIELDS:
        row(f"QCAR null {f}", lambda s, f=f: s["nl"](s["qc"], f))
    row("label_first null city/make/colour/year/weather", lambda s: " / ".join(
        str(s["nl"](s["lf"], f)) for f in STRING_FIELDS + ["weather_conditions"]))
    row("QCAR noised docs", lambda s: sum(1 for r in s["qc"] if r["noise_ops"]))
    row("QCAR originals <250 / >900 chars", lambda s: f"{sum(1 for x in s['ov'] if x < 250)} / {sum(1 for x in s['ov'] if x > 900)}")
    row("label_first length min / median / max", lambda s: f"{min(s['lfl'])} / {int(statistics.median(s['lfl']))} / {max(s['lfl'])}")
    row("label_first texts >700 chars", lambda s: sum(1 for x in s["lfl"] if x > 700))
    L.append("\nQCAR distribution (counts per batch):\n")
    L.append("| field | value | " + " | ".join(n for n, _ in sets) + " |\n| --- | --- | " + " | ".join("---:" for _ in sets) + " |")
    for key, order in (("accident_type", ACCIDENT_TYPES), ("severity", SEVERITIES), ("fault", FAULTS),
                       ("weather_conditions", WEATHERS), ("time_of_day", TIMES)):
        for v in order:
            L.append(f"| {key} | {v} | " + " | ".join(
                str(sum(1 for r in st["qc"] if r["draft_labels"][key] == v)) for _, st in sets) + " |")
    L.append("")
    return L


def write_report(docs, unmet, n_filtered, n_pool):
    sources = ("qcar", "cleanlab", "label_first")
    by = {s: [d for d in docs if d["source"] == s] for s in sources}
    qc = by["qcar"]
    review = sum(1 for d in docs if d["needs_review"])
    L = ["# DATA_REPORT\n"]
    L.append(f"Generated by `.github/skills/claims-data-prep/scripts/prepare_data.py` (QCAR sampling `random.Random({QCAR_SEED})`, noise `random.Random({NOISE_SEED})`). "
             "All labels are **drafts** (`label_status: draft`); no golden set has been created.\n")
    L.append("## 1. Counts per source\n")
    L.append("| source | docs | noised | needs_review |\n| --- | ---: | ---: | ---: |")
    for s in sources:
        L.append(f"| {s} | {len(by[s])} | {sum(1 for d in by[s] if d['noise_ops'])} | "
                 f"{sum(1 for d in by[s] if d['needs_review'])} |")
    L.append(f"| total | {len(docs)} | {sum(1 for d in docs if d['noise_ops'])} | {review} |\n")
    try:
        lf_disp = LABEL_FIRST_PATH.relative_to(ROOT).as_posix()
    except ValueError:
        lf_disp = LABEL_FIRST_PATH.as_posix()
    L.append(f"`label_first` texts live in `{lf_disp}` (hand-authored: target label first, then a "
             "text written to support exactly those labels, with some fields deliberately omitted and labelled "
             "null).\n")

    L.append(f"## 2. Draft label distribution (after nulling, all {len(docs)} docs)\n")
    stratified_ok = True
    for key, order in (("accident_type", ACCIDENT_TYPES), ("severity", SEVERITIES), ("fault", FAULTS),
                       ("weather_conditions", WEATHERS), ("time_of_day", TIMES)):
        L.append(f"### {key}\n")
        L.append("| value | qcar | cleanlab | label_first | total |\n| --- | ---: | ---: | ---: | ---: |")
        cs = {s: Counter(d["draft_labels"][key] for d in by[s]) for s in sources}
        for v in order + [None]:
            tot = sum(cs[s].get(v, 0) for s in sources)
            if v is not None and key != "time_of_day" and tot < 2:
                stratified_ok = False
            L.append(f"| {v if v is not None else 'null'} | " + " | ".join(str(cs[s].get(v, 0)) for s in sources)
                     + f" | {tot} |")
        L.append("")
    L.append("### Stratification of the QCAR sample itself (labels before any nulling)\n")
    L.append("| column | value | qcar docs |\n| --- | --- | ---: |")
    sample = [json.loads(l) for l in SAMPLE_PATH.read_text(encoding="utf-8").splitlines()]
    qc_ok = True
    for col, order in (("accident_type", ACCIDENT_TYPES), ("severity", SEVERITIES), ("fault", FAULTS),
                       ("weather_conditions", WEATHERS)):
        c = Counter(r[col] for r in sample)
        for v in order:
            qc_ok = qc_ok and c.get(v, 0) >= 2
            L.append(f"| {col} | {v} | {c.get(v, 0)} |")
    so = [len(d["original_text"]) for d in qc]
    L.append(f"\nQCAR-only: every value >= 2: **{'yes' if qc_ok else 'NO'}**; unmet quotas: "
             f"{unmet if unmet else 'none'}. Whole corpus (incl. Cleanlab/label_first) every enum value >= 2 "
             f"(time_of_day excluded): **{'yes' if stratified_ok else 'NO'}**. "
             f"QCAR originals under 250 chars: {sum(1 for x in so if x < 250)}; over 900 chars: "
             f"{sum(1 for x in so if x > 900)}. {n_filtered} of {n_pool} pool rows were excluded up front "
             f"(fewer than 3 of 9 evidence checks on the original text).\n")

    L.append("## 3. Null counts per field per source\n")
    L.append("| field | qcar (of %d) | cleanlab (of %d) | label_first (of %d) | total (of %d) |\n"
             "| --- | ---: | ---: | ---: | ---: |" % (len(by["qcar"]), len(by["cleanlab"]), len(by["label_first"]),
                                                      len(docs)))
    nulls = {}
    for f in LABEL_FIELDS:
        nulls[f] = {s: sum(1 for d in by[s] if get_field(d["draft_labels"], f) is None) for s in sources}
        L.append(f"| {f} | " + " | ".join(str(nulls[f][s]) for s in sources) + f" | {sum(nulls[f].values())} |")
    L.append("\nQCAR nulls are only ever string-matchable fields (city, make, colour, year) missing from the final "
             "text; the five enum fields keep the QCAR source label. Cleanlab enum fields other than "
             "make/year are null by construction (not labelled in the source).\n")
    L.append("QCAR nulls caused by noise (present in the original text, absent after noise):\n")
    L.append("| field | nulled | caused by noise |\n| --- | ---: | ---: |")
    for f in STRING_FIELDS:
        k = [e for e, fld in EV_TO_FIELD.items() if fld == f][0]
        by_noise = sum(1 for d in qc if d["_ev_orig"][k] and not d["evidence"][k])
        L.append(f"| {f} | {nulls[f]['qcar']} | {by_noise} |")
    L.append("")

    L.append("## 4. Text length (characters)\n")
    L.append("| set | n | min | median | mean | max | <250 | >900 |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name, ds, field in (("qcar original", qc, "original_text"), ("qcar final (noised)", qc, "text"),
                            ("cleanlab", by["cleanlab"], "text"), ("label_first", by["label_first"], "text"),
                            ("all final", docs, "text")):
        ls = [len(d[field]) for d in ds]
        L.append(f"| {name} | {len(ls)} | {min(ls)} | {int(statistics.median(ls))} | {int(statistics.mean(ls))} | "
                 f"{max(ls)} | {sum(1 for x in ls if x < 250)} | {sum(1 for x in ls if x > 900)} |")
    L.append("")

    L.append("## 5. Noise ops (QCAR docs)\n")
    nc = Counter(o for d in qc for o in d["noise_ops"])
    L.append("| op | docs |\n| --- | ---: |")
    for o in NOISE_ORDER:
        L.append(f"| {o} | {nc.get(o, 0)} |")
    L.append(f"\nNoised QCAR docs: {sum(1 for d in qc if d['noise_ops'])} of {len(qc)}. Cleanlab and label_first "
             f"docs untouched.\n")

    L.append("## 6. Review status\n")
    qr = sum(1 for d in qc if d["needs_review"])
    qn = sum(1 for d in qc if any(get_field(d["draft_labels"], f) is None for f in STRING_FIELDS))
    qcx = sum(1 for d in qc if d["_contra"])
    L.append(f"- needs_review = true: {review} of {len(docs)} (cleanlab 10; QCAR {qr} of {len(qc)}: {qn} with a "
             f"nulled string field, {qcx} with a keyword contradiction; label_first 0).")
    L.append(f"- QCAR contradiction flags (field): {dict(Counter(f for d in qc for f in d['_contra'])) or 'none'}.\n")

    is_b1 = QCAR_SEED == 42 and NOISE_SEED == 7 and LABEL_FIRST_PATH == DEFAULT_LABEL_FIRST
    if is_b1:
        L.append("## 7. BEFORE vs AFTER the nulling-policy change\n")
        L.append("BEFORE = previous run (50 docs: 40 QCAR + 10 Cleanlab; every field with no keyword evidence was "
                 "nulled). AFTER = this run (all docs, %d). Rates are share of docs with a null label; the two corpora "
                 "differ in composition (AFTER adds label_first and has 30 QCAR docs), so the comparison is "
                 "indicative, not like-for-like.\n" % len(docs))
        L.append("| field | BEFORE null | BEFORE rate | AFTER null (all) | AFTER rate | AFTER null (qcar only) |\n"
                 "| --- | ---: | ---: | ---: | ---: | ---: |")
        for f in LABEL_FIELDS:
            a = sum(nulls[f].values())
            L.append(f"| {f} | {BEFORE_NULL[f]}/{BEFORE_DOCS} | {100 * BEFORE_NULL[f] // BEFORE_DOCS}% | "
                     f"{a}/{len(docs)} | {100 * a // len(docs)}% | {nulls[f]['qcar']}/{len(qc)} |")
        L.append(f"\nneeds_review: BEFORE 43/50 (86%; QCAR 33/40) -> AFTER {review}/{len(docs)} "
                 f"({100 * review // len(docs)}%; QCAR {qr}/{len(qc)}). Rare values (severe, head-on at junction, "
                 f"chain collision) were 1 each BEFORE; see section 2 for AFTER.\n")

    sec = 8 if is_b1 else 7
    if COMPARE:
        L.extend(comparison_section(docs, sec, n_pool))
        sec += 1
    L.append(f"## {sec}. Observations and risks\n")
    L.append("1. **Enum labels are now trusted from the source, not from keywords.** Nulling only string fields "
             "removes the false 'missing' cases of the previous run, but it also means some kept enum labels "
             "(especially `fault`, `severity`, `time_of_day`) may not be inferable from the story at all. "
             "QCAR text is LLM-written from the row, so many are, but the hand-verified golden set must "
             "still check each one.")
    L.append("2. **Keyword contradiction flags are crude** (e.g. 'rain' in 'no rain'); they only trigger "
             "`needs_review`, never nulling.")
    L.append("3. **Label-first circularity:** the 12 label_first texts were generated by Claude to fit labels "
             "Claude defined, so they are clean, internally consistent and probably easier than real "
             "claims. If an evaluated model is from a similar family it may do better on them; evaluated "
             "models (Gemini, Qwen) differ, but report label_first and QCAR/Cleanlab accuracy separately.")
    L.append("4. **Cleanlab docs lack most schema labels** (only make/year mapped, the first policy vehicle may "
             "not be the one in the accident). They are still null + needs_review and need hand labelling.")
    L.append("5. **Noise is our own transformation** and mixed-language insertions are generic statements that may "
             "contradict facts; the evidence heuristics only match English. Source text contains literal "
             "'\ufffd' / '?' encoding artefacts, left untouched.\n")
    (OUT / "DATA_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("docs:", len(docs), "unmet:", unmet, "review:", review, "qcar_ok:", qc_ok, "all_ok:", stratified_ok)


if __name__ == "__main__":
    main()
