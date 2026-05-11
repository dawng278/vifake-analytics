#!/usr/bin/env python3
"""
Test script to verify scam detection improvements.
Tests BOTH the rule-based fallback (PhoBERT mock) AND the Vietnamese scam detector.
Covers: Roblox, Free Fire, Liên Quân, PUBG Mobile
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from ai_engine.nlp_worker.phobert_inference import PhoBERTInference
from ai_engine.nlp_worker.intent_detector import detect_scam_intent

phobert = PhoBERTInference.__new__(PhoBERTInference)
phobert.labels = {0: "SAFE", 1: "TOXIC", 2: "MANIPULATIVE"}
phobert.model = None

# (input, expected, description)
TEST_CASES = [
    # === Roblox scams ===
    ("đưa tôi 1000 robux để nhận 1000000 robux", "FAKE_SCAM", "Roblox doubling"),
    ("gửi 100 robux mình trả 1000 robux", "FAKE_SCAM", "Roblox send/receive"),
    ("mình đang event x2 robux nè", "FAKE_SCAM", "Roblox fake x2 event"),
    # === Free Fire scams ===
    ("hack kim cương free fire miễn phí", "FAKE_SCAM", "FF hack kim cương"),
    ("đưa 500 kim cương nhận 5000 kim cương", "FAKE_SCAM", "FF doubling kim cương"),
    ("free elite pass free fire 2024", "FAKE_SCAM", "FF free elite pass"),
    ("tool hack free fire mới nhất", "FAKE_SCAM", "FF tool hack"),
    ("mod free fire auto headshot", "FAKE_SCAM", "FF mod hack"),
    # === Liên Quân scams ===
    ("hack quân huy miễn phí liên quân", "FAKE_SCAM", "LQ hack quân huy"),
    ("x2 quân huy event mới", "FAKE_SCAM", "LQ x2 quân huy"),
    ("hack tướng liên quân free mới nhất", "FAKE_SCAM", "LQ hack tướng"),
    ("tool hack liên quân 2024", "FAKE_SCAM", "LQ tool hack"),
    # === PUBG scams ===
    ("hack uc pubg mobile miễn phí", "FAKE_SCAM", "PUBG hack UC"),
    ("free uc pubg generator 2024", "FAKE_SCAM", "PUBG UC generator"),
    ("hack royale pass miễn phí pubg", "FAKE_SCAM", "PUBG free RP"),
    ("tool hack pubg mobile mới", "FAKE_SCAM", "PUBG tool hack"),
    # === Market Price Anomalies ===
    ("Nạp 10k được 1.000.000 robux", "FAKE_SCAM", "Insane Robux Price Anomaly"),
    ("Shop hot 20k vnd nhận 50.000 kim cương", "FAKE_SCAM", "Insane FF KC Price Anomaly"),
    ("Khuyến mãi 50k có ngay 5000 uc", "FAKE_SCAM", "Insane PUBG UC Price Anomaly"),
    ("Giá rẻ uy tín: 50k = 350 robux", "SAFE", "Realistic Price Shop (SAFE)"),
    # === Account / generic scams ===
    ("cho mình acc để test, sẽ trả lại", "FAKE_SCAM", "Account takeover"),
    ("nhập code này vào browser để nhận skin free", "FAKE_SCAM", "Cookie logger"),
    # === SAFE gaming content ===
    ("Hướng dẫn chơi Roblox cho người mới", "SAFE", "Safe: Roblox tutorial"),
    ("Review tướng mới liên quân mùa 30", "SAFE", "Safe: LQ review"),
    ("Hướng dẫn leo rank PUBG mobile", "SAFE", "Safe: PUBG guide"),
    ("Highlight gameplay Free Fire đỉnh cao", "SAFE", "Safe: FF gameplay"),
    ("Hôm nay mình học toán với thầy Nguyễn", "SAFE", "Safe: Education"),
]

print("=" * 80)
print("ViFake Scam Detection — Multi-Game Verification")
print("=" * 80)

passed = 0
failed = 0

for text, expected, desc in TEST_CASES:
    result = phobert._rule_based_predict(text)
    prediction = result.get("prediction", "UNKNOWN")
    confidence = result.get("confidence", 0)
    matched = result.get("matched_patterns", [])

    if expected == "SUSPICIOUS":
        ok = prediction in ("SUSPICIOUS", "FAKE_SCAM")
    else:
        ok = prediction == expected

    status = "✅" if ok else "❌"
    if not ok:
        failed += 1
    else:
        passed += 1

    print(f"{status} [{desc}]")
    if not ok:
        print(f"   Input:    \"{text[:65]}\"")
        print(f"   Expected: {expected}  Got: {prediction} ({confidence:.3f})")
        if matched:
            print(f"   Matched:  {matched[:3]}")

# Intent tests
print(f"\n--- Intent Detection ---\n")
INTENT_TESTS = [
    ("đưa 1000 robux nhận 1000000 robux", "game_item_doubling", "Roblox doubling intent"),
    ("hack kim cương free fire", "game_item_doubling", "FF hack intent"),
    ("hack quân huy liên quân", "game_item_doubling", "LQ hack intent"),
    ("hack uc pubg", "game_item_doubling", "PUBG hack intent"),
    ("cho mình acc để test", "account_takeover", "Account takeover intent"),
    ("Hôm nay mình học toán", "none", "Safe intent"),
]

for text, expected_intent, desc in INTENT_TESTS:
    intent = detect_scam_intent(text)
    primary = intent.get("primary_intent", "none")
    ok = primary == expected_intent
    status = "✅" if ok else "❌"
    if not ok:
        failed += 1
    else:
        passed += 1
    print(f"{status} [{desc}]")
    if not ok:
        print(f"   Expected: {expected_intent}  Got: {primary}")

print(f"\n{'='*80}")
print(f"TOTAL: {passed}/{passed+failed} passed, {failed} failed")
print(f"{'='*80}")
sys.exit(1 if failed > 0 else 0)
