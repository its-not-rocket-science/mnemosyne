# WCAG 2.1 AA Audit — Mnemosyne

**Audit date:** 2026-04-16  
**Scope:** Parse → lesson → review flow; auth panel; RTL and CJK content.

---

## Automated / static audit — issues found and fixed

| # | Criterion | Issue | Fix applied |
|---|-----------|-------|-------------|
| 1 | 4.1.2 Name, Role, Value | Auth tabs lacked roving tabindex — both buttons were `tabindex="0"`, violating the ARIA APG tab pattern. | Set `tabindex="-1"` on inactive tab in HTML; `switchTab()` now updates `.tabIndex` on every switch. |
| 2 | 2.4.3 Focus Order | Login/logout did not move keyboard focus. After login, focus stayed on the disabled submit button; after logout it stayed on the Sign out button in the now-hidden header. | `showApp({ moveFocus: true })` focuses `#language` on login/register success; `showAuthPanel({ moveFocus: true })` focuses the email input on logout. |
| 3 | 1.3.1 Info and Relationships / 4.1.2 | Fill-blank drill input had no programmatic label — no `<label>`, `aria-label`, or `aria-labelledby`. | Prompt element given `id="drill-prompt-{index}"`; input given `aria-labelledby` pointing to that id. |
| 4 | 4.1.2 Name, Role, Value | "Speak" button text was ambiguous without surrounding visual context for AT users (two Speak buttons on screen in the lesson modal). | Example-speak button: `aria-label="Listen to example"`. Shadowing-drill speak button: `aria-label="Speak drill text aloud"`. |
| 5 | 1.3.1 / 4.1.2 | `#auth-panel` was not `hidden` in HTML — AT could reach it while `#main-content` was visible, and signed-in users saw a flash. | Added `hidden` to `#auth-panel` in HTML; `initAuth()` removes it from the correct panel. |

---

## Automated / static audit — no issues found

| Criterion | Check | Result |
|-----------|-------|--------|
| 1.1.1 Non-text Content | Pill emojis `aria-hidden="true"`; type-badge `aria-hidden="true"`; buttons have text names. | ✓ |
| 1.3.1 | `<dl>` fields use `<dt>`/`<dd>` pairs; heading hierarchy correct. | ✓ |
| 1.4.1 Use of Color | Drill feedback uses ✓ / ✗ symbols + text, not color alone. Type is signalled by icon + badge text + color tint. | ✓ |
| 1.4.4 Resize Text | `clamp()` sizing throughout; no `px` font sizes that would break at 200% zoom. | ✓ |
| 1.4.10 Reflow | Flex/grid layout reflows to single column; no horizontal scroll at 320px. | Verify manually (see below). |
| 1.4.13 Content on Hover | No hover-only content. | ✓ |
| 2.1.1 Keyboard | All interactive elements reachable via Tab; modal focus trap via `inert` + Tab intercept; Escape closes modal; Arrow keys navigate auth tabs. | ✓ |
| 2.1.2 No Keyboard Trap | Modal releases focus on close (`previouslyFocused.focus()`). Auth panel doesn't trap. | ✓ |
| 2.4.1 Skip Link | Present; moves focus to `#main`. | ✓ (verify manually — skip link target hidden until auth) |
| 2.4.2 Page Titled | `<title>Mnemosyne</title>` present. | ✓ |
| 2.4.4 Link Purpose | Buttons have clear text or `aria-label`. | ✓ |
| 2.4.7 Focus Visible | All elements have `:focus-visible` with 3px solid accent outline. | ✓ |
| 2.5.3 Label in Name | Button visible text matches accessible name (or accessible name contains the visible text). | ✓ |
| 2.5.8 Target Size (2.5.8 — WCAG 2.2) | `min-block-size: 2.75rem` (≈44px) on all interactive elements. | ✓ |
| 3.1.1 Language of Page | `<html lang="en">`. | ✓ |
| 3.1.2 Language of Parts | `lang` set on sentence cards, pill buttons, modal title, example text, drill text, fill-blank input. | ✓ |
| 3.2.1 On Focus | No context change on focus. | ✓ |
| 3.3.1 Error Identification | Auth errors surfaced via `role="status"` live region. | ✓ |
| 3.3.2 Labels or Instructions | All form inputs have `<label>` with matching `for`; password strength hint linked via `aria-describedby`. | ✓ |
| 4.1.1 Parsing | HTML uses semantic elements; no duplicate IDs (drill IDs are index-scoped inside shadow DOM). | ✓ |
| 4.1.3 Status Messages | Parse count, review saved, lesson open, auth messages all use `role="status"` or `role="alert"` live regions. | ✓ |

