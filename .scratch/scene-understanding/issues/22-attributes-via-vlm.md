# 22: Object attributes and Vietnamese labels via VLM

**What to build:** The CPU attributes Algorithm sends 1–3 crops per Object to an OpenAI-compatible vision model configured by environment and stores color, material, state and a Vietnamese label. Attributes and Vietnamese labels show in the Object list and detail and take part in search label matching.

**Blocked by:** 20

**Status:** needs-live-check — fake-server test done; requires VLM_* keys

- [ ] After processing, Objects show attributes and a Vietnamese label.
- [ ] The VLM endpoint, key and model come from environment only; switching provider needs no code change.
- [ ] Malformed model output for one Object leaves that Object without attributes and is counted in the Manifest, instead of failing silently.
- [ ] The Stage test uses a fake OpenAI-compatible server.
