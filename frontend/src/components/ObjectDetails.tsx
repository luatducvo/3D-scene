"use client";
import { useFormatter, useTranslations } from "next-intl";
import type { SceneObject } from "../lib/api/types";
import { focus } from "./viewer/camera";

export function ObjectDetails({ object }: { object: SceneObject }) {
  const t = useTranslations(),
    format = useFormatter();
  return (
    <article className="object-details">
      <h2>{object.label}</h2>
      <h3>{t("size")}</h3>
      <div className="dimensions">
        <strong>
          {object.box.size
            .map((n) =>
              format.number(n, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              }),
            )
            .join(" × ")}{" "}
          m
        </strong>
        <span>{t("ui.dimensionOrder")}</span>
      </div>
      <button className="full-width" onClick={() => focus([object.id])}>
        {t("ui.focusObject")}
      </button>
    </article>
  );
}
