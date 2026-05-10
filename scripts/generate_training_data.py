#!/usr/bin/env python3
"""
ViFake Analytics — Synthetic Training Data Generator (Standalone)
Tạo dữ liệu training tổng hợp cho nhóm 8-17 tuổi, không cần MongoDB.

Privacy-by-Design:
  - 100% dữ liệu tổng hợp, không crawl/scrape nội dung thực
  - Không lưu thông tin cá nhân thật
  - Tuân thủ Nghị định 13/2023/NĐ-CP và COPPA

Output:
  - data/synthetic/training_samples_{timestamp}.json  (raw conversations)
  - data/synthetic/phobert_train.jsonl                (PhoBERT fine-tune format)
  - data/synthetic/xgboost_features.csv               (XGBoost feature format)
"""

import json
import random
import uuid
import csv
import os
import re
import sys
from datetime import datetime
from typing import List, Dict, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
NUM_SCAM_SAMPLES  = 2000   # số mẫu scam/fake
NUM_SAFE_SAMPLES  = 800    # số mẫu an toàn (balanced ~28%)
OUTPUT_DIR        = "data/synthetic"
SEED              = 42

random.seed(SEED)

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE RESOURCES
# ─────────────────────────────────────────────────────────────────────────────

TEEN_NAMES = [
    "minh", "an", "bin", "linh", "huy", "mai", "khoa", "tú", "nam", "nga",
    "duy", "bảo", "hà", "việt", "phú", "thành", "long", "quân", "khánh", "ly"
]

CELEBRITIES_VN = [
    "sơn tùng mtp", "jack", "đen vâu", "black pink", "bts", "cris devil gamer",
    "pew pew", "độ mixi", "zyro", "viruss", "thầy ba khoa", "mck"
]

FAKE_DOMAINS = [
    "bit.ly", "cutt.ly", "tinyurl.com", "t.co", "rb.gy", "is.gd",
    "shorturl.at", "tiny.cc", "ow.ly", "t2m.io"
]

EMOJI_SCAM = ["🎁", "🔥", "💰", "🤑", "⚡", "🚀", "💯", "🎉", "👑", "💎"]
EMOJI_SAFE  = ["😊", "📚", "🎮", "⚽", "🎵", "🌸", "👋", "😂", "❤️", "🐱"]

TEENCODE_MAP = {
    "bạn": ["m", "bn", "b", "bạn ơi"],
    "mình": ["t", "mk", "mik"],
    "không": ["k", "ko", "khong"],
    "được": ["đc", "dc"],
    "thật": ["tht", "thật á"],
    "vào": ["vao", "vô"],
    "rồi": ["r", "rồi đó"],
    "luôn": ["lun", "ln"],
    "hôm nay": ["hôm ni", "hn"],
    "đỉnh": ["dinh", "đỉnh nóc"],
}

def teen(text: str) -> str:
    """Áp dụng teencode ngẫu nhiên."""
    for word, variants in TEENCODE_MAP.items():
        if word in text and random.random() < 0.4:
            text = text.replace(word, random.choice(variants), 1)
    return text

def emoji_append(text: str, pool: List[str]) -> str:
    if random.random() < 0.45:
        text += " " + random.choice(pool)
    if random.random() < 0.25:
        text += random.choice(["!!", "!!!"])
    return text

def fake_link() -> str:
    domain = random.choice(FAKE_DOMAINS)
    slug = uuid.uuid4().hex[:7]
    return f"https://{domain}/{slug}"

def name() -> str:
    return random.choice(TEEN_NAMES)

def celeb() -> str:
    return random.choice(CELEBRITIES_VN)

# ─────────────────────────────────────────────────────────────────────────────
# SCAM TEMPLATES  (label = FAKE_SCAM)
# ─────────────────────────────────────────────────────────────────────────────

SCAM_TEMPLATES: List[Dict] = []

