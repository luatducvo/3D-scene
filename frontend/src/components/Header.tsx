"use client";
import { useLocale, useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import Link from "next/link";
export function Header() {
  const t = useTranslations(),
    locale = useLocale(),
    path = usePathname();
  return (
    <header>
      <Link className="brand" href={`/${locale}`}>
        ◈ {t("title")}
      </Link>
      <nav>
        <Link href={`/${locale}`}>{t("scenes")}</Link>
        <Link
          href={path.replace(`/${locale}`, locale === "en" ? "/vi" : "/en")}
        >
          {locale === "en" ? "VI" : "EN"}
        </Link>
      </nav>
    </header>
  );
}
