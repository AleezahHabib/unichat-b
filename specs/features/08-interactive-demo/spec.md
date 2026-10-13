# Feature 08: Interactive Product Demo — Specification

## Overview
An interactive, high-fidelity product demonstration component embedded directly in the marketing landing page, modelled after cap.so. It allows prospective users to experience UniChat's 5-step core cross-platform workflow (Connect, Send, Receive, Ask, Verify) inside a responsive laptop mockup before signing up, with no sign-up or live backend required.

## Placement & Context
- Sits in its own dedicated section with `id="demo"` on the marketing landing page (`/`).
- Located immediately between `PlatformStrip` ("Works with Slack and Discord. Microsoft Teams is next.") and `HowItWorks` ("How UniChat works").
- Heading: "See it work"
- Intro: "Five clicks through a real workflow. No sign-up."
- Does not modify or replace `Hero` or `HeroTabs`.

---

## Acceptance Criteria

### AC-08-01: Section Placement & Gate Overlay
- Renders inside `<section id="demo">` between the platform strip and How UniChat works.
- Displays heading "See it work" and subline "Five clicks through a real workflow. No sign-up.".
- At rest, a frosted gate overlay floats over the laptop screen with a "Start interactive demo" button.
- Nothing starts or transitions automatically; the demo only begins when "Start interactive demo" is clicked.

### AC-08-02: 5-Step Interactive Progression & Reversibility
- Progression advances through 5 discrete steps:
  1. **Connect**: Hotspot over "Link channel". Clicking links Slack & Discord badges and illuminates platform preview panes.
  2. **Send**: Hotspot over "Send" button. Clicking adds Alice Chen's message to UniChat and echoes to Slack; composer clears to placeholder.
  3. **Receive**: Hotspot over Discord pane. Clicking displays Marco Diaz's inbound Discord reply in Discord and UniChat channel.
  4. **Ask**: Hotspot over "Assistant" sidebar nav item. Clicking switches channel view to Assistant thread showing question and cited Gemini answer.
  5. **Verify**: Hotspot over Slack citation chip. Clicking switches back to channel view and highlights/flashes Priya Raman's Slack message.
- Navigation controls (Back, Next, ArrowLeft, ArrowRight) allow stepping forward and backward.
- Every step is strictly reversible: clicking Back undoes the active step's state changes.
- "Replay demo" resets all step changes back to the start.

### AC-08-03: Measurement-Based Hotspot & Tooltip Positioning
- Hotspot circle and contextual tooltip coordinates are computed dynamically via `getBoundingClientRect` relative to the stage container.
- Positions are recalculated on step transitions, window resize, and font loading.
- Tooltip boundaries are clamped to stage edges with safe padding to prevent overflow or clipping.

### AC-08-04: End Card & Action CTAs
- Following completion of Step 5, the interactive rail hides or indicates finish, and the end card displays: "That was the whole product. One place for your team, linked to the tools they already use, with an assistant that shows its work."
- Features relative CTA button `href="/signup"` ("Create a free workspace") and a "Replay demo" button.

### AC-08-05: Responsive Laptop Frame & Accessibility
- On screens >=900px, renders a 16:10 fixed aspect ratio laptop screen with realistic lid bezels and base overhang. Root container side padding matches overhang to guarantee zero horizontal scroll.
- Below 900px, laptop bezel and base chrome are removed completely, rendering full-width content without aspect-ratio constraints.
- Below 760px, app sidebar collapses/hides; below 560px, platform panes stack vertically.
- Fully supports keyboard navigation (Tab, Enter, Space, Arrow keys) with visible focus rings (`:focus-visible`).
- Under `prefers-reduced-motion: reduce`, hotspot pulse animations and message sliding transitions are disabled, while functional progression remains intact.
- Correct light and dark mode styles driven strictly by Skyline design tokens plus `--bezel`, `--bezel-2`, and `--wall`.
