# Accessibility Manual Test Checklist

Manual validation for WCAG 2.2 AA.  Run after any change touching HTML
structure, ARIA attributes, focus management, or live regions.

Code-level audit completed 2026-05-09.  Manual AT tests below are the
remaining validation gate before claiming WCAG 2.2 AA.

---

## Pre-test setup

| Item | Action |
|------|--------|
| Test URL | `http://localhost:8080` (static frontend, backend running) |
| Baseline | Sign in, parse a short Spanish text, confirm sentence cards appear |
| NVDA | version ≥ 2023.x · Firefox ≥ 120 |
| VoiceOver | macOS 14+ or iOS 17+; Safari |
| Mobile | Chrome Android + TalkBack **or** Safari iOS + VoiceOver |
| Windows HC | Settings → Accessibility → High Contrast, any theme |

---

## 1 — Keyboard-only (no AT)

Use only Tab / Shift+Tab / Enter / Space / Arrow keys / Escape.

### 1.1 Page load and skip link

- [ ] Tab from URL bar → skip link "Skip to content" becomes visible
- [ ] Enter on skip link → focus lands on `#main` (parse dialog or results)
- [ ] Tab again → focus enters the parse dialog naturally

### 1.2 Authentication flow

- [ ] Tab → skip link → Tab → auth email field is reached without extra stops
- [ ] Arrow Right / Arrow Left on Sign-in / Create-account tabs switches panel and moves focus
- [ ] Tab within sign-in form visits: email → password → Sign in button
- [ ] Enter on Sign in → success → focus jumps to Language select (first app control)
- [ ] Shift+Tab from Language select → no focus escapes to hidden auth panel

### 1.3 Parse dialog → results

| Step | Expected |
|------|----------|
| Focus lands in parse dialog | Language `<select>` is first focusable element |
| Tab to "Choose your text" | Button reachable, Enter opens text-picker dialog |
| Text-picker dialog opens | Focus moves to textarea |
| Escape | Dialog closes, focus returns to "Choose your text" button |
| Tab to "Fetch" button in text-picker | URL input → Fetch button reachable |
| Tab to "Use this text" | Reachable after text is entered |
| Submit text, parse completes | Parse dialog closes (or stays inline); results section appears |
| Results announced | `#status` live region says "N sentences parsed" |

### 1.4 Sentence cards and annotation marks

- [ ] Tab → reaches each sentence play button in order
- [ ] Annotation marks (coloured pills) are reachable via Tab within each sentence card
- [ ] Enter or Space on a mark → detail pane opens, focus moves to first tab
- [ ] Arrow Left / Arrow Right inside detail pane tab bar switches tabs
- [ ] Escape → detail pane closes, focus returns to the triggering mark
- [ ] Tab does not escape into the inert rest of the page while detail pane is open

### 1.5 Detail pane tabs

- [ ] First tab (Explanation) selected on open
- [ ] Arrow Right → Origins tab (if present) selected and focused
- [ ] Arrow Right again → Context tab
- [ ] Tab from tab bar → moves into the tab panel content, not to the next tab
- [ ] Shift+Tab from first panel element → returns to tab bar

### 1.6 Lesson modal (mnemosyne-modal)

- [ ] "Study" button in detail pane → modal opens, focus on dialog container
- [ ] Tab cycles through: Close → Script-view toggles (if present) → Speak → drill options → rating buttons → back to Close
- [ ] Shift+Tab wraps correctly
- [ ] Rating button click → live region announces result (e.g. "Saved. Next review in 3 day(s).")
- [ ] Escape → modal closes, focus returns to "Study" button
- [ ] Background content is inert (Tab cannot leave modal)

### 1.7 Playback controls

- [ ] Space when focus is in results area (not on button) → plays / pauses
- [ ] Arrow Left / Arrow Right → previous / next sentence announced
- [ ] F → "Follow along enabled / disabled" announced
- [ ] ? → shortcuts dialog opens; Escape closes it

### 1.8 Save / Load lesson dialogs

