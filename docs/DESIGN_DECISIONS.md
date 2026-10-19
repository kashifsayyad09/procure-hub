# Design decisions: applying Design.md and Skill.md

| Topic | Source says | Decision |
|---|---|---|
| Dark theme | "Don't use dark backgrounds" | Light is default and matches the brand. Dark theme exists because the project spec requires it; it reuses the same accent, radii and type. |
| Fonts | KMR Apparat, Suisse Intl | Proprietary and not available. Declared first in the font stacks with Helvetica/system fallbacks, so licensed files can be added with @font-face. |
| Accent text | #e3b210 as brand colour | Used for fills and highlights with #1a1a19 text on top. Never used as small text on #f8f8f8 (insufficient contrast). |
| Section 10 variables | Dark values (#000000 bg, green "brand-red") | These come from a different page of the site and contradict sections 1-9. Ignored. |
| Spacing | 2.1px base unit | Exposed as Tailwind `u1`..`u60` (multiples of 2.1px) and used for layout. A few utilities (h-11 for 44px touch targets) use standard values. |
| Card colour | `#1a1a19` as "cards, surfaces" | Cards are white with #e6e3dc borders. #1a1a19 is used for one feature panel and the logo mark. |
| Status colours | Palette has none | Added muted green and red for statuses, always paired with a text label. |
| Radius | 24px+ for interactive | Cards 24px, buttons 20px, inputs 16px. |
| Shadow | single inset 87px shadow | Replaced by a light two-layer shadow; the inset value renders as a white wash on white cards. |
| Motion (Skill.md) | Use sparingly | One orchestrated hero entrance, scroll reveals on the landing page, count-ups, dashboard entrance, and motion that answers actions (dialogs, sidebar, progress rail). |
