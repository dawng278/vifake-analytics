import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.nlp_worker.teencode_normalizer import _load_dict, normalize

mapping = _load_dict()
sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
print("Top 20 longest keys:")
print(sorted_keys[:20])

print("\nContains 'free fire'?:", "free fire" in mapping)
if "free fire" in mapping:
    print("Value:", mapping["free fire"])

test_strs = [
    "mod free fire auto headshot",
    "free uc pubg generator 2024",
    "Highlight gameplay Free Fire đỉnh cao"
]

print("\n=== Normalization Test ===")
for s in test_strs:
    norm = normalize(s)
    print(f"Input: {s}")
    print(f"Norm : {norm}")
    print("-" * 30)
