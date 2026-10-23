import type { ReactNode } from "react";
import { useEffect } from "react";
import { useLocale, useTranslations } from "use-intl";
import { Link } from "react-router-dom";

export function Header({
  sceneName,
  actions,
}: {
  sceneName?: string;
  actions?: ReactNode;
}) {
  const t = useTranslations(),
    locale = useLocale();
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  return (
    <header className="app-header">
      <Link className="brand" to={`/${locale}`} aria-label={t("scenes")}>
        <span className="brand-copy">
          <strong>{t("ui.brand")}</strong>
          <small>{t("ui.tagline")}</small>
        </span>
      </Link>
      <nav className="breadcrumb" aria-label={t("ui.navigation")}>
        {sceneName ? (
          <>
            <Link to={`/${locale}`}>{t("scenes")}</Link>
            <span aria-hidden="true">/</span>
            <span className="scene-name">{sceneName}</span>
          </>
        ) : (
          <span>{t("ui.yourSpaces")}</span>
        )}
      </nav>
      <div className="header-actions">
        {actions || (
          <Link className="button secondary" to={`/${locale}/scenes/new`}>
            + {t("newScene")}
          </Link>
        )}
      </div>
    </header>
  );
}
