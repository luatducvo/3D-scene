"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { Header } from "../../../../components/Header";
import { UploadDropzone } from "../../../../components/UploadDropzone";
import { StageStepper } from "../../../../components/StageStepper";
import { SceneExplorer } from "../../../../components/SceneExplorer";
import { StatusBadge } from "../../../../components/StatusBadge";
import { IngestReport } from "../../../../components/IngestReport";
import { Modal } from "../../../../components/Modal";
import { sceneApi } from "../../../../lib/api";
import { useSceneProgress } from "../../../../lib/sceneProgress";
import { useViewer } from "../../../../lib/store/viewerStore";

export default function ScenePage({
  params,
}: {
  params: Promise<{ sceneId: string }>;
}) {
  const { sceneId } = use(params),
    t = useTranslations(),
    locale = useLocale(),
    router = useRouter(),
    client = useQueryClient();
  const scene = useQuery({
    queryKey: ["scene", sceneId],
    queryFn: () => sceneApi.getScene(sceneId),
  });
  const events = useSceneProgress(sceneId, scene.data);
  const [settings, setSettings] = useState(false),
    [confirmDelete, setConfirmDelete] = useState(false),
    [uploading, setUploading] = useState(false);
  useEffect(() => {
    useViewer.getState().reset();
    setSettings(false);
    return () => useViewer.getState().reset();
  }, [sceneId]);
  const process = useMutation({
    mutationFn: () => sceneApi.startProcessing(sceneId),
    onSuccess: async () => {
      setSettings(false);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["scene", sceneId] }),
        client.invalidateQueries({ queryKey: ["scenes"] }),
        client.invalidateQueries({ queryKey: ["objects", sceneId] }),
      ]);
    },
  });
  const remove = useMutation({
    mutationFn: () => sceneApi.deleteScene(sceneId),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["scenes"] });
      router.push(`/${locale}`);
    },
  });
  if (scene.isLoading)
    return (
      <>
        <Header />
        <main className="page loading-state" role="status">
          {t("loading")}
        </main>
      </>
    );
  if (!scene.data)
    return (
      <>
        <Header />
        <main className="page">
          <p role="alert">{String(scene.error)}</p>
          <button onClick={() => void scene.refetch()}>{t("ui.retry")}</button>
        </main>
      </>
    );
  const data = scene.data,
    active = data.status === "processing" || process.isPending;
  return (
    <>
      <Header
        sceneName={data.name}
        actions={
          <button
            className="quiet"
            onClick={() => {
              setSettings(true);
              setConfirmDelete(false);
            }}
          >
            {t("ui.options")}
          </button>
        }
      />
      {data.status === "ready" ? (
        <SceneExplorer key={sceneId} scene={data} />
      ) : (
        <main className="page">
          <div className="page-heading">
            <p className="eyebrow">{data.name}</p>
            <h1>
              {t(
                data.status === "processing"
                  ? "ui.processingTitle"
                  : data.status === "failed"
                    ? "ui.failedTitle"
                    : "ui.reviewTitle",
              )}
            </h1>
            <p className="muted">
              {t(
                data.status === "processing"
                  ? "ui.processingSubtitle"
                  : data.status === "failed"
                    ? "locked"
                    : "ui.reviewSubtitle",
              )}
            </p>
            <StatusBadge status={data.status} />
          </div>
          <div className="processing-layout">
            <section className="card work-card">
              {(data.status === "created" || data.status === "uploaded") && (
                <UploadDropzone
                  sceneId={sceneId}
                  onBusyChange={setUploading}
                  onUploaded={() =>
                    void client.invalidateQueries({
                      queryKey: ["scene", sceneId],
                    })
                  }
                />
              )}
              {(data.status === "processing" ||
                data.status === "failed" ||
                Object.keys(events).length > 0) && (
                <StageStepper events={events} />
              )}
              {data.failure && (
                <div className="error-card" role="alert">
                  <strong>{t(`stages.${data.failure.stage}`)}</strong>
                  <p>{data.failure.message}</p>
                  <small>{data.failure.code}</small>
                </div>
              )}
              {data.status === "uploaded" && (
                <div className="process-actions">
                  <p className="muted">{t("ui.uploadReady")}</p>
                  <button
                    disabled={uploading || process.isPending}
                    onClick={() => process.mutate()}
                  >
                    {t("process")}
                  </button>
                </div>
              )}
              {data.status === "failed" && (
                <div className="process-actions">
                  <Link className="button" href={`/${locale}/scenes/new`}>
                    {t("newScene")}
                  </Link>
                  <button
                    className="secondary"
                    onClick={() => setSettings(true)}
                  >
                    {t("rerun")}
                  </button>
                </div>
              )}
              {process.error && <p role="alert">{String(process.error)}</p>}
            </section>
            <aside className="card processing-summary">
              <div className="summary-illustration">
                <img src="/design/capture.svg" alt="" />
              </div>
              <h2>{data.name}</h2>
              <StatusBadge status={data.status} />
              {data.ingest_report && (
                <details open>
                  <summary>{t("report")}</summary>
                  <IngestReport report={data.ingest_report} />
                </details>
              )}
              {active && (
                <p className="caption muted">{t("ui.publicationNotice")}</p>
              )}
            </aside>
          </div>
          <Link className="button secondary back-library" href={`/${locale}`}>
            {t("ui.backLibrary")}
          </Link>
        </main>
      )}
      {settings && (
        <Modal
          title={t("ui.sceneSettings")}
          onClose={() => {
            if (!remove.isPending) setSettings(false);
          }}
        >
          <h3>{data.name}</h3>
          <StatusBadge status={data.status} />
          {(data.status === "ready" || data.status === "failed") && (
            <section className="settings-section">
              <p className="caption muted">{t("ui.rerunDescription")}</p>
              <button disabled={active} onClick={() => process.mutate()}>
                {t("ui.rerunAction")}
              </button>
              {process.error && <p role="alert">{String(process.error)}</p>}
            </section>
          )}
          {active && <p className="muted">{t("busy")}</p>}
          {data.status === "ready" && (
            <p className="caption muted">{t("locked")}</p>
          )}
          {data.ingest_report && (
            <details>
              <summary>{t("report")}</summary>
              <IngestReport report={data.ingest_report} />
            </details>
          )}
          <section className="settings-section danger-section">
            <h3>{t("ui.deleteScene")}</h3>
            <p>{t("ui.deleteDescription")}</p>
            {confirmDelete ? (
              <>
                <p className="field-label">
                  {t("ui.deleteConfirmation", { name: data.name })}
                </p>
                <div className="action-row">
                  <button
                    className="secondary"
                    disabled={remove.isPending}
                    onClick={() => setConfirmDelete(false)}
                  >
                    {t("ui.keepScene")}
                  </button>
                  <button
                    className="danger"
                    disabled={active || remove.isPending}
                    onClick={() => remove.mutate()}
                  >
                    {t("ui.deleteForever")}
                  </button>
                </div>
              </>
            ) : (
              <button
                className="danger"
                disabled={active || uploading}
                onClick={() => setConfirmDelete(true)}
              >
                {t("ui.deleteScene")}
              </button>
            )}
            {remove.error && <p role="alert">{String(remove.error)}</p>}
          </section>
        </Modal>
      )}
    </>
  );
}
