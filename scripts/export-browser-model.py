"""Export the existing DermAI checkpoint; never downloads weights or trains a model."""

import argparse
import gzip
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnx
import onnxruntime as ort
import psutil
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.models.classes import WOUNDTISSUE_CLASSES  # noqa: E402
from ai.models.inference import analyze_with_model, load_model  # noqa: E402
from ai.models.transforms import normalize, resize_longest  # noqa: E402
from ai.preprocessing.enhancement import resize_longest_side  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/public/models/dermai")
    args = parser.parse_args()
    run, out = args.run.resolve(), args.output.resolve()
    for name in ("model.pt", "model_meta.json", "metrics.json", "model_card.md"):
        if not (run / name).is_file():
            raise FileNotFoundError(run / name)
    loaded = load_model(run / "model.pt", "cpu")  # weights_only=True, strict state_dict
    meta = json.loads((run / "model_meta.json").read_text(encoding="utf-8"))
    assert loaded.meta == meta, "Checkpoint metadata differs from model_meta.json"
    assert meta["architecture"] == "unet-resnet18"
    assert meta["classes"] == [c.key for c in WOUNDTISSUE_CLASSES]
    assert meta["normalization"] == "imagenet" and meta["input_size"] == 256
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["dataset"]["images"] == meta["training_images"]
    torch.set_num_threads(1)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "model.onnx"
    # Legacy exporter deliberately used: dynamic H/W and align_corners=False supported by WASM.
    with torch.inference_mode():
        torch.onnx.export(
            loaded.model,
            torch.zeros(1, 3, 256, 256),
            str(path),
            input_names=["image"],
            output_names=["logits"],
            opset_version=17,
            dynamic_axes={"image": {2: "height", 3: "width"}, "logits": {2: "height", 3: "width"}},
            dynamo=False,
            external_data=False,
        )
    onnx.checker.check_model(str(path))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    start = time.perf_counter()
    session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
    load_ms = (time.perf_counter() - start) * 1000
    cases = []
    fixtures = ROOT / "frontend/src/analysis/__fixtures__"
    expected = json.loads((fixtures / "expected.json").read_text())
    # Synthetic RGB fixtures only. No datasets or clinical photos are exported.
    inputs = []
    for name, info in expected.items():
        if (fixtures / f"{name}.rgb.gz").exists():
            rgb = np.frombuffer(gzip.decompress((fixtures / f"{name}.rgb.gz").read_bytes()), np.uint8)
            inputs.append((name, rgb.reshape(info["height"], info["width"], 3)))
    rng = np.random.default_rng(42)
    inputs += [
        (f"random-{w}x{h}", rng.integers(0, 256, (h, w, 3), dtype=np.uint8))
        for h, w in [(173, 319), (319, 173), (1, 256), (256, 1)]
    ]
    for name, rgb in inputs:
        base = resize_longest_side(rgb, 512)
        x = normalize(resize_longest(base, 256))[None]
        with torch.inference_mode():
            start = time.perf_counter()
            reference = loaded.model(torch.from_numpy(x)).numpy()
            torch_ms = (time.perf_counter() - start) * 1000
        times = []
        for _ in range(3):
            start = time.perf_counter()
            actual = session.run(None, {"image": x})[0]
            times.append((time.perf_counter() - start) * 1000)
        delta = np.abs(actual - reference)

        def probabilities(logits, base=base):
            p = torch.softmax(torch.from_numpy(logits), 1)[0].numpy()
            return np.stack([cv2.resize(c, (base.shape[1], base.shape[0])) for c in p])

        p, q = probabilities(reference), probabilities(actual)
        agreement = float(np.mean(p.argmax(0) == q.argmax(0)))
        assert float(delta.max()) < 0.001, (name, delta.max())
        assert agreement >= 0.999, (name, agreement)
        cases.append(
            dict(
                name=name,
                shape=list(x.shape),
                max_logit_error=float(delta.max()),
                mean_logit_error=float(delta.mean()),
                max_probability_error=float(np.abs(p - q).max()),
                label_agreement=agreement,
                pytorch_ms=torch_ms,
                onnx_ms=times,
            )
        )
        if not name.startswith("random"):
            result = analyze_with_model(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), loaded)
            (fixtures / f"{name}.model.labels.gz").write_bytes(gzip.compress(result.tissue_labels.tobytes(), mtime=0))
            (fixtures / f"{name}.model.json").write_text(
                json.dumps(
                    dict(
                        confidence=result.confidence,
                        necrotic_area_ratio=result.necrotic_area_ratio,
                        result=result.result,
                    ),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    report = dict(
        checkpoint_sha256=digest(run / "model.pt"),
        onnx_sha256=digest(path),
        bytes=path.stat().st_size,
        quantization="none; float32",
        opset=17,
        load_ms=load_ms,
        process_rss_bytes=psutil.Process().memory_info().rss,
        process_peak_wset_bytes=getattr(psutil.Process().memory_info(), "peak_wset", None),
        memory_note="Entire Python process including PyTorch and ORT; not browser memory.",
        platform=platform.platform(),
        torch=torch.__version__,
        onnx=onnx.__version__,
        onnxruntime=ort.__version__,
        cases=cases,
    )
    manifest = dict(
        **meta,
        id=f"{meta['name']}:{meta['version']}:onnx",
        file="model.onnx",
        sha256=report["onnx_sha256"],
        bytes=report["bytes"],
        checkpoint_sha256=report["checkpoint_sha256"],
        license="CC-BY-NC-SA-4.0",
        metrics=metrics["summary"],
        class_details=[
            dict(key=c.key, label=c.label, group=c.group, color=c.display_color) for c in WOUNDTISSUE_CLASSES
        ],
    )
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name in ("model_meta.json", "metrics.json", "model_card.md"):
        (out / name).write_bytes((run / name).read_bytes())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
