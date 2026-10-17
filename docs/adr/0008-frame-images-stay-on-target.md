# ADR-0008: Frame images stay on the Target

Status: accepted. Date: 2026-10-18. Amends [ADR-0005](0005-whole-pipeline-on-gpu-host.md) by
removing `recon/rgb` from the downloaded results, and SPEC's evidence stories: best views and answer
evidence carry a Frame id, not an image URL.

On Colab the tunnel from the Target back to the worker measured about 80 KB/s while uploads reached
5.7 MB/s. A 176-Keyframe Scene published 45 MB of `recon/rgb` PNG Frames against 17 MB of mesh and
3 MB of graph and embeddings, so the Frames made up about 70% of every Publication and kept it at
about a quarter of an hour. Their only use after publishing was `image_url` on best views and answer
evidence, and the frontend renders no evidence photos.

The worker now downloads only `graph`, `embeddings` and `mesh`, and only `mesh/` is public.
`BestView` keeps `frame_id`, `bbox` and `score` without `image_url`; answer evidence is
`{object_id, frame_id}`; the `get_object` QA tool no longer lists evidence images. Stages on the
Target still read `recon/rgb` (mesh colour, lift best views, segmentation, attributes).

Considered:

- **Publish only the Frames that best views reference, as JPEG.** About 88 of 176 Frames, 2.9 MB at
  quality 85: keeps evidence URLs for 5% of today's bytes, but adds a conversion step and a second
  image format for photos nobody displays. Rejected for now; it is the way back if evidence photos
  return to the UI.
- **Keep everything and rely on parallel downloads.** Parallel transfer hides latency, not a
  bandwidth limit; rejected.

Consequences: evidence photos cannot be shown without reprocessing under a different decision.
Publications made before this change still contain `recon/rgb`, but those files are no longer
served.
