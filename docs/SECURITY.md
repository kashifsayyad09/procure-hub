# Security notes (Phase 1)

- No secrets in source. `.env` is git-ignored; `.env.example` holds placeholders. Compose refuses to start without `MYSQL_ROOT_PASSWORD`.
- MySQL is bound to 127.0.0.1 only.
- The login form validates input in the browser and sends nothing anywhere. It does not simulate a successful sign-in.
- `/app/<role>` previews are unauthenticated in Phase 1 and show sample data only. Phase 2 adds backend-enforced authentication and role authorization; frontend route guards are a convenience, not the control.
- Dependencies are pinned; run `npm audit` before each release (not run in this phase).
