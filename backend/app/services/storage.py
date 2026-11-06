"""Almacenamiento local de archivos de imagen (STORAGE_PATH/images)."""

from pathlib import Path


class LocalStorage:
    def __init__(self, base_dir: Path) -> None:
        self.images_dir = (base_dir / "images").resolve()

    def path_for(self, filename: str) -> Path:
        path = (self.images_dir / filename).resolve()
        # Defensa en profundidad: nunca salir del directorio de almacenamiento.
        if path.parent != self.images_dir:
            raise ValueError(f"Nombre de archivo no válido: {filename!r}")
        return path

    def save(self, filename: str, data: bytes) -> Path:
        self.images_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(filename)
        path.write_bytes(data)
        return path

    def delete(self, filename: str) -> None:
        self.path_for(filename).unlink(missing_ok=True)

    def exists(self, filename: str) -> bool:
        return self.path_for(filename).is_file()