# ── 1. Robux / Roblox phishing ────────────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "robux_phishing",
        "age_focus": ["8-10", "11-13"],
        "texts": [
            lambda: f"ae {name()} ơi admin roblox đang event free robux nè! vào đây nhận ngay: {fake_link()}",
            lambda: f"{name()} ơi t vừa nhận 50,000 robux free muốn không? click {fake_link()} verify acc là xong",
            lambda: f"🔥 FREE ROBUX 2026! nhập pass roblox vào {fake_link()} để nhận 100k robux miễn phí nha!!!",
            lambda: f"event admin tặng robux cho 200 người đầu chỉ còn 2 slot! {fake_link()} nhanh lên!",
            lambda: f"yo {name()} t có tool hack robux pro, download tại {fake_link()} an toàn 100%",
            lambda: f"minh có cách get robux không cần nạp tiền, dm t hoặc vào {fake_link()}",
            lambda: f"FREE ROBUX chỉ cần share bài này tag 3 bạn rồi inbox t sẽ gửi code",
            lambda: f"{name()} ơi event chỉ hôm nay, nạp robux free bằng cách nhập otp vào {fake_link()}",
            lambda: f"100% REAL free robux không lừa đảo! nhập user + pass tại {fake_link()} là nhận ngay",
            lambda: f"admin game tặng 10k robux cho acc dưới 1 năm, verify tại {fake_link()} trước 12h đêm nay",
        ]
    }
]

# ── 2. Free Fire / Garena / UC scam ───────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "freefire_garena_scam",
        "age_focus": ["11-13", "14-17"],
        "texts": [
            lambda: f"FREE FIRE EVENT! nạp 300 viên kim cương miễn phí tại {fake_link()} hôm nay thôi!",
            lambda: f"{name()} ơi t có tool nạp UC pubg free, link: {fake_link()} không virus an toàn",
            lambda: f"Garena shell giveaway 1000 shell free! đăng nhập tài khoản tại {fake_link()} để nhận",
            lambda: f"FREE FIRE hack skin legendary free tại {fake_link()} chỉ cần nhập uid + pass",
            lambda: f"event tặng kim cương ff, vào {fake_link()} nhập số điện thoại để xác nhận",
            lambda: f"💎 1000 KIM CƯƠNG FREE FIRE MIỄN PHÍ! đăng nhập fb tại {fake_link()} là nhận ngay",
            lambda: f"t chia sẻ cách nạp UC miễn phí pubg mobile: {fake_link()} đã có 500 người dùng",
            lambda: f"hack acc free fire hàng siêu vip lv100 full skin, lấy tại {fake_link()} free đó!",
            lambda: f"Garena đang tặng pass premium 6 tháng! verify số điện thoại tại {fake_link()}",
            lambda: f"tool auto farm kim cương ff miễn phí, tải tại {fake_link()} không ban acc đâu nhé",
        ]
    }
]

# ── 3. TikTok xu / xu ảo ──────────────────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "tiktok_coin_scam",
        "age_focus": ["11-13", "14-17"],
        "texts": [
            lambda: f"XU TIKTOK MIỄN PHÍ! 10,000 xu free tại {fake_link()} không cần thanh toán!!!",
            lambda: f"{name()} ơi t vừa nhận 5000 xu tiktok free, bí kíp tại {fake_link()} đây",
            lambda: f"hack xu tiktok 2026 còn hoạt động, link: {fake_link()} vào nhanh trước khi bị xóa",
            lambda: f"EVENT TIKTOK tặng 1 triệu xu cho 100 creator! đăng ký tại {fake_link()} trước 11pm",
            lambda: f"mua xu tiktok giá rẻ hơn 50%, thanh toán qua {fake_link()} uy tín không lừa",
            lambda: f"tiktok live gift free! chỉ cần follow + share, nhận xu tại {fake_link()}",
            lambda: f"tool tăng xu tiktok tự động miễn phí: {fake_link()} cài vào là chạy luôn",
            lambda: f"🚀 XU TIKTOK FREE 2026 patch mới nhất, tải tại {fake_link()} không cần root",
        ]
    }
]

