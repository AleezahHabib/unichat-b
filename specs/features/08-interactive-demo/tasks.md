# Feature 08: Interactive Product Demo — Tasks

- [x] Add `--bezel`, `--bezel-2`, and `--wall` design tokens to `frontend/src/app/globals.css` (both light & dark modes)
- [x] Update `specs/design/design-system.md` with the new design tokens
- [x] Create `frontend/src/features/landing/components/InteractiveDemo.tsx` porting `interactive-demo.html` with Tailwind v4, tokens, and measurement-based hotspot positioning
- [x] Mount `<InteractiveDemo />` into `frontend/src/app/(marketing)/page.tsx` under `<section id="demo">` between `<PlatformStrip />` and `<HowItWorks />`
- [x] Update `AGENTS.md` (Sections 2, 6, and 14) to document Feature 08 component, specs, and acceptance criteria
- [x] Create Playwright E2E test suite in `frontend/tests/e2e/demo.spec.ts` covering AC-08-01 through AC-08-05
- [x] Run test suite and verify all test cases pass
- [x] Capture visual verification screenshots at 1440px and 375px in both light and dark themes
