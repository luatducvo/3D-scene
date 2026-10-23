import {
  Component,
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "use-intl";
import { sceneApi } from "../lib/api";
import type { Scene } from "../lib/api/types";
import { useViewer } from "../lib/store/viewerStore";
import { focus, goHome } from "./viewer/camera";
import {
  defaultLayers,
  highlightState,
  showMode,
  viewMode,
} from "./viewer/view";
import { SearchError } from "./SearchError";
import { ObjectDetails } from "./ObjectDetails";
import { normalizeSimilarities } from "./viewer/highlight";
import { HeatmapLegend } from "./HeatmapLegend";
import { StatusBadge } from "./StatusBadge";

const SceneCanvas = lazy(() => import("./viewer/SceneCanvas"));
type Panel = "object" | "measure" | "info" | null;

class ViewerBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export function SceneExplorer({ scene }: { scene: Scene }) {
  const t = useTranslations(),
    format = useFormatter();
  const [panel, setPanel] = useState<Panel>(null),
    [attempt, setAttempt] = useState(0);
  const search = useViewer((s) => s.search),
    query = search.trim();
  const appearance = useViewer((s) => s.appearance);
  const selectedId = useViewer((s) => s.selectedId),
    measuring = useViewer((s) => s.measuring),
    points = useViewer((s) => s.points),
    layers = useViewer((s) => s.layers),
    pointSize = useViewer((s) => s.pointSize);
  const closeRef = useRef<HTMLButtonElement>(null),
    previousFocus = useRef<HTMLElement | null>(null);
  const objects = useQuery({
    queryKey: ["objects", scene.id],
    queryFn: () => sceneApi.listObjects(scene.id),
  });
  const [searchError, setSearchError] = useState<unknown>(null);
  const similarities = useViewer((s) => s.similarities);
  const membershipUrl = scene.assets?.membership_url;
  const membership = useQuery({
    queryKey: ["membership", membershipUrl],
    queryFn: () => sceneApi.getMembership(membershipUrl!),
    enabled: !!membershipUrl,
    staleTime: Infinity,
  });
  const membershipMismatch = useViewer((s) => s.membershipMismatch);
  const selected = objects.data?.find((o) => o.id === selectedId);
  const hasPoints = !!scene.assets?.points_url,
    hasMesh = !!scene.assets?.mesh_url;
  const highlighting = highlightState(
    scene.assets ?? {},
    membership.status,
    membershipMismatch,
    viewMode(layers),
  );
  useEffect(() => {
    if (!query) {
      setSearchError(null);
      if (useViewer.getState().highlightedIds.length)
        useViewer.getState().endSearch();
      return;
    }
    const version = useViewer.getState().beginResult();
    let disposed = false;
    setSearchError(null);
    const timer = setTimeout(async () => {
      try {
        const hits = await sceneApi.searchObjects(scene.id, query);
        if (disposed) return;
        const values = normalizeSimilarities(
          Object.fromEntries(
            hits.map((hit) => [hit.object.id, hit.raw_similarity]),
          ),
        );
        setSearchError(null);
        if (
          useViewer.getState().showResult(
            version,
            hits.map((hit) => hit.object.id),
            values,
          )
        )
          focus(hits.map((hit) => hit.object.id));
      } catch (error) {
        if (!disposed) {
          setSearchError(error);
          useViewer.getState().showResult(version, [], {});
        }
      }
    }, 300);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [query, scene.id]);
  useEffect(() => {
    if (!selectedId)
      setPanel((previous) => (previous === "object" ? null : previous));
  }, [selectedId]);
  useEffect(() => {
    useViewer.getState().setLayers(defaultLayers(scene.assets ?? {}));
  }, [scene.id, hasPoints, hasMesh]);
  useEffect(() => {
    if (!panel) return;
    const focused = document.activeElement;
    if (focused instanceof HTMLElement && !focused.closest(".side-panel"))
      previousFocus.current = focused;
    closeRef.current?.focus();
    return () => previousFocus.current?.focus();
  }, [panel]);
  function closePanel() {
    if (panel === "measure") useViewer.getState().setMeasuring(false);
    setPanel(null);
  }
  useEffect(() => {
    function escape(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      useViewer.getState().escape();
      setPanel(null);
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  function openPanel(next: Panel) {
    if (panel === next) {
      closePanel();
      return;
    }
    // Object details belong to the Selection; Measurement and Scene info replace it.
    if (next !== "object") useViewer.getState().deselect();
    useViewer.getState().setMeasuring(next === "measure");
    setPanel(next);
  }
  const distance =
    points.length === 2
      ? Math.hypot(...points[0].map((n, i) => n - points[1][i]))
      : null;
  const title =
    panel === "measure"
      ? t("measure")
      : panel === "info"
        ? t("ui.sceneInfo")
        : t("ui.objectDetails");
  const errorFallback = (
    <div className="viewer-state">
      <p>{t("ui.viewerError")}</p>
      <button className="secondary" onClick={() => setAttempt((n) => n + 1)}>
        {t("ui.retry")}
      </button>
    </div>
  );
  return (
    <main id="main-content" className="explorer">
      <section className="explorer-title">
        <h1>{scene.name}</h1>
        <StatusBadge status={scene.status} />
      </section>
      <div className="explorer-body">
        <div className="viewport" aria-label={t("ui.viewerLabel")}>
          <div className="canvas-surface">
            <ViewerBoundary key={attempt} fallback={errorFallback}>
              <Suspense
                fallback={
                  <div className="viewer-state" role="status">
                    {t("loading")}
                  </div>
                }
              >
                <SceneCanvas
                  sceneId={scene.id}
                  assets={scene.assets || {}}
                  objects={objects.data || []}
                  membership={membership.data ?? null}
                />
              </Suspense>
            </ViewerBoundary>
            {query && searchError != null && (
              <SearchError error={searchError} />
            )}
            {!hasPoints && !hasMesh && (
              <div className="asset-notice" role="status">
                {t("ui.noGeometry")}
              </div>
            )}
            {highlighting !== "available" && (
              <div className="asset-notice" role="status">
                {t("ui.highlightFailed")}
              </div>
            )}
            {Object.keys(similarities).length > 0 && (
              <HeatmapLegend values={Object.values(similarities)} />
            )}
          </div>
          <div className="viewer-topbar">
            <div className="view-modes">
              <div
                className="segmented"
                role="radiogroup"
                aria-label={t("ui.viewMode")}
              >
                {(["points", "mesh"] as const).map((mode) => {
                  const shown = viewMode(layers) === mode;
                  return (
                    <button
                      key={mode}
                      role="radio"
                      aria-checked={shown}
                      className={shown ? "" : "secondary"}
                      disabled={mode === "points" ? !hasPoints : !hasMesh}
                      onClick={() =>
                        useViewer.getState().setLayers(showMode(layers, mode))
                      }
                    >
                      {t(`layers.${mode}`)}
                    </button>
                  );
                })}
              </div>
              {viewMode(layers) === "points" && (
                <label className="point-size">
                  <span>{t("ui.pointSize")}</span>
                  <input
                    type="range"
                    min="0.004"
                    max="0.04"
                    step="0.002"
                    value={pointSize}
                    onChange={(e) =>
                      useViewer.getState().setPointSize(Number(e.target.value))
                    }
                  />
                </label>
              )}
              <label className="instance-colors">
                <span>{t("appearance.instances")}</span>
                <input
                  type="checkbox"
                  role="switch"
                  checked={appearance === "instances"}
                  disabled={highlighting !== "available"}
                  onChange={(e) =>
                    useViewer
                      .getState()
                      .setAppearance(
                        e.target.checked ? "instances" : "original",
                      )
                  }
                />
              </label>
            </div>
            <div className="viewer-search">
              <input
                type="search"
                aria-label={t("search")}
                title={t("englishInput")}
                placeholder={t("search")}
                value={search}
                onChange={(e) => useViewer.getState().setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="spatial-tools" aria-label={t("ui.spatialTools")}>
            <button
              className="secondary tool-button"
              aria-label={t("ui.resetView")}
              title={t("ui.resetView")}
              onClick={() => {
                goHome();
                setPanel(null);
              }}
            >
              {t("ui.resetView")}
            </button>
            <button
              className="secondary tool-button"
              aria-label={t("measure")}
              title={t("measure")}
              aria-pressed={measuring}
              onClick={() => openPanel("measure")}
            >
              {t("measure")}
            </button>
            <button
              className="secondary tool-button"
              aria-label={t("ui.objectDetails")}
              title={t("ui.objectDetails")}
              aria-pressed={panel === "object"}
              disabled={!selectedId}
              onClick={() => openPanel("object")}
            >
              {t("ui.objectDetails")}
            </button>
            <button
              className="secondary tool-button"
              aria-label={t("ui.sceneInfo")}
              title={t("ui.sceneInfo")}
              aria-pressed={panel === "info"}
              onClick={() => openPanel("info")}
            >
              {t("ui.sceneInfo")}
            </button>
          </div>
          <div className="navigation-hints" aria-hidden="true">
            <span>{t("ui.orbitHint")}</span>
            <span>{t("ui.zoomHint")}</span>
            <span>{t("ui.panHint")}</span>
          </div>
          {objects.error && (
            <p className="viewer-error" role="alert">
              {String(objects.error)}
            </p>
          )}
        </div>
        {!panel && (
          <aside className="explorer-guide card">
            <p className="eyebrow">{t("ui.exploreEyebrow")}</p>
            <h2>{t("ui.exploreTitle")}</h2>
            <p className="muted">{t("ui.exploreBody")}</p>
            <div className="guide-hints">
              <p>{t("ui.orbitHint")}</p>
              <p>{t("ui.zoomHint")}</p>
              <p>{t("ui.panHint")}</p>
            </div>
          </aside>
        )}
        <aside
          className="side-panel"
          aria-label={title}
          hidden={!panel}
          tabIndex={0}
          style={{ display: panel ? undefined : "none" }}
        >
          <div className="panel-heading">
            {panel !== "object" && <h2>{title}</h2>}
            <button
              ref={closeRef}
              className="quiet close-panel"
              onClick={closePanel}
            >
              {t("ui.close")}
            </button>
          </div>
          {panel === "object" && selected && (
            <ObjectDetails object={selected} />
          )}
          {panel === "info" && (
            <div className="panel-body">
              <h3>{scene.name}</h3>
              <StatusBadge status={scene.status} />
              <dl className="scene-facts">
                <dt>{t("ui.createdOn")}</dt>
                <dd>
                  {format.dateTime(new Date(scene.created_at), {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}
                </dd>
                <dt>{t("ui.sceneUnits")}</dt>
                <dd>{t("ui.meters")}</dd>
                <dt>{t("ui.upAxis")}</dt>
                <dd>Z ↑</dd>
              </dl>
            </div>
          )}
          {panel === "measure" && (
            <div className="panel-body">
              <p className="muted">
                {t(
                  points.length === 0
                    ? "ui.pickA"
                    : points.length === 1
                      ? "ui.pickB"
                      : "ui.measured",
                )}
              </p>
              <div className="dimensions">
                {distance !== null ? (
                  <>
                    <strong className="distance-value">
                      {format.number(distance, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 3,
                      })}{" "}
                      m
                    </strong>
                    <span>{t("ui.straightDistance")}</span>
                  </>
                ) : (
                  <strong>{points.length ? "A ✓  →  B" : "A  →  B"}</strong>
                )}
              </div>
              <button
                className="full-width"
                onClick={() => useViewer.getState().setMeasuring(true)}
              >
                {t("ui.measureAgain")}
              </button>
              <button className="secondary full-width" onClick={closePanel}>
                {t("ui.exitMeasure")}
              </button>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
