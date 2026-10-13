# 25: Capture guide, quality badges and upload progress

**What to build:** The new-Scene flow gains three capture tips, an in-browser sharpness and exposure score per image computed in a Web Worker (green / amber / red badge), and an upload progress bar.

**Blocked by:** 05

**Status:** done

- [ ] The capture tips show before the dropzone.
- [ ] Each dropped image gets a badge without freezing the page; I can remove red ones before upload.
- [ ] A large upload shows a moving progress bar.
- [ ] Frontend tests cover badge thresholds on sample images.