# ── 4. Discord Nitro / Steam scam ─────────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "discord_steam_scam",
        "age_focus": ["14-17"],
        "texts": [
            lambda: f"DISCORD NITRO FREE 1 NĂM! nhận tại {fake_link()} login discord là xong",
            lambda: f"{name()} ơi t có code nitro free hết hạn hôm nay, claim tại {fake_link()} đi",
            lambda: f"steam wallet 200k free! login steam tại {fake_link()} để nhận tiền vào ví",
            lambda: f"giveaway discord nitro classic 3 tháng, đăng nhập tại {fake_link()} chỉ 50 slot",
            lambda: f"t tặng nitro discord cho {name()}, nhận tại {fake_link()} trước 11h đêm nhé",
            lambda: f"steam free game AAA! login tại {fake_link()} thêm vào library miễn phí",
            lambda: f"💎 NITRO BOOST SERVER FREE! authorize discord app tại {fake_link()} để kích hoạt",
            lambda: f"có code steam 500k hết hạn cuối ngày, nhận tại {fake_link()} trước khi hết",
        ]
    }
]

# ── 5. Mobile Legends / MLBB diamond scam ─────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "mlbb_diamond_scam",
        "age_focus": ["11-13", "14-17"],
        "texts": [
            lambda: f"DIAMOND MOBILE LEGENDS FREE! 3000 diamond tại {fake_link()} nhập uid là nhận",
            lambda: f"{name()} ơi event ml tặng diamond free, vào {fake_link()} xác nhận uid",
            lambda: f"hack diamond ml 2026 mới nhất chưa bị patch: {fake_link()} an toàn 100%",
            lambda: f"mua diamond ml giá rẻ 50%, chuyển khoản xong nhận ngay tại {fake_link()}",
            lambda: f"event moonton tặng skin epic free! đăng nhập ml tại {fake_link()} để nhận",
            lambda: f"tool farm diamond mlbb tự động free: {fake_link()} không ban account đâu nhé",
            lambda: f"💎 3000 DIAMOND ML CHỈ 50K! thanh toán qua {fake_link()} nhận ngay sau 1 phút",
        ]
    }
]

# ── 6. Fake job / CTV online scam ─────────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "fake_job_ctv",
        "age_focus": ["14-17"],
        "texts": [
            lambda: f"TUYỂN CTV ONLINE lương 5 triệu/ngày không cần kinh nghiệm! đăng ký: {fake_link()}",
            lambda: f"tuyển part-time online nhẹ nhàng 300k/h, làm tại nhà bằng điện thoại: {fake_link()}",
            lambda: f"việc làm thêm cho học sinh lương 200-500k/ngày, đăng ký miễn phí: {fake_link()}",
            lambda: f"CẦN GẤP nhân viên đánh giá app online 150k/task, đăng ký tại {fake_link()}",
            lambda: f"làm affiliate marketing từ nhà 10-15tr/tháng, miễn phí đào tạo: {fake_link()}",
            lambda: f"tuyển người like share zalo facebook lương 200k/ngày, không cần kinh nghiệm: {fake_link()}",
            lambda: f"job nhà tuyển gấp: nhập data online 100k/h, đăng ký tại {fake_link()} nộp phí 200k",
            lambda: f"agency quảng cáo tuyển CTV đăng bài, 50k/post, đăng ký và nộp phí kích hoạt: {fake_link()}",
            lambda: f"VIỆC LÀM THÊM HÈ lương 5-8 triệu không đi đâu, chỉ cần nộp phí bảo đảm 300k: {fake_link()}",
            lambda: f"tuyển streamer tiktok live hỗ trợ thiết bị, nộp cọc 500k hoàn lại sau: {fake_link()}",
        ]
    }
]

