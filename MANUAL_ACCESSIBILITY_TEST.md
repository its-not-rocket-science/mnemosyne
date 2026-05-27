# Manual Accessibility Test Script — Mnemosyne

**Purpose:** Step-by-step script for a tester to manually verify keyboard and AT accessibility through Mnemosyne's primary user flow. Run before any public beta tag.

**Prerequisites:**
- Chrome (latest) + NVDA 2024.x for Windows AT testing
- Safari (latest) + VoiceOver for macOS AT testing
- A keyboard with no mouse attached (or mouse unplugged) for keyboard-only passes
- App running locally at `http://localhost:8000` (or staging URL)

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
| 5 | Read the dialog title with AT. | Title announced on open (e.g. "nominative"). |
| 6 | Tab through dialog controls. | Tab order: close button → back button (if history) → related concept links → body text. Focus does NOT leave dialog. |
| 7 | Press Escape. | Concept dialog closes. Focus returns to the `?` button that opened it. Detail pane remains open. |
| 8 | Open the dialog again; activate a related concept link inside the dialog. | Dialog body updates. `aria-live="polite"` region announces new content. Title updates. |
| 9 | Activate the Back button (if shown). | Dialog body reverts to previous concept. Back button hidden when no history. |
| 10 | Activate the close (×) button. | Dialog closes. Focus returns to trigger button. |
| 11 | Open concept dialog; Shift+Tab from first interactive element in dialog. | Focus wraps to last focusable element inside dialog (does not escape to pane). |

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

## Pass / Fail Recording

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

File any failures as GitHub issues tagged `a11y`.
