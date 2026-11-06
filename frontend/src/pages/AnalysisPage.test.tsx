import { screen, within } from "@testing-library/react";
import * as api from "../services/api";
import { makeAnalysis, makeHeuristicResult, makeImage, makeModelVersion, makePage, renderAt } from "../test/utils";

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getHealth: vi.fn(),
  getAnalysis: vi.fn(),
  getImage: vi.fn(),
  deleteImage: vi.fn(),
  listAnalyses: vi.fn(),
  requestAnalysis: vi.fn(),
  listModelVersions: vi.fn(),
}));

const image = makeImage();
const analysis = makeAnalysis({ image_id: image.id });
const completed = makeAnalysis({
  image_id: image.id,
  status: "completed",
  necrotic_area_ratio: 0.237,
  confidence: null,
  result: makeHeuristicResult({ warnings: ["La imagen parece desenfocada."] }),
  completed_at: "2026-11-05T10:05:00Z",
  has_processed_image: true,
});

beforeEach(() => {
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok", app: "DermAI", version: "0.1.0", environment: "testing" });
  vi.mocked(api.getImage).mockResolvedValue(image);
  vi.mocked(api.listModelVersions).mockResolvedValue([]);
});

describe("AnalysisPage", () => {
  it("muestra un análisis sin procesar con la imagen original y el aviso de la API", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(analysis);
    renderAt(`/analyses/${analysis.id}`);

    expect(await screen.findByRole("heading", { name: "Resultado del análisis" })).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByText("Análisis sin procesar")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /lesion\.jpg/ })).toHaveAttribute("src", api.imageFileUrl(image.id));
    expect(screen.queryByRole("group", { name: "Vista de la imagen" })).not.toBeInTheDocument();
    expect(screen.getByText("640 × 480 px")).toBeInTheDocument();
    // Aviso global del layout + aviso devuelto por la API junto al resultado.
    expect(screen.getAllByRole("note", { name: /aviso de uso no diagnóstico/i })).toHaveLength(2);
  });

  it("muestra el resultado del pipeline heurístico", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(completed);
    renderAt(`/analyses/${completed.id}`);

    expect(await screen.findByText("Completado")).toBeInTheDocument();
    expect(screen.getByText("No aplica (método heurístico)")).toBeInTheDocument();
    expect(screen.getByText("dermai-opencv-heuristic v0.1.0")).toBeInTheDocument();
    expect(screen.getByText("La imagen parece desenfocada.")).toBeInTheDocument();
    expect(screen.queryByText("Análisis sin procesar")).not.toBeInTheDocument();

    const composition = screen.getByRole("list", { name: "Composición por color" });
    expect(within(composition).getByText("Negro / marrón oscuro")).toBeInTheDocument();
    expect(within(composition).getByText("23.7 %")).toBeInTheDocument();
    expect(within(composition).getByText("50.0 %")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "Características extraídas" })).toBeInTheDocument();
    expect(screen.getByText("0.82")).toBeInTheDocument(); // circularidad
  });

  it("alterna entre la imagen procesada y la original", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(completed);
    const { user } = renderAt(`/analyses/${completed.id}`);

    const processed = await screen.findByRole("img", { name: /imagen procesada/i });
    expect(processed).toHaveAttribute("src", api.processedImageUrl(completed.id));
    expect(screen.getByRole("list", { name: "Leyenda de la imagen procesada" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Original" }));
    expect(screen.getByRole("img", { name: /imagen analizada/i })).toHaveAttribute("src", api.imageFileUrl(image.id));
    expect(screen.getByRole("button", { name: "Original" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("list", { name: "Leyenda de la imagen procesada" })).not.toBeInTheDocument();
  });

  it("muestra el resultado de un modelo con su confianza, leyenda y métricas", async () => {
    const model = makeModelVersion();
    vi.mocked(api.listModelVersions).mockResolvedValue([model]);
    vi.mocked(api.getAnalysis).mockResolvedValue(
      makeAnalysis({
        status: "completed",
        model_version_id: model.id,
        necrotic_area_ratio: 0.2,
        confidence: 0.734,
        has_processed_image: true,
        result: makeHeuristicResult({
          method: { name: model.name, version: model.version, type: "model", description: "U-Net de prueba." },
          confidence_definition: "Media de la probabilidad de la clase predicha.",
          legend: [
            { label: "Herida detectada", color: "#50dc50", kind: "outline" },
            { label: "Necrosis", color: "#ff00ff", kind: "fill" },
          ],
        }),
      }),
    );
    renderAt(`/analyses/${analysis.id}`);

    expect(await screen.findByText("73.4 % (no calibrada)")).toBeInTheDocument();
    expect(screen.getByText("Proporción de la herida que el modelo clasifica como necrosis")).toBeInTheDocument();
    expect(screen.getByText(/Media de la probabilidad de la clase predicha/, { selector: "p" })).toBeInTheDocument();
    const legend = screen.getByRole("list", { name: "Leyenda de la imagen procesada" });
    expect(within(legend).getByText("Herida detectada")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Composición por color" })).getByText("Necrosis")).toBeInTheDocument();

    const modelCard = await screen.findByRole("region", { name: "Sobre el modelo" });
    expect(within(modelCard).getByText("Prueba de concepto")).toBeInTheDocument();
    expect(within(modelCard).getByText(/Datos de entrenamiento: WoundTissue/)).toBeInTheDocument();
    expect(within(modelCard).getByRole("link", { name: "Créditos y licencias" })).toHaveAttribute(
      "href",
      "/about#creditos",
    );
    expect(within(modelCard).getByRole("row", { name: /media por partición 0.35 ± 0.10 —/ })).toBeInTheDocument();
    expect(within(modelCard).getByRole("row", { name: /agregado 0.41 0.22/ })).toBeInTheDocument();
  });

  it("muestra la confianza cuando el análisis la incluye", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(
      makeAnalysis({ status: "completed", confidence: 0.81, result: { regions: 2 } }),
    );
    renderAt(`/analyses/${analysis.id}`);

    expect(await screen.findByText("81.0 % (no calibrada)")).toBeInTheDocument();
    expect(screen.getByText(/Datos completos del resultado/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Características extraídas" })).not.toBeInTheDocument();
  });

  it("muestra el mensaje de error de un análisis fallido", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(makeAnalysis({ status: "failed", error_message: "Imagen ilegible." }));
    renderAt(`/analyses/${analysis.id}`);

    expect(await screen.findByText("El análisis falló")).toBeInTheDocument();
    expect(screen.getByText("Imagen ilegible.")).toBeInTheDocument();
  });

  it("indica cuando el análisis no existe", async () => {
    vi.mocked(api.getAnalysis).mockRejectedValue(new api.ApiError(404, "Análisis no encontrado."));
    renderAt("/analyses/no-existe");

    expect(await screen.findByRole("heading", { name: "Análisis no encontrado" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al historial" })).toBeInTheDocument();
  });

  it("solicita un nuevo análisis de la misma imagen y lo abre", async () => {
    const next = { ...completed, id: "33333333-3333-4333-8333-333333333333" };
    vi.mocked(api.getAnalysis).mockImplementation(async (id) => (id === next.id ? next : analysis));
    vi.mocked(api.requestAnalysis).mockResolvedValue(next);

    const { user, router } = renderAt(`/analyses/${analysis.id}`);
    await user.click(await screen.findByRole("button", { name: "Analizar de nuevo" }));

    expect(api.requestAnalysis).toHaveBeenCalledWith(image.id, null);
    expect(await screen.findByText("Completado")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(`/analyses/${next.id}`);
  });

  it("elimina la imagen tras confirmar y vuelve al historial", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(analysis);
    vi.mocked(api.deleteImage).mockResolvedValue(undefined);
    vi.mocked(api.listAnalyses).mockResolvedValue(makePage([]));
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    const { user, router } = renderAt(`/analyses/${analysis.id}`);
    await user.click(await screen.findByRole("button", { name: "Eliminar imagen" }));

    expect(confirmSpy).toHaveBeenCalled();
    expect(api.deleteImage).toHaveBeenCalledWith(image.id);
    expect(await screen.findByRole("heading", { name: "Historial de análisis" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/history");
  });

  it("muestra el error si falla la eliminación y permite seguir en la página", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(analysis);
    vi.mocked(api.deleteImage).mockRejectedValue(new api.ApiError(500, "Error interno del servidor (código 500)."));
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const { user, router } = renderAt(`/analyses/${analysis.id}`);
    await user.click(await screen.findByRole("button", { name: "Eliminar imagen" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No se pudo eliminar la imagen");
    expect(router.state.location.pathname).toBe(`/analyses/${analysis.id}`);
    expect(screen.getByRole("button", { name: "Eliminar imagen" })).toBeEnabled();
  });

  it("muestra el error si no se puede solicitar un nuevo análisis", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(analysis);
    vi.mocked(api.requestAnalysis).mockRejectedValue(new api.ApiError(0, "No se pudo conectar con el servidor."));

    const { user } = renderAt(`/analyses/${analysis.id}`);
    await user.click(await screen.findByRole("button", { name: "Analizar de nuevo" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo solicitar un nuevo análisis");
  });

  it("muestra un error con reintento si la API falla al cargar", async () => {
    vi.mocked(api.getAnalysis)
      .mockRejectedValueOnce(new api.ApiError(503, "La base de datos no está configurada."))
      .mockResolvedValueOnce(analysis);

    const { user } = renderAt(`/analyses/${analysis.id}`);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("La base de datos no está configurada.");

    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("heading", { name: "Resultado del análisis" })).toBeInTheDocument();
  });

  it("no elimina nada si se cancela la confirmación", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(analysis);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    const { user } = renderAt(`/analyses/${analysis.id}`);
    await user.click(await screen.findByRole("button", { name: "Eliminar imagen" }));

    expect(api.deleteImage).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Resultado del análisis" })).toBeInTheDocument();
  });
});
