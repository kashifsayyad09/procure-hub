# API (Phase 2: authentication service)

Base path `/api/v1`. Interactive OpenAPI docs: `/docs` on the service (disable with `DOCS_ENABLED=false`).
The browser always calls same-origin `/api/v1/...`; Vite proxies it in development and the ingress will in production.

## Sessions
- **Access token:** JWT (HS256, 15 minutes) returned in the response body. The frontend keeps it in memory only and sends `Authorization: Bearer ...`.
- **Refresh token:** random 384-bit value in an `HttpOnly; SameSite=Strict; Path=/api/v1/auth` cookie (`Secure` unless `COOKIE_SECURE=false`). Single use: every refresh issues a new one. Stored hashed (SHA-256).
- Claims: `iss`, `aud`, `sub` (user id), `role`, `typ=access`, `jti`, `iat`, `exp`.

## Endpoints
| Method and path | Who | Result |
|---|---|---|
| `POST /auth/login` `{email, password}` | anyone | 200 token + user + permissions, sets cookie. 401 wrong credentials, 403 suspended, 429 locked |
| `POST /auth/refresh` | cookie | 200 new token and cookie. 401 invalid, expired or reused (a late reuse revokes the whole session family) |
| `POST /auth/logout` | cookie | 204, revokes the session family, clears cookie |
| `POST /auth/logout-all` | signed in | 204, revokes every session of the user |
| `GET /auth/me` | signed in | current user and permissions |
| `POST /auth/change-password` | signed in | 204, ends all sessions. 400 wrong current password, 422 policy |
| `GET /users` | `user:read` | paged list. Query: `q`, `role`, `is_active`, `page`, `page_size` (max 100) |
| `POST /users` | `user:manage` | 201. 409 duplicate email, 422 policy |
| `GET /users/{id}` | `user:read` | 404 if unknown |
| `PATCH /users/{id}` | `user:manage` | change `full_name`, `role`, `is_active`. A role change or suspension ends the user's sessions. 409 if you target yourself |
| `GET /health/live`, `GET /health/ready` | open | liveness, and readiness (checks the database) |

## Roles and permissions
`employee`, `manager`, `procurement`, `vendor`, `finance`, `admin`. The full matrix is in `app/permissions.py`
(for example only `admin` holds `user:manage` and `role:assign`, only `manager` holds `approval:decide`). Later services reuse these names.

Errors are `{"detail": "message"}` (or a list of messages for validation). Every response carries `X-Request-ID`.
