"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { sceneApi } from "../lib/api";
import type { Quality } from "../lib/quality/score";
type Item = { id: string; file: File; quality?: Quality; error?: boolean };
export function UploadDropzone({
  sceneId,
  onUploaded,
}: {
  sceneId: string;
  onUploaded: () => void;
}) {
  const t = useTranslations();
  const [items, setItems] = useState<Item[]>([]),
    [error, setError] = useState(""),
    [progress, setProgress] = useState<number | null>(null),
    [busy, setBusy] = useState(false);
  const worker = useRef<Worker | null>(null);
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
    return () => w.terminate();
  }, []);
  function add(files: File[]) {
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
    const batch = files.map((file) => ({ id: crypto.randomUUID(), file }));
    setItems((i) => [...i, ...batch]);
    setError("");
    batch
      .filter((i) => i.file.type.startsWith("image/"))
      .forEach((i) => worker.current?.postMessage(i));
  }
  return (
    <section>
      <h2>{t("capture")}</h2>
      <ol className="tips">
        {(t.raw("tips") as string[]).map((tip) => (
          <li key={tip}>{tip}</li>
        ))}
      </ol>
      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!busy) add(Array.from(e.dataTransfer.files));
        }}
      >
        <p>{t("drop")}</p>
        <label className="button">
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
      <ul className="uploads">
        {items.map((item) => (
          <li key={item.id}>
            <span>{item.file.name}</span>
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
              className="subtle"
              disabled={busy}
              onClick={() =>
                setItems((items) => items.filter((x) => x.id !== item.id))
              }
            >
              {t("remove")}
            </button>
          </li>
        ))}
      </ul>
      <button
        disabled={!items.length || busy}
        onClick={async () => {
          setBusy(true);
          setProgress(0);
          try {
            await sceneApi.uploadFiles(
              sceneId,
              items.map((x) => x.file),
              setProgress,
            );
            setItems([]);
            onUploaded();
          } catch (e) {
            setError(String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {t("upload")}
      </button>
      {progress !== null && (
        <>
          <progress max={1} value={progress} />
          <span>{Math.round(progress * 100)}%</span>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
