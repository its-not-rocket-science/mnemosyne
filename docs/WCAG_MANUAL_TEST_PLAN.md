# Mnemosyne — WCAG 2.1 AA Manual Test Plan

**Version:** 1.0  
**Scope:** Public beta accessibility QA  
**Standard:** WCAG 2.1 AA + WCAG 2.2 SC 2.4.11, 2.5.8  
**Last updated:** 2026-04-19

---

## Contents

1. [Setup and tools](#1-setup-and-tools)
2. [Bug severity rubric](#2-bug-severity-rubric)
3. [Issue template](#3-issue-template)
4. [Test scenarios](#4-test-scenarios)
   - [A — Auth flows](#a--auth-flows)
   - [B — Parse → lesson → review](#b--parse--lesson--review)
   - [C — Dashboard and metrics](#c--dashboard-and-metrics)
   - [D — Recommend](#d--recommend)
   - [E — RTL language rendering](#e--rtl-language-rendering)
   - [F — Keyboard-only navigation](#f--keyboard-only-navigation)
   - [G — Focus trap and modal escape](#g--focus-trap-and-modal-escape)
   - [H — Live regions and announcement quality](#h--live-regions-and-announcement-quality)
   - [I — Reduced motion](#i--reduced-motion)
   - [J — Mobile layout (320 px)](#j--mobile-layout-320-px)
   - [K — Touch targets](#k--touch-targets)
   - [L — NVDA smoke test (Windows)](#l--nvda-smoke-test-windows)
   - [M — VoiceOver smoke test (macOS/iOS)](#m--voiceover-smoke-test-macosios)
5. [Regression checklist after each language addition](#5-regression-checklist-after-each-language-addition)

---

## 1. Setup and tools

### Browsers

| Browser | Minimum version | Use for |
|---------|----------------|---------|
| Chrome (stable) | 120+ | Primary desktop + DevTools |
| Firefox (stable) | 121+ | Secondary keyboard test |
| Safari (macOS) | 17+ | VoiceOver |
| Safari (iOS) | 17+ | VoiceOver mobile |
| Chrome (Android) | 120+ | TalkBack (not in this plan) |

### Assistive technology

| Tool | Platform | Version | Pairing |
|------|----------|---------|---------|
| NVDA | Windows | 2023.3+ | Chrome |
| VoiceOver | macOS | built-in | Safari |
| VoiceOver | iOS | built-in | Safari |

### DevTools setup

- **Accessibility tree:** Chrome DevTools → Accessibility tab (Elements panel)
- **Contrast checker:** Chrome DevTools → CSS Overview → Colors, or axe DevTools extension
- **Reduced motion:** Chrome DevTools → Rendering → Emulate CSS media feature `prefers-reduced-motion: reduce`
- **Mobile viewport:** DevTools → Device toolbar → set width to 320 px, then 375 px, then 768 px
- **Touch targets:** Chrome DevTools → Lighthouse → Accessibility audit (tap-target sizes)

### Application setup

1. Server running: `make up` or `make dev`
2. Frontend served at `http://localhost:8080`
3. At least one parse result already in DB (run through B-01 first)
4. Test user account created: email `qa-tester@example.com`, password `TestPass123!`
5. A second test user for multi-user isolation: `qa-tester-2@example.com`

### Notation

| Symbol | Meaning |
|--------|---------|
| `[Tab]` | Press Tab key |
| `[Shift+Tab]` | Press Shift+Tab |
| `[Enter]` | Press Enter |
| `[Space]` | Press Space |
| `[Esc]` | Press Escape |
| `[Arrow]` | Arrow keys |
| `SR: "…"` | Screen reader announces exactly or substantially this text |
| `✓` | Expected pass state |
| `✗` | Record as failure |

---

## 2. Bug severity rubric

| Severity | Label | Definition | SLA |
|----------|-------|-----------|-----|
| **S1** | Blocker | Prevents a user from completing a core task with AT or keyboard alone. No workaround exists. Blocks beta launch. | Fix before ship |
| **S2** | Critical | Task is completable but requires significant extra effort, causes confusion, or violates a WCAG 2.1 AA success criterion. | Fix within 7 days |
| **S3** | Major | Degrades the experience noticeably but doesn't block task completion. Violates a best practice or WCAG 2.2 criterion. | Fix within 30 days |
| **S4** | Minor | Cosmetic or low-impact issue. Inconsistency, suboptimal announcement, missing enhancement. | Backlog |

### Automatic severity escalation

Any issue affecting RTL scripts or non-Latin input that would also affect an LTR user at the same step is escalated by one level (S3 → S2, S2 → S1).

---

## 3. Issue template

Copy this template when filing a bug:

```
**Test ID:** [e.g. F-03]
**WCAG SC:** [e.g. 2.1.1 Keyboard]
**Severity:** [S1 / S2 / S3 / S4]
**Browser + AT:** [e.g. Chrome 120 + NVDA 2023.3]
**OS:** [e.g. Windows 11]
**Viewport:** [e.g. 1280×800 / 320px mobile]
**UI language:** [e.g. English / Arabic]

**Steps to reproduce:**
1. 
2. 
3. 

**Expected:** [What should happen]
**Actual:** [What actually happened]
**Screenshot / recording:** [attach]
**Notes:** [any additional context]
```

---

## 4. Test scenarios

---

### A — Auth flows

#### A-01 — Register: keyboard and contrast

**WCAG:** 1.4.3 Contrast, 2.1.1 Keyboard, 4.1.2 Name Role Value  
**Severity if fails:** S1 (keyboard), S2 (contrast)

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Load `http://localhost:8080`. Tab once. | Focus lands on skip link; skip link becomes visible. | |
| 2 | Press Enter on skip link. | Focus jumps to main content area. | |
| 3 | Page loads with auth panel visible (not logged in). Tab to "Sign in / Create account" tabs. | Tab and Create account tabs are keyboard-focusable; focus ring visible on focused tab. | |
| 4 | Press right arrow or Tab to reach "Create account" tab; press Enter or Space. | Register form revealed. `aria-selected="true"` on Create account tab. | |
| 5 | Tab through form fields: Email, Password, Confirm password, Create account button. | Each field and button receives focus in logical order. No fields are skipped. | |
| 6 | Inspect each label: click label text → focus moves to associated input. | Labels are programmatically associated (`for`/`id` or `aria-labelledby`). | |
| 7 | Using contrast checker: inspect Email field border, Password field border, button background. | All borders ≥ 3:1 against page background. Button text ≥ 4.5:1 against button background. | |
| 8 | Fill Email: `qa-tester@example.com`. Tab to Password. Type `short`. Tab to Confirm. Tab to button. Press Enter. | Validation error appears. Error message is announced by SR (not just colour change). Errors reference field names. | |
| 9 | Fill all fields correctly. Submit. | Redirect to main app. Focus moves to a meaningful element (heading or parse form). SR announces context change. | |

#### A-02 — Login: error state and autocomplete

**WCAG:** 1.3.5 Identify Input Purpose, 4.1.3 Status Messages  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Log out. Tab to Sign in tab. Tab to Email field. | `autocomplete="email"` attribute present on email input. | |
| 2 | Type wrong password. Submit. | 401 error message appears on page. SR announces error without requiring focus move (live region or focus management). | |
| 3 | Error message does not reveal whether email exists or not. | Message reads "Invalid email or password" (or local equivalent) — same for both wrong email and wrong password. | |
| 4 | Correct credentials. Submit. | Logged in. SR announces new state or heading. | |

#### A-03 — Sign out and account deletion

**WCAG:** 2.1.1, 4.1.2  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Tab to account button / user menu. | Button is keyboard-focusable. Label includes user identity (e.g. "Account" or username). | |
| 2 | Activate Sign out. | Session ends. Auth panel returns. Focus moves to a meaningful target (not lost to body). | |
| 3 | Log back in. Tab to Delete account button. Activate it. | Confirmation dialog or inline confirmation appears. Not immediate destructive action. | |
| 4 | Confirm deletion. | Account deleted. Redirected to auth. SR announces outcome. | |

---

### B — Parse → lesson → review

#### B-01 — Parse form: labels, errors, progress bar

**WCAG:** 1.3.1, 2.1.1, 4.1.3  
**Severity if fails:** S1 (keyboard), S2 (live region)

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Tab to Language select. | Label "Language" is announced by SR. Current value announced. | |
| 2 | Open Language select with Space/Enter. Navigate with arrow keys. Select Spanish. Close with Esc or Enter. | Selection works keyboard-only. Closed select does not blur focus prematurely on arrow key press. | |
| 3 | Tab to Title field. | Announced as "Title (optional)" or equivalent. | |
| 4 | Tab to Source URL field. Tab to Text to parse textarea. | Each field is announced with its label. `placeholder` text is not the only label. | |
| 5 | Leave Text empty. Tab to "Parse text" button. Press Enter. | Error "Please enter some text" appears. Announced via live region (polite or assertive). Focus does not move unexpectedly. | |
| 6 | Type "El gato duerme en la silla de madera." in textarea. Press Enter on Parse text button. | Progress bar appears. Label "Parsing text…" (or current UI language equivalent) is visible. Progress bar has `role="progressbar"` with `aria-valuenow` or `aria-label`. | |
| 7 | Wait for parse to complete. | Status region (`role="status"`) announces e.g. "1 sentence parsed. Use Tab to navigate the items." No bell-and-whistle announcement. | |
| 8 | Tab away from the parse button after completion. | Focus moves to first pill or results area in logical DOM order. | |

#### B-02 — Pill interaction

**WCAG:** 2.1.1, 4.1.2, 2.5.3 Label in Name  
**Severity if fails:** S1 (keyboard), S2 (name)

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | After parse, Tab to first pill button. | Pill is focusable. Focus ring visible. Accessible name matches visible label (e.g. "gato"). | |
| 2 | Continue tabbing through all pills in the sentence. | All pills reachable via Tab in document order. No pills skipped. | |
| 3 | Activate first pill with Enter. | Modal opens. SR announces: lesson title or equivalent (e.g. "Lesson open: gato."). | |
| 4 | Without moving focus, press `[Esc]`. | Modal closes. Focus returns to the pill that opened it. | |
| 5 | Reopen modal. Tab within modal. | Focus is trapped inside modal. Tabbing past last interactive element wraps to first. `inert` prevents reaching background content. | |
| 6 | Shift+Tab from first focusable element in modal. | Focus wraps to last element inside modal. Does not reach background. | |

#### B-03 — Lesson modal content

**WCAG:** 1.3.1, 3.1.2, 4.1.2  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Open a vocabulary lesson (Spanish word). | Modal heading announces word. POS, definition, and example are in readable order in the accessibility tree. | |
| 2 | If example text is in Spanish, inspect `lang` attribute on example element. | `lang="es"` or equivalent present on the example text element, not just on a parent. | |
| 3 | Tab to "Speak" button. Activate. | TTS plays. Button label is meaningful without visual context ("Speak example aloud" not just an icon). | |
| 4 | If multiple-choice drill present: Tab to each option. | Options are keyboard-activatable. Selected state communicated (`aria-pressed` or radio role). | |
| 5 | Submit a drill answer. | Feedback (correct/incorrect) announced by SR. Uses `role="alert"` (assertive) for error, `role="status"` (polite) for success. | |
| 6 | Tab to quality rating buttons (Again / Hard / Good / Easy). | All four buttons reachable. Labels match visible text. | |
| 7 | Activate Good (quality=3). | Modal closes or updates. SR announces outcome. Focus returns to pill or moves logically. | |

#### B-04 — Review submission and offline queue

**WCAG:** 4.1.3  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Open DevTools → Network → set to "Offline". Open a lesson. Submit a review. | Review queued silently. Offline badge appears with count. SR announces badge change via live region. | |
| 2 | Restore network (set back to Online). | Queue drains automatically. Badge count decreases or disappears. No duplicate announcements flood the SR. | |
| 3 | Simulate expired JWT: open lesson, manually clear `sessionStorage`. Submit review. | 401 response. SR announces "Session expired — log in again to sync queued reviews" (or UI language equivalent). Badge remains showing queued count. | |

---

### C — Dashboard and metrics

#### C-01 — Dashboard keyboard and structure

**WCAG:** 1.3.1, 2.4.6 Headings and Labels  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Navigate to Dashboard (Tab to nav link or direct URL). | Page has a visible `<h1>` or equivalent. Section headings (Known, Weak, New, Due) are marked as headings or labelled regions. | |
| 2 | Tab through dashboard items. | Items in Known/Weak/New lists are navigable. No keyboard traps. | |
| 3 | Using NVDA/VO: navigate by headings (`H` key in NVDA). | Dashboard sections are reachable by heading navigation without reading all content. | |
| 4 | Resize text to 200% (browser zoom). | No content clipped. Horizontal scroll does not appear on any section at 320 px equivalent. | |

#### C-02 — Metrics page structure

**WCAG:** 1.3.1, 1.4.3  
**Severity if fails:** S3

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Navigate to Metrics. | Page has logical heading structure. | |
| 2 | Any data presented as a chart or colour-coded element: confirm the same information is also in text. | Colour is not the only means of conveying information (SC 1.4.1). | |
| 3 | Inspect "weakest" list items. Each item has object_id, type, mastery_score, lapse_rate. | Values are in the accessibility tree (not hidden from SR). | |

---

### D — Recommend

#### D-01 — Recommend results

**WCAG:** 1.3.1, 2.1.1  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | After at least one parse, navigate to Recommend (if exposed in UI) or call `GET /recommend?language=es`. | Results display. | |
| 2 | Tab through recommended sentences. | Each sentence item is reachable via keyboard. | |
| 3 | Inspect difficulty labels ("easy", "ideal", "hard"). | Labels are in text (not colour-only). | |

---

### E — RTL language rendering

#### E-01 — Arabic parse and modal

**WCAG:** 1.3.2, 3.1.2  
**Severity if fails:** S1 (layout breakage preventing task), S2 (incorrect direction)

Setup: Select Arabic (`ar`) as lesson language.

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Paste: `الكتاب على الطاولة`. Parse. | Sentence card text renders right-to-left. `dir="rtl"` applied to sentence text element. Text not mirrored or broken. | |
| 2 | Open a vocabulary pill. | Modal title, example sentence, drill prompt all render RTL. Text does not bleed into LTR elements. `<bdi>` or `dir="rtl"` present on Arabic text nodes. | |
| 3 | Tab through modal in Arabic mode. | Focus order follows visual order: close button at expected position, fields tab in correct sequence. | |
| 4 | Fill-blank drill with Arabic input: activate input field, type Arabic characters. | Input accepts RTL text. Cursor position and caret movement match RTL expectations. | |
| 5 | Inspect drill feedback text containing both English metalanguage and Arabic word. | `<bdi>` prevents bidirectional bleed. Arabic word does not disrupt surrounding LTR sentence structure. | |
| 6 | Offline badge (if visible) and other UI chrome. | Page chrome remains LTR (not flipped). Only target-language content is RTL. | |

#### E-02 — Hebrew parse and modal

Same as E-01 using Hebrew (`he`) and text: `הספר על השולחן`.

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Paste Hebrew text. Parse. | Sentence card renders RTL. `dir="rtl"` applied. | |
| 2 | Open lesson modal. | Modal content RTL. | |
| 3 | Nikud (vowel marks) display correctly — not stripped or corrupted. | Hebrew text with vowel points renders intact. | |
| 4 | Tab order through modal. | Logical for RTL content. | |

#### E-03 — UI language set to Arabic

**WCAG:** 3.1.1  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Switch UI language to Arabic using the language switcher. | All UI labels (buttons, headings, placeholders) update to Arabic. | |
| 2 | Inspect `<html lang="...">` attribute. | `lang="ar"` set on root element when UI is Arabic. | |
| 3 | The parse form and results area text direction. | UI chrome is RTL. Form flows right-to-left. | |
| 4 | Tab through the page. | Focus order follows visual RTL layout. Skip link still functional. | |
| 5 | Open modal in Arabic UI mode with a Spanish (LTR) lesson. | Modal UI text is RTL. Lesson example text (Spanish) is LTR within its element. No direction mixing breaks layout. | |

---

### F — Keyboard-only navigation

Run these tests with mouse **disconnected or disabled**. Tab, Shift+Tab, Enter, Space, Arrow keys, Esc only.

#### F-01 — Full task flow keyboard-only

**WCAG:** 2.1.1, 2.4.3 Focus Order  
**Severity if fails:** S1

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Load app (not logged in). Tab twice. | Skip link → first focusable element. No focus lost to body or `<html>`. | |
| 2 | Keyboard-navigate through register flow. Create account. | All form fields and submit button reachable. Error messages navigable without mouse. | |
| 3 | Keyboard-navigate: select language (Spanish), fill textarea, press Parse text button. | Select opens and closes with Space/Enter/Esc. No arrow key triggers blur on closed select. | |
| 4 | Tab to first pill after parse. Open lesson. Navigate drill. Submit review. Close modal. | Entire flow completable without mouse. | |
| 5 | Tab to account controls. Sign out. | Sign out button reachable and activatable. | |

#### F-02 — Select focus stability

**WCAG:** 3.2.1 On Focus  
**Severity if fails:** S2

This tests the WeakSet blur fix.

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Tab to Language select. Focus lands on it. | Select does not blur or trigger change on focus alone. | |
| 2 | Press down arrow once. | Next option highlighted inside select. Select does not close. Focus remains on select. | |
| 3 | Press down arrow five more times rapidly. | Each press moves selection. Select stays open. No premature close. | |
| 4 | Press Escape. | Select closes. Focus stays on the select element (does not jump). | |
| 5 | Press Space to reopen. Select an option. Press Enter. | Select closes with new value. Focus stays on select. | |
| 6 | Click select with mouse, then press arrow. | Dropdown opens. Arrow navigates. No blur. | |

#### F-03 — Roving tabindex on tab panels

**WCAG:** 2.1.1, 2.4.3  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Tab to auth panel tabs (Sign in / Create account). | One tab receives focus. | |
| 2 | Press right arrow. | Focus moves to the other tab AND its panel is shown. | |
| 3 | Press left arrow. | Returns to previous tab. | |
| 4 | Tab from tabs to first form field. | Focus enters the currently active panel. Does not enter the hidden panel. | |

#### F-04 — Focus visibility

**WCAG:** 2.4.7 Focus Visible, 2.4.11 Focus Appearance (WCAG 2.2)  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Tab through every interactive element in: parse form, pill list, modal, auth form, dashboard, account button. | Every focused element shows a visible focus indicator (ring, outline, or underline). No element has `outline: none` without a replacement. | |
| 2 | Inspect focus ring colour against the element's background. | Focus ring contrast ≥ 3:1 against adjacent colours (SC 2.4.11). Solid outline (not `color-mix(..., transparent)`). | |
| 3 | Open modal. Tab to close button. Inspect. | Close button focus ring visible inside modal shadow DOM. | |

---

### G — Focus trap and modal escape

#### G-01 — Focus trap correctness

**WCAG:** 2.1.2 No Keyboard Trap (trap must be escapable), 2.4.3  
**Severity if fails:** S1

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Open lesson modal via keyboard. Tab 20 times. | Focus never leaves modal. Cycles within: [close btn] → [lesson content interactive elements] → [quality buttons] → [close btn]. | |
| 2 | Shift+Tab from close button. | Focus wraps to last interactive element in modal (quality button or last focusable). Does not reach page background. | |
| 3 | Tab from last element in modal. | Wraps to first element (close button or modal container). | |
| 4 | Verify `inert` on background: open DevTools while modal is open. Inspect `<main>` or sibling `<body>` children. | `inert` attribute present on all siblings of the modal's containing element. | |

#### G-02 — Modal close and focus return

**WCAG:** 2.4.3  
**Severity if fails:** S1

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Open modal from pill A via keyboard. Close with Esc. | Focus returns to pill A exactly. Not to body, not to a different pill. | |
| 2 | Open modal from pill B. Click close button. | Focus returns to pill B. | |
| 3 | Open modal. Submit a review (which may close modal or update it). | If modal closes after review, focus returns to originating pill. If modal stays open, focus moves to a logical next target within modal. | |
| 4 | Open modal. Click outside modal area (backdrop). | Modal closes if backdrop click is handled. Focus returns to originating pill. If backdrop click is not handled, that is acceptable — modal must still be closeable via Esc. | |
| 5 | Open modal. Press Tab until focus would leave modal. Open a second modal from within (if any nested trigger exists). | Focus trap transfers to innermost modal. Closing inner modal returns focus to trigger inside outer modal, not to page background. | |

#### G-03 — Inert restoration

**WCAG:** 2.1.2  
**Severity if fails:** S1

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Open modal. Close with Esc. Tab through page. | Background elements are reachable again. `inert` removed from all previously inert elements. | |
| 2 | Open modal, close, open again. | Trap re-engages correctly. No stale `inert` attributes left on modal container itself. | |

---

### H — Live regions and announcement quality

#### H-01 — Parse status announcements

**WCAG:** 4.1.3 Status Messages  
**Severity if fails:** S2

Test with SR active (or check via accessibility tree that `role="status"` region updates correctly).

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Submit parse. | SR announces "Parsing text…" (or UI language equivalent) without focus change. | |
| 2 | Parse completes (1 sentence). | SR announces "1 sentence parsed. Use Tab to navigate the items." without focus change. | |
| 3 | Parse completes (3 sentences). | SR announces "3 sentences parsed. Use Tab to navigate the items." | |
| 4 | Submit empty parse. | SR announces the error message. Focus does not move unexpectedly. | |
| 5 | Inspect `#status` in DevTools. | Element has `role="status"` (polite live region). `aria-live="polite"` or equivalent. Clear-then-set pattern: textContent set to '' then new value via `queueMicrotask`. | |

#### H-02 — Lesson modal live region

**WCAG:** 4.1.3  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Open lesson. Submit correct drill answer. | SR announces positive feedback politely. Modal does not steal focus from drill area. | |
| 2 | Submit incorrect answer. | SR announces error assertively (`role="alert"`). | |
| 3 | Submit review (quality rating). | SR announces result or next state change. | |
| 4 | Inspect modal shadow DOM: `.status` and `.status-error` elements. | `.status` has `role="status"` (polite). `.status-error` has `role="alert"` (assertive). Both use clear-then-set pattern. | |

#### H-03 — Offline badge live region

**WCAG:** 4.1.3  
**Severity if fails:** S3

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Go offline. Submit a review. | Offline badge count increases. SR announces change (should be polite — not assertive). | |
| 2 | Come back online. Queue drains. | SR announces badge change or absence. Not silent. Not overly verbose (one announcement per drain, not per review). | |

#### H-04 — Progress bar announcements

**WCAG:** 4.1.3  
**Severity if fails:** S3

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Submit parse. Inspect progress bar element. | `role="progressbar"` present. `aria-valuenow` updates as progress increases (or `aria-label` with descriptive text). `aria-valuemin="0"` and `aria-valuemax="100"`. | |
| 2 | Parse completes. | `aria-valuenow="100"` set. Label changes to "Done." (or UI language equivalent). | |
| 3 | Progress bar hidden after completion. | Element has `hidden` attribute or `display:none`. SR does not announce residual progress values. | |

---

### I — Reduced motion

**WCAG:** 2.3.3 Animation from Interactions (AAA — test anyway)  
Also tests author commitment to `prefers-reduced-motion`.

#### I-01 — Progress bar animation

**Severity if fails:** S3

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Enable `prefers-reduced-motion: reduce` via DevTools → Rendering. | |
| 2 | Submit a parse. | Progress bar fills deterministically. No scanning stripe animation (`progress-scan` keyframe suppressed). | |
| 3 | Inspect `.job-progress__bar--indeterminate` styles. | `animation: none` applied. Bar is set to full width at reduced opacity instead. | |
| 4 | Inspect any other animated elements (pills on hover, modal transitions, offline badge). | All transitions either: (a) instant (0 ms duration), or (b) opacity-only (no translate/scale). No spin, bounce, or sliding animations remain. | |

#### I-02 — Lesson modal transitions

**Severity if fails:** S3

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | With reduced motion active: open modal. | Modal appears immediately. No slide-in or fade-in animation. | |
| 2 | Close modal. | Modal disappears immediately. | |
| 3 | Without reduced motion: open and close modal. | Transition present if implemented. Duration ≤ 300 ms. | |

---

### J — Mobile layout (320 px)

Set DevTools device to 320 × 568 (iPhone SE 1st gen — smallest common viewport).

#### J-01 — Parse form at 320 px

**WCAG:** 1.4.10 Reflow  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Load app at 320 px. No horizontal scroll. | Content reflows into single column. No element requires horizontal scrolling to read. | |
| 2 | Inspect user info email in header. | Email truncates with ellipsis (`text-overflow: ellipsis`) rather than overflowing container. | |
| 3 | Language select, title input, text textarea, parse button. | All form elements full-width or close to it. No elements clipped. | |
| 4 | Parse a short text. Pill list renders. | Pills wrap to multiple lines if needed. No overflow. Horizontal scroll absent. | |

#### J-02 — Lesson modal at 320 px

**WCAG:** 1.4.10 Reflow  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Open lesson modal at 320 px. | Modal fills screen without content clipping. Close button visible. | |
| 2 | Fill-blank drill: inspect input. | Input fills its row (`flex: 1 1 0`). Not clipped at left or right edge. | |
| 3 | Label–value pairs (lemma, gender, POS etc.): inspect `.fields` grid layout. | Switches to single-column stacked layout. Values do not overflow their cells. | |
| 4 | Quality rating buttons (Again / Hard / Good / Easy). | Buttons are visible and tappable. Do not overflow or stack illegibly. | |
| 5 | Scroll within modal. | Modal is scrollable when content exceeds viewport. Close button always visible (sticky or accessible via scroll). | |

#### J-03 — Auth form at 320 px

**WCAG:** 1.4.10  
**Severity if fails:** S2

| # | Step | Expected result | Pass? |
|---|------|----------------|-------|
| 1 | Load auth panel at 320 px. | Tab bar (Sign in / Create account) renders inline or stacked legibly. | |
| 2 | Fill register form. | Email, password, confirm password, and button all visible without horizontal scroll. | |

---

### K — Touch targets

**WCAG:** 2.5.8 Target Size (Minimum) — 24 × 24 CSS px minimum; 44 × 44 CSS px recommended  
**Severity if fails:** S3 (24 px minimum), S2 if below 24 px

#### K-01 — Interactive element sizes

| # | Element | Method | Expected size | Pass? |
|---|---------|--------|--------------|-------|
| 1 | Parse text button | Inspect computed `min-block-size` | ≥ 2.75 rem (≈ 44 px) | |
| 2 | Each pill button | Inspect computed height | ≥ 2.75 rem | |
| 3 | Modal close button | Inspect | ≥ 2.75 rem | |
| 4 | Quality rating buttons (Again/Hard/Good/Easy) | Inspect | ≥ 2.75 rem | |
| 5 | Auth tab buttons (Sign in / Create account) | Inspect | ≥ 2.75 rem | |
| 6 | Sign out button | Inspect | ≥ 2.75 rem | |
| 7 | Delete account button | Inspect | ≥ 2.75 rem | |
| 8 | Language switcher select | Inspect hit area (not just text height) | ≥ 2.75 rem | |
| 9 | Speak button (TTS) | Inspect | ≥ 2.75 rem | |
| 10 | Script view toggle (if present) | Inspect | ≥ 2.75 rem | |

Run Lighthouse (mobile preset) → Accessibility → check "Tap targets" for any items flagged < 48 px.

---

### L — NVDA smoke test (Windows)

**Setup:** Windows + Chrome (latest). NVDA 2023.3+. Browse mode (`Ins+F7` = elements list, `H` = next heading, `B` = next button, `F` = next form field, `Tab` = next focusable, `Ins+T` = window title).

#### L-01 — Page structure

| # | Step | Expected announcement | Pass? |
|---|------|-----------------------|-------|
| 1 | Load app. | Page title announced: "Mnemosyne" or equivalent. | |
| 2 | Press `Ins+F7` → Headings. | At minimum: one `<h1>` heading present. Section headings in logical order. | |
| 3 | Press `H` to navigate headings. | Main heading "Turn text into a living lesson" (or UI lang equivalent) announced. | |
| 4 | Press `F` to navigate form fields. | Email, Password fields announced with labels. Not just placeholder text. | |

#### L-02 — Parse and pill flow

| # | Step | Expected announcement | Pass? |
|---|------|-----------------------|-------|
| 1 | Tab to Language select. | SR: "Language, Spanish, combo box" (or similar). | |
| 2 | Type text. Tab to Parse button. Press Enter. | SR announces: "Parsing text…" from live region. | |
| 3 | Parse completes. | SR announces: "N sentences parsed. Use Tab to navigate the items." | |
| 4 | Tab to first pill. | SR announces word label, e.g. "gato, button". | |
| 5 | Press Enter on pill. | SR announces: "Lesson open: gato." (or UI lang equivalent). Dialog role announced. | |
| 6 | NVDA reads lesson content. | Word, POS, definition, example text all read in order. `lang` attribute causes pronunciation switch for Spanish example. | |
| 7 | Press Esc. | SR announces focus return (pill or surrounding element). | |

#### L-03 — Error and status announcements

| # | Step | Expected announcement | Pass? |
|---|------|-----------------------|-------|
| 1 | Submit empty parse. | SR announces error message without focus change. | |
| 2 | Submit wrong login credentials. | SR announces error. "Invalid email or password" or equivalent. | |
| 3 | Go offline. Submit review. | Offline badge count change announced politely. | |

---

### M — VoiceOver smoke test (macOS/iOS)

#### M-01 — macOS VoiceOver (Safari)

**Setup:** macOS + Safari. Enable VoiceOver: `Cmd+F5`. Navigation: `VO+Arrow` = read next/prev, `VO+Shift+M` = interact with web area, `Tab` = next focusable, `VO+U` = rotor.

| # | Step | Expected announcement | Pass? |
|---|------|-----------------------|-------|
| 1 | Load app. Press `VO+U` → Headings rotor. | Main heading present. | |
| 2 | Tab to language select. | VoiceOver: "Language, pop-up button" (Safari renders `<select>` as pop-up). | |
| 3 | Tab to textarea. | "Text to parse, text area" or equivalent. | |
| 4 | Tab to Parse button. Press Space. | VoiceOver announces parse status from live region. | |
| 5 | Tab to pill. | "gato, button" announced. | |
| 6 | Press Space on pill. | "Lesson open: gato" announced. Dialog presented. | |
| 7 | Press Esc inside modal. | Focus returns to pill. VoiceOver reads pill. | |
| 8 | Check `role="list"` on pill `<ul>`. | VoiceOver should announce list with item count. (VoiceOver + Safari suppresses list semantics for `list-style: none` without `role="list"`.) | |

#### M-02 — iOS VoiceOver (Safari)

**Setup:** iPhone Safari. Enable VoiceOver: Settings → Accessibility → VoiceOver. Swipe right = next element, double-tap = activate, two-finger swipe up = read all.

| # | Step | Expected result | Pass? |
|---|------|----|-------|
| 1 | Load at 375 px. Two-finger swipe up. | Page reads title, then heading, then form in order. No skipped regions. | |
| 2 | Swipe to Language select. Double-tap. | Picker or list appears. Accessible. | |
| 3 | Swipe to textarea. Double-tap. Type text using software keyboard. | Text input works. Cursor position accessible. | |
| 4 | Swipe to Parse button. Double-tap. | Parse triggered. Live region announces status. | |
| 5 | Swipe to a pill. Double-tap. | Modal opens. VoiceOver moves focus inside modal. | |
| 6 | Swipe through modal. | Content readable. No infinite loops. | |
| 7 | Two-finger scrub (Z gesture). | Modal closes. Focus returns to pill. | |
| 8 | Inspect at 320 px: swipe through modal content. | All content reachable without horizontal scroll. Touch targets large enough to activate without precision tapping. | |

---

## 5. Regression checklist after each language addition

Run this abbreviated checklist whenever a new language plugin is added or an existing plugin receives significant changes.

| # | Check | Criterion |
|---|-------|-----------|
| 1 | Sentence card: `dir` and `lang` attributes set correctly for new language | SC 3.1.2 |
| 2 | Modal example text: `dir` and `lang` on example element | SC 3.1.2 |
| 3 | Pill list: `role="list"` present on `<ul>` | SC 1.3.1 |
| 4 | Lesson heading: accessible name matches visible label | SC 2.5.3 |
| 5 | Drill input: accepts characters from the new script without corruption | SC 2.1.1 |
| 6 | Touch targets: all pill buttons ≥ 44 px for new language (longer words may wrap) | SC 2.5.8 |
| 7 | Contrast: lesson content text against modal background in both light and dark modes | SC 1.4.3 |
| 8 | NVDA: `lang` attribute triggers pronunciation switch in example sentence | SC 3.1.2 |
| 9 | If RTL: `<bdi>` wrapping in all drill feedback strings | SC 1.3.2 |
| 10 | If RTL: UI chrome remains LTR when UI language is LTR and target language is RTL | SC 1.3.2 |

---

## Appendix — WCAG success criteria reference

| SC | Title | Level | Where tested |
|----|-------|-------|-------------|
| 1.3.1 | Info and Relationships | A | B-01, B-03, C-01, E |
| 1.3.2 | Meaningful Sequence | A | E-01, G |
| 1.3.5 | Identify Input Purpose | AA | A-02 |
| 1.4.1 | Use of Color | A | C-02 |
| 1.4.3 | Contrast (Minimum) | AA | A-01, C-02 |
| 1.4.10 | Reflow | AA | J |
| 1.4.11 | Non-text Contrast | AA | A-01, F-04 |
| 2.1.1 | Keyboard | A | A, B, F |
| 2.1.2 | No Keyboard Trap | A | G |
| 2.4.1 | Bypass Blocks | A | A-01, F-01 |
| 2.4.3 | Focus Order | A | F, G |
| 2.4.7 | Focus Visible | AA | F-04 |
| 2.4.11 | Focus Appearance | AA (WCAG 2.2) | F-04 |
| 2.5.3 | Label in Name | A | B-02 |
| 2.5.8 | Target Size (Minimum) | AA (WCAG 2.2) | K |
| 3.1.1 | Language of Page | A | E-03 |
| 3.1.2 | Language of Parts | AA | B-03, E, L-02 |
| 3.2.1 | On Focus | A | F-02 |
| 3.2.2 | On Input | A | F-02 |
| 4.1.2 | Name, Role, Value | A | A, B, F, G |
| 4.1.3 | Status Messages | AA | B-01, H |
