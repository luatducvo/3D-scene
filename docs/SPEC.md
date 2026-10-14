# Spec — 3D Scene Understanding System

> Status: ready for implementation · Source of truth for *what* to build. `docs/ARCHITECTURE.md`
> describes *how*; where the two disagree, this spec wins until the architecture doc is updated
> (first milestone).

## Problem Statement

I want to understand a room I have photographed, without owning a depth camera, a LiDAR phone or a
3D-scanning app. Today, a set of phone photos of a room is just a pile of 2D images: I cannot see the
room in 3D, I cannot find "the red mug" without scrolling through every photo, and I cannot ask
"how far is the sofa from the window?" or "how many chairs are there?" and get an answer grounded in
real measurements.

I also want to learn how a modern 3D perception pipeline is built, so every method (reconstruction,
segmentation, embeddings, LLM) must be swappable and the GPU work must run wherever GPUs are
available to me. My own machine has only a 6 GB GPU, so the heavy models must run remotely without the
application code knowing or caring where.

## Solution

A local, single-user web application. I create a **Scene**, upload photos or a short video of one
room, and press Process. The system selects **Keyframes**, reconstructs the room at metric scale with
the floor at height zero, builds a mesh, detects **Objects** with an open vocabulary, describes their
attributes, and builds a **Scene Graph** of spatial **Relations**. While it works I watch each
**Stage** progress live.

When it finishes I explore the room in a 3D viewer, search objects with free text in English or
Vietnamese, inspect each Object's size, attributes and evidence photos, measure between two points,
and ask questions in natural language. Answers come back in the language I asked in, cite the
Objects involved, highlight them in 3D and fly the camera to them. Every number in an answer comes
from a geometric computation, never from the language model's guess.

Heavy Stages run on a remote GPU behind one small HTTP contract. No provider is the default: I configure
the Targets before starting the system, and switching provider is a configuration change, not a code change.

## User Stories

### Scenes and capture
1. As a user, I want to create a named Scene, so that each room I capture is kept separately.
2. As a user, I want to see a list of my Scenes with their status, so that I know which are ready to explore.
3. As a user, I want short capture tips before uploading (walk along the walls, shoot at two heights, lights on), so that my photos reconstruct well.
4. As a user, I want to drag and drop many photos or a single short video, so that uploading is quick.
5. As a user, I want each photo scored for sharpness and exposure in the browser before upload (green / amber / red), so that I can drop bad shots before wasting processing time.
6. As a user, I want an upload progress bar, so that I know a large upload is still moving.
7. As a user, I want to add more files to a Scene until I first press Process, so that I can upload in several batches.
8. As a user, I want the system to refuse new uploads once a Scene has been processed (or is failed), and tell me to create a new Scene, so that a Scene's image set never silently diverges from its results.
9. As a user, I want to delete a Scene, so that its photos, results and any remote copies are removed and disk space is freed.
10. As a user, I want deleting or uploading to be refused while a Job is active for that Scene, so that I cannot corrupt a Scene mid-processing.

### Processing
11. As a user, I want to press Process once and have every Stage run automatically, so that I do not orchestrate anything by hand.
12. As a user, I want to see live progress per Stage (running, done, skipped, failed) in plain language, so that I know what the system is doing.
13. As a user, I want to reconnect to a Scene page mid-processing and immediately see the current state, so that refreshing the browser loses nothing.
14. As a user, I want a second Process request on a busy Scene to be refused, so that only one Job per Scene ever runs.
15. As a user, I want an ingest report listing which files were rejected and why (blur, exposure, duplicate), so that I learn how to capture better.
16. As a user, I want processing to fail early with a clear "not enough keyframes" message, including rejection counts, when too few usable frames remain, so that I do not wait for a meaningless reconstruction.
17. As a user, I want a failed Scene to show which Stage failed and the error message, so that I can understand what went wrong.
18. As a learner, I want to rerun a Scene from a chosen Stage onwards, so that I can compare a new method without redoing earlier Stages.
19. As a learner, I want unchanged Stages (same algorithm and parameters, outputs still present) to be skipped on rerun, so that experiments are fast and cheap.
20. As a learner, I want every Stage after a rerun Stage to run again, so that downstream results never depend on stale inputs.

