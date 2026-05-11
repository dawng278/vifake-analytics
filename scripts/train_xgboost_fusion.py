#!/usr/bin/env python3
"""
Train XGBoost Fusion Model from synthetic Vietnamese scam data.

Usage:
    python scripts/train_xgboost_fusion.py

Saves to:
    ai_engine/fusion_model/xgboost_fusion_model.joblib
    ai_engine/fusion_model/feature_scaler.joblib
    ai_engine/fusion_model/feature_names.json
"""
import sys
import os
import json
import random
import logging
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# ── Label mapping ────────────────────────────────────────────────────────────
LABELS = ["SAFE", "SUSPICIOUS", "FAKE_SCAM"]
LABEL_MAP = {l: i for i, l in enumerate(LABELS)}

SCENARIO_LABEL = {
    # legacy
    "legitimate_conversation": "SAFE",
    "malicious_link":          "SUSPICIOUS",
    "robux_phishing":          "FAKE_SCAM",
    "gift_card_scam":          "FAKE_SCAM",
    "account_theft":           "FAKE_SCAM",
    "crypto_scam":             "FAKE_SCAM",
    # synthetic_v2 scenarios
    "freefire_garena_scam":    "FAKE_SCAM",
    "tiktok_coin_scam":        "FAKE_SCAM",
    "discord_steam_scam":      "FAKE_SCAM",
    "mlbb_diamond_scam":       "FAKE_SCAM",
    "fake_job_ctv":            "FAKE_SCAM",
    "crypto_airdrop_scam":     "FAKE_SCAM",
    "fake_giveaway_prize":     "FAKE_SCAM",
    "romance_grooming_scam":   "FAKE_SCAM",
    "fake_streaming_account":  "FAKE_SCAM",
    "fake_scholarship":        "FAKE_SCAM",
    "otp_phishing":            "FAKE_SCAM",
    "school_daily":            "SAFE",
    "gaming_normal":           "SAFE",
    "entertainment":           "SAFE",
    "social_normal":           "SAFE",
    "advice_genuine":          "SAFE",
    "question_normal":         "SAFE",
}


# ── Lightweight Vietnamese scam scorer (no external deps) ──────────────────
def _scam_score(text: str) -> float:
    """Returns a rough risk score 0-1 for a Vietnamese text snippet."""
    import re
    t = text.lower()
    score = 0.0
    # High-signal patterns
    for pat in [
        r'robux', r'free.*robux', r'nạp.*thẻ', r'gửi.*tiền.*trước',
        r'verify.*acc', r'xác.*minh.*acc', r'airdrop', r'metamask',
        r'usdt', r'connect.*wallet', r'account.*bị.*khóa',
        r'nhận.*thưởng', r'bit\.ly', r'tinyurl', r'click.*link',
        r'nạp.*trước.*để.*nhận', r'chuyển.*khoản.*trước',
    ]:
        if re.search(pat, t):
            score += 0.15
    for kw in ['free', 'hack', 'mật khẩu', 'password', 'login', 'verify']:
        if kw in t:
            score += 0.05
    return min(score, 1.0)


