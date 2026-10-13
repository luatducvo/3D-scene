# 19: 2D segmentation with SAM 3

**What to build:** The real SAM 3 segmentation Algorithm on Modal, prompted with the default indoor English Vocabulary (200–400 noun phrases), keeping masks above the score threshold and merging overlapping masks per Frame.

**Blocked by:** 14, 16

**Status:** needs-live-check — adapter done; SAM 3 on Modal not run

- [ ] The default Vocabulary exists and is referenced from pipeline configuration.
- [ ] Processing my room writes per-Frame masks, labels and scores per the contract; the Manifest reports mask count and Vocabulary size.
- [ ] Gated checkpoint access works with the HF token on Modal; weights are cached on the Volume.
- [ ] Manual smoke check: masks for obvious furniture look correct on a few Frames.
