"use client";
import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { sceneApi } from "../lib/api";
import type { Scene } from "../lib/api/types";
import { useViewer } from "../lib/store/viewerStore";
import { focus, goHome } from "./viewer/camera";
import { defaultLayers, showMode, viewMode } from "./viewer/view";
import { DesignIcon } from "./DesignIcon";
import { ObjectDetails } from "./ObjectDetails";
import { ChatPanel } from "./ChatPanel";
import { StatusBadge } from "./StatusBadge";

const SceneCanvas = dynamic(() => import("./viewer/SceneCanvas"), {
  ssr: false,
});
type Panel = "object" | "chat" | "measure" | "layers" | "info" | null;

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
    [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [attempt, setAttempt] = useState(0);
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
  const results = useQuery({
    queryKey: ["search", scene.id, query],
    queryFn: () => sceneApi.searchObjects(scene.id, query),
    enabled: !!query,
  });
  const selected = objects.data?.find((o) => o.id === selectedId);
  const hasPoints = !!scene.assets?.points_url,
    hasMesh = !!scene.assets?.mesh_url;
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (!query) useViewer.getState().highlight([]);
    else if (results.data) focus(results.data.map((hit) => hit.object.id));
  }, [query, results.data]);
  useEffect(() => {
    if (selectedId) {
      useViewer.getState().setMeasuring(false);
      setPanel("object");
    } else setPanel((previous) => (previous === "object" ? null : previous));
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
    if (panel === "object") useViewer.getState().deselect();
    if (panel === "measure") useViewer.getState().setMeasuring(false);
    setPanel(null);
  }
  useEffect(() => {
    function escape(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      useViewer.getState().deselect();
      useViewer.getState().setMeasuring(false);
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
    useViewer.getState().deselect();
    useViewer.getState().setMeasuring(next === "measure");
    setPanel(next);
  }
  const distance =
    points.length === 2
      ? Math.hypot(...points[0].map((n, i) => n - points[1][i]))
      : null;
  const title =
    panel === "chat"
      ? t("ui.askScene")
      : panel === "layers"
        ? t("ui.displayLayers")
        : panel === "measure"
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
    <main className="explorer">
      <div className="viewport" aria-label={t("ui.viewerLabel")}>
        <ViewerBoundary key={attempt} fallback={errorFallback}>
          <SceneCanvas
            sceneId={scene.id}
            assets={scene.assets || {}}
            objects={objects.data || []}
          />
        </ViewerBoundary>
        {!hasPoints && !hasMesh && (
          <div className="asset-notice" role="status">
            {t("ui.noGeometry")}
          </div>
        )}
        <div className="viewer-topbar">
          <div className="view-modes" aria-label={t("ui.viewMode")}>
            <button
              className={viewMode(layers) === "points" ? "" : "secondary"}
              aria-pressed={viewMode(layers) === "points"}
              disabled={!hasPoints}
              onClick={() =>
                useViewer.getState().setLayers(showMode(layers, "points"))
              }
            >
              {t("layers.points")}
            </button>
            <button
              className={viewMode(layers) === "mesh" ? "" : "secondary"}
              aria-pressed={viewMode(layers) === "mesh"}
              disabled={!hasMesh}
              onClick={() =>
                useViewer.getState().setLayers(showMode(layers, "mesh"))
              }
            >
              {t("layers.mesh")}
            </button>
            <button
              className="secondary"
              aria-expanded={panel === "layers"}
              onClick={() => openPanel("layers")}
            >
              {t("ui.displayLayers")}
            </button>
          </div>
          <div className="viewer-search">
            <input
              type="search"
              aria-label={t("search")}
              placeholder={t("search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {query && (
              <div className="search-status card" role="status">
                {results.isFetching ? (
                  <p>{t("ui.searching")}</p>
                ) : results.error ? (
                  <p role="alert">{String(results.error)}</p>
                ) : (
                  <p>
                    {t("ui.searchCount", { count: results.data?.length || 0 })}
                  </p>
                )}
                <button
                  className="secondary full-width"
                  onClick={() => {
                    setSearch("");
                    setQuery("");
                  }}
                >
                  {t("ui.clearSearch")}
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="spatial-tools" aria-label={t("ui.spatialTools")}>
          <button
            className="secondary icon-button"
            aria-label={t("ui.resetView")}
            title={t("ui.resetView")}
            onClick={() => {
              goHome();
              setPanel(null);
            }}
          >
            <DesignIcon name="home" />
          </button>
          <button
            className="secondary icon-button"
            aria-label={t("measure")}
            title={t("measure")}
            aria-pressed={measuring}
            onClick={() => openPanel("measure")}
          >
            <DesignIcon name="measure" />
          </button>
          <button
            className="secondary icon-button"
            aria-label={t("ui.displayLayers")}
            title={t("ui.displayLayers")}
            aria-pressed={panel === "layers"}
            onClick={() => openPanel("layers")}
          >
            <DesignIcon name="layers" />
          </button>
          <button
            className="secondary icon-button"
            aria-label={t("ui.sceneInfo")}
            title={t("ui.sceneInfo")}
            aria-pressed={panel === "info"}
            onClick={() => openPanel("info")}
          >
            <DesignIcon name="info" />
          </button>
        </div>
        <div className="navigation-hints" aria-hidden="true">
          <span>{t("ui.orbitHint")}</span>
          <span>{t("ui.zoomHint")}</span>
          <span>{t("ui.panHint")}</span>
        </div>
        <button
          className="ask-scene"
          onClick={() => openPanel("chat")}
          aria-expanded={panel === "chat"}
        >
          {t("ui.askScene")}
        </button>
        {objects.error && (
          <p className="viewer-error" role="alert">
            {String(objects.error)}
          </p>
        )}
      </div>
      {panel && (
        <aside className="side-panel" aria-label={title}>
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
          {panel === "chat" && (
            <>
              <p className="caption muted">{t("ui.chatSubtitle")}</p>
              <ChatPanel sceneId={scene.id} />
            </>
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
          {panel === "layers" && (
            <div className="panel-body">
              <p className="muted">{t("ui.layersSubtitle")}</p>
              {(["points", "mesh", "boxes"] as const).map((layer) => (
                <label className="layer-toggle" key={layer}>
                  <span>{t(`layers.${layer}`)}</span>
                  <input
                    type="checkbox"
                    role="switch"
                    checked={layers[layer]}
                    disabled={
                      (layer === "points" && !hasPoints) ||
                      (layer === "mesh" && !hasMesh)
                    }
                    onChange={() => useViewer.getState().toggleLayer(layer)}
                  />
                </label>
              ))}
              <label className="field-label" htmlFor="point-size">
                {t("ui.pointSize")}
              </label>
              <input
                id="point-size"
                type="range"
                min="0.004"
                max="0.04"
                step="0.002"
                value={pointSize}
                onChange={(e) =>
                  useViewer.getState().setPointSize(Number(e.target.value))
                }
              />
              <button
                className="secondary full-width"
                onClick={() => {
                  useViewer
                    .getState()
                    .setLayers(defaultLayers(scene.assets ?? {}));
                  useViewer.getState().setPointSize(0.012);
                }}
              >
                {t("ui.restoreDefaults")}
              </button>
            </div>
          )}
        </aside>
      )}
    </main>
  );
}
