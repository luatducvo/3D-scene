"use client";
import { useState } from "react";
import { useTranslations, useFormatter } from "next-intl";
import { STAGES, type Scene, type Schemas } from "../lib/api/types";

type Stage = Schemas["StageRun"]["stage"];
const METRICS: Record<Stage, string[]> = {
  ingest: ["num_inputs", "num_keyframes"],
  recon: ["num_frames", "metric_scale"],
  align: ["floor_z", "ceiling_height"],
  mesh: ["num_faces", "num_points"],
  segment: ["num_masks", "vocabulary_size"],
  lift: ["num_instances"],
  embed: ["model_id", "dim"],
  attributes: ["num_objects", "invalid_outputs"],
  graph: ["num_objects", "num_relations"],
};

export function PipelineInspector({ scene }: { scene: Scene }) {
  const t = useTranslations("inspector"),
    format = useFormatter();
  const [stage, setStage] = useState<Stage>("ingest");
  const run = scene.stage_runs?.find((item) => item.stage === stage);
  const start = run?.started_at ? Date.parse(run.started_at) : NaN;
  const end = run?.updated_at ? Date.parse(run.updated_at) : NaN;
  const duration =
    run?.status !== "running" &&
    Number.isFinite(start) &&
    Number.isFinite(end) &&
    end >= start
      ? format.number((end - start) / 1000, { maximumFractionDigits: 2 })
      : t("unavailable");
  const available = (value: unknown) =>
    typeof value === "number" && Number.isFinite(value)
      ? format.number(value, { maximumFractionDigits: 3 })
      : typeof value === "string" && value
        ? value
        : t("unavailable");
  return (
    <div className="panel-body inspector">
      <nav className="inspector-stages" aria-label={t("stageList")}>
        {STAGES.map((name) => (
          <button
            key={name}
            className={stage === name ? "" : "secondary"}
            aria-pressed={stage === name}
            onClick={() => setStage(name)}
          >
            {t(`stages.${name}.title`)}
          </button>
        ))}
      </nav>
      <h3>{t(`stages.${stage}.title`)}</h3>
      <dl className="scene-facts">
        <dt>{t("purpose")}</dt>
        <dd>{t(`stages.${stage}.purpose`)}</dd>
        <dt>{t("inputs")}</dt>
        <dd>{t(`stages.${stage}.inputs`)}</dd>
        <dt>{t("outputs")}</dt>
        <dd>{t(`stages.${stage}.outputs`)}</dd>
        <dt>{t("algorithm")}</dt>
        <dd>{run?.algorithm || t("unavailable")}</dd>
        <dt>{t("status")}</dt>
        <dd>{run?.status || t("unavailable")}</dd>
        <dt>{t("timing")}</dt>
        <dd>{duration}</dd>
      </dl>
      {run?.algorithm === "attributes.none" && (
        <p className="caption">{t("disabled")}</p>
      )}
      <h3>{t("statistics")}</h3>
      <dl className="scene-facts">
        {METRICS[stage].map((key) => (
          <div key={key}>
            <dt>{t(`metrics.${stage}.${key}`)}</dt>
            <dd>{available(run?.manifest?.[key])}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
