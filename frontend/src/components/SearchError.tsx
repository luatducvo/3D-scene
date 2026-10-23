import { useTranslations } from "use-intl";
import { ApiError } from "../lib/api";

/** Search failures stay visible in the viewer without a results dropdown. */
export function SearchError({ error }: { error: unknown }) {
  const t = useTranslations();
  const code = error instanceof ApiError ? error.code : "";
  const key = t.has(`searchErrors.${code}`)
    ? `searchErrors.${code}`
    : "searchErrors.other";
  return (
    <p className="search-error" role="alert">
      {t(key)}
    </p>
  );
}
