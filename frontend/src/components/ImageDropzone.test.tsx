import { createEvent, fireEvent, render, screen } from "@testing-library/react";
import { makeFile } from "../test/utils";
import { ImageDropzone } from "./ImageDropzone";

function drop(target: HTMLElement, files: File[]) {
  const event = createEvent.drop(target);
  Object.defineProperty(event, "dataTransfer", { value: { files } });
  fireEvent(target, event);
}

const zone = () => screen.getByText(/selecciona una imagen o arrástrala aquí/i).closest("label") as HTMLElement;

describe("ImageDropzone", () => {
  it("entrega el archivo soltado y marca la zona al arrastrar encima", () => {
    const onSelect = vi.fn();
    render(<ImageDropzone onSelect={onSelect} />);

    fireEvent.dragOver(zone());
    expect(zone()).toHaveClass("dropzone--active");

    const file = makeFile("lesion.png");
    drop(zone(), [file]);
    expect(onSelect).toHaveBeenCalledWith(file);
    expect(zone()).not.toHaveClass("dropzone--active");
  });

  it("quita el resaltado al salir sin soltar", () => {
    render(<ImageDropzone onSelect={vi.fn()} />);
    fireEvent.dragOver(zone());
    fireEvent.dragLeave(zone());
    expect(zone()).not.toHaveClass("dropzone--active");
  });

  it("ignora lo que se suelta mientras está deshabilitada", () => {
    const onSelect = vi.fn();
    render(<ImageDropzone onSelect={onSelect} disabled />);

    fireEvent.dragOver(zone());
    expect(zone()).not.toHaveClass("dropzone--active");
    drop(zone(), [makeFile()]);
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/selecciona una imagen/i)).toBeDisabled();
  });

  it("no hace nada si se suelta algo que no es un archivo", () => {
    const onSelect = vi.fn();
    render(<ImageDropzone onSelect={onSelect} />);
    drop(zone(), []);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("anuncia los formatos y el tamaño máximo", () => {
    render(<ImageDropzone onSelect={vi.fn()} />);
    const input = screen.getByLabelText(/selecciona una imagen/i);
    expect(input).toHaveAttribute("accept", expect.stringContaining("image/png"));
    expect(input).toHaveAccessibleDescription("JPG o PNG, hasta 10 MB");
  });
});
