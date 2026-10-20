"""Create the first administrator. There is no default account.

    ADMIN_PASSWORD=... python -m app.cli create-admin --email you@company.com --name "Your Name"

If ADMIN_PASSWORD is not set the password is prompted for without echo.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select

from .config import get_settings
from .database import make_engine, make_session_factory
from .models import Role, User
from .security import hash_password, password_policy_errors


def create_admin(email: str, name: str, password: str, session_factory) -> str:
    email = email.strip().lower()
    problems = password_policy_errors(password, email)
    if problems:
        raise SystemExit("Password rejected: " + " ".join(problems))
    with session_factory() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("A user with that email already exists.")
        user = User(email=email, full_name=name.strip(), role=Role.ADMIN.value, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        return user.id


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    engine = make_engine(get_settings().database_url)
    uid = create_admin(args.email, args.name, password, make_session_factory(engine))
    print(f"Created administrator {args.email} ({uid})")


if __name__ == "__main__":
    sys.exit(main())
