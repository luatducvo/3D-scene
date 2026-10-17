# 08: QA answers may only state measured numbers

**What to build:** `QAAgent` enforces SPEC's rule that every number in an answer comes from a
geometric tool. Both LLM adapters return the same reply protocol (tool calls, or a final answer via
`final_answer`); `QAAgent` alone executes tools, records the numbers they returned, and rejects a final
answer containing a number that no tool returned, asking the model once more and then failing with
`QA_UNGROUNDED`. Today any reply without tool calls is accepted (audit R3).

**Blocked by:** None

**Status:** implemented

- [x] `OpenAICompatibleLLM` no longer interprets `final_answer` itself; a reply mixing
      `final_answer` with other tool calls runs the other tools first.
- [x] Numbers in a final answer must match a number from this question's tool results (same value
      after rounding to the answer's precision; unit conversions m↔cm allowed); counts and ids
      returned by tools count as facts. One corrective retry, then `QA_UNGROUNDED`.
- [x] Tests through the API + SSE seam with `ScriptedLLM`: an unsupported "999 m" answer fails,
      a measured answer passes, a corrected retry passes, mixed final/tool calls execute the tools.
- [x] docs/architecture/api.md (QA agent) updated.
