import { describe, expect, it } from "vitest";
import { createJsonEventParser } from "./sse";

describe("SSE JSON parser", () => {
  it("handles events split across fetch stream chunks", () => {
    const seen: [string, unknown][] = [];
    const feed = createJsonEventParser((name, payload) => seen.push([name, payload]));
    feed("event: candidates\ndata: {\"targets\":[1,");
    feed("2]}\n\nevent: final\ndata: {\"answer\":\"done\"}\n\n");
    expect(seen).toEqual([["candidates", { targets: [1, 2] }],
      ["final", { answer: "done" }]]);
  });
});
