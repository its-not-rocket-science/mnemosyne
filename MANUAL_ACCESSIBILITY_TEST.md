# Manual Accessibility Test Script — Mnemosyne

**Purpose:** Step-by-step script for a tester to manually verify keyboard and AT accessibility through Mnemosyne's primary user flow. Run before any public beta tag or controlled user testing.

**Scope distinction:**
- **Automated accessibility coverage** — structural ARIA contract checks run in CI via `backend/tests/test_accessibility_static.py`. These catch missing roles, broken label references, and structural regressions. They do not replace AT validation.
- **Code audit** — static review of HTML/CSS/JS against WCAG 2.1 AA criteria. See `WCAG_AUDIT.md`. Completed 2026-05-28; 8 issues found and fixed.
- **Manual AT validation** — this document. A human tester with a real screen reader or keyboard-only setup must run these flows. Automation cannot substitute.

**Prerequisites:**
- Chrome (latest) + NVDA 2024.x for Windows AT testing
- Safari (latest) + VoiceOver for macOS AT testing
- A keyboard with no mouse attached (or mouse unplugged) for keyboard-only passes
- App running locally at `http://localhost:8000` (or staging URL)
- DevTools accessible for zoom/reflow and network-offline tests

---

## Test 1 — Skip Link

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open the page (signed out). Focus is at browser chrome. | Page loaded. |
| 2 | Press Tab once. | Skip link "Skip to main content" appears (visible on focus). |
| 3 | Press Enter. | Focus moves to `#language` select (inside `#main-content`). |
| 4 | Sign in (see Test 2), then repeat steps 1–3. | After sign-in skip link still works and target is reachable. |

---

## Test 2 — Authentication Panel (keyboard)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Tab to "Sign in" tab button. | Announced as tab, selected state. |
| 2 | Press Right Arrow. | "Create account" tab activates; focus moves to its tabpanel. |
| 3 | Press Left Arrow. | "Sign in" tab reactivates; focus moves back to Sign in tabpanel. |
| 4 | Tab through Sign in form. | Order: Email → Password → Submit → "Create account" tab link. No skipped fields. |
| 5 | Enter wrong credentials; submit. | Error message announced via live region. Focus does not move. `aria-invalid` on password field. |
| 6 | Enter correct credentials; submit. | Auth panel hides; focus moves to `#language` select. |
| 7 | Tab to "Sign out" button; press Enter. | Auth panel shows; focus moves to Email input. |

---

## Test 3 — Language Select and Parse Form (keyboard)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Tab to `#language` select (after sign-in). | Select receives focus. |
| 2 | Open the select; choose a language (e.g. Spanish). | Language options load. `aria-busy` present during load, removed after. |
| 3 | Tab to "Mode" select; choose a mode. | Focus order correct: language → mode → input area → load-file label → URL input → fetch button → parse button. |
| 4 | Paste sample text into textarea; Tab to "Parse" button; press Enter. | Status message "N sentences parsed." announced. Sentence cards appear. |
| 5 | Tab to "Load .txt file" label; press Enter/Space. | File picker opens. (If file picker unavailable in headless test, skip.) |

---

## Test 4 — Sentence Cards and Pill Navigation (keyboard)

| Step | Action | Expected |
|------|--------|----------|
| 1 | After parse, Tab through sentence card pills. | Each pill reachable; announced as button with form "Vocabulary lesson: word". |
| 2 | Activate a pill with Enter. | Detail pane opens. Focus moves into pane (or to first interactive element in pane). |
| 3 | Tab through the three tabs: Explanation / Form / Practice. | Each tab announced as tab 1/2/3 of 3; tabpanel content updates. |
| 4 | Escape while detail pane is open (no concept dialog open). | Detail pane closes; focus returns to the activating pill. |

---

## Test 5 — Concept Help Dialog (keyboard — CRITICAL)

