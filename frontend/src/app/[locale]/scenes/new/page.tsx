"use client";
import { useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { sceneApi } from "../../../../lib/api";
import { Header } from "../../../../components/Header";
import { UploadDropzone } from "../../../../components/UploadDropzone";

export default function NewScene() {
  const t = useTranslations(),
    locale = useLocale(),
    router = useRouter();
  const [name, setName] = useState(""),
    [busy, setBusy] = useState(false);
  const created = useRef<string | null>(null);
  return (
    <>
      <Header />
      <main className="page">
        <div className="page-heading">
          <p className="eyebrow">{t("ui.createStep")}</p>
          <h1>{t("ui.uploadTitle")}</h1>
          <p className="muted">{t("ui.uploadSubtitle")}</p>
        </div>
        <div className="card capture-form">
          <label className="field-label" htmlFor="scene-name">
            {t("name")}
          </label>
          <input
            id="scene-name"
            autoFocus
            required
            maxLength={200}
            value={name}
            disabled={busy || !!created.current}
            placeholder={t("ui.sceneNamePlaceholder")}
            onChange={(e) => setName(e.target.value)}
          />
          <UploadDropzone
            disabled={!name.trim()}
            onBusyChange={setBusy}
            upload={async (files, progress) => {
              if (!created.current)
                created.current = (await sceneApi.createScene(name.trim())).id;
              await sceneApi.uploadFiles(created.current, files, progress);
            }}
            onUploaded={() =>
              router.push(`/${locale}/scenes/${created.current}`)
            }
          />
          {!busy && (
            <Link className="button quiet" href={`/${locale}`}>
              {t("ui.cancel")}
            </Link>
          )}
        </div>
      </main>
    </>
  );
}
