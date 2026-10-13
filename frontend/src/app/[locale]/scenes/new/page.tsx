"use client";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { sceneApi } from "../../../../lib/api";
import { Header } from "../../../../components/Header";
export default function NewScene() {
  const t = useTranslations(),
    locale = useLocale(),
    router = useRouter();
  const [name, setName] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <>
      <Header />
      <main className="page narrow">
        <h1>{t("newScene")}</h1>
        <ol className="tips">
          {(t.raw("tips") as string[]).map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ol>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              const scene = await sceneApi.createScene(name.trim());
              router.push(`/${locale}/scenes/${scene.id}`);
            } catch (e) {
              setError(String(e));
              setBusy(false);
            }
          }}
        >
          <label>
            {t("name")}
            <input
              autoFocus
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <button disabled={!name.trim() || busy}>{t("create")}</button>
          {error && <p role="alert">{error}</p>}
        </form>
      </main>
    </>
  );
}
