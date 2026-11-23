import { getSessionId, resetSessionCache } from "./session";

beforeEach(() => {
  localStorage.clear();
  resetSessionCache();
});

describe("sesión anónima", () => {
  it("crea un identificador válido y lo reutiliza", () => {
    const first = getSessionId();
    expect(first).toMatch(/^[A-Za-z0-9-]{16,64}$/);
    expect(getSessionId()).toBe(first);
    expect(localStorage.getItem("dermai.session")).toBe(first);
  });

  it("recupera la sesión guardada en otra visita", () => {
    localStorage.setItem("dermai.session", "abcdef12-3456-4789-8abc-def012345678");
    expect(getSessionId()).toBe("abcdef12-3456-4789-8abc-def012345678");
  });

  it("sustituye un valor guardado no válido", () => {
    localStorage.setItem("dermai.session", "<script>");
    expect(getSessionId()).not.toBe("<script>");
  });

  it("funciona aunque el almacenamiento esté bloqueado", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    const session = getSessionId();
    expect(session).toMatch(/^[A-Za-z0-9-]{16,64}$/);
    expect(getSessionId()).toBe(session);
  });
});
