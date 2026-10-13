"use client";
import { useLocale, useTranslations } from "next-intl";
import type { SceneObject } from "../lib/api/port";
import { useViewer } from "../lib/store/viewerStore";
export function ObjectList({
  objects,
  onQuestion,
}: {
  objects: SceneObject[];
  onQuestion: (question: string) => void;
}) {
  const locale = useLocale(),
    t = useTranslations(),
    selected = useViewer((s) => s.selectedId),
    select = useViewer((s) => s.select);
  const object = objects.find((o) => o.id === selected);
  const label = (o: SceneObject) =>
    locale === "vi" && o.label_vi ? o.label_vi : o.label;
  return (
    <>
      <div className="object-list">
        {objects.map((o) => (
          <button
            className={o.id === selected ? "selected" : "subtle"}
            key={o.id}
            onClick={() => select(o.id)}
          >
            {label(o)}
          </button>
        ))}
      </div>
      {!objects.length && <p>{t("noObjects")}</p>}
      {object && (
        <article>
          <h2>{label(object)}</h2>
          <h3>{t("size")}</h3>
          <p>{object.box.size.map((n) => n.toFixed(2)).join(" × ")} m</p>
          <h3>{t("attributes")}</h3>
          {Object.entries(object.attributes || {}).map(([key, values]) => (
            <p key={key}>
              {key}: {values.join(", ")}
            </p>
          ))}
          <div className="evidence">
            {object.best_views
              ?.filter((v) => v.image_url)
              .map((v) => (
                <a
                  key={v.frame_id}
                  href={v.image_url!}
                  target="_blank"
                  rel="noreferrer"
                >
                  <img src={v.image_url!} alt={t("evidence")} />
                </a>
              ))}
          </div>
          <div className="suggestions">
            {["suggestWhere", "suggestColor", "suggestNear"].map((key) => (
              <button
                key={key}
                className="subtle"
                onClick={() => onQuestion(t(key, { object: label(object) }))}
              >
                {t(key, { object: label(object) })}
              </button>
            ))}
          </div>
        </article>
      )}
    </>
  );
}
