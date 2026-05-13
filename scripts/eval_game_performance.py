#!/usr/bin/env python3
"""
Evaluate ViFake API with per-game confusion matrix and false-negative tracking.

Default datasets:
  - data/real_validation/real_validation_set.jsonl
  - data/real_validation/game_coverage_extension_2026.jsonl

Usage:
  python scripts/eval_game_performance.py --api http://localhost:8000 --token vifake-demo-2024
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


LABELS = ["FAKE_SCAM", "SUSPICIOUS", "SAFE"]

GAME_PATTERNS = {
    "roblox_robux": r"\b(roblox|robux|rbx|gamepass|limited|robux\s*card|rate\s*robux|tỉ\s*giá\s*robux)\b",
    "lienquan": r"(liên\s*quân|lien\s*quan|quân\s*huy|acc\s*lq|skin\s*lq)",
    "pubg": r"\b(pubg|royale\s*pass|acc\s*pubg|\buc\b)\b",
    "freefire": r"(free\s*fire|\bff\b|elite\s*pass|acc\s*ff|kim\s*cương)",
    "minecraft": r"\bminecraft|minecoin|realm\b",
    "fortnite": r"\bfortnite|v-?bucks\b",
    "fc_mobile": r"(fc\s*mobile|fifa\s*mobile|coin\s*fc|acc\s*fc)",
    "mlbb": r"\bmlbb\b|mobile\s*legends|moonton",
    "brawl_stars": r"brawl\s*stars|acc\s*brawl|skin\s*brawl",
}


def normalize_label(v):
    if isinstance(v, int):
        return "FAKE_SCAM" if v == 1 else "SAFE"
    s = str(v or "").upper().strip()
    return s if s in LABELS else "SUSPICIOUS"


def detect_game(text: str) -> str:
    text_lower = (text or "").lower()
    for game, pat in GAME_PATTERNS.items():
        if re.search(pat, text_lower):
            return game
    return "other"


def load_jsonl(path: Path) -> List[Dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def post_json(url, headers, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def poll_job(base_url, headers, job_id, timeout_s=45):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            data = get_json(f"{base_url}/api/v1/job/{job_id}", headers)
            if data.get("status") == "completed":
                return data.get("result", {})
            if data.get("status") == "failed":
                return None
        except Exception:
            pass
        time.sleep(0.45)
    return None


def calc_metrics(rows):
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    support = Counter()

    for r in rows:
        exp = r["expected"]
        pred = r["predicted"]
        support[exp] += 1
        if exp == pred:
            tp[exp] += 1
        else:
            fp[pred] += 1
            fn[exp] += 1

    out = {}
    for label in LABELS:
        p_d = tp[label] + fp[label]
        r_d = tp[label] + fn[label]
        precision = tp[label] / p_d if p_d else 0.0
        recall = tp[label] / r_d if r_d else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": int(support[label]),
        }
    return out


def confusion(rows):
    matrix = {exp: {pred: 0 for pred in LABELS} for exp in LABELS}
    for r in rows:
        matrix[r["expected"]][r["predicted"]] += 1
    return matrix


def print_confusion(title, matrix):
    print(f"\n{title}")
    print("-" * len(title))
    print(f"{'exp\\pred':<14} {'FAKE_SCAM':>10} {'SUSPICIOUS':>11} {'SAFE':>8}")
    for exp in LABELS:
        row = matrix[exp]
        print(f"{exp:<14} {row['FAKE_SCAM']:>10} {row['SUSPICIOUS']:>11} {row['SAFE']:>8}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--token", default="vifake-demo-2024")
    ap.add_argument("--delay", type=float, default=0.12, help="Seconds between submitted samples")
    ap.add_argument("--max-samples", type=int, default=0, help="0 means all")
    ap.add_argument("--verbose", action="store_true", help="Print per-sample prediction lines")
    ap.add_argument("--mode", choices=["api", "local"], default="local", help="Evaluation mode")
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    dataset_paths = [
        base / "data" / "real_validation" / "real_validation_set.jsonl",
        base / "data" / "real_validation" / "game_coverage_extension_2026.jsonl",
    ]

    headers = {
        "Authorization": f"Bearer {args.token}",
        "Content-Type": "application/json",
    }

    samples = []
    for p in dataset_paths:
        if p.exists():
            loaded = load_jsonl(p)
            for row in loaded:
                text = str(row.get("text") or "").strip()
                if not text:
                    continue
                samples.append(
                    {
                        "text": text,
                        "expected": normalize_label(row.get("label")),
                        "scenario": row.get("scenario", "unknown"),
                        "source_file": p.name,
                        "game": row.get("game_domain") or detect_game(text),
                    }
                )

    if args.max_samples > 0:
        samples = samples[: args.max_samples]

    if not samples:
        raise SystemExit("No samples found.")

    print(f"Loaded {len(samples)} samples from {[p.name for p in dataset_paths if p.exists()]}")
    print(f"Mode: {args.mode}")
    if args.mode == "api":
        print(f"API: {args.api}")
        try:
            h = get_json(f"{args.api}/api/v1/health", headers)
            print(f"API health: {h.get('status','ok')} version={h.get('version','?')}")
        except Exception as e:
            raise SystemExit(f"Cannot reach API: {e}")
    else:
        import logging
        from backend_services.api_gateway import main as gateway
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("backend_services.api_gateway.main").setLevel(logging.WARNING)
        logging.getLogger("ai_engine").setLevel(logging.WARNING)
        print("Using local inference path from backend_services.api_gateway.main")

        gaming_keywords = [
            "robux", "roblox", "vbucks", "v-bucks", "skin", "gem", "diamond", "kim cương",
            "free fire", "acc game", "nick game", "trade", "nhân đôi", "liên quân",
            "quân huy", "pubg", "royale pass", "minecraft", "fortnite", "fc mobile",
            "mlbb", "brawl stars", "uc", "gamepass", "limited",
        ]

        def predict_local(text: str):
            nlp_result = gateway._run_nlp_analysis(text)
            vision_result = {
                "combined_risk_score": 0.2,
                "safety_score": 0.8,
                "violent_risk": 0.1,
                "scam_risk": 0.2,
                "sexual_risk": 0.05,
                "inappropriate_risk": 0.1,
                "is_safe": True,
                "requires_review": False,
                "risk_level": "LOW",
                "ocr_risk": 0.0,
            }
            fusion = gateway._run_fusion(vision_result, nlp_result, "facebook", {"content": text, "platform": "facebook"})
            predicted = normalize_label(fusion.get("prediction"))
            confidence = float(fusion.get("confidence") or 0.0)

            # Mirror key post-fusion guardrails in API pipeline for text-only eval.
            nlp_flags_raw = nlp_result.get("flags", [])
            has_scam_flags = any(
                f for f in nlp_flags_raw if not str(f).startswith("SAFE_INDICATORS") and not str(f).startswith("TEENCODE")
            )
            text_l = (text or "").lower()
            has_gaming_context = any(kw in text_l for kw in gaming_keywords)
            if not has_scam_flags and bool(nlp_result.get("is_safe")) and not has_gaming_context:
                predicted = "SAFE"
                confidence = min(confidence if confidence > 0 else 0.25, 0.25)
            elif has_gaming_context and not has_scam_flags and predicted == "SAFE":
                predicted = "SUSPICIOUS"
                confidence = max(confidence, 0.45)
            return predicted, confidence

    rows = []
    for i, s in enumerate(samples, 1):
        predicted = "SUSPICIOUS"
        confidence = 0.0
        error = None

        try:
            if args.mode == "api":
                payload = {
                    "url": f"https://eval.vifake.local/{s['game']}",
                    "platform": "facebook",
                    "priority": "normal",
                    "content": s["text"],
                }
                submit = post_json(f"{args.api}/api/v1/analyze", headers, payload)
                job_id = submit.get("job_id")
                if job_id:
                    out = poll_job(args.api, headers, job_id, timeout_s=45)
                    if out:
                        predicted = normalize_label(out.get("label"))
                        confidence = float(out.get("confidence") or 0.0)
                    else:
                        error = "timeout_or_failed"
                else:
                    error = "no_job_id"
            else:
                predicted, confidence = predict_local(s["text"])
        except Exception as e:
            error = str(e)

        rows.append(
            {
                "index": i,
                "game": s["game"],
                "scenario": s["scenario"],
                "source_file": s["source_file"],
                "expected": s["expected"],
                "predicted": predicted,
                "confidence": round(confidence, 4),
                "error": error,
                "text": s["text"][:220],
            }
        )
        if args.verbose:
            ok = "OK" if s["expected"] == predicted else "XX"
            print(
                f"[{i:03d}/{len(samples)}] {ok} game={s['game']:<12} exp={s['expected']:<11} pred={predicted:<11} conf={confidence:.2f}"
            )
        time.sleep(args.delay)

    total = len(rows)
    correct = sum(1 for r in rows if r["expected"] == r["predicted"])
    acc = correct / total if total else 0.0

    global_conf = confusion(rows)
    global_metrics = calc_metrics(rows)
    print(f"\nOverall accuracy: {acc:.2%} ({correct}/{total})")
    print_confusion("Global confusion matrix", global_conf)

    # Per-game metrics
    by_game = defaultdict(list)
    for r in rows:
        by_game[r["game"]].append(r)

    per_game_summary = {}
    print("\nPer-game summary")
    print("----------------")
    for game in sorted(by_game.keys()):
        g_rows = by_game[game]
        g_total = len(g_rows)
        g_correct = sum(1 for r in g_rows if r["expected"] == r["predicted"])
        g_acc = g_correct / g_total if g_total else 0.0
        g_conf = confusion(g_rows)
        g_metrics = calc_metrics(g_rows)
        scam_fn = sum(1 for r in g_rows if r["expected"] == "FAKE_SCAM" and r["predicted"] == "SAFE")

        per_game_summary[game] = {
            "total": g_total,
            "accuracy": round(g_acc, 4),
            "scam_false_negative_safe": scam_fn,
            "confusion_matrix": g_conf,
            "metrics": g_metrics,
        }
        print(
            f"{game:14} total={g_total:4d} acc={g_acc:6.2%} scam->SAFE FN={scam_fn:3d}"
        )

    out = {
        "summary": {
            "total": total,
            "correct": correct,
            "accuracy": round(acc, 4),
        },
        "global_confusion_matrix": global_conf,
        "global_metrics": global_metrics,
        "per_game": per_game_summary,
        "details": rows,
    }
    out_path = base / "data" / "real_validation" / "game_eval_results.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved detailed results -> {out_path}")


if __name__ == "__main__":
    main()
