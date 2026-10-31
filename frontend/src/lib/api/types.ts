import type { components } from "./schema";
export type Schemas = components["schemas"];
export type Scene = Schemas["SceneDetail"];
export type SceneObject = Schemas["SceneObject"];
export type ProgressEvent = Schemas["ProgressEvent"];
export type StageProgress = Schemas["StageProgress"];
export type Stage = Schemas["StageRun"]["stage"];
/** The Stages in processing order. */
export const STAGES = [
  "ingest",
  "recon",
  "align",
  "mesh",
  "segment",
  "lift",
  "objects",
  "embed",
] as const satisfies readonly Stage[];
// Type-checking fails here when STAGES misses a Stage of the backend's enum.
const stagesComplete: [Exclude<Stage, (typeof STAGES)[number]>] extends [never]
  ? true
  : never = true;
void stagesComplete;
/** One Stage on screen: its latest `stage` event and the last progress it reported. */
export type StageState = ProgressEvent & { progress: StageProgress | null };
/** Builds a ProgressEvent from the fields an event actually carries; the rest are null. */
export const progressEvent = (
  fields: Partial<ProgressEvent> & Pick<ProgressEvent, "type">,
): ProgressEvent => ({
  stage: null,
  status: null,
  algorithm: null,
  manifest: null,
  error: null,
  started_at: null,
  updated_at: null,
  done: null,
  total: null,
  unit: null,
  ...fields,
});
export const stageState = (
  fields: Partial<StageState> & Pick<StageState, "stage">,
): StageState => ({
  ...progressEvent({ type: "stage" }),
  progress: null,
  ...fields,
});
