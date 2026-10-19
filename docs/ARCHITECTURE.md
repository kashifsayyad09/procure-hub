# Architecture (Phase 1 snapshot)

Target architecture is defined in the master build prompt: 11 FastAPI business services plus API gateway and MCP server on EKS, MySQL on RDS, SQS, NGINX ingress, Terraform, GitHub Actions and Argo CD. Phase 1 implements only the frontend foundation and the local database container.

## Frontend structure
- `src/components/ui` primitives; `layout` shell and dashboard template; `tables`, `charts`, `forms`
- `src/animations/gsap`: single GSAP entry (ScrollTrigger registered once), `useGsap` (scoped context, reverts on unmount, skipped under reduced motion), `useCountUp`, presets
- `src/three`: `SceneBackdrop` (lazy, WebGL and reduced-motion fallback) and `ParticleNetwork` (R3F, pauses when tab hidden)
- `src/stores`: Zustand for theme and sidebar; TanStack Query for server state
- `src/services/mockData.ts`: sample data and a simulated fetch, replaced by real APIs from Phase 2

## Performance
Three.js and Recharts are in lazy chunks and are not part of the entry bundle (entry about 118 kB gzip).
