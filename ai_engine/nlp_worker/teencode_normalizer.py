"""
Teencode Normalizer for Vietnamese social media text.

Converts teen-code abbreviations and shorthand to standard Vietnamese
before NLP analysis, improving scam detection accuracy.

Critical mappings:
  mk/pass/pw → mật khẩu (password — high scam signal)
  tk/acc      → tài khoản (account — high scam signal)
  lk/link     → đường dẫn (URL — medium scam signal)
  free/fre    → miễn phí (free — scam bait)
"""
import re
import json
import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

_DICT_PATH = os.path.join(os.path.dirname(__file__), "teencode_dict.json")


@lru_cache(maxsize=1)
def _load_dict() -> dict:
    try:
        with open(_DICT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"teencode_dict.json not found or unreadable: {e}")
        return {}


def normalize(text: str) -> str:
    """Normalize teen-code in *text* and return cleaned string.

    Strategy:
    1. Word-boundary token replacement for dictionary entries.
    2. Preserves punctuation and emoji (only replaces matching tokens).
    3. Case-insensitive matching; output preserves original case cadence.
    """
    if not text or not isinstance(text, str):
        return text

    mapping = _load_dict()
    if not mapping:
        return text

    # Sort by length descending so multi-word entries match before subsets
    sorted_keys = sorted(mapping.keys(), key=len, reverse=True)

    normalized = text
    for key in sorted_keys:
        # Match whole word/phrase (word boundary aware, case-insensitive)
        pattern = r'(?<!\w)' + re.escape(key) + r'(?!\w)'
        replacement = mapping[key]
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    return normalized


def normalize_tokens(tokens: list) -> list:
    """Normalize a list of string tokens (whitespace-split words)."""
    mapping = _load_dict()
    result = []
    for tok in tokens:
        lower = tok.lower()
        result.append(mapping.get(lower, tok))
    return result


def contains_high_risk_teencode(text: str) -> bool:
    """Return True if text contains teencode for password/account keywords.

    These are the strongest scam signals in teen-code:
      mk, pass, pw  → 'mật khẩu'
      tk, acc       → 'tài khoản'
    """
    HIGH_RISK_KEYS = {"mk", "pass", "pw", "tk", "acc", "lấy mk", "lấy pass",
                      "share mk", "share pass", "cho mk", "cho pass",
                      "mất tk", "mất acc", "đổi mk", "đổi pass",
                      "ban acc", "bị ban",
                      # Gaming scam signals
                      "rbx", "rob", "rbux",           # robux abbreviations
                      "cho acc", "cho nick",           # account giving
                      "đưa acc", "mượn acc",           # account lending
                      "trade acc", "swap acc",         # account trading
                      "nhập code",                     # code injection (cookie logger)
                      "drop trade", "dup", "dupe",     # item duplication scam
                      }
    text_lower = text.lower()
    return any(
        bool(re.search(r'(?<!\w)' + re.escape(k) + r'(?!\w)', text_lower))
        for k in HIGH_RISK_KEYS
    )
