# Feature 07: Marketing Landing Page — Implementation Plan

## Architecture & Component Breakdown

All marketing components reside in `frontend/src/features/landing/components/` and are composed inside `frontend/src/app/(marketing)/page.tsx`, `frontend/src/app/(marketing)/about/page.tsx`, and `frontend/src/app/(marketing)/blog/page.tsx`.

### Routes
- `/`: Main Marketing Landing Page.
- `/about`: Company Mission, Architectural Principles, and Technology Stack overview.
- `/blog`: Technical Engineering Articles & Deep Dives index.

### Components List
1. `Navbar.tsx`: Sticky glassmorphic navbar with blur backdrop after 8px scroll, logo SVG, nav links (Features, Integrations, Assistant, FAQ, About, Blog), theme toggle, and CTAs.
2. `AnnouncementPill.tsx`: Subtle pill linking to citation feature context.
3. `HeroBackground.tsx`: Ethereal floating cloud sky background with slow drifting cloud shapes & ambient sky-top radial glows (inspired by Cap).
4. `Hero.tsx` & `HeroTabs.tsx`: Bricolage Grotesque headline with sliding active underline, segmented tab buttons with sliding pill highlight, keyboard navigation, & auto-advance timer.
5. `SyncDemo.tsx`: Signature product window showing:
   - Chat tab mockup (channel with 2 users mid-conversation & live typing).
   - Connect tab mockup (UniChat window left, Slack/Discord panes right, traveling dot message animation & green sync pulse; pauses on prefers-reduced-motion).
   - Ask tab mockup (Gemini assistant answer with static citation chips).
6. `PlatformStrip.tsx`: Monochromatic Slack, Discord, and dashed Teams SVG logos.
7. `HowItWorks.tsx`: 3-step narrative cards ("Create a workspace", "Link a channel", "Ask anything") with "Best for" lines.
8. `FeatureGrid.tsx`: Asymmetric bento grid featuring live arrival, threads, platform badges, semantic search, summaries, and draft replies.
9. `AssistantShowcase.tsx`: Violet-tinted section with copy and static cited conversation.
10. `IntegrationsHub.tsx`: SVG node diagram with UniChat center hub, Slack/Discord spokes, and open platform folder spoke.
11. `Faq.tsx`: 6-question accordion with ARIA expansion state.
12. `FinalCta.tsx`: Sky-gradient closing banner with primary action CTA.
13. `Footer.tsx`: Brand mark, links, and technology stack readout.

### Metadata & OG Image
- Open Graph SVG endpoint / static asset generation for social preview (`public/og.svg`).
- SEO meta tags (title, description, open graph tags) in Next.js layout metadata.
