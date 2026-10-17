import { toApiError } from "./errors";
export async function consumeSSE<T>(
  response: Response,
  receive: (event: T) => void,
) {
  if (!response.ok)
    throw toApiError(await response.json().catch(() => null), response.status);
  if (!response.body) throw new Error("Missing event stream");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(
        /\r\n/g,
        "\n",
      );
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!data) continue;
        const parsed = JSON.parse(data);
        const name = frame
          .split("\n")
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim();
        // Only the `error` event aborts; ordinary payloads may carry an `error` field.
        if (name === "error") throw toApiError(parsed, response.status);
        receive(parsed);
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}
