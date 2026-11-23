/** Error de la API (o del análisis local) con el código HTTP y un mensaje listo para mostrar. `status` es 0 si no hubo respuesta. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
