"use client";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { sceneApi } from "./api";
import {
  stageState,
  type ProgressEvent,
  type Scene,
  type StageState,
} from "./api/types";
export type StageStates = Partial<Record<string, StageState>>;
export interface SceneProgress {
  stages: StageStates;
  /** The last status the stream reported; null until one arrives. */
  status: string | null;
}
const fromRuns = (runs: Scene["stage_runs"] = []): StageStates =>
  Object.fromEntries(
    runs.map((run) => [run.stage, stageState({ ...run, type: "stage" })]),
  );
/** A Stage that starts again clears its progress; later states keep the last report. */
function fold(progress: SceneProgress, event: ProgressEvent): SceneProgress {
  const stage = event.stage;
  if (event.type === "status") return { ...progress, status: event.status };
  if (!stage) return progress;
  const previous = progress.stages[stage];
  if (event.type === "stage")
    return {
      ...progress,
      stages: {
        ...progress.stages,
        [stage]: {
          ...event,
          progress:
            event.status === "running" ? null : (previous?.progress ?? null),
        },
      },
    };
  if (event.type === "progress" && event.total != null)
    return {
      ...progress,
      stages: {
        ...progress.stages,
        [stage]: {
          ...(previous ?? stageState({ stage })),
          progress: {
            done: event.done ?? 0,
            total: event.total,
            unit: event.unit ?? "",
          },
        },
      },
    };
  return progress;
}
/**
 * Follows a Scene's progress from its Stage Runs: the stream's replay and live events fold into
 * per-Stage state, reported through onChange after each event. Returns the function that stops.
 */
export function watchSceneProgress(
  sceneId: string,
  runs: Scene["stage_runs"],
  onChange: (progress: SceneProgress) => void,
): () => void {
  let progress: SceneProgress = { stages: fromRuns(runs), status: null };
  return sceneApi.subscribeProgress(sceneId, (event) => {
    progress = fold(progress, event);
    onChange(progress);
  });
}
/**
 * Per-Stage state for the Scene page: its Stage Runs, followed live while the Scene processes.
 * A terminal status refetches the Scene, so status, assets and failure come from the API.
 */
export function useSceneProgress(sceneId: string, scene?: Scene): StageStates {
  const client = useQueryClient();
  const runs = scene?.stage_runs,
    processing = scene?.status === "processing";
  const [stages, setStages] = useState<StageStates>(() => fromRuns(runs));
  useEffect(() => {
    setStages(fromRuns(runs));
    if (!processing) return;
    return watchSceneProgress(sceneId, runs, (progress) => {
      setStages(progress.stages);
      if (progress.status && progress.status !== "processing")
        void client.invalidateQueries({ queryKey: ["scene", sceneId] });
    });
  }, [sceneId, runs, processing, client]);
  return stages;
}
