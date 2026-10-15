import { expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { ObjectDetails } from "./ObjectDetails";
import type { SceneObject } from "../lib/api/port";
import en from "../../messages/en.json";
import vi from "../../messages/vi.json";

const object: SceneObject = {
  id: "sofa-1",
  label: "sofa",
  label_vi: "Ghế sofa",
  box: { center: [0, 0, 0.5], size: [2.1, 0.86, 0.82], yaw: 0 },
  attributes: { color: ["green"], material: ["fabric"] },
  best_views: [
    {
      frame_id: "frame-1",
      bbox: [0, 0, 100, 100],
      score: 1,
      image_url: "https://example.com/evidence.jpg",
    },
  ],
};

test.each([
  ["en", en, "sofa", "2.10 × 0.86 × 0.82 m"],
  ["vi", vi, "Ghế sofa", "2,10 × 0,86 × 0,82 m"],
] as const)(
  "selected object details in %s expose geometry and attributes without evidence or suggestions",
  (locale, messages, label, dimensions) => {
    const markup = renderToStaticMarkup(
      <NextIntlClientProvider
        locale={locale}
        timeZone="UTC"
        messages={messages}
      >
        <ObjectDetails object={object} />
      </NextIntlClientProvider>,
    );
    expect(markup).toContain(label);
    expect(markup).toContain(dimensions);
    expect(markup).toContain("green");
    expect(markup).toContain("fabric");
    expect(markup).not.toContain("<img");
    expect(markup).not.toContain("evidence.jpg");
    expect(markup).not.toContain("<ul");
    expect(markup).not.toContain("?");
  },
);
