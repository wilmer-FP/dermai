import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { makeFile } from "../test/utils";
import { ApiError } from "./errors";
import * as local from "./localBackend";
import { resetDatabaseConnection } from "./localStore";

const fakeOutput = {
  necroticAreaRatio: 0.25,
  result: {
    method: { name: "dermai-opencv-heuristic", version: "0.1.0" },
    tissue_composition: { necrotic: 0.25, slough: 0.25, granulation: 0.5, other: 0 },
  },
  overlay: { data: new Uint8Array(12), width: 2, height: 2 },
};

beforeEach(async () => {
  await resetDatabaseConnection();
  globalThis.indexedDB = new IDBFactory();
  vi.spyOn(local.browserRuntime, "decode").mockResolvedValue({ data: new Uint8Array(64 * 48 * 3), width: 64, height: 48 });
  vi.spyOn(local.browserRuntime, "analyze").mockResolvedValue(fakeOutput);
  vi.spyOn(local.browserRuntime, "renderProcessed").mockResolvedValue(new Blob(["png"], { type: "image/png" }));
});

describe("modo navegador (IndexedDB)", () => {
  it("indica que el análisis es local", async () => {
    expect(await local.getHealth()).toMatchObject({ status: "ok", analysis_mode: "browser", demo_mode: false });
  });

  it("guarda la imagen con sus datos y la devuelve sin el archivo", async () => {
    const image = await local.uploadImage(makeFile("C:\\fotos\\lesion.png", "image/png", 2048));

    expect(image).toMatchObject({
      original_filename: "lesion.png",
      content_type: "image/png",
      file_size_bytes: 2048,
      width: 64,
      height: 48,
    });
    expect(image.checksum_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(image).not.toHaveProperty("blob");
    expect(await local.getImage(image.id)).toEqual(image);
    // fake-indexeddb no sabe clonar los Blob de jsdom (los navegadores sí): basta con que exista.
    expect(await local.loadImageBlob("original", image.id)).not.toBeNull();
  });

  it("rechaza archivos no válidos antes de guardarlos", async () => {
    await expect(local.uploadImage(makeFile("animacion.gif", "image/gif"))).rejects.toThrow(/Formato no permitido/);
    expect((await local.listImages()).total).toBe(0);
  });

  it("analiza la imagen y guarda el resultado y la imagen procesada", async () => {
    const image = await local.uploadImage(makeFile());
    const analysis = await local.requestAnalysis(image.id);

    expect(analysis).toMatchObject({
      image_id: image.id,
      status: "completed",
      necrotic_area_ratio: 0.25,
      confidence: null,
      has_processed_image: true,
    });
    expect(analysis.disclaimer).toMatch(/No es una herramienta de diagnóstico médico/);
    expect(analysis.completed_at).not.toBeNull();
    expect(await local.getAnalysis(analysis.id)).toEqual(analysis);
    expect(await local.loadImageBlob("processed", analysis.id)).not.toBeNull();
  });

  it("marca el análisis como fallido si el procesamiento falla", async () => {
    vi.mocked(local.browserRuntime.analyze).mockRejectedValueOnce(new Error("imagen ilegible"));
    const image = await local.uploadImage(makeFile());
    const analysis = await local.requestAnalysis(image.id);

    expect(analysis.status).toBe("failed");
    expect(analysis.error_message).toBe("No se pudo procesar la imagen. imagen ilegible");
    expect(analysis.has_processed_image).toBe(false);
  });

  it("no ofrece el modelo experimental en el navegador", async () => {
    const image = await local.uploadImage(makeFile());
    const analysis = await local.requestAnalysis(image.id, "modelo-1");
    expect(analysis.status).toBe("failed");
    expect(analysis.error_message).toMatch(/modelo experimental no está disponible/);
    expect(local.browserRuntime.analyze).not.toHaveBeenCalled();
  });

  it("lista el historial del más reciente al más antiguo, con filtro y paginación", async () => {
    const image = await local.uploadImage(makeFile());
    const first = await local.requestAnalysis(image.id);
    await new Promise((r) => setTimeout(r, 5));
    vi.mocked(local.browserRuntime.analyze).mockRejectedValueOnce(new Error("x"));
    const second = await local.requestAnalysis(image.id);

    const all = await local.listAnalyses();
    expect(all.items.map((a) => a.id)).toEqual([second.id, first.id]);
    expect((await local.listAnalyses({ status: "completed" })).items.map((a) => a.id)).toEqual([first.id]);
    expect(await local.listAnalyses({ limit: 1, offset: 1 })).toMatchObject({ total: 2, limit: 1, offset: 1 });
    expect((await local.listImageAnalyses(image.id)).total).toBe(2);
  });

  it("responde 404 con los recursos que no existen", async () => {
    await expect(local.getImage("no-existe")).rejects.toMatchObject({ status: 404, message: "Imagen no encontrada." });
    await expect(local.getAnalysis("no-existe")).rejects.toBeInstanceOf(ApiError);
    await expect(local.requestAnalysis("no-existe")).rejects.toMatchObject({ status: 404 });
  });

  it("borra la imagen con todos sus análisis y archivos", async () => {
    const image = await local.uploadImage(makeFile());
    const analysis = await local.requestAnalysis(image.id);

    await local.deleteImage(image.id);

    await expect(local.getImage(image.id)).rejects.toMatchObject({ status: 404 });
    await expect(local.getAnalysis(analysis.id)).rejects.toMatchObject({ status: 404 });
    expect(await local.loadImageBlob("processed", analysis.id)).toBeNull();
    expect((await local.listAnalyses()).total).toBe(0);
  });
});
