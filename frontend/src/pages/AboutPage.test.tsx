import { screen, within } from "@testing-library/react";
import * as api from "../services/api";
import { renderAt } from "../test/utils";

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getHealth: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok", app: "DermAI", version: "0.1.0", environment: "testing" });
});

describe("AboutPage", () => {
  it("se abre desde la navegación y explica alcance, privacidad y límites", async () => {
    const { user } = renderAt("/history-no-existe");
    await user.click(screen.getByRole("link", { name: "Acerca de" }));

    expect(await screen.findByRole("heading", { name: "Acerca de DermAI" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Qué hace y qué no hace" })).toBeInTheDocument();
    expect(screen.getByText(/se eliminan sus metadatos/)).toBeInTheDocument();
    expect(screen.getByText(/versión con servidor requiere medidas de protección/)).toBeInTheDocument();
  });

  it("atribuye el dataset con su licencia y enlace", async () => {
    renderAt("/about");

    const credits = await screen.findByRole("table", { name: "Créditos y licencias" });
    const row = within(credits).getByRole("row", { name: /WoundTissue/ });
    expect(row).toHaveTextContent("CC BY-NC-SA 4.0");
    expect(within(row).getByRole("link")).toHaveAttribute("href", "https://github.com/akabircs/WoundTissue");
    expect(screen.getByText(/arXiv:2502.10652/)).toBeInTheDocument();
  });
});
