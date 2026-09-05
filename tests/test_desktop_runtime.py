from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.desktop_runtime import LOOPBACK_HOST, desktop_paths
from jafar.desktop_sidecar import main


def test_desktop_paths_are_app_owned_and_never_inside_an_app_bundle(tmp_path: Path) -> None:
    paths = desktop_paths(tmp_path / "JAFAR").create()

    assert paths.application_support == tmp_path / "JAFAR"
    assert paths.logs == tmp_path / "JAFAR" / "Logs"
    assert paths.cache == tmp_path / "JAFAR" / "Caches"
    assert all(path.is_dir() for path in (paths.application_support, paths.logs, paths.cache))
    assert ".app" not in str(paths.application_support)


def test_desktop_sidecar_rejects_non_loopback_and_missing_ephemeral_token(monkeypatch) -> None:
    monkeypatch.delenv("JAFAR_DESKTOP_IPC_TOKEN", raising=False)
    assert main(["--host", LOOPBACK_HOST, "--port", "8123"]) == 2

    monkeypatch.setenv("JAFAR_DESKTOP_IPC_TOKEN", "a" * 32)
    assert main(["--host", "0.0.0.0", "--port", "8123"]) == 2

    monkeypatch.setenv("JAFAR_DESKTOP_PARENT_PID", "not-a-pid")
    assert main(["--host", LOOPBACK_HOST, "--port", "8123"]) == 2


def test_desktop_ipc_requires_ephemeral_bearer_for_every_private_route(monkeypatch) -> None:
    monkeypatch.setenv("JAFAR_RUNTIME_MODE", "desktop")
    monkeypatch.setenv("JAFAR_DESKTOP_IPC_TOKEN", "a" * 32)
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/oauth/google/callback")
    def callback():
        return {"status": "connected"}

    @app.get("/v1/private")
    def private():
        return {"status": "ok"}

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/v1/private").status_code == 401
    assert client.get("/v1/oauth/google/callback").status_code == 401
    assert client.get("/v1/private", headers={"Authorization": "Bearer " + "a" * 32}).status_code == 200