### Reconstruction and geometry
21. As a user, I want the reconstruction to be in meters, so that sizes and distances are real.
22. As a user, I want the room aligned with gravity, floor at height zero and walls along the axes, so that the viewer feels natural and "above/under/on" are meaningful.
23. As a user, I want the ceiling height estimated when visible, so that I can ask about room dimensions.
24. As a user, I want a textured mesh of the room in the viewer, so that I can orbit and zoom around it.
25. As a user, I want EXIF orientation applied and metadata (including GPS) stripped from working copies, so that photos are upright and my location is not stored.
26. As a user, I want a short video to be split into frames automatically, so that video and photos are equally usable.

### Objects and search
27. As a user, I want objects detected from a broad indoor vocabulary without training anything, so that ordinary rooms work out of the box.
28. As a user, I want each Object shown as an oriented 3D box over the mesh, so that I can see what was found and where.
29. As a user, I want a list of all Objects with English and Vietnamese labels, so that I can browse what is in the room.
30. As a user, I want to tap an Object and see its label, size in meters, attributes (color, material, state) and the best photos of it, so that I can verify what the system saw.
31. As a user, I want to search Objects with free text in English or Vietnamese ("cái ghế màu xanh", "something to sit on"), so that I find things by meaning, not exact label.
32. As a user, I want search results highlighted in the 3D view, so that I see where they are immediately.
33. As a user, I want an Object's identity to be stable from detection to the API to the UI, so that answers, highlights and lists always refer to the same thing.

### Measuring and asking
34. As a user, I want a two-point measuring tool in the viewer, so that I can measure anything myself.
35. As a user, I want to ask where an object is, so that I can locate it.
36. As a user, I want to ask about spatial relations (on, under, above, inside, next to, near, against the wall), so that I understand the layout.
37. As a user, I want to ask how many of something there are, so that I can count objects.
38. As a user, I want to ask about attributes ("what color is the sofa?"), so that I learn details I cannot see in the mesh.
39. As a user, I want to ask distances between objects (surface-to-surface or center-to-center), so that I get real measurements.
40. As a user, I want to ask left/right/in-front/behind questions relative to my current view or to an object's front, so that direction questions make sense.
41. As a user, I want to ask about the room itself (floor size, ceiling height, objects per label), so that I get an overview.
42. As a user, I want answers in the language of my question (Vietnamese or English), so that I can use my own language.
43. As a user, I want the answer streamed as it is written, with a note of which tool is being used, so that I am not staring at a blank panel.
44. As a user, I want every answer to list the Objects it refers to, highlight them and fly the camera there, so that I can check the answer visually.
45. As a user, I want evidence photos attached to the answer, so that I can trust it.
46. As a user, I want numbers in answers to come only from measurements, never invented by the model, so that answers are trustworthy.
47. As a user, I want my questions and answers for a Scene kept, so that I can come back to a conversation.
48. As a user, I want suggested questions when I select an Object, so that I discover what I can ask.

### Interface
49. As a Vietnamese speaker, I want the whole UI available in Vietnamese and English, so that I can use my preferred language.
50. As a phone user, I want the side panel to become a bottom sheet on small screens, so that the viewer stays usable.
51. As a UI developer, I want to run the frontend against a mock backend, so that I can build screens without GPUs or a database.

### Compute and operations
52. As an operator, I want to choose per Stage whether it runs in-process on CPU or on a named GPU target, so that I can place work where it fits.
53. As an operator, I want to move all GPU Stages to another provider by changing one Target setting, so that switching providers is trivial.
54. As an operator, I want one GPU image that runs unchanged on Modal, RunPod (Pod or Serverless), Vast.ai, a local GPU or any Docker host, so that I never write provider-specific application code.
55. As an operator using Modal, I want Modal to build the GPU image from the project's own build definition, so that I do not push a 10+ GB image from a home connection.
56. As an operator, I want the worker to wait through remote cold starts, so that a sleeping GPU container does not fail a Job.
57. As an operator, I want remote targets to receive only the inputs they need, skip files already present (by checksum), and return outputs to my machine, so that transfers are minimal and my machine remains the source of truth.
58. As an operator, I want file transfers chunked under the strictest provider body limit, so that the same contract works on every provider.
59. As an operator, I want remote GPU endpoints protected by a shared token, so that a public proxy URL is not an open door.
60. As an operator, I want model weights cached on my host (and on a provider volume remotely), so that a full reset does not re-download tens of gigabytes.
61. As an operator, I want a single command to reset the system to empty (all Scenes and the database), keeping model weights, so that I can start fresh.
62. As an operator, I want one cross-platform task command set (start, stop, reset, test, export API contract, download models, deploy), so that everything works on Windows without `make`.
63. As an operator, I want to inspect a target's version, GPU and installed algorithms, so that I can confirm a deployment.
64. As an operator, I want LLM and VLM endpoints configured as any OpenAI-compatible URL, key and model, so that I can switch between cloud providers or a local server.

