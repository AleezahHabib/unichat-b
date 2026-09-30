# Feature 07: Marketing Landing Page — Specification

## Overview
High-converting, responsive marketing landing page showcasing UniChat's core capabilities: unified chat, bidirectional Slack and Discord syncing, and grounded Gemini AI intelligence.

## Acceptance Criteria

### AC-07-01: Landing Page render and auth CTA
- Landing page renders completely at `/` without requiring a running backend or active database.
- Includes sticky glassmorphic navbar with logo, navigation links, theme toggle, and CTAs ("Log in", "Get started" / "Create a free workspace").
- Renders all designated sections in order: Navbar, Announcement Pill, Hero, Platform Strip, How It Works, Feature Grid, Assistant Showcase, Integrations Hub, FAQ Accordion, Final CTA, and Footer.
- Fully responsive from 375px mobile view up to 1440px+ desktop view.

### AC-07-02: Hero tabs & responsive headline interaction
- Hero tabs (Chat Mode, Connect Mode, Ask Mode) are keyboard navigable using arrow keys, Home, End, and Space/Enter keys.
- Tabs auto-advance every ~9 seconds until interacted with by the user.
- Switching tabs updates the interactive product frame seamlessly and updates the headline word emphasis (`Chat.`, `Connect.`, `Ask.`) and subline text.
- Subline container reserves height (`min-h-[4.5rem]` / `sm:min-h-[3.5rem]`) with a 200ms ease-out crossfade and 8px vertical shift (50ms delay) to guarantee zero layout shift.

### AC-07-03: Atmospheric background & reduced motion
- `HeroBackground` renders layered, blurred SVG clouds with GPU-accelerated horizontal drift (`transform: translate3d`).
- Cloud drifting animation automatically pauses when scrolled out of view or when the document is hidden.
- When `prefers-reduced-motion: reduce` is enabled, all background cloud drifting and subline text vertical shifts freeze completely still (`animation: none !important; transform: none !important`).

### AC-07-04: Theme toggle persistence
- Theme toggle supports switching between light and dark modes.
- User theme selection persists across page reloads using `localStorage`.

### AC-07-05: Performance and visual excellence
- Zero dynamic layout shifts across all viewport sizes (1440px down to 375px).
- Includes proper metadata, title, description, and an original SVG-based Open Graph (OG) social card.
- Standard visual structure and design system compliance ("Skyline" tokens).
