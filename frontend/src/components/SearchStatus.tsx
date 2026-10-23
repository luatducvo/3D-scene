import { useTranslations } from "use-intl";
import { ApiError } from "../lib/api";

/** The result line of a viewer search: searching, a hit count, or the error in the user's language. */
export function SearchStatus({
  fetching,
  error,
  count,
  onClear,
}: {
  fetching: boolean;
  error: unknown;
  count: number;
  onClear: () => void;
}) {
  const t = useTranslations();
  // Messages are chosen by API error code; the API's English message is never shown.
  const code = error instanceof ApiError ? error.code : "";
  const key = t.has(`searchErrors.${code}`)
    ? `searchErrors.${code}`
    : "searchErrors.other";
  return (
    <div className="search-status card" role="status">
      {fetching ? (
        <p>{t("ui.searching")}</p>
      ) : error ? (
        <p role="alert">{t(key)}</p>
      ) : (
        <p>{count ? t("ui.searchCount", { count }) : t("heatmap.empty")}</p>
      )}
      <button className="secondary full-width" onClick={onClear}>
        {t("ui.clearSearch")}
      </button>
    </div>
  );
}
