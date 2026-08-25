from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request_json(url: str, *, api_key: str | None = None, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Jafar-API-Key"] = api_key
    request = Request(url, data=data, headers=headers, method="POST" if payload else "GET")
    with urlopen(request, timeout=2) as response:  # noqa: S310 - loopback smoke only.
        return json.loads(response.read().decode("utf-8"))


def _wait_for_health(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = _request_json(f"{base_url}/health")
            if result.get("status") == "ok":
                return
        except (URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"backend did not become healthy: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start a loopback-only Jafar backend with an ephemeral API key and smoke /v1/command."
    )
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--hold",
        action="store_true",
        help="keep the backend running for a manual Apple -> /v1/command smoke test",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    port = args.port or _free_port()
    api_key = secrets.token_urlsafe(24)
    base_url = f"http://127.0.0.1:{port}"
    command_url = f"{base_url}/v1/command"

    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "staging",
            "API_KEY": api_key,
            "EXTERNAL_AI_ENABLED": "false",
            "TELEGRAM_POLLING_ENABLED": "false",
            "PYTHONPATH": str(repo_root / "src"),
        }
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "jafar.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=repo_root,
        env=env,
    )

    try:
        _wait_for_health(base_url)
        response = _request_json(
            command_url,
            api_key=api_key,
            payload={
                "text": "проверка связи",
                "user_id": "private-beta-smoke",
                "source_device": "mac",
            },
        )
        if response.get("intent") != "health":
            raise RuntimeError(f"unexpected command response: {response}")

        print("PRIVATE BETA BACKEND SMOKE: PASS")
        print(f"APPLE_ENDPOINT={command_url}")
        print(f"EPHEMERAL_API_KEY={api_key}")
        print("The key is temporary and is not written to Git or disk by this script.")

        if args.hold:
            print("Backend is running on loopback. Press Ctrl-C after the Apple smoke test.")
            while process.poll() is None:
                time.sleep(1)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
