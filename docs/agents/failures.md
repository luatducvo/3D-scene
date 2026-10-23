# Failures

## Nothing falls back

A failure surfaces; no code path stands in for the one that failed.

- An Algorithm, model or Target that fails raises. Its Stage fails, then its Job, then its Scene, and the Scene keeps its previous Publication.
- Do not add an alternative method, a default value in place of a missing input or output, a CPU path when `device: cuda` was configured, or a silent skip.
- Retrying the same call is not a fallback: waiting for a cold Target, or retrying a 429 or 5xx from the same endpoint, is fine.
- Reading is strict too. A Publication or Stage output that lacks a file the current code expects is invalid and raises; the user reprocesses the Scene. Do not add branches for results written by older code.

## Raising

- Backend code raises `SceneError(code, message, status_code=400, details=None)` from `scene_core/errors.py`. The code is UPPER_SNAKE_CASE and stable; the message is an English sentence a user can act on.
- Reuse an existing code when one fits; `grep -rn 'SceneError("' backend` lists them. Common ones: `INVALID_PARAMETERS`, `INVALID_MODEL_OUTPUT`, `RESULTS_INVALID`, `COMPUTE_UNAVAILABLE`, `COMPUTE_FAILED`, `SCENE_BUSY`, `SCENE_NOT_FOUND`.
- An exception raised inside a Stage, on any Target, becomes the Scene's `failure` `{stage, code, message, details}`; an error that is not a `SceneError` becomes `STAGE_FAILED`. A failure during publish has stage `publish`.
- scene-compute returns the Algorithm's own code and details for a failed Compute Run, so a failure reads the same in-process and on a GPU host.

## Showing

- The API answers every error as `{"error": {"code", "message"}}`; streamed endpoints send it as an `error` event.
- The frontend turns these into `ApiError(code, message)` (`src/lib/api/errors.ts`) and shows them; it never replaces an error with made-up content.
