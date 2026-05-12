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
- **State changed:** none directly in this module.
- **Persistence:** none directly from button click.
- **UI changed:** opens external difficulty dialog via `window.mnemosyneDifficulty?.openDialog?.()`.
- **Lesson/annotation rendering:** none directly.
- **Difficulty impact:** potential, delegated to difficulty dialog module.
- **Notes:** **incomplete from this control alone**; it is a launcher, not a direct toggle.

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

## Gaps, cosmetic controls, duplication, wiring findings

1. **Adaptive appears in two places conceptually:**
   - Main-bar **Adaptive** button = dialog launcher.
   - Advanced/system-body **Adaptive toggle** = actual feature state.
   - This is functional but conceptually duplicated and can confuse users.

2. **⚙ gear is disclosure-only (cosmetic relative to learning behavior):**
   - It does not alter lesson or difficulty itself; it only reveals controls that do.

3. **Adaptive button itself is incomplete as a behavior control:**
   - No local state mutation, no persistence, no announce; behavior is delegated to an external dialog API.
   - If `window.mnemosyneDifficulty` is unavailable, click is effectively no-op.

4. **Potential fallback duplication path exists by design:**
   - `adaptive-reader.js` can create `#reader-adaptive-toolbar` fallback when unified system body is absent; in normal integrated path it populates `#reader-system-body`.
   - This is not active duplication at runtime when unified bar exists, but it is dual code path complexity.