This flow tests the grammar concept help dialog introduced after the initial audit.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open a pill whose Explanation tab has a field with a `?` (help) button. | Field and its help buttons visible. |
| 2 | Tab to the label-help `?` button (left of the two). | Button aria-label includes the field name (e.g. "Explain concept: Grammatical Case"). |
| 3 | Tab to the value-help `?` button (right of the two). | Button aria-label includes the field value (e.g. "Explain concept: nominative"). Label and value buttons have DISTINCT aria-labels. |
| 4 | Press Enter on the value-help button. | Concept dialog opens. Focus moves into dialog. Dialog has role="dialog", aria-modal="true", aria-labelledby pointing to title. |
| 4a | While dialog is loading (observe briefly after step 4). | Body shows "Loading…" text. AT announces "Loading…" via polite live region (`aria-live="polite"` on body). `aria-busy="true"` present on loading element. |
| 4b | DevTools → Network → set to Offline; activate a `?` button. | Body shows localised error message. AT announces error immediately (error paragraph has `role="alert"`). |
| 5 | Read the dialog title with AT. | Title announced on open (e.g. "nominative"). |
| 6 | Tab through dialog controls. | Tab order: close button → back button (if history) → related concept links → body text. Focus does NOT leave dialog. |
| 7 | Press Escape. | Concept dialog closes. Focus returns to the `?` button that opened it. Detail pane remains open. |
| 8 | Open the dialog again; activate a related concept link inside the dialog. | Dialog body updates. `aria-live="polite"` region announces new content. Title updates. |
| 9 | Activate the Back button (if shown). | Dialog body reverts to previous concept. Back button hidden when no history. |
| 10 | Activate the close (×) button. | Dialog closes. Focus returns to trigger button. |
| 11 | Open concept dialog; Shift+Tab from first interactive element in dialog. | Focus wraps to last focusable element inside dialog (does not escape to pane). |
| 12 | Open a concept that has a "Practice this concept" CTA button (concept with practice_tags). | CTA button visible with non-empty label. Tab reaches it. Activating it closes dialog and switches detail pane to Practice tab. |

---

## Test 6 — Form Tab (morphology axes, keyboard)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open a pill; switch to Form tab. | Morphology axes table visible (if data present). |
| 2 | Tab to an axis label-help `?` button. | aria-label contains axis name (e.g. "Explain concept: Case"). |
| 3 | Tab to the axis value-help `?` button. | aria-label contains axis value (e.g. "Explain concept: Acc"). |
| 4 | Activate and verify dialog opens, Escape closes, focus returns. | Same as Test 5. |

---

## Test 7 — Practice Tab Drills (keyboard)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open a pill; switch to Practice tab. | First drill rendered. |
| 2 | **Multiple-choice:** Tab to options; press Space/Enter on one. | Option selected; feedback shown; "Correct!" or error message announced via live region. |
| 3 | **Fill-blank:** Tab to input; type answer; Tab to Check; press Enter. | Feedback announced. |
| 4 | **Shadowing drill:** Tab to "Speak" button. | aria-label includes "drill text" (not ambiguous "Speak"). Press Enter triggers speech. |
| 5 | **True/false:** Tab to True/False buttons; press Space. | Feedback announced. |
| 6 | Tab to rating buttons (Again / Hard / Good / Easy). | Four buttons reachable in order. |
| 7 | Press Space on any rating. | "Saved. Next review in N day(s)." announced via polite live region. No focus move. |

---

## Test 8 — RTL Languages (keyboard and visual)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Set language to Arabic or Hebrew; parse RTL text. | Sentence cards text flows right-to-left. |
| 2 | Open detail pane; check Explanation tab. | Field labels on inline-start side; layout mirrored correctly. |
| 3 | Tab through fill-blank drill for RTL text. | Input `dir="rtl"` set; text entry cursor at right side. |
| 4 | Visual check: no text overflow or cut-off in RTL layout at default viewport. | Pass. |

---

## Test 9 — Screen Reader Smoke Tests (NVDA + Chrome)

Perform with NVDA in Browse mode initially; switch to Forms mode for inputs.