- [ ] "Save lesson" button → dialog opens, title input focused
- [ ] Escape → dialog closes, focus returns to "Save lesson" button
- [ ] "Load a saved lesson" dialog → list items reachable via Tab, Enter loads

### 1.9 About dialog tabs

- [ ] Footer "About Mnemosyne" button → dialog opens
- [ ] Two tabs: "One principle" (selected) and "Why Mnemosyne?"
- [ ] Arrow Right → "Why Mnemosyne?" tab selected and focused
- [ ] Arrow Left → "One principle" tab selected and focused
- [ ] Tab from tab bar → moves into panel content

### 1.10 Footer

- [ ] Privacy policy link → GDPR dialog opens, focus on first button; Escape closes
- [ ] Interface language select → reachable by Tab, changes UI language

---

## 2 — NVDA + Firefox

NVDA browse mode (arrow) and application/forms mode (NVDA+Space).

### 2.1 Page structure

- [ ] Headings list (NVDA+F6 or H key): h1 "Turn text into a living lesson", h2 parse heading, h2 results heading all present
- [ ] Landmark list (NVDA+F7 or D key): banner, main, contentinfo (footer) present; "Phrase details" landmark appears after annotation mark activated
- [ ] No duplicate `aria-label` values on landmarks

### 2.2 Live regions

| Region | Trigger | Expected announcement |
|--------|---------|-----------------------|
| `#status` (role=status) | Parse completes | "3 sentences parsed" (or similar) |
| `#a11y-live` (role=status) | Annotation focused | "Annotation: [label]" |
| `#reader-nowplaying` (aria-live=polite) | Playback starts | sentence text announced |
| Drill feedback (aria-live=polite) | Answer selected | "✓ Correct!" or "✗ The answer is …" |
| Modal status (role=status) | Rating saved | "Saved. Next review in N day(s)." |
| Modal error (role=alert) | Rating fails | error message announced immediately |

### 2.3 Dialogs

- [ ] Native `<dialog>` opens → NVDA announces dialog role and accessible name (h2 text)
- [ ] Escape closes dialog → NVDA reads the page content the trigger was on
- [ ] `mnemosyne-modal` (shadow DOM) → NVDA reads "dialog, [word]" on open

### 2.4 Forms

- [ ] Every input has a visible and announced label (no "unlabelled field")
- [ ] `aria-required` fields announced as "required" before value
- [ ] Password hint `#pw-hint` announced via `aria-describedby` when password field focused
- [ ] Error messages in `role=status` regions announced without browsing to them

### 2.5 RTL content (Arabic / Hebrew)

- [ ] Parse Arabic or Hebrew text
- [ ] Annotation marks read with correct RTL text in order
- [ ] Detail pane: field values in Arabic/Hebrew are announced with correct language tag (lang="ar" / lang="he")
- [ ] No garbled reading order caused by bidi algorithm confusion

---

## 3 — VoiceOver + Safari (macOS)

Use VO+U for rotor, VO+Left/Right to navigate, VO+Space to activate.

### 3.1 Headings and landmarks

- [ ] Rotor → Headings: correct hierarchy visible
- [ ] Rotor → Landmarks: main, banner, contentinfo present

### 3.2 Modal

- [ ] Lesson modal opens → VoiceOver announces "web dialog [word]"
- [ ] VO+Tab cycles within the modal shadow DOM
- [ ] Escape closes, VoiceOver returns to trigger element

### 3.3 Custom elements as buttons

- [ ] `<mark role="button">` annotation pills announced as "button, [label]"
- [ ] Activation via VO+Space opens detail pane

### 3.4 Live regions

- [ ] Parse status, drill feedback, and rating result all announced without user navigation

### 3.5 CJK (Chinese / Japanese)

- [ ] Parse Chinese or Japanese text
- [ ] VoiceOver reads characters with correct language tag (lang="zh" / lang="ja")
- [ ] Pinyin / romaji fields announced when present (script-view toggle works in AT)

---

## 4 — Mobile screen reader smoke test

