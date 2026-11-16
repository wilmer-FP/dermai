import { NavLink, Outlet } from "react-router";
import { useApiHealth } from "../hooks/useApiHealth";
import { ApiStatus } from "./ApiStatus";
import { Disclaimer } from "./Disclaimer";

function formatHours(hours: number): string {
  return Number.isInteger(hours) ? String(hours) : hours.toFixed(1);
}

export function Layout() {
  const apiHealth = useApiHealth();
  const demo = apiHealth.health?.demo_mode === true;
  const retention = apiHealth.health?.demo_retention_hours;
  const browserMode = apiHealth.health?.analysis_mode === "browser";

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <header className="header">
        <div className="container header__inner">
          <NavLink to="/" className="brand">
            <span className="brand__mark" aria-hidden="true" />
            DermAI
          </NavLink>
          <nav aria-label="Principal">
            <ul className="nav">
              <li>
                <NavLink to="/" end className="nav__link">
                  Analizar
                </NavLink>
              </li>
              <li>
                <NavLink to="/history" className="nav__link">
                  Historial
                </NavLink>
              </li>
              <li>
                <NavLink to="/about" className="nav__link">
                  Acerca de
                </NavLink>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      <div className="container">
        <Disclaimer />
        {demo && (
          <aside className="notice" role="note" aria-label="Demo pública">
            <strong>Demo pública.</strong> Solo tú ves las imágenes que subes, y se borran automáticamente
            {retention ? ` a las ${formatHours(retention)} horas` : ""}. No subas fotos que identifiquen a nadie.
          </aside>
        )}
        {browserMode && (
          <aside className="notice" role="note" aria-label="Análisis en el navegador">
            <strong>Análisis en tu navegador.</strong> Las fotos no se envían a ningún servidor: se analizan y se
            guardan solo en este navegador. Puedes elegir la heurística o el modelo entrenado real
            (descarga de 55 MiB más los motores de procesamiento). No hay sustitución automática entre métodos.
          </aside>
        )}
        {apiHealth.status === "waking" && (
          <p className="notice notice--waiting" role="status">
            <span className="spinner" aria-hidden="true" />
            No se puede conectar con el servidor. Si es la demo gratuita, puede estar arrancando (1–2 minutos); se
            reintenta automáticamente.
          </p>
        )}
      </div>

      <main id="main" className="container main">
        <Outlet />
      </main>

      <footer className="footer">
        <div className="container footer__inner">
          <p>DermAI · Prototipo de investigación educativa. No sustituye la evaluación de un profesional sanitario.</p>
          <ApiStatus state={apiHealth} />
        </div>
      </footer>
    </div>
  );
}
