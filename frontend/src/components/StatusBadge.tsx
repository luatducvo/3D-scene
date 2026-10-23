import { useTranslations } from "use-intl";

export function StatusBadge({ status }: { status: string }) {
  const t = useTranslations();
  return (
    <span className="badge" data-status={status}>
      {t(`status.${status}`)}
    </span>
  );
}