### Extensibility (learning goals)
65. As a learner, I want to add a new method for a Stage by adding one class, one optional dependency group and one registration entry, then selecting it in configuration, so that nothing else changes.
66. As a learner, I want installing a method's dependency group to be enough to make it available, so that each runtime installs only what it runs.
67. As a learner, I want to add a new spatial Relation by adding one rule and listing it in configuration, so that the Scene Graph is extensible.
68. As a learner, I want to add a new QA capability by adding one tool, so that the agent grows without touching the loop.
69. As a learner, I want to add a new 3D rendering layer by adding one component to the layer map, so that the viewer is extensible.
70. As a learner, I want the backend API contract exported as an OpenAPI file that the frontend generates its types from, so that frontend and backend never drift.

## Implementation Decisions

### Domain language
- Canonical terms (to be recorded in the repo glossary): **Scene**, **Keyframe**, **Frame**, **Stage**, **Algorithm**, **Target**, **Workspace**, **Manifest**, **Vocabulary**, **Job**, **Stage Run**, **Compute Run**, **Instance**, **Object**, **Relation**, **Scene Graph**.
- "Run" is never used bare. A **Job** is one processing request for a Scene (queued by Process). A **Stage Run** is the record of a completed Stage with its algorithm and config hash. A **Compute Run** is one execution of an Algorithm on a GPU target.
- An **Instance** (output of lifting: points, label, best views) becomes exactly one **Object** (box, attributes) with the same id. No merging or splitting after lifting.

### Modules
- **scene-core** (no heavy dependencies): domain models, Stage Manifests, Workspace path resolution, ports, pure-numpy geometry (box fitting, plane fitting, distances, footprint overlap), the registry, the Executor, configuration models and loaders, error codes.
- **scene-stages**: one Algorithm per Stage method, each heavy method behind its own optional dependency group; a set of `*.fake` Algorithms (one per Stage) that write contract-valid outputs and are used by the walking skeleton and by tests.
- **scene-worker**: Postgres Job queue, pipeline runner, publisher (Scene Graph → database), compute backends (in-process and HTTP), composition root.
- **scene-compute**: the portable GPU server implementing the compute contract, a Compute Run registry, chunked file transfer.
- **scene-api**: REST + SSE API, Postgres adapters, local file store, event fan-out, text-embedding adapter, LLM adapter, QA agent and its tools, composition root.
- **frontend**: Next.js app with a `SceneApi` port (HTTP and mock implementations), viewer layers, search, object list, chat, capture guide, upload with in-browser quality scoring, measuring tool, i18n.

### Architectural decisions (deviations from or clarifications of the architecture doc)
- **Algorithms are pure workspace transforms.** They never access the database. After the last Stage succeeds, the worker **publishes** the Scene Graph file and the object embeddings file into Postgres through the Scene repository. (To be recorded as ADR-0001.)
- **Executor lives in scene-core**, so both the GPU server and the worker's in-process backend share it without the worker depending on the GPU server package.
- **Registration is by package entry points only**, resolved lazily. Groups: one for Stage Algorithms, one for Relation rules. No decorator-based registry. Listing available Algorithms must not import heavy libraries.
- **Walking skeleton first.** Every layer is wired end-to-end with fake Algorithms before any real model is integrated; real Algorithms then replace fakes Stage by Stage.
- **No GPU provider is the default.** GPU Stages name their Target through `GPU_TARGET`, in the real and the fake GPU pipeline alike; every real GPU Algorithm ships in one image ([ADR-0002](ADR-0002-single-gpu-image-ultralytics-sam3.md)); the worker refuses to start when a selected Target is unset or has no URL. Vast.ai, rented by hand, is the first provider exercised live. The Modal deployment builds the image from the same Dockerfile used everywhere; other providers pull the image built locally and pushed to Docker Hub. Modal, local GPU, RunPod and generic Docker hosts are written but not exercised during development. See [VAST-PLAN](VAST-PLAN.md).
- **Task runner** is a stdlib-only Python script invoked through `uv`, replacing the Makefile.
- **Lift** is an in-house re-implementation of MaskClustering's view-consensus approach (masks → 3D points via aligned depth and poses → mask graph weighted by cross-view consensus → iterative clustering → score×area label voting), not a vendored research repo. The registry key stays `lift.maskclustering`.

