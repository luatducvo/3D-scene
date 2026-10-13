# 14: Run GPU Stages on Modal

**What to build:** The single GPU image definition and a Modal deployment that builds from it, keeps one container, caches model weights on a Modal Volume, and serves the compute contract. A `modal` Target in compute configuration and a deploy task. Includes the one-time human setup of a Modal account, token and secret.

**Blocked by:** 13

**Status:** needs-human — code and deploy file ready; requires the user's Modal account, secret and `uv run tasks.py deploy-modal`

- [ ] Human step documented: create the Modal account, log in the CLI, create the secret holding the compute token and HF token.
- [ ] `uv run tasks.py deploy-modal` deploys and prints the endpoint URL; putting it in compute configuration is the only other change.
- [ ] With the GPU Stages (still fake) targeting Modal, a Scene processes end-to-end from the browser.
- [ ] A scaled-to-zero container is waited for (cold start) instead of failing the Job.
- [ ] The unverified Modal options (Dockerfile build args, web server with concurrency and startup timeout) are confirmed and noted.
