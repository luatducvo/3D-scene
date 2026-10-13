import { httpSceneApi } from "./http";
import { mockSceneApi } from "./mock";
export const sceneApi =
  process.env.NEXT_PUBLIC_API_MODE === "mock" ? mockSceneApi : httpSceneApi;