---

## Manual testing required

These items cannot be verified statically. They should be tested before the public beta tag.

### Keyboard-only walkthrough

1. **Skip link** — Tab to skip link, activate, verify focus lands on `#language` select (inside `#main`). Note: skip link target is inside `#main-content` which is hidden until auth; after sign-in verify skip link works.
2. **Auth panel** — Tab through Sign in form; Arrow-key navigate to Create account tab; confirm tabpanel switches and focus moves. Tab through register form.
3. **Language select** — Tab to `#language`; confirm options navigable with arrow keys; confirm `aria-busy` removed after load.
4. **Parse form** — Tab through all fields; activate "Load .txt file" label; activate "Fetch" button; submit parse form.
5. **Sentence cards and pills** — Tab through pill buttons; activate a pill with Enter/Space; confirm modal opens.
6. **Modal focus trap** — Confirm focus is inside modal and Tab does not leave; Shift+Tab wraps correctly; Escape closes and returns focus to activating pill.
7. **Drill keyboard** — Multiple-choice: Tab to option, Space/Enter to answer. Fill-blank: Tab to input, type, Enter to submit. True/false: same as multiple-choice.
8. **Rating buttons** — Tab to Again/Hard/Good/Easy; activate with Space/Enter.
9. **Logout** — Tab to Sign out button; activate; confirm auth panel shows and focus moves to email input.

### Screen-reader testing (NVDA + Chrome, VoiceOver + Safari)

1. **Auth panel tabs** — Announce as "Sign in, tab, 1 of 2" (NVDA) or "Sign in, selected, tab" (VoiceOver); arrow key announces and activates the other tab.
2. **Auth errors** — Mistyped password: live region announces the error message.
3. **Language select `aria-busy`** — NVDA/VoiceOver should announce "Loading languages…" while busy, then announce the selected language after options load.
4. **Parse status** — "3 sentences parsed. Use Tab to navigate the items." announced after successful parse.
5. **Pill accessible names** — "Vocabulary lesson: gato" (not the emoji or badge alone).
6. **Modal title** — Dialog is announced with its title when it opens.
7. **Drill feedback** — "✓ Correct!" / "✗ The answer is …" announced via live region without requiring user action.
8. **Review saved** — "Saved. Next review in 3 day(s)." announced after rating.
9. **RTL content** — Arabic/Hebrew example text announced with the correct language voice; fill-blank input IME switches to RTL.
10. **Logout** — "Sign out button" announced; after click, focus and announcement move to auth panel.

### Colour contrast (manual or with browser DevTools)

- Drill feedback green (`oklch(0.45 0.15 145)` on light Canvas): verify ≥ 4.5:1.
- Drill feedback green dark mode (`oklch(0.70 0.15 145)` on dark Canvas): verify ≥ 4.5:1.
- `var(--muted)` text (60% CanvasText): on system light/dark backgrounds verify ≥ 4.5:1 for small text, ≥ 3:1 for large.
- Auth tab active underline (accent colour on surface): verify ≥ 3:1 non-text contrast.

### 1.4.10 Reflow at 320px

- Open DevTools, set viewport to 320px wide.
- Auth panel form fields should stack vertically without overflow.
- Pill list should wrap; no horizontal scroll introduced.
- Modal should not exceed viewport width.

---

## Known limitations (deferred to future work)

- **Screen-reader testing on macOS/iOS** — VoiceOver behaviour with shadow DOM (mnemosyne-modal, mnemosyne-pill) differs between browsers and OS versions. Particularly the `inert` propagation on older Safari. Test with Safari 17+.
- **Windows High Contrast Mode** — `color-mix(in oklch, …)` may produce unexpected results under forced-color media. Add a `@media (forced-colors: active)` pass to components.css and modal CSS.
- **Zoom to 400%** — WCAG 2.1 AA only requires 200% reflow; 400% is AAA but worth testing on the modal since `max-block-size: 90dvh` combined with large font sizes may clip content.
