"""Sube la carpeta del Space (deploy/huggingface/build) a Hugging Face.

Requisitos (una sola vez):
    .\\backend\\.venv\\Scripts\\python -m pip install huggingface_hub
    .\\backend\\.venv\\Scripts\\hf auth login        # pega tu token (permiso "write")

Uso (desde la raíz del proyecto, después de scripts/build-space.ps1):
    .\\backend\\.venv\\Scripts\\python deploy\\huggingface\\publish.py
"""

import argparse
import sys
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError, LocalTokenNotFoundError

BUILD_DIR = Path(__file__).resolve().parent / "build"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publica la API de DermAI en un Space de Hugging Face.")
    parser.add_argument("--repo", default="Wilmer-FP/dermai", help="Space de destino (usuario/nombre)")
    parser.add_argument("--folder", type=Path, default=BUILD_DIR)
    args = parser.parse_args(argv)

    if not (args.folder / "Dockerfile").is_file():
        print(f"No existe {args.folder / 'Dockerfile'}. Ejecuta antes scripts\\build-space.ps1.", file=sys.stderr)
        return 1

    api = HfApi()
    try:
        user = api.whoami()["name"]
    except (LocalTokenNotFoundError, HfHubHTTPError):
        print("No hay sesión de Hugging Face. Ejecuta: .\\backend\\.venv\\Scripts\\hf auth login", file=sys.stderr)
        return 1

    print(f"Sesión de Hugging Face: {user}. Publicando en el Space {args.repo}…")
    api.create_repo(args.repo, repo_type="space", space_sdk="docker", exist_ok=True)
    api.upload_folder(
        folder_path=args.folder,
        repo_id=args.repo,
        repo_type="space",
        commit_message="Actualizar la API de DermAI",
    )
    owner, name = args.repo.split("/")
    print(f"Listo. Space: https://huggingface.co/spaces/{args.repo}")
    print(f"API (cuando termine de construirse): https://{owner.lower()}-{name.lower()}.hf.space/docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