### Scene lifecycle rules
- Status flow: `created → uploaded → processing → ready | failed`. Re-processing (from a Stage) is allowed from `ready` or `failed`.
- Uploads are accepted only in `created` or `uploaded`. Otherwise: HTTP 409, code `SCENE_LOCKED`.
- At most one active Job (queued or running) per Scene, enforced by a partial unique index. Process, upload or delete while a Job is active: HTTP 409, code `SCENE_BUSY`.
- Ingest has a `min_keyframes` parameter (default 10). Below it the Stage fails with code `NOT_ENOUGH_KEYFRAMES` and the rejection counts per reason.
- Stage skip rule: skip when a Stage Run exists with the same config hash (algorithm + params) **and** its output folders still exist; once any Stage runs, every later Stage runs.
- Deleting a Scene removes database rows, the local Scene folder, and Workspaces on every non-shared remote target.

### API contract
- Versioned under `/api/v1`; OpenAPI exported from the API models is the source of truth and is committed; the frontend generates types from it.
- Endpoints as in the architecture doc §9.2. Questions use `POST /scenes/{scene_id}/queries` (the doc's sequence diagram saying `/query` is a typo).
- Error body `{"error": {"code", "message"}}`, UPPER_SNAKE_CASE codes, matching HTTP status. Codes introduced here: `SCENE_LOCKED`, `SCENE_BUSY`, `NOT_ENOUGH_KEYFRAMES` (surfaced as the Scene's failure), `COMPUTE_UNAVAILABLE` (HTTP 503 when the embed Stage's Target is unset or unreachable for a query).
- Progress SSE replays current Stage Run state on connect, then streams `stage` and `status` events. Answer SSE streams `tool`, `delta`, `final` (`answer`, `object_ids`, `evidence`).
- All file URLs are absolute and issued by the API; the files endpoint serves only whitelisted subfolders and rejects traversal.
- Units are SI; coordinates are z-up with floor at z = 0.

### Compute contract
- As specified in the architecture doc §6.2 (readiness ping, info, Workspace file listing with checksums, chunked upload with offset/total/checksum, ranged download, Workspace delete, asynchronous Compute Runs with polling, short synchronous invoke). Every request finishes in under 30 s; every body is at most the configured chunk size (default 25 MB). App auth via `X-Compute-Token`.

### Schema
- As in the architecture doc §9.4, plus the partial unique index on active Jobs per Scene. The object embedding column dimension must equal the embedding model's output dimension; verify it when integrating the real embedding model.

### QA agent
- The LLM plans and phrases; all numbers come from tools. Tools: find objects, count objects, measure distance, get relations, relative direction, get object, get room info. At most 6 tool-calling steps. Answers in the question's language. Conversation persisted per Scene.

### Delivery milestones
Each ends in something runnable in the browser.
- **M0** Repo reset (uv workspace replaces the scaffold), task runner, glossary, ADR-0001, architecture doc brought in line with this spec.
- **M1** Walking skeleton: all services, database, SSE and a minimal UI, running fake Algorithms on CPU.
- **M2** Compute contract + GPU server deployed on a remote provider (Vast.ai first), fake GPU Stages running remotely.
- **M3** Real ingest, reconstruction, alignment and mesh; mesh viewer; ingest report.
- **M4** Real segmentation, lifting and embeddings; free-text search.
- **M5** Real attributes and Scene Graph; publish; object list, boxes, object detail.
- **M6** QA agent and chat.
- **M7** UI completion: capture guide, quality badges, upload progress, measuring tool, full Vietnamese, mobile layout, suggested questions.
- **M8** Remaining targets: local GPU profile, Modal, RunPod and generic deploy docs, registry image publishing, remote Workspace cleanup on delete.

### Acceptance criteria (per milestone)
- **M1:** with the fake pipeline, creating a Scene, uploading the synthetic fixture images and pressing Process shows all 9 Stages complete over SSE; the Scene becomes `ready`; a fake room mesh and Object boxes render; reprocessing skips all Stages; reprocessing from a Stage reruns it and every later Stage; the 409 rules hold.
- **M2:** the same flow with fake GPU Stages targeting a configured remote Target completes; files round-trip by checksum; a Target that is not yet ready is waited for, not failed (including cold starts on providers that scale to zero).
- **M3:** the user's room capture produces a mesh where the floor is at z ≈ 0, walls are axis-aligned and a known dimension (e.g. a door's height ≈ 2 m) is plausible; rejected files are listed by reason.
- **M4:** searching a visible object by an English or Vietnamese phrase ranks it in the top results and highlights it.
- **M5:** every Object has a box, labels in both languages and attributes; relations shown for an Object agree with what is visible.
- **M6:** a question in Vietnamese is answered in Vietnamese, cites Object ids, highlights them and flies the camera; distances in the answer equal the tool's output.
- **M7/M8:** features listed above are present; M8 targets are documented but not required to be exercised.
- Judgement of reconstruction and perception quality is qualitative (no benchmarks).

