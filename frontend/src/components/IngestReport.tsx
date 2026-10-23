import { useTranslations } from "use-intl";

export function IngestReport({ report }: { report: Record<string, unknown> }) {
  const t = useTranslations();
  const rejected = report.rejected;
  return (
    <div className="ingest-report">
      <dl className="report-counts">
        {typeof report.num_inputs === "number" && (
          <div>
            <dt>{t("ui.inputCount")}</dt>
            <dd>{report.num_inputs}</dd>
          </div>
        )}
        {typeof report.num_keyframes === "number" && (
          <div>
            <dt>{t("ui.keptCount")}</dt>
            <dd>{report.num_keyframes}</dd>
          </div>
        )}
      </dl>
      {rejected !== null &&
        typeof rejected === "object" &&
        Object.entries(rejected).map(([reason, files]) => {
          if (!Array.isArray(files) || !files.length) return null;
          const label = ["blur", "exposure", "duplicate", "invalid"].includes(
            reason,
          )
            ? t(`ui.rejection.${reason}`)
            : reason;
          return (
            <div className="rejection-group" key={reason}>
              <h3>
                {label} · {files.length}
              </h3>
              <ul>
                {files
                  .filter((file): file is string => typeof file === "string")
                  .map((file, i) => (
                    <li key={`${file}-${i}`}>{file}</li>
                  ))}
              </ul>
            </div>
          );
        })}
    </div>
  );
}
