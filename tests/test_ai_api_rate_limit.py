from fastapi.testclient import TestClient

from jafar import main


class _Limiter:
    def __init__(self, result=True, fail=False):
        self.result = result
        self.fail = fail
        self.keys = []

    def allow(self, key: str) -> bool:
        self.keys.append(key)
        if self.fail:
            raise RuntimeError("database unavailable")
        return self.result


def test_ai_analysis_returns_429_before_dispatch_when_rate_limit_is_exhausted(monkeypatch) -> None:
    limiter = _Limiter(result=False)
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    monkeypatch.setattr(main.settings, "ai_rate_limit_window_seconds", 60)
    monkeypatch.setattr(main, "ai_rate_limiter", limiter)

    response = TestClient(main.app).post(
        "/v1/analyze",
        json={"text": "test", "task": "legal_analysis", "matter_type": "general"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert limiter.keys == ["/v1/analyze"]


def test_ai_rate_limit_backend_failure_is_fail_closed(monkeypatch) -> None:
    limiter = _Limiter(fail=True)
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    monkeypatch.setattr(main, "ai_rate_limiter", limiter)

    response = TestClient(main.app).post(
        "/v1/analyze",
        json={"text": "test", "task": "legal_analysis", "matter_type": "general"},
    )

    assert response.status_code == 503
    assert "rate-limit safety service unavailable" in response.json()["detail"]


def test_non_ai_dashboard_is_not_consumed_by_ai_rate_limiter(monkeypatch) -> None:
    limiter = _Limiter(result=False)
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    monkeypatch.setattr(main, "ai_rate_limiter", limiter)

    response = TestClient(main.app).get("/v1/dashboard")

    assert response.status_code == 200
    assert limiter.keys == []
