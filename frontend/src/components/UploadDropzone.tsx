"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { sceneApi } from "../lib/api";
import type { Quality } from "../lib/quality/score";
import { DesignIcon } from "./DesignIcon";

type Item = {
  id: string;
  file: File;
  preview?: string;
  quality?: Quality;
  error?: boolean;
};
type Upload = (
  files: File[],
  progress: (ratio: number) => void,
) => Promise<void>;
export function UploadDropzone({
  sceneId,
  upload,
  disabled = false,
  onBusyChange,
  onUploaded,
}: {
  sceneId?: string;
  upload?: Upload;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onUploaded: () => void;
}) {
  const t = useTranslations();
  const [items, setItems] = useState<Item[]>([]),
    [error, setError] = useState(""),
    [progress, setProgress] = useState<number | null>(null),
    [busy, setBusy] = useState(false),
    [dragging, setDragging] = useState(false);
  const worker = useRef<Worker | null>(null),
    previews = useRef(new Set<string>());
  useEffect(() => {
    const w = new Worker(
      new URL("../lib/quality/blurWorker.ts", import.meta.url),
    );
    worker.current = w;
    w.onmessage = ({ data }) =>
      setItems((items) =>
        items.map((item) =>
          item.id === data.id ? { ...item, ...data } : item,
        ),
      );
    return () => {
      w.terminate();
      previews.current.forEach((url) => URL.revokeObjectURL(url));
      previews.current.clear();
    };
  }, []);
  function add(files: File[]) {
    if (busy || !files.length) return;
    const all = [...items.map((x) => x.file), ...files];
    if (
      all.some(
        (f) => !f.type.startsWith("image/") && !f.type.startsWith("video/"),
      ) ||
      (all.some((f) => f.type.startsWith("video/")) && all.length !== 1)
    ) {
      setError(t("invalidFiles"));
      return;
    }
    const batch = files.map((file) => {
      const preview = file.type.startsWith("image/")
        ? URL.createObjectURL(file)
        : undefined;
      if (preview) previews.current.add(preview);
      return { id: crypto.randomUUID(), file, preview };
    });
    setItems((i) => [...i, ...batch]);
    setError("");
    setProgress(null);
    batch
      .filter((i) => i.file.type.startsWith("image/"))
      .forEach((i) => worker.current?.postMessage({ id: i.id, file: i.file }));
  }
  function remove(item: Item) {
    if (item.preview) {
      URL.revokeObjectURL(item.preview);
      previews.current.delete(item.preview);
    }
    setItems((items) => items.filter((x) => x.id !== item.id));
  }
  const checking = items.some(
    (item) =>
      item.file.type.startsWith("image/") && !item.quality && !item.error,
  );
  return (
    <section className="upload-section" aria-label={t("capture")}>
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(Array.from(e.dataTransfer.files));
        }}
      >
        <DesignIcon name="upload" />
        <h2>{t("drop")}</h2>
        <p className="muted">{t("ui.fileFormats")}</p>
        <label className="button secondary file-picker" aria-disabled={busy}>
          {t("choose")}
          <input
            type="file"
            multiple
            accept="image/*,video/*"
            disabled={busy}
            onChange={(e) => {
              add(Array.from(e.target.files || []));
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <p className="caption muted">{t("ui.qualityBeforeUpload")}</p>
      {items.length > 0 && (
        <>
          <div className="section-heading">
            <h3>{t("ui.selectedFiles", { count: items.length })}</h3>
            <span className="muted caption">{t("ui.readyToUpload")}</span>
          </div>
          <ul className="uploads">
            {items.map((item) => (
              <li className="upload-item" key={item.id}>
                {item.preview ? (
                  <img
                    className="upload-preview"
                    src={item.preview}
                    alt={item.file.name}
                  />
                ) : (
                  <div className="video-preview">{t("ui.video")}</div>
                )}
                <span className="file-name" title={item.file.name}>
                  {item.file.name}
                </span>
                {item.file.type.startsWith("image/") && (
                  <span className={`quality ${item.quality?.level || ""}`}>
                    {t(
                      item.error
                        ? "qualityUnavailable"
                        : item.quality?.level || "qualityPending",
                    )}
                  </span>
                )}
                <button
                  className="quiet remove-file"
                  disabled={busy}
                  onClick={() => remove(item)}
                  aria-label={t("ui.removeFile", { name: item.file.name })}
                >
                  {t("remove")}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="upload-actions">
        <button
          disabled={disabled || !items.length || busy || checking}
          onClick={async () => {
            setBusy(true);
            onBusyChange?.(true);
            setProgress(0);
            setError("");
            try {
              const files = items.map((x) => x.file);
              if (upload) await upload(files, setProgress);
              else if (sceneId)
                await sceneApi.uploadFiles(sceneId, files, setProgress);
              else throw new Error("A scene or upload handler is required");
              items.forEach((item) => {
                if (item.preview) {
                  URL.revokeObjectURL(item.preview);
                  previews.current.delete(item.preview);
                }
              });
              setItems([]);
              onUploaded();
            } catch (e) {
              setError(String(e));
            } finally {
              setBusy(false);
              onBusyChange?.(false);
            }
          }}
        >
          {busy ? t("ui.uploading") : t("upload")}
        </button>
        {progress !== null && (
          <div className="upload-progress" role="status">
            <progress aria-label={t("upload")} max={1} value={progress} />
            <span>{Math.round(progress * 100)}%</span>
          </div>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
