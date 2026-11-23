import "@testing-library/jest-dom/vitest";

// jsdom no implementa las URL de objeto que usa la vista previa.
if (!URL.createObjectURL) {
  URL.createObjectURL = () => "blob:preview";
  URL.revokeObjectURL = () => undefined;
}
