# Memory Map audit (current behavior)

## Answer
The current app **does not directly measure learner knowledge via in-app drill/test correctness in the Memory Map UI layer**. The map is an **inferred exposure/review-strength signal**.

## Where logic lives
- UI model/rendering: `frontend/js/adaptive-reader.js`
- UI copy/labels: `frontend/js/i18n.js`
- API source used for sync: `GET /dashboard` in `backend/api/routes/dashboard.py`
- Dashboard status + mastery scoring: `backend/srs/knowledge.py`

## What Weak / Fading / Strong are based on
In `adaptive-reader.js`, each annotation gets a local record with:
- `strength` (0..1)
- `lastReviewed`
- `decayRate`
- `nextReview`

Band thresholds are:
- **Strong**: `strength >= 0.82`
- **Fading**: `0.55 <= strength < 0.82`
- **Weak**: `strength < 0.55`

Strength decays over elapsed time using an exponential function (`currentStrength`).

## Inputs used (and not used)
### Used
1. **Manual annotation labels** (`weak` / `learning` / `known`) set from the reader UI buttons.
2. **Dashboard sync values** from backend `UserKnowledgeRow` (`status`, `mastery_score`, `last_seen`, `due_at`, `total_reviews`).
3. **Time decay heuristic** in frontend (`currentStrength`).

### Not used directly by Memory Map banding
- No direct scoring stream from a dedicated quiz/drill correctness endpoint is consumed in this UI module.
- No per-question right/wrong aggregation is computed inside `adaptive-reader.js`.

Note: Dashboard mastery/status itself is FSRS-based retrievability from review history (`backend/srs/knowledge.py`), but Memory Map still presents a **derived UI band**, not a direct psychometric mastery test result.

## Copy adjustment made
To avoid implying measured mastery:
- “Memory map” label changed to **“Exposure map”**.
- Help copy now explicitly states this is inferred and not a graded test score.
- Inline/tooltips changed from “Memory %” to **“Exposure %” / “inferred exposure”**.