| # | Scenario | Expected NVDA announcement |
|---|----------|---------------------------|
| 1 | Page load | "Mnemosyne" document title |
| 2 | Auth tab focus | "Sign in, tab, 1 of 2" |
| 3 | Auth error | Error text via live region (no focus move) |
| 4 | Language `aria-busy` | "Loading languages…" while pending |
| 5 | Parse success | "N sentences parsed. Use Tab to navigate the items." |
| 6 | Pill button | "Vocabulary lesson: [word], button" |
| 7 | Detail pane tab | "[Tab name], tab, [N] of 3, selected" |
| 8 | Concept dialog open | "[Dialog title], dialog" on open; description text available via describedby |
| 8a | Concept dialog loading state | "Loading…" announced via polite live region immediately on open |
| 8b | Concept dialog error state (go offline first) | Error message announced assertively (role=alert on error paragraph) |
| 9 | Related concept activated | New concept text announced via polite live region (aria-live on body) |
| 10 | Concept dialog close | Focus returns to `?` button; no announcement of closed state required (dialog removed from DOM) |
| 11 | Drill feedback | "✓ Correct!" or "✗ The answer is …" via polite live region |
| 12 | Review saved | "Saved. Next review in N day(s)." via polite live region |
| 13 | Logout | Auth panel email input announced on focus |

---

## Test 10 — Screen Reader Smoke Tests (VoiceOver + Safari)

| # | Scenario | Expected VoiceOver announcement |
|---|----------|--------------------------------|
| 1 | Auth tabs | "Sign in, selected, tab" |
| 2 | Arrow key to other tab | "[Tab name], tab" (activates immediately) |
| 3 | Pill list | "list, N items" on entry |
| 4 | Pill button | "Vocabulary lesson: [word], button" |
| 5 | Modal open | "[Title], web dialog" |
| 6 | Escape in concept dialog | Dialog dismissed; focus returns to button |
| 7 | Focus trap | VO+Tab does not leave concept dialog |

---

## Test 11 — Colour Contrast (browser DevTools)

Use Chrome DevTools → Rendering → Emulate CSS media: `prefers-color-scheme: dark` and repeat for light.

| Element | Token / Value | Requirement |
|---------|--------------|-------------|
| Body text on canvas | `CanvasText` on `Canvas` | ≥ 4.5:1 |
| Muted text (`--muted`) | 60% CanvasText | ≥ 4.5:1 small, ≥ 3:1 large |
| Accent colour links/buttons | `--accent` on `Canvas` | ≥ 4.5:1 text, ≥ 3:1 non-text |
| Drill feedback correct (light) | `oklch(0.45 0.15 145)` | ≥ 4.5:1 |
| Drill feedback correct (dark) | `oklch(0.70 0.15 145)` | ≥ 4.5:1 |
| Input border | `--border-input` on `Canvas` | ≥ 3:1 |
| Pill button borders | `color-mix(in oklch, type-ref 60%, Canvas)` — all 8 type colors | ≥ 3:1 |

---

## Test 12 — Reflow at 320 CSS Pixels

1. DevTools → device toolbar → set width to 320px, 1× DPR.
2. Scroll page — no horizontal scroll bar.
3. Auth form fields stack vertically; no field clipped.
4. Sentence cards wrap to multiple lines; no pill truncated.
5. Detail pane fields grid collapses to one column; no overflow.
6. Concept dialog fits within 320px; body text scrollable if long.

---

## Test 13 — Reduced Motion

**Device:** Any. Use Chrome DevTools → Rendering → Emulate CSS media: `prefers-reduced-motion: reduce`.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Enable reduced-motion emulation. | No visual change required — setting takes effect on next animation/transition. |
| 2 | Open and close the detail pane. | Pane appears/disappears without slide or fade animation. No transform transitions visible. |
| 3 | Open and close the concept help dialog. | Dialog appears/disappears without animation. |
| 4 | Activate a multiple-choice drill option. | Feedback appears immediately; no pulse or fade-in transition. |
| 5 | Activate the FSRS rating buttons. | "Saved." message appears immediately. |
| 6 | Trigger the parse progress bar (large text). | Progress bar updates without smooth animation (steps or instant updates acceptable). |
| 7 | Disable reduced-motion emulation; repeat steps 2–4. | Animations are present again. (Confirms the media query is wired correctly, not always-off.) |

