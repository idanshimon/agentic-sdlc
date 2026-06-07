---
version: alpha
name: Ledger Insights
description: Operator dashboard for the governed agentic SDLC reference design — calm, dense, technical. For developers and product people who need to read the system at a glance, not be sold to.
colors:
  primary: "#0EA5E9"
  secondary: "#A78BFA"
  tertiary: "#10B981"
  neutral: "#0B0F14"
  surface: "#11161D"
  elevated: "#161D26"
  overlay: "#1E2632"
  border: "#243042"
  borderMuted: "#1B232E"
  text: "#E6EDF3"
  textSecondary: "#9FB0C3"
  textTertiary: "#697789"
  success: "#22C55E"
  warning: "#F59E0B"
  danger: "#EF4444"
  info: "#0EA5E9"
  planeStandards: "#A78BFA"
  planePipeline: "#0EA5E9"
  planeLedger: "#22C55E"
  planeAgentHQ: "#F472B6"
typography:
  display:
    fontFamily: "Geist"
    fontSize: 2.25rem
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  h1:
    fontFamily: "Geist"
    fontSize: 1.5rem
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  h2:
    fontFamily: "Geist"
    fontSize: 1.125rem
    fontWeight: 600
    lineHeight: 1.3
  h3:
    fontFamily: "Geist"
    fontSize: 0.9375rem
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Geist"
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Geist"
    fontSize: 0.75rem
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.02em"
  mono:
    fontFamily: "Geist Mono"
    fontSize: 0.8125rem
    fontWeight: 400
    lineHeight: 1.5
rounded:
  none: 0px
  sm: 4px
  md: 6px
  lg: 8px
  xl: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
  xxxl: 48px
components:
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "16px"
  card-elevated:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "20px"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#001018"
    rounded: "{rounded.md}"
    padding: "10px"
  button-secondary:
    backgroundColor: "{colors.overlay}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "10px"
  badge:
    backgroundColor: "{colors.overlay}"
    textColor: "{colors.textSecondary}"
    rounded: "{rounded.full}"
    padding: "4px"
  badge-success:
    backgroundColor: "{colors.success}"
    textColor: "#001f0a"
    rounded: "{rounded.full}"
  badge-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#1a0000"
    rounded: "{rounded.full}"
---

## Overview

**Ledger Insights** is the operator UI for the four-plane agentic SDLC reference
design. Audience: software engineers, platform engineers, product managers,
program managers, governance reviewers. Not consumers, not marketing.

Design posture is **calm and dense** — closer to Linear, Grafana, GitHub
Actions, Vercel observability than to a marketing landing page. Every pixel
must do work. Decoration is the enemy.

Three opinions:

1. **Read-first.** This dashboard exists to *read* the system. Mutations
   (approve gate, reject decision, pause run) live behind explicit, slow
   affordances; the default surface is "what is going on?"
2. **Plane-coded.** Standards (violet), Pipeline (blue), Ledger (green),
   Agent HQ (pink). Color encodes which of the four architecture planes a
   piece of data belongs to. Use a `<PlaneBadge>` to render the chip.
3. **Token-driven, swap-friendly.** Every visual primitive is a CSS variable
   exported from `lib/design/tokens.ts`. Replacing shadcn with MUI or a
   custom design system is a `components/ui/*` change, never a page change.

## Colors

