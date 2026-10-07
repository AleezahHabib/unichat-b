# FistaChat Design System: "Skyline"

## 1. Visual Philosophy & Direction
Inspired by cap.so's bright, airy, confident aesthetic:
- Concise, commanding headlines.
- Interactive live product preview controlled via intuitive tabs.
- Realistic, high-fidelity application window with clean glass borders.
- Generous whitespace and scannable visual rhythm.
- **NOT** a clone: no reused Cap assets, copy, or borrowed layouts. FistaChat brings its own distinct identity tailored to cross-platform chat and AI workflows.

---

## 2. Color Palette ("Skyline")

| Token | Light Mode Hex | Dark Mode Hex | Usage / Meaning |
| :--- | :--- | :--- | :--- |
| `bg` | `#F6F9FF` | `#070B16` | Deep base canvas background |
| `surface` | `#FFFFFF` | `#0E1424` | Primary card, modal, and panel background |
| `surface-2` | `#EEF3FC` | `#151D31` | Secondary nested surfaces, message bubbles, inputs |
| `border` | `#DDE5F2` | `#22304A` | Crisp structural borders and dividers |
| `ink` | `#0B1324` | `#E8EEFA` | Primary high-contrast text and headings |
| `ink-muted` | `#5A6A85` | `#8C9AB5` | Secondary text, timestamps, placeholders |
| `primary` | `#2F6BFF` | `#5B8CFF` | Primary brand actions, active tabs, buttons |
| `ai` | `#7C5CFF` | `#9B84FF` | AI assistants, citations, sparkle accents, summary badges |
| `live` | `#16C79A` | `#2EE0AE` | Online presence, active socket indicator, synced status |
| `danger` | `#E5484D` | `#FF6B6F` | Destructive actions, delete warnings, error alerts |
| `sky-top` | `#DCE9FF` | `#0B1733` | Subtle hero top atmosphere gradient tint |

### Platform Identity Badges
External source badges exclusively use their official brand colors with crisp white text:
- **Slack Badge**: Background `#4A154B`, Text `#FFFFFF`
- **Discord Badge**: Background `#5865F2`, Text `#FFFFFF`

---

## 3. Typography
- **Headlines & Display**: Bricolage Grotesque (`@fontsource-variable/bricolage-grotesque`, bundled locally)
- **UI & Body**: Geist Sans (`geist`, bundled locally)
- **Code & Terminal Elements**: Geist Mono (`geist`, bundled locally)

### Type Scale & Rules
- **Scale**: `14px` (Captions/meta), `16px` (Body standard), `18px` (Large body/subheadings), `22px` (H3/Card headers), `28px` (H2/Section titles), `40px` (Page titles), `64px` / `72px` (Hero desktop, `44px` on mobile).
- **Tracking**: `-0.03em` on display headings and titles.
- **Line Height**: `1.6` for long-form body text.
- **Line Length**: Max ~`70` characters for readability.

---

## 4. Radii & Elevation
- **Controls & Buttons**: `10px` (`rounded-[10px]`)
- **Cards & Dialogs**: `14px` (`rounded-[14px]`)
- **Product Windows & Hero Frames**: `18px` (`rounded-[18px]`)
- **Borders**: Clean `1px` borders using token `border`.

---

## 5. Motion & Micro-Interactions
- **Transitions**: `150ms` - `250ms` `ease-out` on user-triggered actions (button hovers, tab clicks, modal pops).
- **Signature Autonomous Animation**: Exactly **one** autonomous loop is permitted across the entire application: the **Hero Sync Demo Loop** showing a message flowing between Slack, FistaChat, and Discord with live AI citation.
- **Accessibility & Reduced Motion**:
  - The hero sync demo strictly checks `prefers-reduced-motion`.
  - When reduced motion is requested, all animation frames stop, presenting a static, beautifully rendered final preview frame.

---

## 6. Anti-Patterns & Explicit Rules (Things to Avoid)
1. **NO ALL-CAPS eyebrow labels** (e.g. no `INTELLIGENCE PLATFORM` headers). Use natural title casing or short phrases.
2. **NO single accented words** in headlines (e.g. no "Unified chat for *modern* teams" with one color-splashed word).
3. **NO trailing arrows** appended to buttons or links (e.g. no `Get Started ->` or `Learn More →`).
4. **NO middle-dot-joined metadata** (e.g. avoid `General • 3 mins ago • 14 replies`). Use structured spacing, pills, or clean tabular alignment.
5. **NO repeated fade-slide-up animations** triggered on every scroll section.
6. **NO identical-shadow repetitive card grids**. Use asymmetric visual weighting.
7. **NO decorative gradient washes** outside the designated `sky-top` hero glow and subtle `ai` accents.

