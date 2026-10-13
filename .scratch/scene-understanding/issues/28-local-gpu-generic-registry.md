# 28: Local GPU profile, generic host and registry image publishing

**What to build:** The optional local-GPU Compose profile running the same compute image with shared storage, a generic Docker-host deployment guide, tasks to build and push the compute image to a registry, and the model download task.

**Blocked by:** 14

**Status:** implemented — local-gpu profile, generic guide and image tasks written; not exercised (6 GB GPU)

- [ ] The local-GPU profile starts and passes the readiness ping (fitting real models on a 6 GB GPU is not required).
- [ ] Build and push tasks produce a `linux/amd64` image in the registry.
- [ ] The model download task fetches weights into the host model cache without loading them on a GPU.
- [ ] The generic guide lists the run command, required environment and the compute configuration entry.
