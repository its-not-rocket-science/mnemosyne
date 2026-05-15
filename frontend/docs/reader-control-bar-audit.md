# Reader Control Bar Audit

This audit covers controls in `#reader-control-bar`: **Subtle, Learning, Deep, Flow, Focus, Adaptive, and ⚙ advanced settings**.

## Control-by-control behavior

### 1) Subtle
- **State changed:** sets `currentMode = 'subtle'` in `reading-experience.js`.
- **Persistence:** writes localStorage key `mnemosyne.reader.annotationMode`.
- **UI changed:** marks the Subtle segmented button as active (`aria-pressed`, active class).
- **Lesson/annotation rendering:** sets `document.documentElement.dataset.annotationReveal` and `#results[data-annotation-reveal]` to `subtle`.
- **Difficulty impact:** no direct difficulty modulation.
- **Notes:** behavior is meaningful and wired.

### 2) Learning
- **State changed:** sets `currentMode = 'learning'`.
- **Persistence:** writes `mnemosyne.reader.annotationMode`.
- **UI changed:** Learning segmented button active.
- **Lesson/annotation rendering:** same dataset toggle path (`annotationReveal='learning'`).
- **Difficulty impact:** no direct difficulty modulation.
- **Notes:** this is also the fallback default if mode is invalid.

### 3) Deep
- **State changed:** sets `currentMode = 'deep'`.
- **Persistence:** writes `mnemosyne.reader.annotationMode`.
- **UI changed:** Deep segmented button active.
- **Lesson/annotation rendering:** dataset toggle path (`annotationReveal='deep'`).
- **Difficulty impact:** no direct difficulty modulation.
- **Notes:** meaningful and wired.

### 4) Flow
- **State changed:** toggles `flowMode` in `flow-mode.js`.
- **Persistence:** writes `mnemosyne.reader.flowMode`.
- **UI changed:** Flow button `aria-pressed`, active class, localized on/off label.
- **Lesson/annotation rendering:** toggles `body.reader-flow-mode`; while playback is active it marks active sentence card (`data-flow-active`) and centers it.
- **Difficulty impact:** indirectly changes playback speed by pacing mode (`mnemosyne:pacing-updated` -> TTS rate mapping).
- **Notes:** fully wired and meaningful.

### 5) Focus
- **State changed:** toggles `focusMode` in `reading-experience.js`.
- **Persistence:** writes `mnemosyne.reader.focusMode`.
- **UI changed:** Focus button `aria-pressed`, active class, localized on/off label.
- **Lesson/annotation rendering:** toggles `body.reader-focus-mode` (page dim/focus styling).
- **Difficulty impact:** none.
- **Notes:** meaningful and wired.

### 6) Adaptive (main bar button)
- **State changed:** toggles `adaptiveEnabled` in `adaptive-reader.js` via `mnemosyne:toggle-adaptive-reader` event.
- **Persistence:** `mnemosyne.reader.adaptive.enabled` written by adaptive-reader.js handler.
- **UI changed:** `aria-pressed` + active class updated; annotation visibility changes on next render cycle.
- **Lesson/annotation rendering:** directly affects annotation quieting based on memory strength.
- **Difficulty impact:** none; difficulty settings are in ⚙ Advanced settings.
- **Notes:** properly wired — button reflects real adaptive state. Difficulty dialog moved to ⚙ system body.

### 7) ⚙ Advanced settings
- **State changed:** toggles visibility of `#reader-system-body` (`hidden` flag).
- **Persistence:** none.
- **UI changed:** updates `aria-expanded` and open class on the gear button.
- **Lesson/annotation rendering:** none by itself.
- **Difficulty impact:** none by itself.
- **Notes:** **disclosure-only control**; meaningful primarily as container access.

## What is inside Advanced settings (system body)

These are populated by `adaptive-reader.js` and are the controls that actually alter adaptive behavior:

- **Adaptive on/off toggle** (`#reader-adaptive-toggle`)
  - Persists `mnemosyne.reader.adaptive.enabled`
  - Toggles `body.reader-adaptive-enabled`
  - Quiets known/low-level annotations and updates minimap/summary.

- **Reinforcement toggle** (`#reader-reinforcement-toggle`)
  - Persists `mnemosyne.reader.reinforcement.enabled`
  - Toggles `body.reader-reinforcement-enabled`
  - Hides strong-memory annotations in reinforcement mode.

- **Sync / Reset actions**
  - Sync refreshes memory from `/dashboard`.
  - Reset clears local adaptive memory state.

## Notes

1. **Adaptive button is now a real toggle:**
   - Dispatches `mnemosyne:toggle-adaptive-reader`; `adaptive-reader.js` handles state mutation, persistence, and render.
   - `aria-pressed` reflects `adaptiveEnabled` state; `reader-focus-btn--active` class applied when on.
   - `reading-experience.js` re-syncs the button on `mnemosyne:adaptive-reader-changed`.

2. **Difficulty settings are in ⚙ Advanced settings:**
   - "Difficulty settings…" button in the system body opens the modulation dialog.
   - No longer accessible from the main bar (correct: it is an advanced preference, not a reading mode).

3. **⚙ gear is disclosure-only (cosmetic relative to learning behavior):**
   - It does not alter lesson or difficulty itself; it only reveals controls that do.

4. **Fallback toolbar path (`#reader-adaptive-toolbar`) remains for offline/no-control-bar contexts.**