Pass criteria: no animated transitions occur while `prefers-reduced-motion: reduce` is active.

---

## Test 14 — 200% Browser Zoom

**Device:** Desktop Chrome or Firefox. Press Ctrl+= (Windows) or Cmd+= (macOS) until browser shows 200%.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Set zoom to 200%. | Page still usable. No overlapping elements. |
| 2 | Sign in. | Auth form usable. Submit button visible without scrolling (or accessible via scroll). |
| 3 | Parse a short text. | Parse button and status visible. |
| 4 | Open a sentence pill. | Detail pane slides in or appears. Content readable. |
| 5 | Navigate Explanation / Form / Practice tabs. | All three tabs reachable. Tab bar does not overflow off-screen. |
| 6 | Open concept help dialog. | Dialog visible within viewport (may require scroll). Close button reachable. |
| 7 | Scroll the page. | No horizontal scroll bar appears (content reflows, not truncated). |

Pass criteria: all interactive elements reachable, no content lost to overflow.

---

## Test 15 — 400% Zoom / Reflow (WCAG 1.4.10)

**Device:** Desktop Chrome. Set zoom to 400% (Ctrl+= × 6 from 100%).

| Step | Action | Expected |
|------|--------|----------|
| 1 | Set zoom to 400%. | Page reflows into single-column layout. No horizontal scroll. |
| 2 | Tab through main page. | Skip link reachable. Language select reachable. Parse button reachable. |
| 3 | Parse a text (paste short snippet). | Status message visible. Sentence cards visible (stacked vertically). |
| 4 | Open a pill. | Detail pane fills most of viewport width. Content readable. |
| 5 | Open concept dialog. | Dialog visible and scrollable. Close button reachable. |
| 6 | Check that no content is clipped or requires 2D scrolling. | WCAG 1.4.10: content must not require scrolling in two dimensions (unless essential). |

Pass criteria: all primary flows completable at 400% without 2D scrolling.

---

## Test 16 — Offline and Error States

**Device:** Any. Use Chrome DevTools → Network → Offline toggle.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Sign in; go offline (DevTools → Network → Offline). | Offline badge visible in UI. |
| 2 | Attempt to parse text while offline. | Error message shown; announced via live region. App does not crash. |
| 3 | Complete a review while offline. | Review queued in IndexedDB offline queue. No error message. |
| 4 | Go back online. | Queued reviews drain automatically. Success/count message announced. |
| 5 | Go offline; activate a concept help `?` button. | Concept dialog shows localised error (not a blank dialog). Error announced via `role=alert`. |
| 6 | Go offline; reload the page (PWA cache). | App shell loads from service worker cache. Core layout renders. |
| 7 | Go offline; wait for JWT to expire (or manually clear localStorage). | "Session expired" message shown in all supported UI languages when drain is attempted. |

Pass criteria: offline states have visible and AT-announced feedback; app does not crash or show blank UI.

---

## Test 17 — Practice Tab Full Coverage

Extends Test 7 with additional drill types and edge cases introduced after initial audit.

**Setup:** Parse a multi-sentence text in a language with full morphological analysis (Spanish, French, German, or Russian). Open a vocabulary/conjugation pill and switch to the Practice tab.

