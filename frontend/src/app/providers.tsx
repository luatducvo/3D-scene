"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient());
  const [ready, setReady] = useState(
    process.env.NEXT_PUBLIC_API_MODE !== "mock",
  );
  const [error, setError] = useState("");
  const t = useTranslations();
  useEffect(() => {
    if (!ready)
      import("../lib/api/mock")
        .then((m) => m.startMockWorker())
        .then(() => setReady(true))
        .catch((e) => setError(String(e)));
  }, [ready]);
  return (
    <QueryClientProvider client={client}>
      {error ? (
        <p role="alert">
          {t("error")}: {error}
        </p>
      ) : ready ? (
        children
      ) : (
        <p>{t("loading")}</p>
      )}
    </QueryClientProvider>
  );
}
