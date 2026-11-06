import { screen, within } from "@testing-library/react";
import * as api from "../services/api";
import { makeAnalysis, makePage, renderAt } from "../test/utils";

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getHealth: vi.fn(),
  listAnalyses: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok", app: "DermAI", version: "0.1.0", environment: "testing" });
});

describe("HistoryPage", () => {
  it("lista los análisis con enlace al detalle", async () => {
    const items = [
      makeAnalysis({ id: "aaaaaaaa-0000-4000-8000-000000000001" }),
      makeAnalysis({ id: "bbbbbbbb-0000-4000-8000-000000000002", status: "completed", necrotic_area_ratio: 0.5 }),
    ];
    vi.mocked(api.listAnalyses).mockResolvedValue(makePage(items));
    renderAt("/history");

    const list = await screen.findByRole("list", { name: "Análisis" });
    const links = within(list).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/analyses/aaaaaaaa-0000-4000-8000-000000000001");
    expect(within(links[1]).getByText("Completado")).toBeInTheDocument();
    expect(within(links[1]).getByText("Área: 50.0 %")).toBeInTheDocument();
    expect(api.listAnalyses).toHaveBeenCalledWith({ limit: 10, offset: 0, status: undefined });
  });

  it("muestra un estado vacío con enlace para analizar", async () => {
    vi.mocked(api.listAnalyses).mockResolvedValue(makePage([]));
    renderAt("/history");

    expect(await screen.findByText("Todavía no hay análisis.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Analizar una imagen" })).toHaveAttribute("href", "/");
  });

  it("filtra por estado y lo refleja en la URL", async () => {
    vi.mocked(api.listAnalyses).mockResolvedValue(makePage([]));
    const { user, router } = renderAt("/history");
    await screen.findByText("Todavía no hay análisis.");

    await user.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "failed");

    expect(await screen.findByText("No hay análisis con estado «Fallido».")).toBeInTheDocument();
    expect(api.listAnalyses).toHaveBeenLastCalledWith({ limit: 10, offset: 0, status: "failed" });
    expect(router.state.location.search).toBe("?status=failed");
  });

  it("pagina conservando el filtro", async () => {
    const items = Array.from({ length: 10 }, (_, i) =>
      makeAnalysis({ id: `${String(i).padStart(8, "0")}-0000-4000-8000-000000000000` }),
    );
    vi.mocked(api.listAnalyses).mockImplementation(async ({ offset = 0 } = {}) =>
      makePage(items, { total: 25, offset }),
    );
    const { user, router } = renderAt("/history?status=pending");

    expect(await screen.findByText("Mostrando 1–10 de 25")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Mostrando 11–20 de 25")).toBeInTheDocument();
    expect(api.listAnalyses).toHaveBeenLastCalledWith({ limit: 10, offset: 10, status: "pending" });
    expect(router.state.location.search).toBe("?status=pending&offset=10");

    await user.click(screen.getByRole("button", { name: "Anterior" }));
    expect(await screen.findByText("Mostrando 1–10 de 25")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?status=pending");
  });

  it("muestra el error y permite reintentar", async () => {
    vi.mocked(api.listAnalyses)
      .mockRejectedValueOnce(new api.ApiError(0, "No se pudo conectar con el servidor."))
      .mockResolvedValueOnce(makePage([]));
    const { user } = renderAt("/history");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No se pudo conectar con el servidor.");
    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("Todavía no hay análisis.")).toBeInTheDocument();
  });
});
