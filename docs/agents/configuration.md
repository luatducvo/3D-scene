# Configuration

Choosing an Algorithm, its params or a Target is a configuration change, not a code change.

## Files

| File | Holds |
| --- | --- |
| `backend/config/pipeline.yaml` | the real Algorithm for each Stage and its params |
| `backend/config/pipeline.fake.yaml` | Fake Algorithms on the in-process `cpu` Target; the default when `PIPELINE_CONFIG` is unset |
| `backend/config/pipeline.fake-gpu.yaml` | Fake Algorithms on `${GPU_TARGET}`, to test a remote Target without weights |
| `backend/config/compute.yaml` | every Target: `inprocess` or `http` with URL, token, chunk size, timeouts |
| `backend/config/vocabularies/*.txt` | Vocabularies for the segment Stage, one concept per line |
| `backend/.env.example` | every backend environment variable, with a comment |
| `frontend/.env.example` | `NEXT_PUBLIC_API_URL`, `API_INTERNAL_URL`, `NEXT_PUBLIC_API_MODE` (`http` or `mock`) |

## Rules

- A pipeline file declares all eight Stages in order and one `target` that every Stage runs on.
- `${VAR}` in a YAML file expands from the environment. In a pipeline file an unset variable stays literal, so the worker's start-up error names it.
- `PIPELINE_CONFIG`, `COMPUTE_CONFIG` and `GPU_TARGET` select the files and the Target.
- A new environment variable goes into the matching `.env.example` with a comment. `backend/.env` holds the user's secrets: never commit it, print it or copy values out of it. `main.py` creates it from `.env.example` on first use.
- `uv run main.py reset` deletes every Scene and the database. Ask before running it.
