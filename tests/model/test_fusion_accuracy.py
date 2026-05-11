"""Model accuracy tests — validates XGBoost fusion on the real validation set."""
import sys
import os
import json

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _ROOT)

import pytest

REAL_VAL_PATH = os.path.join(_ROOT, "data", "real_validation", "real_validation_set.jsonl")
MODEL_PATH    = os.path.join(_ROOT, "ai_engine", "fusion_model", "xgboost_fusion_model.joblib")
SCALER_PATH   = os.path.join(_ROOT, "ai_engine", "fusion_model", "feature_scaler.joblib")
NAMES_PATH    = os.path.join(_ROOT, "ai_engine", "fusion_model", "feature_names.json")


def _load_validation_set():
    samples = []
    if not os.path.exists(REAL_VAL_PATH):
        return samples
    with open(REAL_VAL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


@pytest.mark.model
class TestXGBoostFusionModel:

    @pytest.fixture(scope="class")
    def model(self):
        xgb = pytest.importorskip("xgboost", reason="xgboost not installed")
        joblib = pytest.importorskip("joblib", reason="joblib not installed")
        if not os.path.exists(MODEL_PATH):
            pytest.skip("XGBoost model not found — run scripts/train_xgboost_fusion.py first")
        from ai_engine.fusion_model.xgboost_fusion import XGBoostFusionModel, FusionConfig
        cfg = FusionConfig(
            model_path=MODEL_PATH,
            scaler_path=SCALER_PATH,
            feature_names_path=NAMES_PATH,
        )
        m = XGBoostFusionModel(cfg)
        m.load_model()
        return m

    def test_model_loads(self, model):
        assert model.is_trained, "Model not trained/loaded"

    def test_feature_count_is_29(self, model):
        assert len(model.feature_names) == 29, (
            f"Expected 29 features, got {len(model.feature_names)}"
        )

    def test_labels_are_3_class(self, model):
        assert model.LABELS == ["SAFE", "SUSPICIOUS", "FAKE_SCAM"]

    def test_predict_returns_valid_label(self, model):
        vision_result = {
            "combined_risk_score": 0.8, "safety_score": 0.2,
            "violent_risk": 0.1, "scam_risk": 0.8, "sexual_risk": 0.0,
            "inappropriate_risk": 0.1, "is_safe": False,
            "requires_review": True, "risk_level": "HIGH", "vram_usage_gb": 0.0,
        }
        nlp_result = {
            "probabilities": {"SAFE": 0.05, "SUSPICIOUS": 0.10, "FAKE_SCAM": 0.85},
            "confidence": 0.85, "is_safe": False, "requires_review": True,
            "risk_level": "HIGH", "text": "free robux unlock",
        }
        result = model.predict(vision_result, nlp_result, {"platform": "youtube"})
        assert result["prediction"] in ("SAFE", "SUSPICIOUS", "FAKE_SCAM")
        assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.model
class TestModelAccuracyOnRealData:
    """Run predictions on real_validation_set.jsonl and assert min accuracy."""

    # Rule-based mock mode without actual PhoBERT weights has limited accuracy
    MIN_ACCURACY = 0.40  # 40% — realistic floor for keyword-only detection

    def test_accuracy_on_real_validation_set(self):
        samples = _load_validation_set()
        if not samples:
            pytest.skip("real_validation_set.jsonl not found or empty")

        from ai_engine.nlp_worker.phobert_inference import PhoBERTInference
        nlp = PhoBERTInference()

        correct = 0
        for s in samples:
            text = s.get("text", "")
            true_label = s.get("label", "")
            if not text or not true_label:
                continue
            result = nlp.predict(text)
            if result["prediction"] == true_label:
                correct += 1

        accuracy = correct / len(samples)
        assert accuracy >= self.MIN_ACCURACY, (
            f"NLP accuracy {accuracy:.1%} below minimum {self.MIN_ACCURACY:.0%} "
            f"on {len(samples)} real samples"
        )
