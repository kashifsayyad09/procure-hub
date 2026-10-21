# Security notes (Phase 2)

## What is enforced
- **Authorization is server-side.** Every protected route checks the token, then loads the user so a role change or suspension takes effect immediately. Route guards in React only improve navigation.
- **Passwords:** argon2id, per-password salt, rehash on login when parameters change. Policy: 12 to 128 characters, a letter and a number, not containing the email name. Verifying an unknown email runs against a dummy hash to equalise timing.
- **Login abuse:** 5 failed attempts lock the account for 15 minutes. Wrong password and unknown email return the identical message.
- **Tokens:** access JWT pinned to HS256 with issuer, audience, expiry and type checks (`alg=none`, other algorithms, wrong secret, wrong audience and refresh-as-access are tested). Refresh tokens are opaque, hashed at rest, rotated on every use, and a late reuse revokes the whole family.
- **Browser storage:** no token in localStorage or sessionStorage. The access token is in memory; the refresh token is an HttpOnly, SameSite=Strict cookie limited to `/api/v1/auth`.
- **Secrets:** no defaults. The service refuses to start without `DATABASE_URL` and a `JWT_SECRET` of 32+ characters. The first admin is created with a CLI and a password you supply; there is no built-in account.
- **Least privilege:** the MySQL user `auth_svc` can reach only `auth_db` (tested: access to another database is denied). The init script rejects passwords containing quotes or backslashes so they cannot alter the SQL.
- **Database password handling:** passed as a separate variable and URL-encoded by the code, so characters such as `@`, `:`, `/`, `%` and `#` are safe.
- **Removed from Phase 1:** the unauthenticated role previews and `/app/*` access.
- Auth responses are `Cache-Control: no-store`. Logs are JSON and never contain passwords or tokens.

## Known limitations (later phases)
- No per-IP rate limiting yet (ingress, Phase 14). The 429 lockout response confirms an email exists, but only after repeated failures against it.
- No password reset by email (Phase 10), no forced change of an admin-set initial password, no MFA.
- Security events go to structured logs; they reach the Audit service in Phase 10.
- Access tokens use a shared secret. Services that verify them locally see a role change up to 15 minutes late; consider asymmetric keys before production.
- The Docker image and Compose stack were not run here (no Docker). The service and scripts were tested against a real MySQL 8.0 server instead.
- `npm audit` and `pip-audit` were clean when run. Re-run before each release.