def _build_features(sample: dict, rng: random.Random) -> list:
    """Build feature vector matching XGBoostFusionModel.extract_features() order."""
    text = sample.get("text", "")
    label_str = SCENARIO_LABEL.get(sample.get("scenario", ""), "FAKE_SCAM")
    is_scam = label_str != "SAFE"
    risk = _scam_score(text)
    noise = lambda s: max(0.0, min(1.0, s + rng.gauss(0, 0.05)))

    # ── Vision features (10) ─────────────────────────────────────────────────
    # Simulated: scam posts tend to have higher visual risk
    vision_risk = noise(risk * 0.8 + (0.3 if is_scam else 0.05))
    vision_safety = 1.0 - vision_risk
    f_vision = [
        noise(vision_risk),        # combined_risk_score
        noise(vision_safety),      # safety_score
        noise(0.1 if is_scam else 0.02),  # violent_risk
        noise(vision_risk),        # scam_risk
        0.0,                       # sexual_risk
        noise(0.05),               # inappropriate_risk
        1.0 if not is_scam else 0.0,  # is_safe
        1.0 if is_scam else 0.0,   # requires_review
        (1.0 if risk > 0.6 else (0.5 if risk > 0.3 else 0.0)),  # risk_level_encoded
        0.0,                       # vram_usage_normalized
    ]

    # ── NLP features (10 = 4 probs + 6 extras) ──────────────────────────────
    # Simulate probabilities across LABELS ["SAFE", "FAKE_TOXIC", "FAKE_SCAM", "FAKE_MISINFO"]
    if label_str == "SAFE":
        probs = [noise(0.80), noise(0.10), noise(0.10)]
    elif label_str == "SUSPICIOUS":
        probs = [noise(0.15), noise(0.70), noise(0.15)]
    elif label_str == "FAKE_SCAM":
        probs = [noise(0.05), noise(0.10), noise(0.85)]
    else:
        probs = [noise(0.05), noise(0.10), noise(0.85)]
    # Normalise probs
    total = sum(probs)
    probs = [p / total for p in probs]

    nlp_confidence = max(probs)
    f_nlp = probs + [
        nlp_confidence,            # confidence
        1.0 if not is_scam else 0.0,  # is_safe
        1.0 if is_scam else 0.0,   # requires_review
        (1.0 if risk > 0.6 else (0.5 if risk > 0.3 else 0.0)),  # risk_level_encoded
        min(float(len(text)) / 500.0, 1.0),   # text_length_normalized
        min(float(text.count("http")) / 10.0, 1.0),  # url_count_normalized
        min(float(text.count("!")) / 20.0, 1.0),     # exclamation_count_normalized
    ]

    # ── Metadata features (8) ────────────────────────────────────────────────
    age_encoding = {"8-10": 0.0, "11-13": 0.5, "14-17": 1.0, "unknown": 0.25}
    age_val = age_encoding.get(sample.get("age_group", "unknown"), 0.25)

    scenario_order = ["robux_phishing", "gift_card_scam", "malicious_link", "account_theft", "crypto_scam"]
    scenario = sample.get("scenario", "unknown")
    scenario_one_hot = [1.0 if scenario == s else 0.0 for s in scenario_order]

    meta = sample.get("metadata", {})
    f_meta = [
        age_val,
        *scenario_one_hot,
        float(sample.get("realism_score", 0.5)),
        min(float(meta.get("conversation_turns", 0)) / 10.0, 1.0),
        1.0 if "teencode" in meta.get("language_variant", "") else 0.0,
    ]

    return f_vision + f_nlp + f_meta


def load_data() -> list:
    base = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")
    samples = []

    # ── New JSONL format (synthetic_v2) ──────────────────────────────────────
    jsonl_path = os.path.join(base, "phobert_train.jsonl")
    if os.path.exists(jsonl_path):
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                # Normalise to the format _build_features expects
                samples.append({
                    "text":          rec.get("text", ""),
                    "scenario":      rec.get("scenario", "robux_phishing"),
                    "age_group":     rec.get("age_focus", "unknown"),
                    "realism_score": 0.85,
                    "metadata":      {"conversation_turns": 4, "language_variant": "mixed"},
                    # _label_str used below to override SCENARIO_LABEL lookup
                    "_label_str":    rec.get("label_str", "FAKE_SCAM"),
                })
        logger.info(f"  Loaded {len(samples)} samples from phobert_train.jsonl")

    # ── Legacy JSON files ────────────────────────────────────────────────────
    for fname in ["phobert_train.json", "phobert_val.json",
                  "processed_synthetic_data.json"]:
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            # also try data/ root
            path = os.path.join(os.path.dirname(__file__), "..", "data", fname)
        if os.path.exists(path):
            try:
                data = json.load(open(path, encoding="utf-8"))
                if isinstance(data, list):
                    samples.extend(data)
                    logger.info(f"  Loaded {len(data)} samples from {fname}")
            except Exception as e:
                logger.warning(f"  Skipping {fname}: {e}")

    logger.info(f"Total raw samples: {len(samples)}")
    return samples


