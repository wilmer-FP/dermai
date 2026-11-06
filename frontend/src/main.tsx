import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { routes } from "./App";
import "./styles.css";

// En GitHub Pages la aplicación vive en /dermai/ (VITE_BASE_PATH al compilar).
const basename = import.meta.env.BASE_URL.replace(/\/+$/, "") || "/";
const router = createBrowserRouter(routes, { basename });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
