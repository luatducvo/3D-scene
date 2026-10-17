# ADR-0004: Skip VLM attributes

Status: accepted. Date: 2026-10-15. Deviates from [SPEC](../SPEC.md) user stories 30 and 38 and the M5
acceptance criterion "labels in both languages and attributes".

## Context

`attributes.vlm_api` sends up to three crops per Object to an OpenAI-compatible vision model. With
OpenRouter and `deepseek/deepseek-v4.1-flash` the Stage took about 15 minutes per Scene, and every
run is a paid API call per Object. Parallel requests reduce the wall time, but the Stage still costs
money and adds an external dependency to every Scene.

Open-vocabulary search does not depend on this Stage. `embed.metaclip2` embeds Object crops and the
query text in one multilingual space, and both search and the QA tool `find_objects` rank Objects by
that similarity. The attributes Stage only adds `label_vi` (one point of exact label matching in
search) and the color, material and state strings that the QA tool `get_object` returns.

## Decision

The pipeline runs `attributes.none`, which writes `attributes/attributes.json` with an empty entry
for every Instance and an empty `errors.json`. It calls no endpoint. `attributes.vlm_api` stays in
the registry, unchanged, so it can be switched back on in `backend/config/pipeline.yaml` without
code changes. The Stage itself remains, because the pipeline must declare all nine Stages in order.

## Alternatives considered

- Keep `attributes.vlm_api` with parallel requests: faster, but still paid and slow per Scene.
- Derive attributes without a VLM: `label_vi` from a fixed translation of the segmentation
  vocabulary, and color or material by MetaCLIP 2 zero-shot over the existing embeddings. Rejected
  for now as extra work; it remains the cheapest way back to the M5 criterion.

## Consequences

- Every Object is published with `label_vi = null` and empty `attributes`.
- The Vietnamese UI shows the English label; the object detail shows no color, material or state.
- Search loses the exact `label_vi` match but keeps multilingual embedding search.
- The QA agent cannot answer attribute questions such as "what color is the sofa?" from data.
- M5 is accepted without "labels in both languages and attributes". `VLM_*` variables are unused
  while this ADR holds.
