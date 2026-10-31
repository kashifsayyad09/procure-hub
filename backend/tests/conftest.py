"""Starts the auth, purchase request and approval services as real processes (SQLite files, real HTTP between them)
so the whole procurement hand-off can be tested, including what happens when one service is down."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parent.parent
SERVICES = {"auth": ("auth-service", "auth.db"), "pr": ("purchase-request-service", "pr.db"), "approval": ("approval-service", "approval.db")}
PASSWORD = "Valid-Passw0rd-2026"  # contains no one's email name, so it passes the password policy


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(check, timeout=20.0, interval=0.25, message="condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = check()
            if last:
                return last
        except Exception as e:  # noqa: BLE001  (service may still be starting)
            last = e
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {message}; last: {last!r}")


class Stack:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.ports = {k: free_port() for k in SERVICES}
        self.procs: dict[str, subprocess.Popen] = {}
        self.tokens: dict[str, str] = {}
        secret = "e2e-user-secret-" + "u" * 32
        internal = "e2e-internal-secret-" + "i" * 32
        self.base_env = {**os.environ, "JWT_SECRET": secret, "INTERNAL_JWT_SECRET": internal, "COOKIE_SECURE": "false", "LOG_LEVEL": "WARNING",
                         "BACKGROUND_JOBS": "true", "RECONCILE_INTERVAL_SECONDS": "1", "ESCALATION_HOURS": "48"}
        for k in ("DATABASE_URL", "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            self.base_env.pop(k, None)

    def env(self, name: str) -> dict:
        e = dict(self.base_env)
        # E2E_AUTH_DB_URL, E2E_PR_DB_URL, E2E_APPROVAL_DB_URL run the same tests against MySQL instead of SQLite files
        e["DATABASE_URL"] = os.environ.get(f"E2E_{name.upper()}_DB_URL") or f"sqlite:///{self.tmp / SERVICES[name][1]}"
        if name == "pr":
            e["APPROVAL_SERVICE_URL"] = self.url("approval")
        if name == "approval":
            e["PURCHASE_REQUEST_SERVICE_URL"] = self.url("pr")
            e["AUTH_SERVICE_URL"] = self.url("auth")
        return e

    def url(self, name: str) -> str:
        return f"http://127.0.0.1:{self.ports[name]}"

    def cwd(self, name: str) -> Path:
        return BACKEND / "services" / SERVICES[name][0]

    def migrate(self, name: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=self.cwd(name), env=self.env(name), check=True, capture_output=True)

    def start(self, name: str) -> None:
        log = open(self.tmp / f"{name}.log", "ab")  # noqa: SIM115
        self.procs[name] = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(self.ports[name])],
                                            cwd=self.cwd(name), env=self.env(name), stdout=log, stderr=subprocess.STDOUT)
        wait_until(lambda: httpx.get(self.url(name) + "/health/live", timeout=1).status_code == 200, message=f"{name} to start")

    def stop(self, name: str) -> None:
        p = self.procs.pop(name, None)
        if p:
            p.terminate()
            p.wait(timeout=10)

    def stop_all(self) -> None:
        for n in list(self.procs):
            self.stop(n)

    def call(self, service: str, method: str, path: str, token: str | None = None, **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return httpx.request(method, self.url(service) + path, headers=headers, timeout=10, **kw)

    def login(self, email: str) -> str:
        r = self.call("auth", "POST", "/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]

    def make_user(self, email: str, name: str, role: str) -> dict:
        r = self.call("auth", "POST", "/api/v1/users", self.tokens["admin"], json={"email": email, "full_name": name, "role": role, "password": PASSWORD})
        assert r.status_code == 201, r.text
        self.tokens[email] = self.login(email)
        return r.json()


@pytest.fixture(scope="session")
def stack(tmp_path_factory):
    s = Stack(tmp_path_factory.mktemp("stack"))
    try:
        for n in SERVICES:
            s.migrate(n)
        subprocess.run([sys.executable, "-m", "app.cli", "create-admin", "--email", "root@example.com", "--name", "Root Admin"], cwd=s.cwd("auth"),
                       env={**s.env("auth"), "ADMIN_PASSWORD": PASSWORD}, check=True, capture_output=True)
        for n in ("auth", "pr", "approval"):
            s.start(n)
        s.tokens["admin"] = s.login("root@example.com")
        for email, name, role in [("erin@example.com", "Erin Employee", "employee"), ("emma@example.com", "Emma Employee", "employee"),
                                  ("mia@example.com", "Mia Manager", "manager"), ("max@example.com", "Max Manager", "manager"), ("mona@example.com", "Mona Manager", "manager"),
                                  ("pat@example.com", "Pat Procurement", "procurement"), ("vera@example.com", "Vera Vendor", "vendor")]:
            s.make_user(email, name, role)
        yield s
    finally:
        s.stop_all()
        for log in s.tmp.glob("*.log"):
            if os.environ.get("E2E_SHOW_LOGS"):
                print(f"--- {log.name}\n{log.read_text()[-2000:]}")
