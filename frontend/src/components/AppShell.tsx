import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useLocale, useTranslations } from "use-intl";

/** Fixed application chrome; each route owns the scrolling inside its content slot. */
export function AppShell({ children }: { children: ReactNode }) {
  const t = useTranslations();
  const locale = useLocale();
  const { pathname } = useLocation();
  const scenePath =
    pathname.startsWith(`/${locale}/scenes/`) &&
    pathname !== `/${locale}/scenes/new`;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("ui.skipToContent")}
      </a>
      <div className="app-route">{children}</div>
      <nav className="app-navigation" aria-label={t("ui.navigation")}>
        <NavLink to={`/${locale}`} end>
          {t("scenes")}
        </NavLink>
        <NavLink to={`/${locale}/scenes/new`}>{t("ui.captureNav")}</NavLink>
        {scenePath ? (
          <NavLink to={pathname}>{t("ui.exploreNav")}</NavLink>
        ) : (
          <span aria-disabled="true">{t("ui.exploreNav")}</span>
        )}
        <span className="navigation-caption">{t("ui.navigationCaption")}</span>
      </nav>
    </div>
  );
}