- **Primary (#0EA5E9)** — interactive accent (links, focus rings, primary buttons). Used sparingly.
- **Secondary (#A78BFA)** — the Standards plane color. Also used for "system" / "governance" surfaces.
- **Tertiary (#10B981)** — the Ledger plane color. Used for success, ledger writes, audit-clean states.
- **Plane palette** — `planeStandards` violet, `planePipeline` blue, `planeLedger` green, `planeAgentHQ` pink. These are SEMANTIC: only use them when the surface represents that plane.
- **Neutral (#0B0F14)** — page background. Slightly cool, near-black, not OLED black (true black creates aggressive halos against bright accents).
- **Surface (#11161D)** — card background, one step up from neutral.
- **Elevated (#161D26)** — modal/popover background, two steps up.
- **Overlay (#1E2632)** — input background, badge fill, three steps up.
- **Border (#243042)** — default card/input border. **Always 1px solid.** Never use shadows for separation; the design uses border + surface contrast.

Light-theme palette is **derived automatically** by inverting the L channel of OKLCH; agents must not hand-author light values.

## Typography

**Geist Sans** for everything, **Geist Mono** for IDs, GUIDs, code, run_ids,
bundle refs (`[security/v0.1.0/PHI-001]`), timestamps in compact tables.

Hierarchy is conveyed by **size and weight**, never by color alone. Color is
reserved for semantic state (success/warning/danger/plane).

Tabular numbers (`font-variant-numeric: tabular-nums`) on every metric, KPI,
duration, count, currency value. Latin numbers must line up vertically in
tables — non-tabular is unacceptable for a dashboard.

## Layout & Spacing

- **Container max-width** — 1440px content area; 1600px for table-heavy pages.
- **App shell** — collapsible left sidebar (240px expanded / 64px collapsed) + sticky top bar (56px) + main content. Mobile: sidebar becomes a sheet via the topbar hamburger.
- **Grid base** — 4px. All padding/margin/gap snap to the spacing scale.
- **Density** — comfortable default (16px card padding, 12px row height in tables). User can toggle "compact" via Tweaks panel (8px card padding, 8px row height).

## Elevation & Depth

- **No drop shadows on cards.** Border + surface step provides separation. Drop shadows are reserved for *floating* elements: popovers, dropdowns, command palette, sheets, modals.
- **Modal shadow** — `0 24px 48px -16px rgba(0,0,0,0.6)`.
- **Backdrop blur** — `backdrop-filter: blur(12px)` on the modal overlay so the underlying UI shows through softly.

## Shapes

- Cards: 8px rounded (`rounded-lg`).
- Buttons: 6px rounded (`rounded-md`).
- Inputs: 6px rounded (`rounded-md`).
- Badges / pills: fully rounded (`rounded-full`).
- Sharp corners are forbidden on interactive surfaces — they read as engineering placeholders, not design.

## Components

Token references in the front matter are the contract. Component implementations
live in `apps/ledger-insights-ui/src/components/`. The taxonomy:

- **`components/ui/`** — shadcn-provided primitives (Button, Card, Badge, Dialog, Sheet, Tabs, Table, Tooltip, Command, Sonner). **Replace this directory** to swap the design system.
- **`components/domain/`** — agentic-sdlc semantic components (RunCard, StageTimeline, DecisionCard, BundleCard, PlaneBadge, GateBanner, AmbiguityCard, LedgerEntry, ResolverDialog). Built ON TOP of `components/ui/`.
- **`components/layout/`** — AppShell, Sidebar, TopBar, Breadcrumbs, CommandPalette, ThemeToggle.
- **`components/charts/`** — Recharts wrappers with the theme baked in (TrendChart, DonutChart, SparkLine).

`<PlaneBadge plane="standards" />` is the canonical example. It pulls
`colors.planeStandards` from tokens, renders a 8x8 dot + label, and is
re-used in 4 different pages. Hand-coding the violet hex anywhere else is
a code-review block.

## Do's and Don'ts

- ✅ Use `<PlaneBadge>`, `<Badge variant="…">`, `<StatusDot status="…">`.
- ✅ Use tabular-nums on every metric.
- ✅ Use Geist Mono for any identifier humans copy (run_id, GUID, ledger entry id, bundle ref).
- ❌ Don't hard-code colors. Tokens or nothing.
- ❌ Don't use drop shadows on cards.
- ❌ Don't use emoji as icons. Lucide React only.
- ❌ Don't add a hero section, marketing copy, "join the future" CTA, gradient backgrounds, glassmorphism, or generic SaaS card grids. This is an operator dashboard, not a landing page.
- ❌ Don't add data that isn't real. Empty states say "No runs yet" — they don't show fake demo data.
