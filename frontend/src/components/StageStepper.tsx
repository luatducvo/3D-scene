"use client";
import { useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { STAGES as stages, type StageState } from "../lib/api/types";
import type { StageStates } from "../lib/sceneProgress";
const units = ["image", "frame", "mask", "object", "step"];
function clock(milliseconds: number) {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000)),
    hours = Math.floor(seconds / 3600),
    minutes = Math.floor((seconds % 3600) / 60),
    rest = String(seconds % 60).padStart(2, "0");
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${rest}`
    : `${minutes}:${rest}`;
}
export function StageStepper({
  events,
  now,
}: {
  events: StageStates;
  /** Fixed clock for rendering tests; omitted, the component ticks every second while a Stage runs. */
  now?: number;
}) {
  const t = useTranslations(),
    format = useFormatter();
  const running = stages.some((stage) => events[stage]?.status === "running");
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    if (now !== undefined || !running) return;
    const timer = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [now, running]);
  const current = now ?? tick;
  const fraction = (event?: StageState) =>
    event?.progress && event.progress.total > 0
      ? Math.min(1, event.progress.done / event.progress.total)
      : 0;
  // Every Stage weighs the same; the running one adds the share it has reported.
  const completed = stages.reduce((sum, stage) => {
    const status = events[stage]?.status;
    if (status === "done") return sum + 1;
    return status === "running" ? sum + fraction(events[stage]) : sum;
  }, 0);
  return (
    <section className="processing-progress" aria-live="polite">
      <h2>{t("progress")}</h2>
      <div className="job-progress">
        <progress
          aria-label={t("progress")}
          value={completed}
          max={stages.length}
        />
        <span>
          {t("stagesCompleted", {
            done: format.number(completed, { maximumFractionDigits: 1 }),
            total: stages.length,
          })}
        </span>
      </div>
      <ol className="stepper">
        {stages.map((stage, index) => {
          const event = events[stage],
            status = event?.status || "pending",
            started = event?.started_at ? Date.parse(event.started_at) : NaN,
            finished = event?.updated_at ? Date.parse(event.updated_at) : NaN,
            elapsed =
              status === "running"
                ? current - started
                : status === "done"
                  ? finished - started
                  : NaN,
            progress = event?.progress;
          let estimate = "";
          if (status === "running" && progress && progress.done > 0) {
            const share = fraction(event);
            if (share >= 0.05 && share < 1 && elapsed >= 10_000) {
              const minutes = Math.round(
                (elapsed * (1 - share)) / share / 60_000,
              );
              estimate =
                minutes < 1
                  ? t("etaSoon")
                  : minutes < 60
                    ? t("etaMinutes", { minutes })
                    : t("etaHours", {
                        hours: Math.floor(minutes / 60),
                        minutes: minutes % 60,
                      });
            }
          }
          return (
            <li key={stage} data-status={status}>
              <span className="stage-number" aria-hidden="true">
                {status === "done" ? "✓" : index + 1}
              </span>
              <span>{t(`stages.${stage}`)}</span>
              <strong>
                {t(`status.${status}`)}
                {Number.isFinite(elapsed) && ` · ${clock(elapsed)}`}
              </strong>
              {status === "running" && (
                <div className="stage-progress">
                  {progress && progress.total > 0 ? (
                    <progress
                      aria-label={t(`stages.${stage}`)}
                      value={progress.done}
                      max={progress.total}
                    />
                  ) : (
                    <progress aria-label={t(`stages.${stage}`)} />
                  )}
                  {progress && progress.total > 0 && (
                    <span>
                      {progress.done}/{progress.total}{" "}
                      {units.includes(progress.unit)
                        ? t(`units.${progress.unit}`, { count: progress.total })
                        : progress.unit}
                      {estimate && ` · ${estimate}`}
                    </span>
                  )}
                </div>
              )}
              {event?.error && (
                <pre role="alert">{JSON.stringify(event.error, null, 2)}</pre>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
