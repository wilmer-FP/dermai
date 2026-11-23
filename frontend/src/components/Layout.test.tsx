import { act, screen } from "@testing-library/react";
import * as api from "../services/api";
import { renderAt } from "../test/utils";

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getHealth: vi.fn(),
  listModelVersions: vi.fn(),
}));

const HEALTH = { status: "ok" as const, app: "DermAI", version: "0.1.0", environment: "development" };

beforeEach(() => {
  vi.mocked(api.listModelVersions).mockResolvedValue([]);
});

describe("Layout", () => {
  it("muestra siempre el aviso de uso no diagnóstico y la navegación", async () => {
    vi.mocked(api.getHealth).mockResolvedValue(HEALTH);
    renderAt("/");

    expect(screen.getByRole("note", { name: /aviso de uso no diagnóstico/i })).toHaveTextContent(
      "No es una herramienta de diagnóstico médico.",
    );
    expect(screen.getByRole("link", { name: "Analizar" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Historial" })).toHaveAttribute("href", "/history");
    expect(await screen.findByText("API conectada · v0.1.0")).toBeInTheDocument();
    expect(screen.queryByRole("note", { name: "Demo pública" })).not.toBeInTheDocument();
  });

  it("en la demo pública explica que las imágenes son privadas y temporales", async () => {
    vi.mocked(api.getHealth).mockResolvedValue({ ...HEALTH, demo_mode: true, demo_retention_hours: 6 });
    renderAt("/");

    const notice = await screen.findByRole("note", { name: "Demo pública" });
    expect(notice).toHaveTextContent("Solo tú ves las imágenes que subes");
    expect(notice).toHaveTextContent("a las 6 horas");
  });

  it("reintenta mientras el servidor despierta y se conecta cuando responde", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      vi.mocked(api.getHealth).mockRejectedValueOnce(new api.ApiError(0, "sin conexión")).mockResolvedValue(HEALTH);
      renderAt("/history-desconocida");

      expect(await screen.findByText(/API no disponible · reintentando/)).toBeInTheDocument();
      expect(screen.getByText(/puede estar arrancando/)).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(await screen.findByText("API conectada · v0.1.0")).toBeInTheDocument();
      expect(screen.queryByText(/puede estar arrancando/)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
