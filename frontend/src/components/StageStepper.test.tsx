import { expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { StageStepper } from "./StageStepper";
import messages from "../../messages/en.json";
import type { ProgressEvent } from "../lib/api/port";
const event = (
  stage: string,
  status: string,
  error: ProgressEvent["error"] = null,
): ProgressEvent => ({
  type: "stage",
  stage,
  status,
  algorithm: null,
  manifest: null,
  error,
});
test("progress shows skipped, active and failed stages with the actionable error", () => {
  const markup = renderToStaticMarkup(
    <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
      <StageStepper
        events={{
          ingest: event("ingest", "skipped"),
          recon: event("recon", "running"),
          mesh: event("mesh", "failed", { message: "No surface" }),
        }}
      />
    </NextIntlClientProvider>,
  );
  expect(markup).toContain("Skipped");
  expect(markup).toContain("Running");
  expect(markup).toContain("No surface");
});
