"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { sceneApi } from "../../lib/api";
import { Header } from "../../components/Header";
import { StatusBadge } from "../../components/StatusBadge";

export default function SceneList() {
  const t = useTranslations(),
    locale = useLocale(),
    format = useFormatter();
  const [filter, setFilter] = useState("all"),
    [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["scenes"],
    queryFn: () => sceneApi.listScenes(),
    refetchInterval: 5000,
  });
  const scenes = query.data || [];
  const filtered = scenes.filter(
    (scene) =>
      (filter === "all" || scene.status === filter) &&
      scene.name
        .toLocaleLowerCase(locale)
        .includes(search.toLocaleLowerCase(locale)),
  );
  return (
    <>
      <Header />
      <main className="page library-page">
        <div className="page-heading heading">
          <div>
            <p className="eyebrow">{t("ui.library")}</p>
            <h1>{t("ui.libraryTitle")}</h1>
            <p className="muted">{t("ui.librarySubtitle")}</p>
          </div>
          <Link className="button" href={`/${locale}/scenes/new`}>
            + {t("newScene")}
          </Link>
        </div>
        {query.error && (
          <p role="alert">
            {String(query.error)}{" "}
            <button className="secondary" onClick={() => void query.refetch()}>
              {t("ui.retry")}
            </button>
          </p>
        )}
        <div className="library-filters">
          <div className="filter-buttons">
            {["all", "ready", "processing", "failed"].map((status) => (
              <button
                key={status}
                aria-pressed={filter === status}
                className={filter === status ? "" : "quiet"}
                onClick={() => setFilter(status)}
              >
                {status === "all" ? t("ui.all") : t(`status.${status}`)} ·{" "}
                {status === "all"
                  ? scenes.length
                  : scenes.filter((s) => s.status === status).length}
              </button>
            ))}
          </div>
          <input
            type="search"
            aria-label={t("ui.findScene")}
            placeholder={t("ui.findScene")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {query.isLoading && (
          <p role="status" className="loading-state">
            {t("loading")}
          </p>
        )}
        <div className="scene-grid">
          {filtered.map((scene) => (
            <article className="card scene-card" key={scene.id}>
              <Link
                className={`scene-preview ${scene.status === "ready" ? "cloud-preview" : "capture-preview"}`}
                href={`/${locale}/scenes/${scene.id}`}
                aria-label={t("ui.openScene", { name: scene.name })}
              >
                <img
                  src={
                    scene.status === "ready"
                      ? "/design/room-cloud.svg"
                      : "/design/capture.svg"
                  }
                  alt=""
                />
              </Link>
              <StatusBadge status={scene.status} />
              <h2>
                <Link href={`/${locale}/scenes/${scene.id}`}>{scene.name}</Link>
              </h2>
              <p className="muted">
                {format.dateTime(new Date(scene.created_at), {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </p>
              <Link
                className="button secondary full-width"
                href={`/${locale}/scenes/${scene.id}`}
              >
                {scene.status === "ready"
                  ? t("ui.openSceneShort")
                  : scene.status === "processing"
                    ? t("ui.viewProgress")
                    : t("ui.viewDetails")}
              </Link>
            </article>
          ))}
        </div>
        {!query.isLoading && !query.error && filtered.length === 0 && (
          <section className="empty-state card">
            <h2>
              {scenes.length ? t("ui.noMatchingScenes") : t("ui.emptyTitle")}
            </h2>
            <p className="muted">
              {scenes.length ? t("ui.noMatchingScenesBody") : t("empty")}
            </p>
            {scenes.length ? (
              <button
                className="secondary"
                onClick={() => {
                  setSearch("");
                  setFilter("all");
                }}
              >
                {t("ui.clearFilters")}
              </button>
            ) : (
              <Link className="button" href={`/${locale}/scenes/new`}>
                {t("newScene")}
              </Link>
            )}
          </section>
        )}
      </main>
    </>
  );
}
