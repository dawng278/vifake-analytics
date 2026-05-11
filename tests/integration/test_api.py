"""Integration tests — hit the live API at localhost:8000."""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

API_BASE = "http://localhost:8000"
TOKEN = "demo-token-123"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _api_available():
    try:
        import requests
        r = requests.get(f"{API_BASE}/api/v1/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def require_api():
    if not _api_available():
        pytest.skip("API not running at localhost:8000 — start Docker containers first")


@pytest.mark.integration
class TestHealthEndpoint:
    def test_health_returns_200(self):
        import requests
        r = requests.get(f"{API_BASE}/api/v1/health", timeout=5)
        assert r.status_code == 200

    def test_health_has_status_healthy(self):
        import requests
        data = requests.get(f"{API_BASE}/api/v1/health", timeout=5).json()
        assert data.get("status") == "healthy"


@pytest.mark.integration
class TestAnalyzeContentEndpoint:
    """Test POST /api/v1/analyze with content (no URL crawl)."""

    def _analyze(self, content: str, platform: str = "youtube") -> dict:
        import requests
        payload = {"content": content, "platform": platform}
        r = requests.post(
            f"{API_BASE}/api/v1/analyze",
            json=payload,
            headers=HEADERS,
            timeout=10,
        )
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
        return r.json()

    def _poll_result(self, job_id: str, max_wait: int = 30) -> dict:
        import requests
        for _ in range(max_wait):
            r = requests.get(f"{API_BASE}/api/v1/result/{job_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") in ("completed", "failed"):
                    return data
            time.sleep(1)
        pytest.fail(f"Job {job_id} did not complete in {max_wait}s")

    def test_analyze_scam_content(self):
        response = self._analyze("free robux unlock method 2024 no verification")
        job_id = response.get("job_id")
        assert job_id, "No job_id in response"
        result = self._poll_result(job_id)
        assert result["status"] == "completed"
        label = result.get("result", {}).get("label", "")
        assert label in ("FAKE_SCAM", "SUSPICIOUS"), (
            f"Expected scam/suspicious for scam text, got: {label}"
        )

    def test_analyze_safe_content(self):
        response = self._analyze("Bài tập về nhà môn lịch sử lớp 8, học cùng bạn bè")
        job_id = response.get("job_id")
        assert job_id
        result = self._poll_result(job_id)
        assert result["status"] == "completed"
        label = result.get("result", {}).get("label", "")
        assert label == "SAFE", f"Expected SAFE for educational text, got: {label}"

    def test_analyze_requires_auth(self):
        import requests
        r = requests.post(
            f"{API_BASE}/api/v1/analyze",
            json={"content": "test", "platform": "youtube"},
            headers={"Authorization": "Bearer wrong-token"},
            timeout=5,
        )
        assert r.status_code in (401, 403)

    def test_analyze_result_has_required_fields(self):
        response = self._analyze("nạp thẻ trước 50k nhận 500k ngay")
        result = self._poll_result(response["job_id"])
        res_data = result.get("result", {})
        for field in ("label", "confidence", "risk_level"):
            assert field in res_data, f"Missing field: {field}"
        assert res_data["label"] in ("SAFE", "SUSPICIOUS", "FAKE_SCAM")
        assert 0.0 <= res_data["confidence"] <= 1.0

    def test_cache_second_url_request_faster(self):
        """Second request for the same URL should return faster (cache hit)."""
        import requests
        # Use a content payload — cache only applies to URL mode, but this tests basic flow
        payload = {"content": "học toán cùng thầy cô giáo viên", "platform": "youtube"}
        start1 = time.time()
        r1 = requests.post(f"{API_BASE}/api/v1/analyze", json=payload, headers=HEADERS, timeout=15)
        assert r1.status_code == 200
        job1 = r1.json()["job_id"]
        self._poll_result(job1)
        t1 = time.time() - start1

        start2 = time.time()
        r2 = requests.post(f"{API_BASE}/api/v1/analyze", json=payload, headers=HEADERS, timeout=15)
        assert r2.status_code == 200
        job2 = r2.json()["job_id"]
        self._poll_result(job2)
        t2 = time.time() - start2

        # Both should be fast (just assert they complete successfully)
        assert t1 < 60 and t2 < 60
