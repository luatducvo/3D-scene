"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { sceneApi } from "../../lib/api";
import { Header } from "../../components/Header";
export default function SceneList() {
  const t = useTranslations(),
    locale = useLocale(),
    client = useQueryClient();
  const query = useQuery({
    queryKey: ["scenes"],
    queryFn: () => sceneApi.listScenes(),
  });
  const remove = useMutation({
    mutationFn: sceneApi.deleteScene,
    onSuccess: () => client.invalidateQueries({ queryKey: ["scenes"] }),
  });
  return (
    <>
      <Header />
      <main className="page">
        <div className="heading">
          <h1>{t("scenes")}</h1>
          <Link className="button" href={`/${locale}/scenes/new`}>
            + {t("newScene")}
          </Link>
        </div>
        {query.isLoading && <p>{t("loading")}</p>}
        {(query.error || remove.error) && (
          <p role="alert">{String(query.error || remove.error)}</p>
        )}
        <div className="scene-grid">
          {query.data?.map((scene) => (
            <article className="card" key={scene.id}>
              <div className="room-icon">◈</div>
              <h2>
                <Link href={`/${locale}/scenes/${scene.id}`}>{scene.name}</Link>
              </h2>
              <p className="badge">{t(`status.${scene.status}`)}</p>
              <button
                className="subtle"
                disabled={scene.status === "processing" || remove.isPending}
                onClick={() => remove.mutate(scene.id)}
              >
                {t("delete")}
              </button>
            </article>
          ))}
        </div>
        {query.data?.length === 0 && <p>{t("empty")}</p>}
      </main>
    </>
  );
}
