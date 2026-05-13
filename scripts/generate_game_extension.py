#!/usr/bin/env python3
"""
Generate synthetic game-domain extension for PhoBERT training.

Output:
  - data/synthetic/phobert_train_game_extension.json
  - data/synthetic/phobert_val_game_extension.json
"""

import json
import random
from pathlib import Path


RNG = random.Random(20260513)

GAMES = [
    ("roblox", ["robux", "rbx", "limited", "gamepass", "robux card"]),
    ("lien_quan", ["liên quân", "quân huy", "acc lq", "skin lq"]),
    ("pubg", ["pubg", "uc", "royale pass", "acc pubg"]),
    ("free_fire", ["free fire", "kim cương", "elite pass", "acc ff"]),
    ("fortnite", ["fortnite", "vbucks", "skin hiếm", "acc fortnite"]),
    ("mlbb", ["mlbb", "mobile legends", "kim cương ml", "acc mlbb"]),
    ("fc_mobile", ["fc mobile", "fifa mobile", "coin fc", "acc fc"]),
    ("brawl_stars", ["brawl stars", "gem", "skin brawl", "acc brawl"]),
    ("minecraft", ["minecraft", "minecoin", "realm", "account minecraft"]),
]

SCAM_PATTERNS = [
    "shop {item} rate siêu rẻ, nạp trước {money}k nhận ngay {qty} trong 5 phút",
    "event tặng {item} free, nhập user + pass để verify nhận quà",
    "chỉ hôm nay x2 {item}, gửi otp để kích hoạt ưu đãi",
    "tool hack {item} 2026, tải apk mod không ban acc",
    "admin game hỗ trợ nạp {item}, chuyển khoản trước rồi mình gửi code sau",
]

SUSPICIOUS_PATTERNS = [
    "bán {item} giá rẻ, chỉ giao dịch chuyển khoản",
    "bán acc game rank cao full skin, có trung gian cá nhân",
    "mua acc xịn giá tốt, cọc trước 30% rồi giao pass",
    "rate {item} hôm nay bao nhiêu, có shop nào uy tín không",
]

SAFE_PATTERNS = [
    "ai có tips chơi {item} hiệu quả không",
    "mình vừa leo rank xong, ai chơi {game} cùng không",
    "review skin mới trong {game}, nhìn đẹp thật",
    "cảnh báo: đừng đưa otp hoặc pass khi mua bán acc game",
]


def make_row(text: str, label_int: int, scenario: str, severity: str):
    return {
        "text": text,
        "label": label_int,
        "scenario": scenario,
        "severity": severity,
        "age_group": RNG.choice(["8-10", "11-13", "14-17"]),
        "realism_score": round(RNG.uniform(0.86, 0.98), 2),
        "risk_indicators": {
            "asks_for_credentials": any(k in text.lower() for k in ["pass", "otp", "verify"]),
            "includes_fake_link": any(k in text.lower() for k in ["http://", "https://", "bit.ly", "tinyurl"]),
            "creates_urgency": any(k in text.lower() for k in ["chỉ hôm nay", "5 phút", "ngay"]),
        },
        "metadata": {
            "synthetic_id": f"gameext_{RNG.randint(100000, 999999)}",
            "conversation_turns": RNG.choice([1, 2, 3]),
            "language_variant": RNG.choice(["teencode_heavy", "mixed_vn_en", "formal_vn"]),
        },
    }


def build_samples():
    rows = []
    for game, items in GAMES:
        # FAKE_SCAM heavy samples
        for _ in range(28):
            item = RNG.choice(items)
            tpl = RNG.choice(SCAM_PATTERNS)
            text = tpl.format(
                item=item,
                game=game.replace("_", " "),
                money=RNG.choice([20, 50, 99, 199, 299]),
                qty=RNG.choice(["10k " + item, "x2 " + item, "full skin", "acc vip"]),
            )
            rows.append(make_row(text, 1, f"{game}_scam_extension", "high"))

        # SUSPICIOUS market samples (binary label=1 for protective bias)
        for _ in range(10):
            item = RNG.choice(items)
            tpl = RNG.choice(SUSPICIOUS_PATTERNS)
            text = tpl.format(item=item, game=game.replace("_", " "))
            rows.append(make_row(text, 1, f"{game}_suspicious_market", "medium"))

        # SAFE normal gameplay samples
        for _ in range(10):
            item = RNG.choice(items)
            tpl = RNG.choice(SAFE_PATTERNS)
            text = tpl.format(item=item, game=game.replace("_", " "))
            rows.append(make_row(text, 0, f"{game}_safe_normal", "low"))
    RNG.shuffle(rows)
    return rows


def split_train_val(rows, val_ratio=0.2):
    n_val = int(len(rows) * val_ratio)
    return rows[n_val:], rows[:n_val]


def main():
    base = Path(__file__).resolve().parents[1]
    out_dir = base / "data" / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = build_samples()
    train_rows, val_rows = split_train_val(rows, val_ratio=0.2)

    train_path = out_dir / "phobert_train_game_extension.json"
    val_path = out_dir / "phobert_val_game_extension.json"

    train_path.write_text(json.dumps(train_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    val_path.write_text(json.dumps(val_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated {len(train_rows)} train extension rows -> {train_path}")
    print(f"Generated {len(val_rows)} val extension rows -> {val_path}")


if __name__ == "__main__":
    main()