| Step | Action | Expected |
|------|--------|----------|
| 1 | **Chunk recall drill:** Observe the "Say this aloud" prompt. | Text visible, language `lang` attribute on display element matches sentence language. |
| 2 | **Fill-blank drill:** Type a correct answer; press Enter. | "Correct!" feedback announced via polite live region. |
| 3 | **Fill-blank drill:** Type a wrong answer; press Enter. | Error feedback with correct answer announced via polite live region. |
| 4 | **Multiple-choice:** Navigate options with Tab / arrow keys; press Space or Enter. | Selected option visually highlighted; feedback announced. |
| 5 | **True/false drill:** Tab to True button; press Space. | Feedback announced. Tab to False button; press Space on a second question. Feedback announced. |
| 6 | **Shadowing drill:** Tab to "Speak" button. Press Enter. | If Web Speech API available, speech starts. Button aria-label includes the drill target (not just "Speak"). |
| 7 | **Grammar discrimination (nuance drill):** If available for language — Two sentences shown; Tab to options. | Both sentences read by AT. Option buttons reachable and labelled. |
| 8 | After any drill, Tab to rating buttons. | Four buttons: Again / Hard / Good / Easy — all reachable, announced with label and keyboard shortcut hint if shown. |
| 9 | Press a rating button via keyboard. | "Saved. Next review in N day(s)." announced via polite live region. |
| 10 | Repeat steps 2–9 with an Arabic or Hebrew pill. | Drill text `dir="rtl"` set. Input also `dir="rtl"`. Feedback correct direction. |
| 11 | Open a pill for a language with `morphology_light` capability (Hindi/Turkish/Finnish). | Practice tab renders; drills shown; no crash. Confidence notes visible if present. |

Pass criteria: all drill types completable by keyboard alone; feedback announced by AT; RTL drills work correctly.

---

## Pass / Fail Recording

Copy this table into the session results template below; fill in during the test run.

| Test | Pass | Fail | Notes |
|------|------|------|-------|
| 1 Skip link | | | |
| 2 Auth keyboard | | | |
| 3 Parse form | | | |
| 4 Sentence cards | | | |
| 5 Concept dialog | | | |
| 6 Form tab axes | | | |
| 7 Practice drills | | | |
| 8 RTL layout | | | |
| 9 NVDA smoke | | | |
| 10 VoiceOver smoke | | | |
| 11 Colour contrast | | | |
| 12 Reflow 320px | | | |
| 13 Reduced motion | | | |
| 14 200% zoom | | | |
| 15 400% zoom/reflow | | | |
| 16 Offline/error states | | | |
| 17 Practice tab full | | | |

File any failures as GitHub issues tagged `a11y`.

---

## Session Results Template

Use one copy of this template per test run. Store completed results in `docs/accessibility_results/` (filename: `YYYY-MM-DD_<tester>_<AT>.md`).

```markdown
# Manual AT Test Session — Mnemosyne

## Session metadata

| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD |
| Tester | Name / handle |
| Browser + version | e.g. Chrome 125.0.6422 |
| OS | e.g. Windows 11 22H2 / macOS 14.4 |
| AT tool + version | e.g. NVDA 2024.1 / VoiceOver (built-in) / keyboard-only |
| Viewport / zoom | e.g. 1440×900 100% / 320px / 400% |
| Language direction tested | LTR / RTL / both |
| App commit / version | git SHA or tag |
| App URL | http://localhost:8000 or staging URL |

## Results

| Test | Pass | Fail | Notes |
|------|------|------|-------|
| 1 Skip link | | | |
| 2 Auth keyboard | | | |
| 3 Parse form | | | |
| 4 Sentence cards | | | |
| 5 Concept dialog | | | |
| 6 Form tab axes | | | |
| 7 Practice drills | | | |
| 8 RTL layout | | | |
| 9 NVDA smoke | | | |
| 10 VoiceOver smoke | | | |
| 11 Colour contrast | | | |
| 12 Reflow 320px | | | |
| 13 Reduced motion | | | |
| 14 200% zoom | | | |
| 15 400% zoom/reflow | | | |
| 16 Offline/error states | | | |
| 17 Practice tab full | | | |

## Defects found

<!-- Link each defect to a GitHub issue. -->

| # | Test | Description | Severity | Issue |
|---|------|-------------|----------|-------|
| 1 | | | | |

## Overall assessment

<!-- Pass / Conditional pass / Fail -->

## Tester sign-off

> I confirm the above results reflect my direct testing observations on the date and
> environment recorded above.
>
> — [Tester name], [Date]
```
