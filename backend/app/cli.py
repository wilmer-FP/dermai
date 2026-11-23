"""Comandos de administración.

Registrar el modelo de una ejecución de entrenamiento (desde `backend/` o con `--app-dir backend`):

    python -m app.cli register-model ../ai/experiments/runs/<ejecución> --activate

Copia `model.pt` a `ai/models/weights/<nombre>-<versión>.pt` (no versionado) y crea la fila en
`model_versions` con la descripción y el resumen de métricas de la ejecución.
"""

import argparse
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.core.database import get_sessionmaker
from app.models import ModelVersion

WEIGHTS_DIR = PROJECT_ROOT / "ai" / "models" / "weights"


class CommandError(Exception):
    pass


def register_model(
    db: Session,
    run_dir: Path,
    activate: bool = False,
    weights_dir: Path = WEIGHTS_DIR,
    if_missing: bool = False,
) -> ModelVersion:
    """Registra el modelo de una ejecución. Con `if_missing`, si la versión ya existe no hace nada."""
    run_dir = run_dir.resolve()
    meta_path, metrics_path, checkpoint = run_dir / "model_meta.json", run_dir / "metrics.json", run_dir / "model.pt"
    for path in (meta_path, metrics_path, checkpoint):
        if not path.is_file():
            raise CommandError(f"Falta {path.name} en {run_dir}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    name, version = meta["name"], meta["version"]

    existing = db.scalar(select(ModelVersion).where(ModelVersion.name == name, ModelVersion.version == version))
    if existing is not None:
        if if_missing:
            return existing
        raise CommandError(f"Ya existe la versión {name} {version}. Cambia `version` en la configuración.")

    weights_dir.mkdir(parents=True, exist_ok=True)
    target = weights_dir / f"{name}-{version}.pt"
    if target.exists():
        raise CommandError(f"Ya existe {target}; no se sobrescribe.")
    shutil.copy2(checkpoint, target)

    try:
        weights_path = target.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        weights_path = str(target)

    if activate:
        db.execute(update(ModelVersion).values(is_active=False))
    model = ModelVersion(
        name=name,
        version=version,
        architecture=meta.get("architecture"),
        description=meta.get("description"),
        weights_path=weights_path,
        metrics={**metrics.get("summary", {}), "run_id": meta.get("run_id"), "dataset": meta.get("dataset")},
        is_active=activate,
    )
    db.add(model)
    try:
        db.commit()
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    db.refresh(model)
    return model


def update_metrics(db: Session, run_dir: Path) -> ModelVersion:
    """Actualiza el resumen de métricas de una versión ya registrada desde su ejecución."""
    run_dir = run_dir.resolve()
    meta = json.loads((run_dir / "model_meta.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    model = db.scalar(
        select(ModelVersion).where(ModelVersion.name == meta["name"], ModelVersion.version == meta["version"])
    )
    if model is None:
        raise CommandError(f"No existe la versión {meta['name']} {meta['version']}.")
    model.metrics = {**metrics.get("summary", {}), "run_id": meta.get("run_id"), "dataset": meta.get("dataset")}
    db.commit()
    db.refresh(model)
    return model


def set_active(db: Session, name: str, version: str, active: bool) -> ModelVersion:
    model = db.scalar(select(ModelVersion).where(ModelVersion.name == name, ModelVersion.version == version))
    if model is None:
        raise CommandError(f"No existe la versión {name} {version}.")
    if active:
        db.execute(update(ModelVersion).values(is_active=False))
    model.is_active = active
    db.commit()
    db.refresh(model)
    return model


def main(argv: list[str] | None = None, session_factory: Callable[[], Session] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Administración de DermAI")
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register-model", help="Registrar el modelo de una ejecución de entrenamiento")
    register.add_argument("run_dir", type=Path)
    register.add_argument("--activate", action="store_true", help="Marcarlo como modelo activo")
    register.add_argument("--if-missing", action="store_true", help="No fallar si la versión ya está registrada")

    refresh = commands.add_parser("update-metrics", help="Actualizar las métricas de una versión registrada")
    refresh.add_argument("run_dir", type=Path)

    for command, help_text in (
        ("activate-model", "Activar una versión"),
        ("deactivate-model", "Desactivar una versión"),
    ):
        sub = commands.add_parser(command, help=help_text)
        sub.add_argument("name")
        sub.add_argument("version")

    args = parser.parse_args(argv)
    factory = session_factory or get_sessionmaker()
    with factory() as db:
        try:
            if args.command == "register-model":
                model = register_model(db, args.run_dir, args.activate, if_missing=args.if_missing)
                print(f"Registrado {model.name} {model.version} (id {model.id}, activo: {model.is_active})")
            elif args.command == "update-metrics":
                model = update_metrics(db, args.run_dir)
                print(f"Métricas actualizadas: {model.name} {model.version}")
            else:
                model = set_active(db, args.name, args.version, args.command == "activate-model")
                print(f"{model.name} {model.version}: activo = {model.is_active}")
        except CommandError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
