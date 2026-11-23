import { makeFile } from "../test/utils";
import { validateImageFile } from "./imageValidation";

describe("validateImageFile", () => {
  it("acepta JPG y PNG", () => {
    expect(validateImageFile(makeFile("a.png", "image/png"))).toBeNull();
    expect(validateImageFile(makeFile("a.JPG", "image/jpeg"))).toBeNull();
    expect(validateImageFile(makeFile("a.jpeg", "image/jpeg"))).toBeNull();
  });

  it("acepta archivos sin tipo MIME si la extensión es válida", () => {
    expect(validateImageFile(makeFile("a.png", ""))).toBeNull();
  });

  it("rechaza archivos vacíos", () => {
    expect(validateImageFile(makeFile("a.png", "image/png", 0))).toBe("El archivo está vacío.");
  });

  it("rechaza extensiones o tipos no permitidos", () => {
    expect(validateImageFile(makeFile("a.gif", "image/gif"))).toMatch(/Formato no permitido/);
    expect(validateImageFile(makeFile("a.png", "application/pdf"))).toMatch(/Formato no permitido/);
    expect(validateImageFile(makeFile("sin-extension", "image/png"))).toMatch(/Formato no permitido/);
  });

  it("rechaza archivos mayores que el máximo", () => {
    const file = makeFile("big.png", "image/png", 2 * 1024 * 1024);
    expect(validateImageFile(file, 1)).toBe("El archivo pesa 2.0 MB; el máximo es 1 MB.");
    expect(validateImageFile(file, 2)).toBeNull();
  });
});
