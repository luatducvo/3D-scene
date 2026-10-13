# 23: Ask questions (QA tracer)

**What to build:** The Ask tab. The QA agent runs a function-calling loop (at most 6 steps) against an OpenAI-compatible LLM using the first tools (find objects, count objects, get object, get room info), answers in the question's language, uses only tool results, and streams tool, delta and final events. Conversations persist per Scene. The final answer highlights the cited Objects, flies the camera to them and shows evidence images.

**Blocked by:** 11

**Status:** done — requires LLM_* keys for live use

- [ ] Asking "how many chairs are there?" streams an answer citing Object ids; they highlight and the camera flies to them.
- [ ] A Vietnamese question gets a Vietnamese answer.
- [ ] Reloading the Scene shows the previous conversation.
- [ ] The LLM endpoint is configured by environment; a fake LLM client can be selected by configuration for tests.
- [ ] API tests (primary seam, scripted fake LLM) cover the tool loop, the 6-step cap, persistence and the event stream.
