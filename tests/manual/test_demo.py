#!/usr/bin/env python3
import urllib.request, json, time, sys

def post(url, data, headers):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=15) as r: return json.load(r)

def get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r: return json.load(r)

def poll_job(base, job_id, headers, poll_interval=1.0, max_wait=45):
    """Poll job status until completed/failed or timeout."""
    deadline = time.time() + max_wait
    attempt = 0
    while time.time() < deadline:
        try:
            j = get(f"{base}/api/v1/job/{job_id}", headers)
            status = j.get('status', '')
            if status == 'completed':
                return j
            if status == 'failed':
                return {'error': j.get('error', 'job failed'), 'status': 'failed'}
        except Exception as e:
            pass  # transient network error — keep polling
        # Adaptive delay: fast at first, back off after a few tries
        delay = 0.5 if attempt < 3 else (1.0 if attempt < 8 else 2.0)
        time.sleep(delay)
        attempt += 1
    return {'error': f'Timed out after {max_wait}s', 'status': 'timeout'}

H = {'Authorization': 'Bearer vifake-demo-2024', 'Content-Type': 'application/json'}
BASE = 'http://localhost:8000'

# --- Health check before running tests ---
try:
    health = get(BASE + '/api/v1/health', {})
    print(f"✅ API is healthy — active_jobs={health.get('active_jobs',0)}\n")
except Exception as e:
    print(f"❌ Cannot reach API at {BASE}: {e}")
    print("   Make sure the server is running: python backend_services/api_gateway/main.py")
    sys.exit(1)

tests = [
    ("SCAM Robux",   "Ib mình để nhận 80,000 Robux miễn phí! Cần nạp thẻ trước 50k để xác nhận acc nha m.", "FAKE_SCAM"),
    ("GIVEAWAY",     "GIVEAWAY khủng! Share bài này + tag 3 bạn = nhận ngay iPhone 15 Pro! Chỉ còn 2 giờ!!!", "FAKE_SCAM"),
    ("USDT Crypto",  "Gửi 0.01 ETH về ví MetaMask này nhận lại 0.05 ETH. USDT airdrop còn 100 slot!", "FAKE_SCAM"),
    ("OTP Lừa Đảo", "Admin game nhắn tin yêu cầu bạn nhập OTP để nhận thưởng sự kiện. Nhập ngay tại đây!", "FAKE_SCAM"),
    ("AN TOÀN",      "Hôm nay mình học toán với thầy Nguyễn, bài tập khá hay các bạn ơi!", "SAFE"),
    ("SAFE Gaming",  "Team t vừa leo rank bạch kim III rồi! Ai muốn duo queue không?", "SAFE"),
]

print("=== ViFake Demo Test ===\n")
passed = 0
total = len(tests)

for name, txt, expected in tests:
    t0 = time.time()
    try:
        r = post(BASE+'/api/v1/analyze',
                 {'url':'https://demo.local','platform':'facebook','priority':'high','content':txt}, H)
        jid = r.get('job_id')
        if not jid:
            print(f"❌ [{name}] — no job_id in response: {r}")
            continue

        j = poll_job(BASE, jid, H)
        elapsed = time.time() - t0

        if j.get('error'):
            print(f"❌ [{name}] — {j['error']} ({elapsed:.1f}s)")
            continue

        res = j.get('result', {})
        det = res.get('analysis_details', {})
        label = res.get('label', '?')
        ok = label == expected
        if ok:
            passed += 1
        icon = "✅" if ok else "❌"
        print(f"{icon} [{name}]  ({elapsed:.1f}s)")
        print(f"   label={label} (expected {expected})  risk={res.get('risk_level')}  conf={res.get('confidence',0):.2f}")
        print(f"   nlp_conf={det.get('nlp_confidence','?')}  vision_conf={det.get('vision_confidence','?')}")
        flags = det.get('nlp_flags', [])
        if flags:
            print(f"   flags={flags[:4]}")

    except Exception as e:
        print(f"❌ [{name}] — Exception: {e}")
    print()

print(f"Result: {passed}/{total} passed")
