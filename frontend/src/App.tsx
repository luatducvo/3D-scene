import { lazy, Suspense } from "react";
import { IntlProvider, useTranslations } from "use-intl";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import messages from "../messages/en.json";
import { Providers } from "./Providers";
import { AppShell } from "./components/AppShell";
import { Header } from "./components/Header";

const SceneList = lazy(() => import("./pages/SceneList"));
const NewScene = lazy(() => import("./pages/NewScene"));
const ScenePage = lazy(() => import("./pages/ScenePage"));

function Screens() {
  const t = useTranslations();
  return (
    <Suspense
      fallback={
        <>
          <Header />
          <main id="main-content" className="page loading-state" role="status">
            {t("loading")}
          </main>
        </>
      }
    >
      <Routes>
        <Route path="/" element={<Navigate to="/en" replace />} />
        <Route path="/en" element={<SceneList />} />
        <Route path="/en/scenes/new" element={<NewScene />} />
        <Route path="/en/scenes/:sceneId" element={<ScenePage />} />
        <Route
          path="*"
          element={
            <>
              <Header />
              <main id="main-content" className="page route-state">
                <h1>{t("ui.notFound")}</h1>
                <Link className="button" to="/en">
                  {t("ui.backLibrary")}
                </Link>
              </main>
            </>
          }
        />
      </Routes>
    </Suspense>
  );
}

export function App() {
  return (
    <IntlProvider
      locale="en"
      messages={messages}
      timeZone={Intl.DateTimeFormat().resolvedOptions().timeZone}
    >
      <AppShell>
        <Providers>
          <Screens />
        </Providers>
      </AppShell>
    </IntlProvider>
  );
}