---

## 7. Landing Page Section Architecture
The marketing landing page renders these 12 sections in strict order:

1. **Navbar**: Sleek glassmorphic bar featuring brand mark, links (Features, Integrations, Spec-First, FAQ), theme toggle, and Auth actions (Log in / Open App).
2. **Announcement Pill**: Subtle, non-intrusive pill announcing open-spec release and Gemini 2.5 Flash intelligence.
3. **Hero Section**: 
   - Powerful headline: *"Chat. Connect. Ask."*
   - Interactive segmented tabs (`Chat`, `Connect`, `Ask`) allowing prospective users to toggle the live product view via click or arrow keys.
   - Realistic window preview showcasing the signature **SyncDemo** autonomous loop (with reduced-motion fallback).
4. **Platform Strip**: Clean row showing native FistaChat alongside verified bi-directional sync with Slack and Discord.
5. **How It Works**: 3-step visual narrative detailing workspace creation, 1:1 channel linking, and ambient AI assistance.
6. **Feature Grid (Asymmetric)**: Non-uniform bento layout highlighting realtime speed, thread organization, and presence indicators.
7. **Assistant Showcase**: Interactive demo view highlighting cited channel summaries, direct jump-to links, and composer reply drafts.
8. **Integrations Hub Diagram**: Visual node diagram demonstrating how FistaChat's unified `messages` table relays data to and from Slack Socket Mode and Discord Webhooks without echoes.
9. **"Built Spec-First" Section**: High-tech interactive card pairing an authentic folder tree with a simulated terminal showing test verification.
10. **FAQ**: Clean accordion answering technical questions regarding zero-docker setups, data privacy, free-tier limits, and cross-platform sync.
11. **Final CTA**: High-impact closing panel prompting immediate signup into the user's workspace.
12. **Footer**: Minimalist footer with legal links, GitHub repository, documentation shortcuts, and live status beacon.

---

## 8. Accessibility & WCAG AA Contrast Audit

All core text/background pairs from Section 2 were audited for WCAG 2.1 Level AA conformance (minimum 4.5:1 for standard body text, 3.0:1 for large text/UI components):

| Pair | Light Hex Pair | Contrast Ratio | Dark Hex Pair | Contrast Ratio | WCAG AA Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ink` on `bg` | `#0B1324` on `#F6F9FF` | **17.58:1** | `#E8EEFA` on `#070B16` | **16.88:1** | **PASS** | Exceeds AAA requirement (7:1) |
| `ink` on `surface` | `#0B1324` on `#FFFFFF` | **18.54:1** | `#E8EEFA` on `#0E1424` | **15.77:1** | **PASS** | Exceeds AAA requirement (7:1) |
| `ink` on `surface-2` | `#0B1324` on `#EEF3FC` | **16.65:1** | `#E8EEFA` on `#151D31` | **14.41:1** | **PASS** | Exceeds AAA requirement (7:1) |
| `ink-muted` on `bg` | `#5A6A85` on `#F6F9FF` | **5.19:1** | `#8C9AB5` on `#070B16` | **6.93:1** | **PASS** | Meets AA (>= 4.5:1) |
| `ink-muted` on `surface` | `#5A6A85` on `#FFFFFF` | **5.48:1** | `#8C9AB5` on `#0E1424` | **6.47:1** | **PASS** | Meets AA (>= 4.5:1) |
| `ink-muted` on `surface-2` | `#5A6A85` on `#EEF3FC` | **4.92:1** | `#8C9AB5` on `#151D31` | **5.91:1** | **PASS** | Meets AA (>= 4.5:1) |
| White on `slack` badge | `#FFFFFF` on `#4A154B` | **14.00:1** | `#FFFFFF` on `#4A154B` | **14.00:1** | **PASS** | High contrast branding badge |
| White on `discord` badge | `#FFFFFF` on `#5865F2` | **4.61:1** | `#FFFFFF` on `#5865F2` | **4.61:1** | **PASS** | Meets AA (>= 4.5:1) |
| Accent text on `surface` | e.g. `#2F6BFF` on `#FFFFFF` | **4.50:1** | e.g. `#5B8CFF` on `#0E1424` | **5.80:1** | **PASS** | Badges use tinted backgrounds (`bg-primary/10 text-primary`) |

**Result**: **PASS**. All core text and surface pairings strictly adhere to WCAG AA contrast standards. No color tokens required alteration.
