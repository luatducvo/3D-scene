import { expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { ObjectDetails } from "./ObjectDetails";
import type { SceneObject } from "../lib/api/types";
import en from "../../messages/en.json";

const object: SceneObject = {
  id: "sofa-1",
  label: "sofa",
  box: { center: [0, 0, 0.5], size: [2.1, 0.86, 0.82], yaw: 0 },
  best_views: [
    {
      frame_id: "frame-1",
      bbox: [0, 0, 100, 100],
      score: 1,
    },
  ],
};

test("selected object details expose label and geometry without attributes, evidence or suggestions", () => {
  const markup = renderToStaticMarkup(
    <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
      <ObjectDetails object={object} />
    </NextIntlClientProvider>,
  );
  expect(markup).toContain("sofa");
  expect(markup).toContain("2.10 × 0.86 × 0.82 m");
  expect(markup).not.toContain("attribute");
  expect(markup).not.toContain("<img");
  expect(markup).not.toContain("frame-1");
  expect(markup).not.toContain("<ul");
  expect(markup).not.toContain("?");
});
