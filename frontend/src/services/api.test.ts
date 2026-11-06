import {
  ApiError,
  deleteImage,
  getAnalysis,
  getHealth,
  getImage,
  imageFileUrl,
  listAnalyses,
  listImageAnalyses,
  listImages,
  listModelVersions,
  processedImageUrl,
  requestAnalysis,
  uploadImage,
} from "./api";
import { SESSION_HEADER, getSessionId } from "./session";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockFetch(response: Response | Promise<Response>) {
  const fetchMock = vi.fn().mockReturnValue(Promise.resolve(response));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("cliente de la API", () => {
  it("devuelve el JSON de una respuesta correcta", async () => {
    const fetchMock = mockFetch(jsonResponse({ id: "abc", status: "pending" }));
    await expect(getAnalysis("abc")).resolves.toEqual({ id: "abc", status: "pending" });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/analyses/abc", expect.anything());
  });

  it("usa el mensaje `detail` de la API en los errores", async () => {
    mockFetch(jsonResponse({ detail: "Análisis no encontrado." }, 404));
    const error = await getAnalysis("x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, message: "Análisis no encontrado." });
  });

  it("une los mensajes de validación de FastAPI", async () => {
    mockFetch(jsonResponse({ detail: [{ msg: "Input should be a valid UUID" }, { msg: "otro" }] }, 422));
    await expect(getAnalysis("x")).rejects.toThrow("Input should be a valid UUID · otro");
  });

  it("usa un mensaje genérico si el cuerpo no es JSON", async () => {
    mockFetch(new Response("", { status: 413 }));
    await expect(getAnalysis("x")).rejects.toThrow("El archivo supera el tamaño máximo permitido.");
  });

  it.each([
    [404, "Recurso no encontrado."],
    [415, "Formato de archivo no permitido."],
    [503, "El servicio no está disponible en este momento."],
    [502, "No se pudo conectar con el servidor. Comprueba que el backend está en marcha."],
    [500, "Error interno del servidor (código 500)."],
    [418, "La petición falló (código 418)."],
  ])("usa un mensaje genérico para el código %i sin `detail`", async (status, message) => {
    mockFetch(jsonResponse({ otra: "cosa" }, status));
    await expect(getAnalysis("x")).rejects.toThrow(message);
  });

  it("informa de los fallos de red con status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(getAnalysis("x")).rejects.toMatchObject({ status: 0, message: expect.stringContaining("backend") });
  });

  it("sube la imagen como multipart en el campo `file`", async () => {
    const fetchMock = mockFetch(jsonResponse({ id: "img" }, 201));
    const file = new File(["data"], "lesion.png", { type: "image/png" });
    await uploadImage(file);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/images");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("solicita un análisis con cuerpo JSON", async () => {
    const fetchMock = mockFetch(jsonResponse({ id: "a" }, 201));
    await requestAnalysis("img-1");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/images/img-1/analyses");
    expect(JSON.parse(init.body as string)).toEqual({ model_version_id: null });
  });

  it("construye la consulta del historial omitiendo valores vacíos", async () => {
    const fetchMock = mockFetch(jsonResponse({ items: [], total: 0, limit: 10, offset: 20 }));
    await listAnalyses({ limit: 10, offset: 20, status: "completed" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/analyses?limit=10&offset=20&status=completed");

    fetchMock.mockReturnValue(Promise.resolve(jsonResponse([])));
    await listModelVersions();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/model-versions");
  });

  it("construye el resto de URLs de la API", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})));
    vi.stubGlobal("fetch", fetchMock);
    await getHealth();
    await getImage("img-1");
    await listImages({ limit: 5 });
    await listImageAnalyses("img-1", { offset: 10 });
    await listModelVersions(true);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/health",
      "/api/v1/images/img-1",
      "/api/v1/images?limit=5",
      "/api/v1/images/img-1/analyses?offset=10",
      "/api/v1/model-versions?active_only=true",
    ]);
  });

  it("acepta respuestas 204 sin cuerpo", async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(deleteImage("img-1")).resolves.toBeUndefined();
  });

  it("codifica los identificadores y añade la sesión a las URL de archivos", () => {
    const session = encodeURIComponent(getSessionId());
    expect(imageFileUrl("a/b")).toBe(`/api/v1/images/a%2Fb/file?session=${session}`);
    expect(processedImageUrl("a/b")).toBe(`/api/v1/analyses/a%2Fb/processed-image?session=${session}`);
  });

  it("envía la sesión anónima en cada petición", async () => {
    const fetchMock = mockFetch(jsonResponse({ id: "abc" }));
    await getAnalysis("abc");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)[SESSION_HEADER]).toBe(getSessionId());
  });
});
