"use client";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import type { SceneObject } from "../lib/api/types";
import { focus } from "./viewer/camera";

export function ObjectDetails({ object }: { object: SceneObject }) {
  const t = useTranslations(),
    locale = useLocale(),
    format = useFormatter();
  return (
    <article className="object-details">
      <h2>
        {locale === "vi" && object.label_vi ? object.label_vi : object.label}
      </h2>
      <div className="attribute-tags">
        {Object.values(object.attributes || {})
          .flat()
          .map((value, i) => (
            <span className="badge" key={`${value}-${i}`}>
              {value}
            </span>
          ))}
      </div>
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
