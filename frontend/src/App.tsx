import type { RouteObject } from "react-router";
import { Layout } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { HistoryPage } from "./pages/HistoryPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { UploadPage } from "./pages/UploadPage";

/** Rutas de la aplicación; las pruebas las reutilizan con un router en memoria. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <UploadPage /> },
      { path: "history", element: <HistoryPage /> },
      { path: "about", element: <AboutPage /> },
      { path: "analyses/:analysisId", element: <AnalysisPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
