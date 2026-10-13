"use client";
import { useTranslations } from "next-intl";
import type { ProgressEvent } from "../lib/api/port";
export const stages = [
  "ingest",
  "recon",
  "align",
  "mesh",
  "segment",
  "lift",
  "embed",
  "attributes",
  "graph",
];
export function StageStepper({
  events,
}: {
  events: Record<string, ProgressEvent>;
}) {
  const t = useTranslations();
  return (
    <section>
      <h2>{t("progress")}</h2>
      <ol className="stepper">
        {stages.map((stage) => (
          <li key={stage} data-status={events[stage]?.status || "pending"}>
            <span>{t(`stages.${stage}`)}</span>
            <strong>{t(`status.${events[stage]?.status || "pending"}`)}</strong>
            {events[stage]?.error && (
              <pre role="alert">
                {JSON.stringify(events[stage].error, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