# ── 7. Crypto / Airdrop / NFT scam ────────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "crypto_airdrop_scam",
        "age_focus": ["14-17"],
        "texts": [
            lambda: f"🚀 AIRDROP ALERT! nhận 500 USDT miễn phí! connect ví metamask tại {fake_link()} ngay!",
            lambda: f"DeFi farm mới lợi nhuận 50%/tháng! deposit USDT tối thiểu 100 tại {fake_link()}",
            lambda: f"NFT exclusive 100 slot! mint ngay tại {fake_link()} giá floor 10x sau launch",
            lambda: f"nhập seed phrase ví vào {fake_link()} để xác thực và nhận 1000 USDT airdrop",
            lambda: f"approve smart contract này nhận airdrop token mới: {fake_link()} event 24h",
            lambda: f"USDT x2 trong 24h! gửi 100 USDT vào {fake_link()} nhận 200 USDT sau 1 ngày",
            lambda: f"meme coin mới pre-sale! mua sớm x100 lợi nhuận, đăng ký whitelist: {fake_link()}",
            lambda: f"p2e game mới hot 2026 kiếm 50 USDT/ngày, deposit 200 USDT để bắt đầu: {fake_link()}",
        ]
    }
]

# ── 8. Fake giveaway / prize / QR ─────────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "fake_giveaway_prize",
        "age_focus": ["8-10", "11-13", "14-17"],
        "texts": [
            lambda: f"🎁 GIVEAWAY KHỦNG! share bài tag 3 bạn nhận ngay iPhone 15 Pro! {fake_link()}",
            lambda: f"chúc mừng bạn đã trúng thưởng 5,000,000đ! nhận tại {fake_link()} trước 24h",
            lambda: f"EVENT {celeb().upper()} tặng 100 fan signed album! đăng ký tại {fake_link()} còn 5 slot",
            lambda: f"quét QR code nhận 1,000,000đ ngay! mã QR: {fake_link()} nhập thông tin ngân hàng",
            lambda: f"bạn là người thứ 1 triệu truy cập, nhận 500k! xác nhận tại {fake_link()}",
            lambda: f"minigame fb: like + share + tag 3 bạn = cơ hội nhận xe máy Honda! {fake_link()}",
            lambda: f"⚡ FLASH GIVEAWAY {celeb()} livestream tặng 10 fan laptop! đăng ký: {fake_link()}",
            lambda: f"Samsung tặng Galaxy S25 cho 50 khách hàng! verify số điện thoại: {fake_link()}",
            lambda: f"nhận voucher shopee 500k free! nhập số thẻ ngân hàng tại {fake_link()} để xác nhận",
            lambda: f"SPIN WHEEL nhận iPhone! quay tại {fake_link()} nộp phí vận chuyển 100k để nhận thưởng",
        ]
    }
]

# ── 9. Romance / grooming scam ────────────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "romance_grooming_scam",
        "age_focus": ["14-17"],
        "texts": [
            lambda: f"hi {name()} t thấy profile bạn hay quá kết bạn được không? t du học sinh ở Mỹ",
            lambda: f"chào {name()}, t là model đang casting ở HN, trông bạn dễ thương! nói chuyện thêm nhé",
            lambda: f"t muốn gặp bạn lắm nhưng cần tiền vé máy bay, cho t mượn 2tr được không {name()}?",
            lambda: f"{name()} ơi t đang kẹt ở sân bay cần 500k để về, giúp t với chuyển khoản {fake_link()}",
            lambda: f"t có quà từ nước ngoài gửi cho bạn nhưng phải nộp phí hải quan 300k: {fake_link()}",
            lambda: f"đừng nói với bố mẹ nhé, chuyển tiền riêng cho t qua ví: {fake_link()}",
            lambda: f"{name()} bạn xinh lắm, t muốn tặng quà nhưng cần bạn gửi ảnh trước nhé",
            lambda: f"t yêu bạn rồi {name()} ơi, cần tiền mua vé gặp bạn, chuyển 1tr cho t nhé: {fake_link()}",
        ]
    }
]