def main():
    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import classification_report
        import joblib
    except ImportError as e:
        logger.error(f"Missing dependency: {e}. Run: pip install xgboost scikit-learn joblib")
        sys.exit(1)

    rng = random.Random(42)

    logger.info("📂 Loading synthetic training data...")
    samples = load_data()
    if not samples:
        logger.error("No training data found!")
        sys.exit(1)

    logger.info("🔧 Building feature vectors...")
    X, y = [], []
    for s in samples:
        # prefer explicit _label_str (from new JSONL loader) over scenario lookup
        label_str = s.get("_label_str") or SCENARIO_LABEL.get(s.get("scenario", ""), "FAKE_SCAM")
        if label_str not in LABEL_MAP:
            label_str = "FAKE_SCAM"
        label_idx = LABEL_MAP[label_str]
        features = _build_features(s, rng)
        X.append(features)
        y.append(label_idx)

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int32)
    logger.info(f"  Feature matrix: {X.shape}, Labels: {np.unique(y, return_counts=True)}")

    # Feature names (must match extract_features order)
    feature_names = [
        "vision_combined_risk", "vision_safety_score",
        "vision_violent_risk", "vision_scam_risk", "vision_sexual_risk", "vision_inappropriate_risk",
        "vision_is_safe", "vision_requires_review", "vision_risk_level_encoded",
        "vision_vram_usage_normalized",
        "nlp_prob_safe", "nlp_prob_suspicious", "nlp_prob_fake_scam",
        "nlp_confidence", "nlp_is_safe", "nlp_requires_review", "nlp_risk_level_encoded",
        "nlp_text_length_normalized", "nlp_url_count_normalized", "nlp_exclamation_count_normalized",
        "metadata_age_group_encoded",
        "metadata_scenario_robux_phishing", "metadata_scenario_gift_card_scam",
        "metadata_scenario_malicious_link", "metadata_scenario_account_theft",
        "metadata_scenario_crypto_scam",
        "metadata_realism_score", "metadata_conversation_turns_normalized", "metadata_contains_teencode",
    ]

    logger.info("✂️  Splitting train/test...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info("📏 Scaling features...")
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    logger.info("🚀 Training XGBoost (n_estimators=200, max_depth=6, class-weighted)...")
    # Class weights: up-weight minority classes (SAFE, FAKE_MISINFO) and SUSPICIOUS (index 2 if present)
    # LABELS = ["SAFE", "FAKE_TOXIC", "FAKE_SCAM", "FAKE_MISINFO"]
    # The training data skews heavily toward FAKE_SCAM — this helps SAFE & other recall
    from collections import Counter
    label_counts = Counter(y_train.tolist())
    n_total = len(y_train)
    n_classes = len(LABELS)
    # sklearn-style: weight = n_total / (n_classes * count)
    sample_weight = np.array([
        n_total / (n_classes * max(label_counts.get(yi, 1), 1))
        for yi in y_train
    ], dtype=np.float32)
    logger.info(f"  Label distribution (train): {dict(sorted(label_counts.items()))}")
    logger.info(f"  Sample weights range: [{sample_weight.min():.3f}, {sample_weight.max():.3f}]")

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
        use_label_encoder=False,
        num_class=len(LABELS),
    )
    model.fit(X_train_s, y_train, sample_weight=sample_weight,
              eval_set=[(X_test_s, y_test)], verbose=False)

    train_acc = model.score(X_train_s, y_train)
    test_acc = model.score(X_test_s, y_test)
    logger.info(f"  Train accuracy: {train_acc:.3f}  |  Test accuracy: {test_acc:.3f}")
    y_pred = model.predict(X_test_s)
    # Only show labels that appear in y_test
    present_labels = sorted(set(y_test))
    present_names = [LABELS[i] for i in present_labels]
    logger.info("\n" + classification_report(y_test, y_pred, labels=present_labels, target_names=present_names))

    # Save artefacts
    out_dir = os.path.join(os.path.dirname(__file__), "..", "ai_engine", "fusion_model")
    os.makedirs(out_dir, exist_ok=True)

    model_path = os.path.join(out_dir, "xgboost_fusion_model.joblib")
    scaler_path = os.path.join(out_dir, "feature_scaler.joblib")
    names_path = os.path.join(out_dir, "feature_names.json")

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    json.dump(feature_names, open(names_path, "w"), ensure_ascii=False, indent=2)

    logger.info(f"\n✅ Saved model  → {model_path}")
    logger.info(f"✅ Saved scaler → {scaler_path}")
    logger.info(f"✅ Saved names  → {names_path}")
    logger.info(f"\nTest accuracy: {test_acc:.1%} | Feature count: {len(feature_names)}")


if __name__ == "__main__":
    main()
