---
name: design-plnty-app
description: Design system extracted from Plnty (https://plnty.app/). Use when building UI that should match this brand's visual identity.
triggers:
  - "Plnty"
  - "plnty-app"
  - "design like Plnty"
  - "Plnty風"
source: https://plnty.app/
extractedAt: 2026-10-18T18:52:02.723Z
tags: ["light", "rounded", "accented", "bold-typography", "sans-serif"]
---
# Design System Inspired by Plnty

> Auto-extracted from `https://plnty.app/` on 2026-10-18

## 1. Visual Theme & Atmosphere

Friendly, approachable design with rounded shapes and generous whitespace.

The hero section leads with "The agentic creative canvas for professional creators." followed by "Plnty is a powerful suite of design tools that turns ideas into finished work across image, video, v".

**Key Characteristics:**
- KMR Apparat as the heading font (custom web font loaded via @font-face)
- Suisse Intl as the body font for all running text
- Heading weight 500, letter-spacing -4.2px
- Light/white background (#f8f8f8) as the primary canvas
- Primary accent `#e3b210` used for CTAs and brand highlights
- 1 shadow level(s) detected — standard shadows
- Rounded corners (24px+) creating a friendly, approachable feel
- Tags: light, rounded, accented, bold-typography, sans-serif

## 2. Color Palette & Roles

### Primary
- **Primary Accent** (`#e3b210`) · `--color-primary`: Brand color, CTA backgrounds, link text, interactive highlights.
- **Secondary Accent** (`#dfba34`) · `--color-secondary`: Secondary brand, hover states, complementary highlights.
- **Background** (`#f8f8f8`) · `--color-bg`: Page background, primary canvas.
- **Background Secondary** (`#1a1a19`) · `--color-bg-secondary`: Cards, surfaces, alternating sections.

### Text
- **Text Primary** (`#1a1a19`) · `--color-text`: Headings and body text.
- **Text Secondary** (`#666666`) · `--color-text-secondary`: Muted text, captions, placeholders.

### Borders & Surfaces
- **Border** (`#e6e3dc`) · `--color-border`: Dividers, outlines, input borders.

### Full Extracted Palette

| # | Hex | CSS Variable | Role | Area | Contrast |
|---|---|---|---|---|---|
| 1 | `#e6e3dc` | `--palette-1` | badge | large | text-dark |
| 2 | `#1a1a19` | `--palette-2` | block | large | text-light |
| 3 | `#d1cfc9` | `--palette-3` | button | medium | text-dark |
| 4 | `#000000` | `--palette-4` | button | small | text-light |
| 5 | `#a68aff` | `--palette-5` | button | small | text-dark |
| 6 | `#dfba34` | `--palette-6` | button | small | text-dark |
| 7 | `#e3b210` | `--palette-7` | text-accent | small | text-dark |
| 8 | `#f8f8f8` | `--palette-8` | badge | small | text-dark |
| 9 | `#47146e` | `--palette-9` | text-accent | small | text-light |

## 3. Typography Rules

- **Heading Font:** `KMR Apparat` (web font)
- **Body Font:** `Suisse Intl` (web font)

### Type Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|---|---|---|---|---|---|
| H1 | KMR Apparat | 105px | 500 | 105px | -4.2px |
| H2 | KMR Apparat | 23px | 500 | 23px | normal |
| H3 | KMR Apparat | 30px | 500 | 30px | -0.6px |
| Body | Suisse Intl | 18px | 400 | 26px | normal |

### Type Scale

| Token | Size | Suggested Usage |
|---|---|---|
| Display | `105px` | headings |
| H1 | `89.1px` | headings |
| H2 | `72px` | headings |
| H3 | `68px` | headings |
| H4 | `51.83px` | headings |
| Body L | `40px` | body / supporting text |
| Body | `34px` | body / supporting text |
| Small | `32px` | body / supporting text |
| XS | `24px` | body / supporting text |
| Caption | `23px` | body / supporting text |

## 4. Component Stylings

### Primary Button

```css
.btn-primary {
  background: #e6e3dc;
  color: #1a1a19;
  border-radius: 16px;
  padding: 0px 8px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  cursor: pointer;
}
```

### Filled Button

```css
.btn-filled {
  background: #a68aff;
  color: #47146e;
  border-radius: 16px;
  padding: 0px 12px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  cursor: pointer;
}
```

### Ghost Button

```css
.btn-ghost {
  background: transparent;
  color: #6c6962;
  border-radius: 0px;
  padding: 1px 0px;
  font-size: 18px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Ghost Button 2

```css
.btn-ghost-2 {
  background: transparent;
  color: #1a1a19;
  border-radius: 0px;
  padding: 0px 0px;
  font-size: 16px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Filled Button 2

```css
.btn-filled-2 {
  background: #000000;
  color: #f8f8f8;
  border-radius: 20px;
  padding: 0px 16px;
  font-size: 16px;
  font-weight: 500;
  border: none;
  cursor: pointer;
}
```

### Outline Button

```css
.btn-outline {
  background: transparent;
  color: #0d0d0d;
  border-radius: 20px;
  padding: 0px 16px;
  font-size: 16px;
  font-weight: 500;
  border: 1.44906px solid rgb(0, 0, 0);
  cursor: pointer;
}
```

## 5. Layout Principles

- **Base spacing unit:** `2.1px` — use multiples (4.2px, 6.300000000000001px, 8.4px, etc.)

### Spacing Scale (extracted from real elements)

| Token | Value | Role |
|---|---|---|
| spacing-1 | `2.1px` | element |
| spacing-2 | `16px` | element |
| spacing-3 | `1px` | element |
| spacing-4 | `12px` | element |
| spacing-5 | `29px` | card |
| spacing-6 | `32px` | card |
| spacing-7 | `44px` | card |
| spacing-8 | `80px` | section |

### Border Radius Scale

| Token | Value | Element |
|---|---|---|
| radius-card | `24px` | card |
| radius-button | `12px` | button |
| radius-card | `50px` | card |
| radius-card | `22.4638px` | card |
| radius-card | `35px` | card |
| radius-card | `20px` | card |

## 6. Depth & Elevation

| Level | Shadow | Usage |
|---|---|---|
| Low | `rgb(248, 248, 248) 0px 0px 87.2px 10px inset` | Cards, subtle elevation |


## 7. Do's and Don'ts

### Do
- Use `#f8f8f8` as the primary background color
- Use `KMR Apparat` for all headings and `Suisse Intl` for body text
- Use `#e3b210` as the single dominant accent/CTA color
- Maintain `2.1px` as the base spacing unit — all gaps should be multiples
- Use rounded corners (`24px`+) consistently for all interactive elements
- Make headlines large and bold — typography is the hero element
- Apply the shadow system for elevation — use the extracted shadow values
- Use weight 500 for headings to match the brand's typographic voice

### Don't
- Don't use colors outside the extracted palette without justification
- Don't substitute KMR Apparat/Suisse Intl with generic alternatives
- Don't use irregular spacing — stick to 2.1px grid
- Don't use dark/black backgrounds — this is a light-themed design
- Don't use sharp corners — they feel hostile in this rounded design language
- Don't use pure black (#000000) for text — use `#1a1a19` instead
- Don't add decorative elements not present in the original design — no badges, ribbons, banners, or ornaments unless the source site uses them
- Don't invent UI patterns the source site doesn't have — if the original has no NEW badge, don't add one just because a red is in the palette

## 8. Responsive Behavior

| Breakpoint | Width | Notes |
|---|---|---|
| Mobile | < 640px | Single column, stack sections, reduce font sizes ~80% |
| Tablet | 640–1024px | 2-column where appropriate, maintain spacing ratios |
| Desktop | 1024–1440px | Full layout as designed |
| Wide | > 1440px | Max-width container, center content |

- Touch targets: minimum 44×44px on mobile
- Maintain 2.1px base unit across breakpoints — only scale multipliers

## 9. Agent Prompt Guide

### Quick Color Reference

```
Background:  #f8f8f8
Text:        #1a1a19
Accent:      #e3b210
Secondary:   #dfba34
Border:      #e6e3dc
```

### Example Prompts

1. "Build a hero section with a `#f8f8f8` background, `KMR Apparat` heading in `#1a1a19`, and a `#e3b210` CTA button with 16px radius."
2. "Create a pricing card using background `#1a1a19`, border `#e6e3dc`, `Suisse Intl` for text, and 6.300000000000001px padding."
3. "Design a navigation bar — `#f8f8f8` background, `#1a1a19` links, `#e3b210` for active state."
4. "Build a feature grid with 3 columns, 6.300000000000001px gap, each card using the card component style."
5. "Create a footer with `#1a1a19` background, `#f8f8f8` text, and 4.2px padding."

### Iteration Guide

1. Start with layout structure (sections, grid, spacing)
2. Apply colors from the palette — background first, then text, then accents
3. Set typography — font families, sizes from the type scale, weights
4. Add components — buttons, cards, inputs using the specs above
5. Apply border-radius consistently across all elements
6. Add shadows for depth — use the extracted shadow values, not defaults
7. Check responsive behavior — test mobile and tablet layouts
8. Final pass — verify all colors match, spacing is consistent, fonts are correct

## 10. CSS Custom Properties

> 120 custom properties extracted from `:root` / `html` stylesheets.

### Color Variables

| Variable | Value |
|---|---|
| `--color-bg` | `#000000` |
| `--color-text-primary` | `#ededed` |
| `--color-text-body-chapter` | `#d4d4d4` |
| `--color-text-secondary` | `#a1a1a1` |
| `--color-text-tertiary` | `#737373` |
| `--color-text-quaternary` | `#525252` |
| `--color-hairline-subtle` | `rgba(255, 255, 255, .08)` |
| `--color-hairline-resting` | `rgba(255, 255, 255, .1)` |
| `--color-hairline-strong` | `rgba(255, 255, 255, .2)` |
| `--color-hairline-hover` | `rgba(255, 255, 255, .25)` |
| `--color-divider-faint` | `rgba(255, 255, 255, .06)` |
| `--color-brand-red` | `#79a636` |
| `--color-brand-red-hover` | `#8eb456` |
| `--color-pill-resting` | `#fcfcfc` |
| `--color-pill-hover` | `#ffffff` |
| `--color-pill-text` | `#000000` |
| `--hp-ink` | `#1a1a19` |
| `--hp-ink-soft` | `#33332f` |
| `--hp-surface` | `#f8f8f8` |
| `--hp-pill` | `#e6e3dc` |
| `--hp-ink-muted` | `#6c6962` |
| `--hp-panel` | `#e6e5e1` |
| `--hp-arrow` | `#e3b210` |
| `--hp-pill-hover` | `#d1cbbd` |
| `--hp-ink-hover` | `#000000` |
| `--hp-selection-bg` | `#d9cdff` |
| `--hp-selection-ink` | `#1a1a19` |
| `--hp-cta-blue` | `#76c1f5` |
| `--hp-cta-blue-hover` | `#2ba1f2` |
| `--hp-cta-blue-ink` | `#092538` |
| ... | *(9 more)* |

### Spacing Variables

| Variable | Value |
|---|---|
| `--size-body` | `17px` |
| `--size-pull-quote` | `22px` |
| `--size-toc-section-header` | `13px` |
| `--size-toc-row` | `16px` |
| `--size-toc-num` | `13px` |
| `--size-card-title` | `16px` |
| `--size-card-meta` | `12px` |
| `--size-breadcrumb` | `13px` |
| `--size-footer-link` | `14px` |
| `--size-footer-legal` | `12px` |
| `--size-pill` | `13px` |
| `--size-cta-pill` | `14px` |
| `--lh-tight` | `1` |
| `--lh-display` | `.96` |
| `--lh-body` | `1.55` |
| `--lh-pull-quote` | `1.35` |
| `--lh-comfortable` | `1.5` |
| `--tracking-display` | `-.022em` |
| `--tracking-body` | `-.005em` |
| `--tracking-caps` | `.18em` |
| ... | *(24 more)* |

### Typography Variables

| Variable | Value |
|---|---|
| `--font-sans` | `"Suisse Intl", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif` |
| `--font-serif` | `"Suisse Works", "Times New Roman", serif` |

### Other Variables

| Variable | Value |
|---|---|
| `--color-brand-red-rgb` | `121, 166, 54` |
| `--size-hero-title` | `clamp(48px, 8vw, 120px)` |
| `--size-hero-subtitle` | `clamp(15px, 1.3vw, 17px)` |
| `--size-chapter-title` | `clamp(56px, 7.5vw, 104px)` |
| `--ease-out-soft` | `cubic-bezier(.16, 1, .3, 1)` |
| `--ease-move` | `cubic-bezier(.2, 0, 0, 1)` |
| `--duration-fast` | `.18s` |
| `--duration-medium` | `.32s` |
| `--duration-slow` | `.9s` |
| `--hp-ticker-height` | `calc(20 * var(--hp-u))` |
| `--hp-size-ticker` | `calc(11.3466 * var(--hp-u))` |
| `--hp-ticker-duration` | `66s` |
| `--hp-u-base` | `clamp(1px, .06944vw, 1.3333px)` |
| `--hp-u` | `var(--hp-u-base)` |
| `--hp-frame-w` | `calc(1440 * var(--hp-u))` |
| ... | *(20 more)* |