# ── 10. Fake streaming / account sharing scam ─────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "fake_streaming_account",
        "age_focus": ["11-13", "14-17"],
        "texts": [
            lambda: f"netflix premium 4K share acc giá 30k/tháng! thanh toán tại {fake_link()} uy tín",
            lambda: f"bán acc spotify premium 6 tháng chỉ 50k, chuyển khoản vào {fake_link()} nhận pass ngay",
            lambda: f"youtube premium family 1 năm chỉ 100k share! đặt hàng tại {fake_link()}",
            lambda: f"bán acc tiktok follow sẵn 10k giá 200k, đặt hàng tại {fake_link()} ship ngay",
            lambda: f"acc game rank cao bán rẻ, list tại {fake_link()} chuyển khoản là nhận pass",
            lambda: f"netflix + spotify + youtube combo 1 tháng chỉ 50k! đặt tại {fake_link()}",
            lambda: f"bán sub youtube 1000 sub thật chỉ 150k, order tại {fake_link()} uy tín không lừa",
        ]
    }
]

# ── 11. Fake scholarship / education scam ─────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "fake_scholarship",
        "age_focus": ["14-17"],
        "texts": [
            lambda: f"HỌC BỔNG 100% du học Mỹ 2026! đăng ký tại {fake_link()} nộp phí hồ sơ 2tr",
            lambda: f"tuyển học sinh xuất sắc học bổng toàn phần! điền form tại {fake_link()} phí xét duyệt 500k",
            lambda: f"học tiếng Anh miễn phí 3 tháng với giáo viên nước ngoài! đăng ký: {fake_link()} phí giáo trình 300k",
            lambda: f"khoá học lập trình python miễn phí từ MIT! đăng ký tại {fake_link()} nộp phí tài liệu 200k",
            lambda: f"học bổng chính phủ 50tr cho học sinh giỏi! nộp hồ sơ online tại {fake_link()} phí 1tr",
        ]
    }
]

