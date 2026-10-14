# Feature 08: Interactive Product Demo — Implementation Plan

## Component Architecture

The interactive demo is built as a self-contained, high-fidelity client component:
`frontend/src/features/landing/components/InteractiveDemo.tsx`

Integrated into `frontend/src/app/(marketing)/page.tsx` between `<PlatformStrip />` and `<HowItWorks />`.

### Component Structure
1. **Outer Section & Frame (`#demo`)**:
   - Section header with Title "See it work" and Subline "Five clicks through a real workflow. No sign-up."
   - Centering container: Downsized from 1040px to 800px max-width (`max-w-[800px] mx-auto px-6 max-[900px]:px-0`) with 24px (`px-6`) side gutters.
   - Laptop lid: Styled with `--bezel` and `--bezel-2` gradients, lid radius `18px 18px 4px 4px` (`rounded-[18px_18px_4px_4px]`), `pt-3 px-3 pb-3.5` creating balanced top/side bezels and a 14px bottom chin.
   - Camera dot: Small webcam lens dot (`w-1.5 h-1.5 rounded-full bg-black/70 border border-white/10`) centered in the top bezel (`absolute top-1.5 left-1/2 -translate-x-1/2`).
   - Laptop screen: 16:10 aspect ratio screen (`aspect-[16/10]`) with `--wall` gradient backdrop, 8px inner radius, and `p-4 sm:p-5` padding ensuring floating cards never touch the bezels.
   - Laptop base: Positioned directly below the lid with `-mx-4` chassis overhang (`h-[12px] -mx-4 rounded-[0_0_12px_12px]`), notch, and top highlight seam; fits cleanly within the container's `px-6` gutters to prevent horizontal scroll at all viewports (900px, 1000px, 1440px), hidden below 900px.

2. **Stage & Product Mockup**:
   - **UniChat App Window**:
     - Chrome bar: Traffic lights, URL (`unichat.app/workspace/northwind/launch`).
     - Sidebar (hidden <760px): Workspace mark ("Northwind Labs"), channel list (`#general`, `#product`, `#launch`), workspace items (`Assistant`, `Search`, `Settings`).
     - Channel View (`#launch`): Link button ("Link channel"), Slack/Discord platform pills, message feed with Alice Chen, Bob Okafor, Priya Raman, Marco Diaz messages, message composer.
     - Assistant View: Prompt query, Gemini answer block, and citation chips for Alice Chen, Priya Raman (Slack), and Marco Diaz (Discord).
   - **Platform Panes** (side-by-side or stacked <560px):
     - Slack Pane (`#launch`): Priya Raman inbound message and Alice Chen echo via UniChat.
     - Discord Pane (`#launch`): Empty state / Marco Diaz reply message.

3. **Overlay & Interaction Engine**:
   - **Gate Overlay**: Frosted backdrop with glowing pulse button "Start interactive demo".
   - **Dynamic Hotspot (`fc-spot`)**: Absolute positioned pulsating circular button (`aria-describedby="fc-tip"`), focused on active step element.
   - **Tooltip (`fc-tip`)**: Step number, chip label, descriptive body, and navigation hint, clamped within stage boundaries.
   - **Control Rail (`fc-rail`)**: Step progress track (nodes 1-5 with done/current states) and Back/Next action buttons.
   - **Completion Banner (`fc-done`)**: Closing message with relative CTA `/signup` and "Replay demo" reset button.

4. **Measurement & State Logic**:
   - Internal React state for `isStarted`, `currentStep` (0..5), `viewMode` (`channel` vs `assistant`), and step DOM mutation state.
   - Step definitions containing `chip`, `targetId`, `text`, `apply()`, and `undo()` handlers.
   - `useLayoutEffect` / `useEffect` + `ResizeObserver` / `window.resize` tracking stage bounding client rect and target bounding client rect for sub-pixel alignment.
   - Keyboard event listeners for ArrowLeft (Back) and ArrowRight (Next).

---

## Token Integration
Add 3 new tokens to `frontend/src/app/globals.css`:
- `--bezel`: `#232C40` (Light & Dark)
- `--bezel-2`: `#121A2B` (Light & Dark)
- `--wall`:
  - Light: `linear-gradient(150deg, #D7E6FF, #F3F7FF 55%, #E9F0FF)`
  - Dark: `linear-gradient(150deg, #15223F, #0A1026 55%, #101A33)`
Document tokens in `specs/design/design-system.md`.

---

## Test Verification
- Create Playwright E2E test suite in `frontend/tests/e2e/demo.spec.ts` covering AC-08-01 through AC-08-05.
- Run tests and capture visual verification screenshots at 1440px and 375px across both light and dark themes.
