/**
 * Camera commands for the whole UI. The canvas's controls attach a driver on mount; a command
 * given before then still updates the viewer state, and the controls apply it when they attach.
 */
import { useViewer } from "../../lib/store/viewerStore";
export interface CameraDriver {
  /** Fly to the whole room. */
  goHome(): void;
  /** Fit the given Objects in view. */
  focus(ids: string[]): void;
}
let driver: CameraDriver | null = null;
export function attachCamera(next: CameraDriver): () => void {
  driver = next;
  return () => {
    if (driver === next) driver = null;
  };
}
/** Clear the selection and highlights and show the whole room. */
export function goHome() {
  useViewer.getState().clear();
  driver?.goHome();
}
/** Fit Objects in view without changing result colors or selection. */
export function focus(ids: string[]) {
  if (ids.length) driver?.focus(ids);
}
