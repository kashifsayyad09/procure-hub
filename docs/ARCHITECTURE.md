# Architecture (Phase 1 snapshot)

Target architecture is defined in the master build prompt: 11 FastAPI business services plus API gateway and MCP server on EKS, MySQL on RDS, SQS, NGINX ingress, Terraform, GitHub Actions and Argo CD. Phase 1 implements only the frontend foundation and the local database container.

## Frontend structure
- `src/components/ui` primitives; `layout` shell and dashboard template; `tables`, `charts`, `forms`
- `src/animations/gsap`: single GSAP entry (ScrollTrigger registered once), `useGsap` (scoped context, reverts on unmount, skipped under reduced motion), `useCountUp`, presets
- `src/three`: `SceneBackdrop` (lazy, WebGL and reduced-motion fallback) and `ParticleNetwork` (R3F, pauses when tab hidden)
- `src/stores`: Zustand for theme and sidebar; TanStack Query for server state
- `src/services/mockData.ts`: sample data and a simulated fetch, replaced by real APIs from Phase 2

## Performance
Three.js and Recharts are in lazy chunks and are not part of the entry bundle (entry about 120 kB gzip).

## Phase 2 additions
```
Browser --/api/v1--> (Vite proxy in dev, ingress later) --> auth-service --> auth_db
```
- `backend/services/auth-service`: FastAPI app factory (`app.main:create_app`), SQLAlchemy 2, Alembic, Pydantic settings, JSON logging with request IDs.
- Frontend: `services/api.ts` (memory token, one shared silent refresh, one retry), `stores/authStore.ts`, `components/auth/RequireAuth.tsx`, `pages/admin/UsersPage.tsx`.
- Other services will verify the same JWT (shared secret, issuer and audience) and check the permission they need.

## Phase 3 additions
```
Browser --/api/v1--> Vite proxy (dev) --+--> auth-service (8001)             --> auth_db
                     ingress (later)    +--> purchase-request-service (8002) --> purchase_request_db
```
- **Shared package** `backend/shared/procurehub_common`: roles, permission matrix, token verification, logging, request-ID middleware, health routes, DB URL builder. No database models, so services stay independent.
- **Token flow:** the auth service signs the access token (it now also carries the user's name and email). The Purchase Request service verifies the signature, issuer, audience and expiry itself and takes the role from the token. It never calls the auth service per request and has no foreign key to its users.
- **Purchase request service layers:** thin routers, `service.py` for business rules and ownership, SQLAlchemy models, Pydantic schemas. History and documents carry an explicit sequence number because MySQL timestamps only have one-second precision.
- **Frontend:** `features/purchase-requests` (types, exact money helpers, status badge, timeline), employee pages for the dashboard, list, multi-step form and detail. The employee dashboard now uses real data; the other roles still use sample data.
- **Database setup:** a one-shot `db-init` container runs `infrastructure/docker/db-bootstrap/bootstrap.sh` on every `docker compose up`. It is idempotent, so new services and changed passwords reach an existing data volume.
