#!/usr/bin/env python3
"""
Audit dataset coverage for child/teen gaming scam detection.

Usage:
  python scripts/audit_game_coverage.py
"""

import json
import re
from collections import Counter
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


PATTERNS = {
    "roblox_robux": r"\b(roblox|robux|rbx|gamepass|limited|gift\s*card|robux\s*card|tỉ\s*giá\s*robux|rate\s*robux)\b",
    "lienquan": r"(liên\s*quân|lien\s*quan|quân\s*huy|acc\s*(lq|liên\s*quân)|skin\s*lq)",
    "pubg": r"\b(pubg|uc|royale\s*pass|acc\s*pubg|skin\s*pubg)\b",
    "freefire": r"(free\s*fire|\bff\b|kim\s*cương|elite\s*pass|acc\s*ff)",
    "minecraft": r"\bminecraft\b",
    "fortnite": r"\bfortnite|v-?bucks\b",
    "fc_mobile": r"(fc\s*mobile|fifa\s*mobile|ea\s*sports\s*fc)",
    "mlbb": r"\bmlbb\b|mobile\s*legends|moonton",
    "brawl_stars": r"brawl\s*stars",
}


def normalize_label(value):
    if isinstance(value, int):
        return "FAKE_SCAM" if value == 1 else "SAFE"
    return str(value or "").upper()


def summarize(rows, label_key="label"):
    total = Counter()
    scam = Counter()
    suspicious = Counter()
    safe = Counter()

    for row in rows:
        text = str(row.get("text") or row.get("content") or "").lower()
        label = normalize_label(row.get(label_key))
        for name, pattern in PATTERNS.items():
            if re.search(pattern, text):
                total[name] += 1
                if label == "FAKE_SCAM":
                    scam[name] += 1
                elif label == "SUSPICIOUS":
                    suspicious[name] += 1
                elif label == "SAFE":
                    safe[name] += 1
    return total, scam, suspicious, safe


def print_table(title, rows, label_key="label"):
    total, scam, suspicious, safe = summarize(rows, label_key)
    print(f"\n{title}")
    print("-" * len(title))
    for k in PATTERNS:
        print(
            f"{k:14} total={total[k]:4} scam={scam[k]:4} suspicious={suspicious[k]:4} safe={safe[k]:4}"
        )


def main():
    base = Path(__file__).resolve().parents[1]
    syn_train = load_json(base / "data" / "synthetic" / "phobert_train.json")
    syn_val = load_json(base / "data" / "synthetic" / "phobert_val.json")
    ext_train_path = base / "data" / "synthetic" / "phobert_train_game_extension.json"
    ext_val_path = base / "data" / "synthetic" / "phobert_val_game_extension.json"
    ext_train = load_json(ext_train_path) if ext_train_path.exists() else []
    ext_val = load_json(ext_val_path) if ext_val_path.exists() else []
    real_base = load_jsonl(base / "data" / "real_validation" / "real_validation_set.jsonl")
    real_ext_path = base / "data" / "real_validation" / "game_coverage_extension_2026.jsonl"
    real_ext = load_jsonl(real_ext_path) if real_ext_path.exists() else []
    real_combined = real_base + real_ext

    print(f"Synthetic base rows: {len(syn_train) + len(syn_val)}")
    print(f"Synthetic extension rows: {len(ext_train) + len(ext_val)}")
    print(f"Synthetic total rows: {len(syn_train) + len(syn_val) + len(ext_train) + len(ext_val)}")
    print(f"Real-validation base rows: {len(real_base)}")
    print(f"Real-validation extension rows: {len(real_ext)}")
    print(f"Real-validation combined rows: {len(real_combined)}")
    print_table(
        "Synthetic coverage (PhoBERT base + game extension)",
        syn_train + syn_val + ext_train + ext_val,
        "label",
    )
    print_table("Real validation coverage (base only)", real_base, "label")
    if real_ext:
        print_table("Real validation coverage (base + extension)", real_combined, "label")

    scenario_counts = Counter(r.get("scenario", "NA") for r in syn_train + syn_val + ext_train + ext_val)
    print("\nTop synthetic scenarios:")
    for name, c in scenario_counts.most_common(12):
        print(f"- {name}: {c}")


if __name__ == "__main__":
    main()
