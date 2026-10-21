"""Builds the database URL. Passing host, user and password separately avoids URL-escaping bugs: a password
containing '@', ':', '/', '%' or '#' would corrupt a hand-assembled DATABASE_URL."""
import os
from collections.abc import Mapping

from sqlalchemy.engine import URL


def resolve_database_url(explicit: str | None = None, env: Mapping[str, str] | None = None) -> str | URL:
    env = os.environ if env is None else env
    explicit = explicit or env.get("DATABASE_URL")
    if explicit:
        return explicit
    missing = [k for k in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not env.get(k)]
    if missing:
        raise RuntimeError("Set DATABASE_URL, or all of DB_HOST, DB_NAME, DB_USER and DB_PASSWORD. Missing: " + ", ".join(missing))
    return URL.create(
        "mysql+pymysql",
        username=env["DB_USER"],
        password=env["DB_PASSWORD"],
        host=env["DB_HOST"],
        port=int(env.get("DB_PORT") or 3306),
        database=env["DB_NAME"],
    )
