import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslations } from "use-intl";
import { Header } from "./components/Header";
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient());
  const [ready, setReady] = useState(import.meta.env.VITE_API_MODE !== "mock");
  const [error, setError] = useState("");
  const t = useTranslations();
  useEffect(() => {
    if (!ready)
      import("./lib/api/mock")
        .then((m) => m.startMockWorker())
        .then(() => setReady(true))
        .catch((e) => setError(String(e)));
  }, [ready]);
  return (
    <QueryClientProvider client={client}>
      {error ? (
        <>
          <Header />
          <main id="main-content" className="page route-state">
            <p role="alert">
              {t("error")}: {error}
            </p>
          </main>
        </>
      ) : ready ? (
        children
      ) : (
        <>
          <Header />
          <main id="main-content" className="page loading-state" role="status">
            {t("loading")}
          </main>
        </>
      )}
    </QueryClientProvider>
  );
}
