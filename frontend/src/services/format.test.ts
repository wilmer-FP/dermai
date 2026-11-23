import { formatBytes, formatDate, formatDimensions, formatNumber, formatRatio, shortId } from "./format";

describe("formatos", () => {
  it("formatea tamaños en B, KB y MB", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
  });

  it("muestra «—» cuando no hay valor válido", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("no es una fecha")).toBe("—");
    expect(formatRatio(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
    expect(formatDimensions(null, 10)).toBe("—");
  });

  it("formatea proporciones, números, dimensiones e identificadores", () => {
    expect(formatRatio(0.1234)).toBe("12.3 %");
    expect(formatNumber(0.876, 1)).toBe("0.9");
    expect(formatDimensions(640, 480)).toBe("640 × 480 px");
    expect(shortId("abcdef12-3456")).toBe("abcdef12");
    expect(formatDate("2026-11-05T10:00:00Z")).toMatch(/2026/);
  });
});
