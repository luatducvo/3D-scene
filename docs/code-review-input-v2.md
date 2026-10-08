# Input v2 review

Reviewed `git diff 2ed393e...2979f20` in two independent agents against ticket 25,
ADR 0009 and the user's Q1–Q4 plus final design confirmation.

## Standards

No documented-standard violations. The independent script/backend verifiers and
stable artifact namespace conform to the chosen boundary and Scene preservation.

**Possible Duplicated Code, P3:** raw alignment parsing and Package verification
repeated the same shape/finite/rigid-transform rules. Fixed with
`is_rigid_transform` inside the standalone script. The backend verifier remains
independent, as required by the Package contract. This was a heuristic judgement,
not a hard violation.

## Spec

1. **Drop zone, P2.** Ticket 25 requires “UI chỉ cho chọn/kéo thả file `.s3dpkg`”.
   The dashed label previously relied on the smaller native file input's drop
   behavior. Fixed: `onDragOver`/`onDrop` cover the label, prevent default browser
   navigation and use the same file/busy checks as file selection.
2. **Missing-alignment gate, P2.** Ticket 25 requires “Thiếu hoặc sai ma trận căn
   chỉnh ... không xuất Package hoàn chỉnh”. A current acceptance line in the
   implementation plan still expected an unaligned Scan to pass the pipeline.
   Fixed: the gate now requires prep rejection; historical v1 measurements remain
   explicitly historical.

Totals: Standards 1 P3 duplication finding, Spec 2 P2 findings (drop zone and
contradictory gate); all addressed. No scope creep found.

## Verification

- 56 backend tests, 5 standalone prep tests, 2 frontend tests passed; lint,
  OpenAPI freshness, TypeScript and native/Docker static builds passed.
- Both real Packages are v2 in `dataset/preprocessing/`, ignored by Git and Docker.
  Independent API verification and S1 extraction passed; original files unchanged.
  Scene0000_00 points match the previously validated aligned reference exactly,
  and the camera pose matches within tolerance: `spikes/preprocessing-v2.json`.
- Running API has no inbox schema/endpoint or raw/preprocessing mount. Legacy
  upload/reload reject before changing the two existing ready Scenes; a historical
  Keyframe still loads: `spikes/upload-v2-live.json`.
- Browser UI shows v2 upload and both ready Scenes, with no inbox list. Screenshot
  capture timed out in the browser tool; UI state was checked without uploading
  the user's new Packages.
