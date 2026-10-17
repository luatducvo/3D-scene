import { expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { StageStepper } from "./StageStepper";
import messages from "../../messages/en.json";
import { stageState, type Stage, type StageState } from "../lib/api/types";
const event = (
  stage: Stage,
  status: string,
  error: StageState["error"] = null,
): StageState => stageState({ stage, status, error });
test("progress shows done, active and failed stages with the actionable error", () => {
  const markup = renderToStaticMarkup(
    <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
      <StageStepper
        events={{
          ingest: event("ingest", "done"),
          recon: event("recon", "running"),
          mesh: event("mesh", "failed", { message: "No surface" }),
        }}
      />
    </NextIntlClientProvider>,
  );
  expect(markup).toContain("Done");
  expect(markup).toContain("Running");
  expect(markup).toContain("No surface");
});

test("progress shows the Job bar, the running Stage count, elapsed time and an estimate", () => {
  const start = "2026-10-14T13:00:00Z";
  const markup = renderToStaticMarkup(
    <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
      <StageStepper
        now={Date.parse("2026-10-14T13:10:00Z")}
        events={{
          ingest: event("ingest", "done"),
          recon: event("recon", "done"),
          align: event("align", "done"),
          mesh: {
            ...event("mesh", "done"),
            started_at: "2026-10-14T12:58:00Z",
            updated_at: start,
          },
          attributes: {
            ...event("attributes", "running"),
            started_at: start,
            progress: { done: 50, total: 150, unit: "object" },
          },
        }}
      />
    </NextIntlClientProvider>,
  );
  expect(markup).toContain('aria-label="Processing progress"');
  expect(markup).toContain("4.3 of 9 stages");
  expect(markup).toContain("50/150 objects");
  expect(markup).toContain("10:00");
  expect(markup).toContain("2:00");
  expect(markup).toContain("about 20 min left");
});

test("a running Stage without counts shows an indeterminate bar", () => {
  const markup = renderToStaticMarkup(
    <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
      <StageStepper
        now={Date.parse("2026-10-14T13:00:05Z")}
        events={{
          recon: {
            ...event("recon", "running"),
            started_at: "2026-10-14T13:00:00Z",
          },
        }}
      />
    </NextIntlClientProvider>,
  );
  expect(markup).toMatch(
    /<progress aria-label="Reconstruct the room"><\/progress>/,
  );
  expect(markup).not.toContain("left");
});