## Testing Decisions

### What makes a good test
- Test external behavior through public seams, never internal structure. A test should survive refactoring the code behind its seam.
- Prefer the highest seam. Lower-level tests exist only where the logic is numeric and easy to get subtly wrong.
- No GPU in automated tests. Fake Algorithms and a fake LLM client stand in, selected through the same configuration mechanism production uses.
- Fixtures are tiny and synthetic (generated images, synthetic depth/poses), committed to the repo. The user's real room capture is git-ignored and used only for manual smoke tests.

### Seams (agreed)
1. **Backend REST API + SSE (primary seam).** Real Postgres, real worker, fake Algorithms, fake LLM client wired by configuration. Covers the Scene lifecycle and 409 rules, Job queueing, the runner's skip/force rules, failure reporting, SSE replay and streaming, publish into the database, objects listing, search, files whitelist, and the QA agent's answer stream. No separate unit tests for runner, queue or publisher.
2. **Compute contract.** The worker's HTTP backend against the GPU server running in-process with fake Algorithms, non-shared storage and tiny chunks: checksum-based skip, chunked upload and ranged download, failed Compute Run surfaces as an error, wrong token rejected, path traversal rejected, shared-storage mode skips transfers.
3. **Stage Algorithm contract.** For CPU Algorithms (ingest, mesh, Scene Graph): given a Workspace prepared from fixtures, the Algorithm writes the documented layout and returns a valid Manifest (e.g. ingest rejects blurred, dark and duplicate fixtures; enforces `min_keyframes`).
4. **Frontend `SceneApi` port.** UI behavior tested against the mock implementation (MSW), e.g. progress stepper reacting to the event stream, search highlighting, chat rendering a final answer.

Additional pure unit tests only for numeric geometry: box fitting, footprint overlap, distances, plane fitting, and each Relation rule's thresholds.

### Prior art
- None in the repository yet (it contains only a scaffold). The first tests written in M1 at seams 1 and 3 become the prior art for later milestones.

### Manual verification
- Real GPU Algorithms are smoke-tested on the configured provider (Vast.ai first) with the user's room capture at M3–M6, checked against the acceptance criteria above.

## Out of Scope
- Multi-user use, authentication, sharing Scenes, any public deployment (ports bind to localhost).
- Benchmarks, accuracy metrics, model comparisons, and fallback paths when a component fails.
- Depth sensors, LiDAR, known camera poses, or any input other than RGB photos/video.
- Multiple rooms or whole buildings in one Scene; merging Scenes; adding photos to an already-processed Scene.
- Editing Scenes (moving, relabeling or deleting Objects by hand).
- Cancelling a running Job.
- Redis, object storage, cloud persistence of Scenes; the user's own machine is the source of truth.
- Native mobile app or in-app camera capture.
- Exercising Modal, local GPU, RunPod and generic targets during development (written and documented only).
- Fine-tuning or training any model.
- Localization of anything other than user-facing UI strings.

## Further Notes
- Environment: Windows 11 host with Git Bash, Docker with the NVIDIA runtime, an RTX 3050 6 GB (insufficient for every GPU Stage), no `make`, no GitHub CLI.
- Prerequisites the user must provide: a Vast.ai account with credit, a public Docker Hub repository for the GPU images, a Hugging Face token and gated access to SAM 3 (both available), and an OpenAI-compatible cloud API key for LLM and VLM.
- Verify before integrating: Hugging Face model ids, MapAnything's inference arguments and output keys, the embedding model's output dimension, Modal's support for building from a Dockerfile together with web-server, concurrency and startup-timeout options, and torch version compatibility across GPU dependency groups.
- The user commits changes; implementing agents only edit files.
- No issue tracker is configured, so this spec lives in the repository rather than as a `ready-for-agent` issue. Running `/setup-matt-pocock-skills` later would allow publishing it as one.
