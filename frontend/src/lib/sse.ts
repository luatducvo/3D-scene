import { createParser } from "eventsource-parser";

export function createJsonEventParser(onEvent: (name: string, payload: unknown) => void) {
  const parser = createParser({ onEvent(event) {
    onEvent(event.event || "message", JSON.parse(event.data));
  } });
  return (chunk: string) => parser.feed(chunk);
}
