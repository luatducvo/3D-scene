"use client";
import { useTranslations } from "next-intl";
import { heatmapColor } from "./viewer/highlight";

export function HeatmapLegend({ values }: { values: number[] }) {
  const t = useTranslations("heatmap");
  const single = new Set(values).size === 1;
  return (
    <div className="heatmap-legend card" role="status" aria-label={t("title")}>
      <strong>{t("title")}</strong>
      <div
        className="heatmap-ramp"
        style={{
          background: single
            ? heatmapColor(1).getStyle()
            : `linear-gradient(to right, ${Array.from({ length: 13 }, (_, i) => `${heatmapColor(i / 12).getStyle()} ${(i / 12) * 100}%`).join(", ")})`,
        }}
      />
      <div className="heatmap-labels">
        {!single && <span>{t("cool")}</span>}
        <span>{single ? t("same") : t("hot")}</span>
      </div>
      <p>{single ? t("single") : t("relative")}</p>
    </div>
  );
}
