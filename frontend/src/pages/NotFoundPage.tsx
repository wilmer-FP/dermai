import { Link } from "react-router";
import { EmptyState } from "../components/Feedback";

export function NotFoundPage() {
  return (
    <EmptyState>
      <title>Página no encontrada · DermAI</title>
      <h1>Página no encontrada</h1>
      <p>La dirección no corresponde a ninguna sección de DermAI.</p>
      <Link to="/" className="button button--primary">
        Volver al inicio
      </Link>
    </EmptyState>
  );
}
