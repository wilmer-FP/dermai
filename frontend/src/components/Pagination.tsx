interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}

export function Pagination({ total, limit, offset, onChange }: PaginationProps) {
  if (total === 0) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  const hasPrevious = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <nav className="pagination" aria-label="Paginación">
      <p>
        Mostrando {from}–{to} de {total}
      </p>
      <div className="pagination__buttons">
        <button
          type="button"
          className="button button--secondary button--small"
          disabled={!hasPrevious}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Anterior
        </button>
        <button
          type="button"
          className="button button--secondary button--small"
          disabled={!hasNext}
          onClick={() => onChange(offset + limit)}
        >
          Siguiente
        </button>
      </div>
    </nav>
  );
}
