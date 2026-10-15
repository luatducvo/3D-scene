"use client";
import type { ReactNode } from "react";
import { useEffect } from "react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { DesignIcon } from "./DesignIcon";

export function Header({
  sceneName,
  actions,
}: {
  sceneName?: string;
  actions?: ReactNode;
}) {
  const t = useTranslations(),
    locale = useLocale(),
    path = usePathname();
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  return (
    <header className="app-header">
      <Link className="brand" href={`/${locale}`} aria-label={t("scenes")}>
        <DesignIcon name="brand" />
        <span>scene</span>
      </Link>
      <nav className="breadcrumb" aria-label={t("ui.navigation")}>
        {sceneName ? (
          <>
            <Link href={`/${locale}`}>{t("scenes")}</Link>
            <span aria-hidden="true">/</span>
            <span className="scene-name">{sceneName}</span>
          </>
        ) : (
          <span>{t("ui.yourSpaces")}</span>
        )}
      </nav>
      <div className="header-actions">
        {actions}
        <Link
          className="button secondary language-switch"
          href={path.replace(`/${locale}`, locale === "en" ? "/vi" : "/en")}
          aria-label={t("ui.switchLanguage")}
        >
          <span className={locale === "vi" ? "active-language" : ""}>VI</span>
          <span aria-hidden="true">/</span>
          <span className={locale === "en" ? "active-language" : ""}>EN</span>
        </Link>
      </div>
    </header>
  );
}
