import type { components } from "./schema";
export type Schemas = components["schemas"];
export type Scene = Schemas["SceneDetail"];
export type SceneObject = Schemas["SceneObject"];
export type ProgressEvent = Schemas["ProgressEvent"];
/** Builds a ProgressEvent from the fields an event actually carries; the rest are null. */
export const progressEvent = (
  fields: Partial<ProgressEvent> & Pick<ProgressEvent, "type">,
): ProgressEvent => ({
  stage: null,
  status: null,
  algorithm: null,
  manifest: null,
  error: null,
  progress: null,
  started_at: null,
  updated_at: null,
  done: null,
  total: null,
  unit: null,
  ...fields,
});
export type QueryEvent = Schemas["QueryEvent"];
export interface SceneApi {
  listScenes(): Promise<Schemas["SceneSummary"][]>;
  createScene(name: string): Promise<Schemas["SceneCreated"]>;
  deleteScene(id: string): Promise<void>;
  getScene(id: string): Promise<Scene>;
  uploadFiles(
    id: string,
    files: File[],
    progress?: (ratio: number) => void,
  ): Promise<void>;
  startProcessing(id: string): Promise<void>;
  listObjects(id: string): Promise<SceneObject[]>;
  searchObjects(id: string, query: string): Promise<Schemas["SearchHit"][]>;
  subscribeProgress(
    id: string,
    receive: (event: ProgressEvent) => void,
  ): () => void;
  askQuestion(
    id: string,
    body: Schemas["QueryRequest"],
    receive: (event: QueryEvent) => void,
    signal?: AbortSignal,
  ): Promise<void>;
  getMessages(id: string): Promise<Schemas["Message"][]>;
}
