import { screen } from "@testing-library/react";
import * as api from "../services/api";
import { makeAnalysis, makeFile, makeImage, makeModelVersion, renderAt } from "../test/utils";

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getHealth: vi.fn(),
  uploadImage: vi.fn(),
  requestAnalysis: vi.fn(),
  getAnalysis: vi.fn(),
  getImage: vi.fn(),
  listModelVersions: vi.fn(),
}));

const fileInput = () => screen.getByLabelText(/selecciona una imagen/i);
const consentBox = () => screen.getByRole("checkbox", { name: /confirmo que la imagen/i });
const submitButton = () => screen.getByRole("button", { name: /subir y solicitar análisis/i });

beforeEach(() => {
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok", app: "DermAI", version: "0.1.0", environment: "testing" });
  vi.mocked(api.listModelVersions).mockResolvedValue([]);
});

describe("UploadPage", () => {
  it("sin modelos activos no muestra el selector de método", async () => {
    renderAt("/");
    await screen.findByRole("heading", { name: "Analizar una imagen" });
    expect(api.listModelVersions).toHaveBeenCalledWith(true);
    expect(screen.queryByRole("group", { name: "Método de análisis" })).not.toBeInTheDocument();
  });

  it("permite elegir un modelo activo y lo envía en la solicitud", async () => {
    const model = makeModelVersion();
    const image = makeImage();
    vi.mocked(api.listModelVersions).mockResolvedValue([model]);
    vi.mocked(api.uploadImage).mockResolvedValue(image);
    vi.mocked(api.requestAnalysis).mockResolvedValue(makeAnalysis());
    vi.mocked(api.getAnalysis).mockResolvedValue(makeAnalysis());
    vi.mocked(api.getImage).mockResolvedValue(image);

    const { user } = renderAt("/");
    const picker = await screen.findByRole("group", { name: "Método de análisis" });
    expect(screen.getByRole("radio", { name: /heurística de opencv/i })).toBeChecked();
    expect(picker).toHaveTextContent("entrenado con 13 imágenes · Dice medio 0.35");

    await user.click(screen.getByRole("radio", { name: /modelo experimental unet-resnet18-woundtissue/i }));
    await user.upload(fileInput(), makeFile("lesion.png"));
    await user.click(consentBox());
    await user.click(submitButton());

    expect(await screen.findByRole("heading", { name: "Resultado del análisis" })).toBeInTheDocument();
    expect(api.requestAnalysis).toHaveBeenCalledWith(image.id, model.id);
  });

  it("solo permite enviar con una imagen válida y la confirmación marcada", async () => {
    const { user } = renderAt("/");
    expect(submitButton()).toBeDisabled();

    await user.upload(fileInput(), makeFile("lesion.png"));
    expect(screen.getByRole("img", { name: /vista previa/i })).toBeInTheDocument();
    expect(submitButton()).toBeDisabled();

    await user.click(consentBox());
    expect(submitButton()).toBeEnabled();
  });

  it("rechaza en el cliente un formato no permitido", async () => {
    const { user } = renderAt("/", { applyAccept: false });
    await user.upload(fileInput(), makeFile("animacion.gif", "image/gif"));

    expect(screen.getByRole("alert")).toHaveTextContent("Formato no permitido");
    expect(screen.queryByRole("img", { name: /vista previa/i })).not.toBeInTheDocument();
    expect(api.uploadImage).not.toHaveBeenCalled();
  });

  it("sube la imagen, solicita el análisis y abre el resultado", async () => {
    const image = makeImage();
    const analysis = makeAnalysis({ image_id: image.id });
    vi.mocked(api.uploadImage).mockResolvedValue(image);
    vi.mocked(api.requestAnalysis).mockResolvedValue(analysis);
    vi.mocked(api.getAnalysis).mockResolvedValue(analysis);
    vi.mocked(api.getImage).mockResolvedValue(image);

    const { user, router } = renderAt("/");
    await user.upload(fileInput(), makeFile("lesion.png"));
    await user.click(consentBox());
    await user.click(submitButton());

    expect(await screen.findByRole("heading", { name: "Resultado del análisis" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(`/analyses/${analysis.id}`);
    expect(api.uploadImage).toHaveBeenCalledWith(expect.objectContaining({ name: "lesion.png" }));
    expect(api.requestAnalysis).toHaveBeenCalledWith(image.id, null);
  });

  it("muestra el error del servidor y no vuelve a subir la imagen al reintentar", async () => {
    const image = makeImage();
    vi.mocked(api.uploadImage).mockResolvedValue(image);
    vi.mocked(api.requestAnalysis)
      .mockRejectedValueOnce(new api.ApiError(503, "La base de datos no está configurada."))
      .mockResolvedValueOnce(makeAnalysis());
    vi.mocked(api.getAnalysis).mockResolvedValue(makeAnalysis());
    vi.mocked(api.getImage).mockResolvedValue(image);

    const { user } = renderAt("/");
    await user.upload(fileInput(), makeFile("lesion.png"));
    await user.click(consentBox());
    await user.click(submitButton());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("La imagen se subió, pero no se pudo registrar el análisis");
    expect(alert).toHaveTextContent("La base de datos no está configurada.");

    await user.click(submitButton());
    expect(await screen.findByRole("heading", { name: "Resultado del análisis" })).toBeInTheDocument();
    expect(api.uploadImage).toHaveBeenCalledTimes(1);
    expect(api.requestAnalysis).toHaveBeenCalledTimes(2);
  });

  it("muestra el rechazo del backend al subir", async () => {
    vi.mocked(api.uploadImage).mockRejectedValue(new api.ApiError(422, "El archivo no es una imagen válida."));

    const { user } = renderAt("/");
    await user.upload(fileInput(), makeFile("falsa.png"));
    await user.click(consentBox());
    await user.click(submitButton());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No se pudo subir la imagen");
    expect(alert).toHaveTextContent("El archivo no es una imagen válida.");
    expect(api.requestAnalysis).not.toHaveBeenCalled();
  });
});
