"use client";
import { use, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Header } from "../../../../components/Header";
import { UploadDropzone } from "../../../../components/UploadDropzone";
import { StageStepper, stages } from "../../../../components/StageStepper";
import { ObjectList } from "../../../../components/ObjectList";
import { ChatPanel } from "../../../../components/ChatPanel";
import { sceneApi } from "../../../../lib/api";
import {
  progressEvent,
  type ProgressEvent,
} from "../../../../lib/api/port";
import { useViewer } from "../../../../lib/store/viewerStore";
const SceneCanvas = dynamic(
  () => import("../../../../components/viewer/SceneCanvas"),
  { ssr: false },
);
export default function ScenePage({
  params,
}: {
  params: Promise<{ sceneId: string }>;
}) {
  const { sceneId } = use(params),
    t = useTranslations(),
    client = useQueryClient();
  const scene = useQuery({
    queryKey: ["scene", sceneId],
    queryFn: () => sceneApi.getScene(sceneId),
  });
  const objects = useQuery({
    queryKey: ["objects", sceneId],
    queryFn: () => sceneApi.listObjects(sceneId),
    enabled: scene.data?.status === "ready",
  });
  const [events, setEvents] = useState<Record<string, ProgressEvent>>({}),
    [stage, setStage] = useState(""),
    [tab, setTab] = useState("objects"),
    [suggestion, setSuggestion] = useState(""),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState("");
  const measuring = useViewer((s) => s.measuring);
  const searchResult = useQuery({
    queryKey: ["search", sceneId, query],
    queryFn: () => sceneApi.searchObjects(sceneId, query),
    enabled: !!query.trim() && scene.data?.status === "ready",
  });
  useEffect(() => {
    const timeout = setTimeout(() => setQuery(search), 300);
    return () => clearTimeout(timeout);
  }, [search]);
  useEffect(() => {
    if (!query.trim()) useViewer.getState().highlight([]);
    else if (searchResult.data)
      useViewer.getState().highlight(searchResult.data.map((h) => h.object.id));
  }, [query, searchResult.data]);
  useEffect(() => {
    useViewer.getState().clear();
    return () => useViewer.getState().clear();
  }, [sceneId]);
  useEffect(() => {
    if (scene.data?.stage_runs)
      setEvents(
        Object.fromEntries(
          scene.data.stage_runs.map((run) => [
            run.stage,
            progressEvent({ ...run, type: "stage" }),
          ]),
        ),
      );
  }, [scene.data?.stage_runs]);
  useEffect(() => {
    if (scene.data?.status !== "processing") return;
    return sceneApi.subscribeProgress(sceneId, (event) => {
      if (event.type === "stage" && event.stage)
        setEvents((previous) => ({ ...previous, [event.stage!]: event }));
      if (event.type === "progress" && event.stage && event.total != null)
        setEvents((previous) => ({
          ...previous,
          [event.stage!]: {
            ...(previous[event.stage!] ??
              progressEvent({ type: "stage", stage: event.stage })),
            progress: {
              done: event.done ?? 0,
              total: event.total!,
              unit: event.unit ?? "",
            },
          },
        }));
      if (event.type === "status")
        void client.invalidateQueries({ queryKey: ["scene", sceneId] });
    });
  }, [sceneId, scene.data?.status, client]);
  const process = useMutation({
    mutationFn: () => sceneApi.startProcessing(sceneId, stage || undefined),
    onSuccess: () => {
      setEvents({});
      return client.invalidateQueries({ queryKey: ["scene", sceneId] });
    },
  });
  if (scene.isLoading)
    return (
      <>
        <Header />
        <p className="page">{t("loading")}</p>
      </>
    );
  if (!scene.data)
    return (
      <>
        <Header />
        <p role="alert">{String(scene.error)}</p>
      </>
    );
  const data = scene.data;
  return (
    <>
      <Header />
      {data.status === "ready" ? (
        <main className="explorer">
          <div className="viewport">
            <SceneCanvas
              sceneId={sceneId}
              assets={data.assets || {}}
              objects={objects.data || []}
            />
            <div className="viewer-toolbar">
              <input
                aria-label={t("search")}
                placeholder={t("search")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <button
                aria-pressed={measuring}
                onClick={() => useViewer.getState().setMeasuring(!measuring)}
              >
                {t("measure")}
              </button>
              <button onClick={() => useViewer.getState().clear()}>
                {t("clear")}
              </button>
              {measuring && <span>{t("measureHint")}</span>}
              {searchResult.error && (
                <p role="alert">{String(searchResult.error)}</p>
              )}
            </div>
          </div>
          <aside className="side-panel">
            <h1>{data.name}</h1>
            <div className="tabs">
              {["objects", "ask"].map((key) => (
                <button
                  aria-pressed={tab === key}
                  className={tab === key ? "selected" : "subtle"}
                  key={key}
                  onClick={() => setTab(key)}
                >
                  {t(key)}
                </button>
              ))}
            </div>
            {tab === "objects" ? (
              <ObjectList
                objects={objects.data || []}
                onQuestion={(q) => {
                  setSuggestion(q);
                  setTab("ask");
                }}
              />
            ) : (
              <ChatPanel sceneId={sceneId} suggestion={suggestion} />
            )}
            <details>
              <summary>{t("rerun")}</summary>
              <select value={stage} onChange={(e) => setStage(e.target.value)}>
                <option value="">{t("allStages")}</option>
                {stages.map((s) => (
                  <option key={s} value={s}>
                    {t(`stages.${s}`)}
                  </option>
                ))}
              </select>
              <button
                disabled={process.isPending}
                onClick={() => process.mutate()}
              >
                {t("process")}
              </button>
            </details>
            {process.error && <p role="alert">{String(process.error)}</p>}
            {data.ingest_report && (
              <details>
                <summary>{t("report")}</summary>
                <pre>{JSON.stringify(data.ingest_report, null, 2)}</pre>
              </details>
            )}
          </aside>
        </main>
      ) : (
        <main className="page narrow">
          <h1>{data.name}</h1>
          <p className="badge">{t(`status.${data.status}`)}</p>
          {["created", "uploaded"].includes(data.status) && (
            <UploadDropzone
              sceneId={sceneId}
              onUploaded={() =>
                void client.invalidateQueries({ queryKey: ["scene", sceneId] })
              }
            />
          )}
          <StageStepper events={events} />
          {data.failure && (
            <p role="alert">
              {t(`stages.${data.failure.stage}`)}: {data.failure.code} —{" "}
              {data.failure.message}
            </p>
          )}
          {data.ingest_report && (
            <details open>
              <summary>{t("report")}</summary>
              <pre>{JSON.stringify(data.ingest_report, null, 2)}</pre>
            </details>
          )}
          {data.status === "processing" ? (
            <p>{t("busy")}</p>
          ) : (
            <>
              <select
                aria-label={t("rerun")}
                value={stage}
                onChange={(e) => setStage(e.target.value)}
              >
                <option value="">{t("allStages")}</option>
                {stages.map((s) => (
                  <option value={s} key={s}>
                    {t(`stages.${s}`)}
                  </option>
                ))}
              </select>
              <button
                disabled={data.status === "created" || process.isPending}
                onClick={() => process.mutate()}
              >
                {t("process")}
              </button>
              {data.status === "failed" && <p>{t("locked")}</p>}
            </>
          )}
          {process.error && <p role="alert">{String(process.error)}</p>}
        </main>
      )}
    </>
  );
}
