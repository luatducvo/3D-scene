# Implementation review

Fixed point: `2b0174d54ca80d57b1d89eaffff966b3d1fc17a6`.
Reviewed diff: `git diff 2b0174d...c573f38`.
Two independent agents reviewed Standards and Spec, following the implement skill.

## Standards

1. **GPU admission violation, P1:** offline stages ignored an unreachable LLM
   management endpoint. This contradicted `implement_plan.md` §10's unload
   confirmation protocol. Fixed by failing the job clearly when unloading cannot
   be confirmed; a regression test covers the failure.
2. **Possible Duplicated Code / Shotgun Surgery, P2:** four inference paths
   duplicated lock, unload, admission and load logic. Fixed with `model_session`,
   which holds the same GPU lock through inference. This was a judgement call,
   not a tooling or documented-style violation.

## Spec

1. **Ticket 19, P1:** “Câu trả lời chứa ID hoặc con số không có trong kết quả Solver
   bị chặn.” Decimal and composite word quantities bypassed the guard. Fixed:
   reject unsupported composites and validate quantities separately from ID
   occurrences; regression cases include `2.2`, `one hundred`, `thirty`, and an
   invented quantity equal to an allowed ID.
2. **Ticket 19, P2:** “viewer tô Target và vật liên quan.” `related` was omitted
   from the frontend event mapping. Fixed: related Objects and Structures now
   highlight, while primary Targets retain camera focus and bboxes.
3. **Ticket 16, P2:** “Candidate ... Label, alt label và độ giống MobileCLIP.”
   Solver candidates lacked Object image embeddings. Fixed: functional phrases
   can use similarity scores when precise labels cannot ground them; a regression
   test distinguishes a chair from a cabinet.
4. **Ticket 10, P2:** “mặt sàn và các mặt tường (RANSAC theo trục Z đã căn).” Floor
   used only a percentile. Fixed: axis-constrained horizontal-plane consensus and
   median refinement, tested against low outliers; S2's configuration hash changed.
5. **Ticket 22, P2:** “scene graph được lọc theo câu hỏi.” Open questions truncated
   all Objects without filtering. Fixed: named labels and their relation neighbors
   receive context priority; general room questions retain the room summary.

Totals: Standards 2 findings, Spec 5 findings, all addressed. The worst Standards
finding was unsafe GPU admission; the worst Spec finding was the number guard.

## Verification limits

The 30-question comparison measures agreement with hand-authored Programs on
measured Objects, not ScanRefer ground truth. See `spikes/query-eval.json`.
GitHub CI evidence identifies its exact tested commit in `spikes/github-ci.json`.
The browser screenshot API timed out during the final Structure check; the
Structure Lookup, UI state and absence of shader errors were checked, and the
earlier mesh/bbox/evidence visual inspection completed.
