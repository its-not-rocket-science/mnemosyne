# WCAG 2.1 AA Audit — Mnemosyne

**Audit date:** 2026-05-27 (updated from 2026-04-18)
**Scope:** Parse → lesson → detail pane → concept help dialog → review flow; auth panel; RTL and CJK content.
**Method:** Static code review of all frontend HTML, CSS, and JS (index.html,
global.css, components.css, mnemosyne-modal.js, mnemosyne-pill.js,
mnemosyne-detail-pane.js, main.js, auth.js). No automated browser tool was run;
see `MANUAL_ACCESSIBILITY_TEST.md` for the full manual keyboard/AT test script.

---

## Automated / static audit — issues found and fixed

| # | Criterion | Issue | Fix applied |
|---|-----------|-------|-------------|
| 1 | 4.1.2 Name, Role, Value | Auth tabs lacked roving tabindex — both buttons were `tabindex="0"`, violating the ARIA APG tab pattern. | Set `tabindex="-1"` on inactive tab in HTML; `switchTab()` now updates `.tabIndex` on every switch. |
| 2 | 2.4.3 Focus Order | Login/logout did not move keyboard focus. After login, focus stayed on the disabled submit button; after logout it stayed on the Sign out button in the now-hidden header. | `showApp({ moveFocus: true })` focuses `#language` on login/register success; `showAuthPanel({ moveFocus: true })` focuses the email input on logout. |
| 3 | 1.3.1 Info and Relationships / 4.1.2 | Fill-blank drill input had no programmatic label — no `<label>`, `aria-label`, or `aria-labelledby`. | Prompt element given `id="drill-prompt-{index}"`; input given `aria-labelledby` pointing to that id. |
| 4 | 4.1.2 Name, Role, Value | "Speak" button text was ambiguous without surrounding visual context for AT users (two Speak buttons visible in the lesson modal). | Example-speak button: `aria-label="Speak example aloud"`. Shadowing-drill speak button: `aria-label="Speak drill text aloud"`. (Note: an earlier revision used `aria-label="Listen to example"` on the example-speak button — this violated SC 2.5.3; corrected in fix #8 below.) |
| 5 | 1.3.1 / 4.1.2 | `#auth-panel` was not `hidden` in HTML — AT could reach it while `#main-content` was visible, and signed-in users saw a flash. | Added `hidden` to `#auth-panel` in HTML; `initAuth()` removes it from the correct panel. |
| 6 | 1.4.11 Non-text Contrast | Input, textarea, and select borders used `color-mix(in srgb, CanvasText 20%, Canvas)` ≈ #CCC on white ≈ 1.6:1 against Canvas. Button borders in the modal used `color-mix(in srgb, CanvasText 25%, transparent)` ≈ 1.75:1. Both fail the 3:1 minimum required for UI component boundaries. | Introduced `--border-input: color-mix(in srgb, CanvasText 45%, Canvas)` in `:root` (≈ 3.1:1 in light mode; adequate in dark mode). Applied to `input`/`textarea`/`select` (global.css), `.ghost-button`/`.rating-button`/`.script-toggle__btn` (components.css), and all modal shadow-DOM buttons (mnemosyne-modal.js). Pill button borders raised from 35% to 60% of the type reference color — verify in browser per type-color since oklch values cannot be analytically reduced to WCAG luminance without rendering. |
| 7 | 1.3.1 Info and Relationships | `list-style: none` on `.sentence-card__pills` removes list semantics in Safari VoiceOver without a compensating `role="list"`, depriving AT users of the item count and position. | Added `list.setAttribute('role', 'list')` when building each pill `<ul>` in `renderResults()` (main.js). |
| 8 | 2.5.3 Label in Name | Example-speak button `aria-label="Listen to example"` did not contain the visible label text "Speak", violating the requirement that the accessible name contains the visible text. Voice-control users who say "click Speak" would fail. | Changed to `aria-label="Speak example aloud"` — "Speak" is now the first word of the accessible name. |

---

## Automated / static audit — no issues found

| Criterion | Check | Result |
|-----------|-------|--------|
| 1.1.1 Non-text Content | Pill emojis `aria-hidden="true"`; type-badge `aria-hidden="true"`; decorative eyebrow `aria-hidden="true"`; offline dot `aria-hidden="true"`; all buttons have text names. | ✓ |
| 1.3.1 | `<dl>` fields use `<dt>`/`<dd>` pairs; heading hierarchy correct (h1 → h2 per section/modal); all form inputs have `<label for="…">`. | ✓ |
| 1.3.2 Meaningful Sequence | DOM order matches reading order throughout; no CSS-only reordering that alters meaning. | ✓ |
| 1.4.1 Use of Color | Drill feedback uses ✓ / ✗ symbols + text, not color alone. Type signalled by icon + badge text + color tint. Rating buttons use text labels (Again/Hard/Good/Easy). | ✓ |
| 1.4.3 Contrast (text) | `--muted` (60% CanvasText ≈ 5.7:1); `--accent #3557ff` on white (≈ 4.86:1); `--error-color oklch(0.48 0.20 29)` annotated "dark enough for 4.5:1 on light Canvas"; drill feedback green `oklch(0.45 0.15 145)` is dark — verify manually (see below). | ✓ (manual verification recommended for oklch values) |
| 1.4.4 Resize Text | `clamp()` sizing throughout; no fixed `px` font sizes. | ✓ |
| 1.4.10 Reflow | Flex/grid layout reflows to single column at 320px; no horizontal scroll. Three specific 320px fixes applied in prior audit. | ✓ (verify manually) |
| 1.4.13 Content on Hover | No hover-only content. | ✓ |
| 2.1.1 Keyboard | All interactive elements reachable via Tab; modal focus trap via `inert` + Tab intercept; Escape closes modal; Arrow keys navigate auth tabs. Drill Check button and rating buttons all reachable. | ✓ |
| 2.1.2 No Keyboard Trap | Modal releases focus on close (`previouslyFocused.focus()`). Auth panel does not trap. | ✓ |
| 2.4.1 Skip Link | Present; `href="#main"` with `tabindex="-1"` on `<main>` for programmatic focus. | ✓ (verify manually — skip link target is inside `#main-content` which is hidden until auth) |
| 2.4.2 Page Titled | `<title>Mnemosyne</title>` present. | ✓ |
| 2.4.4 Link Purpose | Buttons have clear text or `aria-label`; privacy link text "Privacy policy" is descriptive; no generic "click here". | ✓ |
| 2.4.7 Focus Visible | All interactive elements have `:focus-visible` with `3px solid var(--accent)` outline; modal buttons use `3px solid var(--accent, #3557ff)`. Shadow-DOM `.dialog:focus { outline: none }` applies only to programmatic focus (modal open), not Tab navigation. | ✓ |
| 2.5.3 Label in Name | All button visible text is contained in or equals the accessible name. Fixed in issue #8 above. | ✓ (see fix #8) |
| 2.5.8 Target Size (WCAG 2.2) | `min-block-size: 2.75rem` (≈ 44 CSS px) on all interactive elements including auth tabs, pill buttons, and modal buttons. | ✓ |
| 3.1.1 Language of Page | `<html lang="en">`. | ✓ |
| 3.1.2 Language of Parts | `lang` set on sentence cards, pill buttons, modal title, example text, drill text/prompt, fill-blank input via `#applyTargetLang`. | ✓ |
| 3.2.1 On Focus | No context change on focus. | ✓ |
| 3.3.1 Error Identification | Auth errors and parse errors surfaced via `role="status"` / `role="alert"` live regions. `aria-invalid="true"` set on textarea when empty on submit. | ✓ |
| 3.3.2 Labels or Instructions | All form inputs have `<label>` with matching `for`; password strength hint linked via `aria-describedby="pw-hint"`. | ✓ |
| 4.1.1 Parsing | Semantic elements throughout; no duplicate IDs (drill IDs are index-scoped inside shadow DOM per lesson). | ✓ |
| 4.1.2 Name, Role, Value | Tablist/tab/tabpanel ARIA pattern correct; progressbar has `aria-valuenow/min/max`; `aria-busy` on select and submit button during async operations; `aria-required="true"` on required inputs; `aria-modal="true"` on dialog. | ✓ |
| 4.1.3 Status Messages | Parse count, review saved, lesson open, auth messages, file load — all use `role="status"` or `role="alert"` live regions. Clear-then-set pattern (via `queueMicrotask`) re-announces identical messages. | ✓ |

---

## Automated / static audit — 2026-05-27 additions (concept help dialog)

| # | Criterion | Issue | Fix applied |
|---|-----------|-------|-------------|
| 9 | 4.1.2 Name, Role, Value | Concept help dialog body was not linked to the `role="dialog"` element via `aria-describedby`, so AT had no programmatic association to the explanatory body text. | Added `id="dp-concept-body"` to the body `<div>`; added `aria-describedby="dp-concept-body"` to `#dp-concept-dialog`. |
| 10 | 4.1.3 Status Messages | When user navigates to a related concept inside the dialog, the body content updates but no live region announces the change, leaving AT users without confirmation that the view changed. | Added `aria-live="polite" aria-atomic="false"` to the concept dialog body element, so screen readers announce new concept text on update. |
| 11 | 2.4.6 Headings and Labels / 4.1.2 | All concept help `?` buttons had the same accessible name ("Explain concept"), making it impossible for AT users to distinguish the label-help button from the value-help button without surrounding visual context. | Label-help button `aria-label` now includes the field label (e.g. "Explain concept: Grammatical Case"); value-help button includes the field value (e.g. "Explain concept: nominative"). Same fix applied to morphology axis help buttons in the Form tab. |

---

## Automated / static audit — no issues found (concept dialog)

| Criterion | Check | Result |
|-----------|-------|--------|
| 2.1.1 Keyboard | Concept dialog has a focus trap: Tab cycles only through dialog's focusable elements; Escape closes dialog and returns focus to the triggering `?` button (not the detail pane close). | ✓ |
| 2.1.2 No Keyboard Trap | Dialog releases focus to trigger button on close. | ✓ |
| 1.3.1 Info and Relationships | Dialog uses `role="dialog"`, `aria-modal="true"`, `aria-labelledby="dp-concept-title"`, `aria-describedby="dp-concept-body"`. | ✓ |
| 2.4.3 Focus Order | On open: focus moves into dialog. On Escape/close-button: focus returns to trigger. On related-concept navigate: focus stays in dialog; body updates in-place. | ✓ |
| 4.1.2 Name, Role, Value | Close button has `aria-label="Close concept explanation"`. Back button has `aria-label="Back to previous concept"`. | ✓ (verify labels match final implementation) |

---

## Manual testing required

These items cannot be verified statically. Run before the public beta tag.

### Keyboard-only walkthrough

1. **Skip link** — Tab to skip link, activate, verify focus lands on `#language` select (inside `#main`). Test after sign-in since the target is hidden pre-auth.
2. **Auth panel** — Tab through Sign in form; Arrow-key navigate to Create account tab; confirm tabpanel switches and focus moves. Tab through register form.
3. **Language select** — Tab to `#language`; confirm options navigable with arrow keys; confirm `aria-busy` removed after load.
4. **Parse form** — Tab through all fields; activate "Load .txt file" label; activate "Fetch" button; submit parse form.
5. **Sentence cards and pills** — Tab through pill buttons; activate a pill with Enter/Space; confirm detail pane opens.
6. **Detail pane tabs** — Arrow keys navigate tabs; Escape closes pane and returns focus to pill.
7. **Concept help dialog** — Tab to a `?` button; press Enter; confirm dialog opens with focus inside; Tab cycles within dialog only; Escape closes dialog (not pane) and focus returns to `?` button. Confirm label-help and value-help buttons have distinct `aria-label` values.
8. **Modal focus trap** — Confirm focus is inside modal and Tab does not leave; Shift+Tab wraps to last focusable; Escape closes and returns focus to activating pill.
9. **Drill keyboard** — Multiple-choice: Tab to option, Space/Enter to answer. Fill-blank: Tab to input, type, Enter to submit. Shadowing: Tab to Speak button, Enter activates. True/false: same as multiple-choice.
10. **Rating buttons** — Tab to Again/Hard/Good/Easy; activate with Space/Enter; confirm "Saved" status announced.
11. **Logout** — Tab to Sign out button; activate; confirm auth panel shows and focus moves to email input.

### Screen-reader testing (NVDA + Chrome, VoiceOver + Safari)

1. **Auth panel tabs** — Announce as "Sign in, tab, 1 of 2" (NVDA) or "Sign in, selected, tab" (VoiceOver); arrow key announces and activates the other tab.
2. **Auth errors** — Mistyped password: live region announces the error message without moving focus.
3. **Language select `aria-busy`** — Should announce "Loading languages…" while busy, then the selected language after options load.
4. **Parse status** — "3 sentences parsed. Use Tab to navigate the items." announced after successful parse.
5. **Pill list** — Announced as a list with item count (e.g. "list, 5 items"); each pill announced as "Vocabulary lesson: gato, button".
6. **Modal title** — Dialog announced with its title when it opens.
7. **Concept help dialog** — Activating a `?` button announces dialog title and body text (via `aria-describedby`). Navigating to related concepts announces new body text via `aria-live="polite"`. Escape closes and focus returns to trigger button.
8. **Distinct concept button labels** — Two `?` buttons on the same field must announce different labels (field name vs field value). Tab between them to confirm no duplicate announcement.
9. **Drill feedback** — "✓ Correct!" / "✗ The answer is …" announced via polite live region.
10. **Review saved** — "Saved. Next review in 3 day(s)." announced after rating without focus move.
11. **RTL content** — Arabic/Hebrew example text announced with correct language voice; fill-blank input IME switches to RTL.
12. **Logout** — Focus and announcement move to auth panel email input.

### Colour contrast (browser DevTools or contrast analyser)

Verify these oklch/color-mix values in the rendered browser (cannot be analytically confirmed from source):

- **Drill feedback correct (light):** `oklch(0.45 0.15 145)` on Canvas white — need ≥ 4.5:1.
- **Drill feedback correct (dark):** `oklch(0.70 0.15 145)` on dark Canvas — need ≥ 4.5:1.
- **Pill button borders:** `color-mix(in oklch, <type-ref> 60%, Canvas)` — verify per type-color (green, blue, amber, purple, yellow, orange, teal, red) in both light and dark mode — need ≥ 3:1 against Canvas.
- **`--muted` text (60% CanvasText):** On system light/dark backgrounds — need ≥ 4.5:1 for small text, ≥ 3:1 for large text.
- **Auth tab active underline (`--accent` on `--surface`):** Need ≥ 3:1 non-text contrast.
- **`--border-input` (45% CanvasText):** Should be ≥ 3:1 against Canvas in default OS light/dark themes.

### 1.4.10 Reflow at 320px

- DevTools viewport at 320px wide.
- Auth panel form fields stack vertically; no horizontal overflow.
- Pill list wraps; sentence cards do not scroll horizontally.
- Modal does not exceed viewport width; `.fields` grid switches to single-column layout.

---

## Known limitations (deferred)

- **Automated tool run not performed.** A Lighthouse or axe-core sweep against the running app (not static source) may surface additional issues, particularly for dynamic content (options populated from `/languages`, cards rendered by `renderResults()`).
- **Windows High Contrast Mode** — `color-mix(in oklch, …)` may produce unexpected results under forced-color media. A `@media (forced-colors: active)` pass is recommended for components.css and the modal shadow DOM.
- **Zoom to 400%** — WCAG 2.1 AA requires 200% reflow; 400% (AAA) is worth testing since `max-block-size: 90dvh` on the modal combined with large font sizes may clip content on small viewports.
- **`inert` and older Safari** — VoiceOver + Safari 16 and earlier may not fully honour `inert` on shadow-DOM siblings. Test with Safari 17+; consider `aria-hidden` as a fallback for older versions if real-world usage warrants it.
- **Language not updated on page title** — The `<title>` remains "Mnemosyne" regardless of selected language. For multi-page apps this matters more; for this SPA it is an informational note.
