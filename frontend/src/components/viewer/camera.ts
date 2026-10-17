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
/** Highlight Objects and fit them in view, even when they are already highlighted. */
export function focus(ids: string[]) {
  useViewer.getState().highlight(ids);
  if (ids.length) driver?.focus(ids);
}
