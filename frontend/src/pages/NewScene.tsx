import { useRef, useState } from "react";
import { useLocale, useTranslations } from "use-intl";
import { useNavigate, useParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { sceneApi } from "../lib/api";
import { Header } from "../components/Header";
import { UploadDropzone } from "../components/UploadDropzone";

export default function NewScene() {
  const t = useTranslations(),
    locale = useLocale(),
    navigate = useNavigate();
  const [name, setName] = useState(""),
    [busy, setBusy] = useState(false);
  const created = useRef<string | null>(null);
  return (
    <>
      <Header />
      <main id="main-content" className="page capture-page">
        <div className="page-heading">
          <p className="eyebrow">{t("ui.createStep")}</p>
          <h1>{t("ui.uploadTitle")}</h1>
          <p className="muted">{t("ui.uploadSubtitle")}</p>
        </div>
        <div className="capture-layout">
          <div
            className="card capture-form"
            role="region"
            aria-label={t("ui.captureForm")}
            tabIndex={0}
          >
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
                  created.current = (
                    await sceneApi.createScene(name.trim())
                  ).id;
                await sceneApi.uploadFiles(created.current, files, progress);
              }}
              onUploaded={() =>
                navigate(`/${locale}/scenes/${created.current}`)
              }
            />
            {!busy && (
              <Link className="button quiet" to={`/${locale}`}>
                {t("ui.cancel")}
              </Link>
            )}
          </div>
          <aside
            className="capture-tips card"
            aria-label={t("ui.captureGuide")}
            tabIndex={0}
          >
            <p className="eyebrow">{t("ui.guideCapture")}</p>
            <h2>{t("ui.captureGuide")}</h2>
            <ol>
              {["tipOne", "tipTwo", "tipThree", "tipFour"].map((key) => (
                <li key={key}>{t(`ui.${key}`)}</li>
              ))}
            </ol>
            <p className="muted">{t("ui.captureNote")}</p>
          </aside>
        </div>
      </main>
    </>
  );
}