### 4.1 TalkBack (Android, Chrome)

- [ ] Swipe to navigate: skip link → page landmark summary → parse dialog
- [ ] Double-tap on "Choose your text" → text-picker opens
- [ ] Double-tap on annotation mark → detail pane opens, VoiceOver announces it
- [ ] Swipe left/right within tab bar switches tabs
- [ ] Double-tap "Close" or swipe-dismiss → detail pane / modal closes, focus returns
- [ ] Live regions fire for parse completion and drill feedback

### 4.2 VoiceOver (iOS, Safari)

- [ ] Swipe through page in reading order: skip link → nav → h1 → parse controls
- [ ] Flick right past all annotation marks without focus trap
- [ ] Modal closes on two-finger scrub (standard VoiceOver dismiss)
- [ ] RTL text (Arabic, Hebrew) announced in correct direction

---

## 5 — Windows High Contrast

Switch to any High Contrast theme; reload the page.

- [ ] All text is readable (no white-on-white or black-on-black)
- [ ] Sentence-card borders visible (2px ButtonText border via forced-colors rule)
- [ ] Focus outlines visible on all interactive elements (3px Highlight outline)
- [ ] Annotation marks distinguishable without colour only (border present in forced-colors)
- [ ] Correct / wrong drill state uses `outline: 3px solid Highlight / Mark` not colour fill only
- [ ] Modal overlay backdrop visible (UA maps `color-mix(black)` to a system shadow equivalent)
- [ ] No content lost due to background-image gradient stripping

---

## 6 — Reduced motion

Enable "Reduce Motion" in OS settings or browser `prefers-reduced-motion: reduce`.

- [ ] Sentence-card hover: no `box-shadow` transition
- [ ] Primary button hover: no `translateY(-1px)` transform
- [ ] Detail pane: no slide-in transition (should appear immediately)
- [ ] Now-playing bar: no slide animation
- [ ] Passage transitions (if enabled): no scroll animation
- [ ] Status live regions: `transition: none` (no fade-in delay that might swallow announcement)

---

## 7 — Colour contrast spot-check

Use browser DevTools accessibility panel or axe browser extension.

| Element | Expected ratio | WCAG level |
|---------|----------------|------------|
| Primary button text (#fff on --tc-500 #C44B22) | ≥ 4.73:1 | AA |
| Secondary text (--wn-600 on --wn-50) | ≥ 7.89:1 | AAA |
| Annotation mark label on card background | ≥ 4.5:1 | AA |
| Disabled button (opacity 0.5) | exempt | — |
| Focus outline (3px accent on adjacent bg) | ≥ 3:1 | AA (2.4.11) |
| Drill feedback "correct" (oklch 0.45 0.15 145 on Canvas) | ≥ 4.5:1 | AA |

---

## 8 — Known gaps / external-test-only items

These cannot be verified statically and are not covered by automated tests:

| Gap | Why external |
|-----|--------------|
| NVDA + Firefox screen-reader smoke test | Requires live AT interaction |
| VoiceOver + Safari modal dismiss | Requires iOS device or macOS AT |
| TalkBack swipe-dismiss detail pane | Requires Android device |
| Pitch-accent and tonal language TTS accuracy | Requires listening test |
| Actual screen-reader reading order in RTL | bidi rendering is browser-specific |

---

## Automated smoke test

No Playwright dependency exists in this repo.  A lightweight static
structural check lives in `backend/tests/test_accessibility_static.py`
and verifies without a browser:

- Every `<dialog>` in `index.html` has `aria-labelledby` pointing to an `<h2>`
- Every `<input>` and `<textarea>` (by id pattern) has a matching `<label for>`
- The skip link `href="#main"` matches a `<main id="main">` element
- `role="tablist"` containers have at least two `role="tab"` children
- `role="tab"` elements each have `aria-controls` pointing to an existing `role="tabpanel"`
- The `#a11y-live` live region is present with `role="status"` and `aria-live="polite"`

Run: `pytest backend/tests/test_accessibility_static.py -v`