# ── 12. OTP / SIM swap / phishing link ────────────────────────────────────────
SCAM_TEMPLATES += [
    {
        "scenario": "otp_phishing",
        "age_focus": ["11-13", "14-17"],
        "texts": [
            lambda: f"ngân hàng {name()} cần xác minh tài khoản! nhập OTP tại {fake_link()} để tránh khóa",
            lambda: f"momo của bạn sắp bị khóa! xác thực ngay tại {fake_link()} nhập otp trong 10 phút",
            lambda: f"tin nhắn từ vietcombank: tài khoản bất thường! đăng nhập xác minh: {fake_link()}",
            lambda: f"zalopay thông báo: nhận thưởng 200k! xác nhận số điện thoại tại {fake_link()}",
            lambda: f"có người đăng nhập fb của bạn từ nước ngoài! verify ngay tại {fake_link()}",
            lambda: f"mã otp của bạn là [ĐÃ ẨN] vui lòng nhập vào {fake_link()} để hoàn tất giao dịch",
        ]
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# SAFE TEMPLATES  (label = SAFE)
# ─────────────────────────────────────────────────────────────────────────────

SAFE_TEMPLATES: List[Dict] = []

SAFE_TEMPLATES += [
    {
        "scenario": "school_daily",
        "texts": [
            lambda: f"hôm nay học toán với thầy Nguyễn bài tập khó quá {name()} ơi",
            lambda: f"bạn nào giải được bài hình học trang 87 không chỉ t với",
            lambda: f"mai có kiểm tra văn t chưa ôn gì hết, ai có đề cương không?",
            lambda: f"hôm ni có buổi ngoại khóa học kỹ năng sống ở trường hay lắm",
            lambda: f"bài thể dục hôm nay mệt quá! nhưng vui {EMOJI_SAFE[0]}",
            lambda: f"ôn thi học kỳ nào ae ơi, môn lý khó quá t hơi lo",
            lambda: f"thầy giáo trả bài kiểm tra hôm nay t được 8 điểm vui quá!",
            lambda: f"ai đi học nhóm chiều nay không? t muốn ôn bài toán chương 3",
            lambda: f"bài tập tiếng anh hôm nay nhiều quá {name()} ơi cùng làm không",
            lambda: f"hôm nay trường có hội trại truyền thống vui lắm, mọi người chụp ảnh hết",
        ]
    },
    {
        "scenario": "gaming_normal",
        "texts": [
            lambda: f"ai chơi minecraft không? t vừa build xong cái nhà mới đẹp lắm",
            lambda: f"free fire rank hôm nay t leo được bạch kim III rồi! {name()} chơi chung không",
            lambda: f"bạn nào có skin ff đẹp không? t đang dùng skin mặc định hơi buồn",
            lambda: f"ml hôm nay t solo rank được 10 kill hay không nhỉ các bạn",
            lambda: f"roblox mới update thêm map mới hay lắm, mọi người thử chưa?",
            lambda: f"ai có kinh nghiệm leo rank pubg chỉ t với, t bị stuck ở gold mãi",
            lambda: f"t vừa mua skin mới trong game bằng tiền tiết kiệm sinh nhật, đẹp lắm!",
            lambda: f"hôm nay t bị thua liên tục trong ml, chắc cần luyện thêm hero mới",
            lambda: f"genshin impact version mới có nhân vật gì hay không các bạn?",
            lambda: f"t vừa clear được boss cuối trong game rpg mobile mới, khó vãi",
        ]
    },
    {
        "scenario": "entertainment",
        "texts": [
            lambda: f"ai xem phim spider-man mới chưa? hay không? t muốn rủ bạn đi xem",
            lambda: f"mọi người nghe nhạc gì dạo này? t đang obsess bài mới của {celeb()}",
            lambda: f"anime mùa này có gì hay không? t vừa xem xong demon slayer rồi",
            lambda: f"tập mới của {celeb()} hôm nay lên youtube hay lắm, mọi người xem chưa",
            lambda: f"hôm nay đi xem phim với gia đình, phim hoạt hình Disney mới hay lắm",
            lambda: f"ai có gợi ý series phim trên netflix không? xem hết rồi không biết xem gì",
            lambda: f"review sách 'dám bị ghét' hay lắm, ai thích đọc sách thử đọc nhé",
            lambda: f"podcast học tiếng anh của kênh này hay lắm, ai muốn t share link không",
            lambda: f"mùa giải bóng đá hôm nay đội t thắng 3-1 vui quá các bạn ơi",
            lambda: f"t vừa học được kỹ thuật vẽ mới, để t post ảnh lên cho mọi người xem",
        ]
    },
    {
        "scenario": "social_normal",
        "texts": [
            lambda: f"chúc mừng sinh nhật {name()} nha! chúc bạn nhiều sức khỏe và may mắn 🎉",
            lambda: f"cuối tuần này mọi người có rảnh không? đi cafe ngồi tám không",
            lambda: f"t mới học nấu ăn, làm được mì ý đầu tiên không đẹp lắm nhưng ăn được",
            lambda: f"hôm nay trời đẹp quá mọi người! ra ngoài chơi thể thao đi",
            lambda: f"t đang tập vẽ digital art, ai có gợi ý app tốt trên điện thoại không?",
            lambda: f"ai ở {name()} ơi đang học ôn đại học chưa? cùng học nhóm nhé",
            lambda: f"hôm nay lễ 30/4 gia đình t đi picnic vui lắm, chụp được nhiều ảnh đẹp",
            lambda: f"t muốn học coding python, bắt đầu từ đâu các bạn nhỉ?",
            lambda: f"ai có khuyến nghị sách tiếng anh cho trình độ intermediate không ạ",
            lambda: f"t vừa thi xong đợt tuyển thủ đội bóng trường, hi vọng được chọn",
        ]
    },
    {
        "scenario": "advice_genuine",
        "texts": [
            lambda: f"bạn nào bị bắt nạt ở trường nhớ báo cho thầy cô nhé, đừng im lặng",
            lambda: f"nhắc nhở: không chia sẻ mật khẩu cho ai kể cả bạn thân nha mọi người",
            lambda: f"ai gặp link lạ trên fb nhớ đừng click vào, dễ bị hack lắm!",
            lambda: f"tip bảo vệ tài khoản: bật 2FA cho tất cả app quan trọng nhé các bạn",
            lambda: f"nhớ uống đủ nước khi học bài nhé mọi người, quan trọng lắm đó",
            lambda: f"hôm nay t đọc được bài về nhận biết scam online hay lắm, share cho mọi người",
            lambda: f"ai có bạn bè bị lừa online nhớ giúp họ báo cáo cho cơ quan chức năng nhé",
            lambda: f"mẹo học bài: chia nhỏ ra học 25 phút nghỉ 5 phút, hiệu quả lắm đó",
        ]
    },
    {
        "scenario": "question_normal",
        "texts": [
            lambda: f"bạn nào biết công thức tính diện tích hình thang không chỉ t với",
            lambda: f"hỏi: khi nào thì dùng present perfect thay vì simple past vậy?",
            lambda: f"ai biết cách cài python trên windows không? t cần học lập trình",
            lambda: f"hỏi thật: học toán tốt cần luyện tập bao nhiêu bài mỗi ngày?",
            lambda: f"bạn nào học được guitar tự học ở nhà không? khuyến nghị kênh youtube đi",
            lambda: f"t đang phân vân chọn ngành đại học, ai có lời khuyên không?",
            lambda: f"hỏi: làm thế nào để cải thiện điểm tiếng anh nói? bị nhút nhát quá",
            lambda: f"ai có kinh nghiệm thi vào trường chuyên chỉ t ôn bài với",
        ]
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# GENERATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def build_text(template_fn) -> str:
    """Gọi lambda template, thêm teencode & emoji ngẫu nhiên."""
    raw = template_fn()
    raw = teen(raw)
    return raw.strip()

def generate_scam_samples(n: int) -> List[Dict]:
    samples = []
    all_fns = [(t["scenario"], t["age_focus"], fn)
               for t in SCAM_TEMPLATES
               for fn in t["texts"]]

    for _ in range(n):
        scenario, age_focus, fn = random.choice(all_fns)
        text = build_text(fn)
        text = emoji_append(text, EMOJI_SCAM)
        samples.append({
            "id": str(uuid.uuid4()),
            "text": text,
            "label": "FAKE_SCAM",
            "scenario": scenario,
            "age_focus": random.choice(age_focus),
            "source": "synthetic_v2",
            "generated_at": datetime.now().isoformat(),
        })
    return samples

def generate_safe_samples(n: int) -> List[Dict]:
    samples = []
    all_fns = [(t["scenario"], fn)
               for t in SAFE_TEMPLATES
               for fn in t["texts"]]

    for _ in range(n):
        scenario, fn = random.choice(all_fns)
        text = build_text(fn)
        text = emoji_append(text, EMOJI_SAFE)
        samples.append({
            "id": str(uuid.uuid4()),
            "text": text,
            "label": "SAFE",
            "scenario": scenario,
            "age_focus": random.choice(["8-10", "11-13", "14-17"]),
            "source": "synthetic_v2",
            "generated_at": datetime.now().isoformat(),
        })
    return samples

# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT WRITERS
# ─────────────────────────────────────────────────────────────────────────────

def write_raw_json(samples: List[Dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"  [raw JSON]   {path}  ({len(samples)} samples)")

def write_phobert_jsonl(samples: List[Dict], path: str):
    """Format cho PhoBERT fine-tune: {text, label_id} per line."""
    label_map = {"SAFE": 0, "FAKE_SCAM": 1}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for s in samples:
            rec = {
                "text": s["text"],
                "label": label_map.get(s["label"], 1),
                "label_str": s["label"],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  [PhoBERT JSONL] {path}  ({len(samples)} lines)")

def write_xgboost_csv(samples: List[Dict], path: str):
    """Lightweight feature CSV cho XGBoost re-training."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def extract_features(text: str) -> Dict:
        t = text.lower()
        return {
            "text_len":         len(text),
            "word_count":       len(text.split()),
            "has_url":          int(bool(re.search(r'https?://', t))),
            "has_shortlink":    int(bool(re.search(r'bit\.ly|tinyurl|cutt\.ly|t\.co|rb\.gy', t))),
            "exclaim_count":    text.count("!"),
            "caps_ratio":       sum(1 for c in text if c.isupper()) / max(len(text), 1),
            "has_free":         int("free" in t or "miễn phí" in t or "tặng" in t),
            "has_money":        int(bool(re.search(r'robux|kim cương|diamond|xu |usdt|vnđ|vnđ|triệu|ngàn đồng|\d+k\b', t))),
            "has_urgency":      int(bool(re.search(r'nhanh|gấp|hôm nay|còn \d+|24h|hết hạn|chỉ hôm nay', t))),
            "has_click_cta":    int(bool(re.search(r'click|tap vào|nhấp|vào đây|link|đường link|tại đây', t))),
            "has_otp_pass":     int(bool(re.search(r'otp|mật khẩu|password|pass |verify|xác minh', t))),
            "has_prize":        int(bool(re.search(r'giveaway|trúng thưởng|nhận ngay|quà|prize|nhận tiền', t))),
            "has_crypto":       int(bool(re.search(r'usdt|nft|airdrop|metamask|seed phrase|crypto|blockchain', t))),
            "has_job_scam":     int(bool(re.search(r'ctv|cộng tác viên|lương \d|phí kích hoạt|phí đào tạo|phí bảo đảm', t))),
            "teen_code_count":  sum(1 for w in ["t ", "m ", "bn ", "ko ", "k ", "dc ", "r "] if w in t),
        }

    fieldnames = ["text", "label"] + list(extract_features("sample").keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in samples:
            row = {"text": s["text"], "label": s["label"]}
            row.update(extract_features(s["text"]))
            writer.writerow(row)
    print(f"  [XGBoost CSV]  {path}  ({len(samples)} rows)")

def write_report(samples: List[Dict], path: str):
    label_counts = {}
    scenario_counts = {}
    age_counts = {}
    for s in samples:
        label_counts[s["label"]] = label_counts.get(s["label"], 0) + 1
        scenario_counts[s["scenario"]] = scenario_counts.get(s["scenario"], 0) + 1
        age_counts[s["age_focus"]] = age_counts.get(s["age_focus"], 0) + 1

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_samples": len(samples),
        "label_distribution": label_counts,
        "scenario_distribution": scenario_counts,
        "age_focus_distribution": age_counts,
        "note": "100% synthetic data — Privacy-by-Design. No real user data collected.",
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  [Report JSON]  {path}")
    return report

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print("  ViFake — Synthetic Training Data Generator v2")
    print(f"  SCAM samples : {NUM_SCAM_SAMPLES}")
    print(f"  SAFE samples : {NUM_SAFE_SAMPLES}")
    print(f"  Total        : {NUM_SCAM_SAMPLES + NUM_SAFE_SAMPLES}")
    print("  Privacy      : 100% synthetic, no real data")
    print("=" * 60)

    print("\n[1/4] Generating scam samples...")
    scam = generate_scam_samples(NUM_SCAM_SAMPLES)

    print("[2/4] Generating safe samples...")
    safe = generate_safe_samples(NUM_SAFE_SAMPLES)

    all_samples = scam + safe
    random.shuffle(all_samples)

    print("\n[3/4] Writing output files...")
    write_raw_json(all_samples,    f"{OUTPUT_DIR}/training_samples_{ts}.json")
    write_phobert_jsonl(all_samples, f"{OUTPUT_DIR}/phobert_train.jsonl")
    write_xgboost_csv(all_samples,  f"{OUTPUT_DIR}/xgboost_features.csv")

    print("\n[4/4] Writing report...")
    report = write_report(all_samples, f"{OUTPUT_DIR}/generation_report_{ts}.json")

    print("\n" + "=" * 60)
    print("  DONE!")
    print(f"  Total samples : {report['total_samples']}")
    for k, v in sorted(report["label_distribution"].items()):
        pct = v / report["total_samples"] * 100
        print(f"    {k:<12} {v:>5} ({pct:.1f}%)")
    print("\n  Scenarios covered:")
    for k, v in sorted(report["scenario_distribution"].items(), key=lambda x: -x[1]):
        print(f"    {k:<35} {v:>4}")
    print("\n  Age focus:")
    for k, v in sorted(report["age_focus_distribution"].items()):
        print(f"    {k:<10} {v:>4}")
    print("=" * 60)

if __name__ == "__main__":
    main()
