import json
import math

import cv2
import numpy as np
import pytest

from ai.preprocessing import (
    ImageDecodeError,
    PipelineConfig,
    TissueThresholds,
    analyze_image,
    analyze_image_bytes,
    decode_image,
    encode_png,
    preprocess,
)
from ai.preprocessing.enhancement import resize_longest_side, shades_of_gray
from ai.preprocessing.features import glcm_features, shape_features
from ai.preprocessing.segmentation import fill_holes, segment_lesion
from ai.preprocessing.tissue import EXCLUDED, NECROTIC

import synthetic

# ---------- Lectura ----------


def test_decode_png_with_alpha_and_grayscale_returns_bgr():
    rgba = np.zeros((10, 12, 4), np.uint8)
    gray = np.full((10, 12), 128, np.uint8)
    for image in (rgba, gray):
        ok, buffer = cv2.imencode(".png", image)
        assert ok
        decoded = decode_image(buffer.tobytes())
        assert decoded.shape == (10, 12, 3)
        assert decoded.dtype == np.uint8


@pytest.mark.parametrize("data", [b"", b"no es una imagen"])
def test_decode_rejects_invalid_data(data):
    with pytest.raises(ImageDecodeError):
        decode_image(data)


def test_encode_png_round_trip():
    image = synthetic.wound()
    assert np.array_equal(decode_image(encode_png(image)), image)


# ---------- Preprocesamiento ----------


@pytest.mark.parametrize(
    ("shape", "expected"), [((480, 640), (384, 512)), ((24, 32), (384, 512)), ((900, 300), (512, 171))]
)
def test_resize_longest_side_keeps_aspect_ratio(shape, expected):
    resized = resize_longest_side(np.zeros((*shape, 3), np.uint8), 512)
    assert resized.shape[:2] == expected


def test_shades_of_gray_removes_color_cast():
    gray_scene = synthetic.uniform((128, 128, 128))
    cast = np.clip(gray_scene.astype(np.float32) * [1.3, 1.0, 0.75], 0, 255).astype(np.uint8)  # dominante azul

    corrected = shades_of_gray(cast, power=6, strength=1.0)
    means = corrected.reshape(-1, 3).mean(axis=0)
    assert means.max() - means.min() < 3
    assert np.array_equal(shades_of_gray(cast, strength=0.0), cast)


def test_preprocess_outputs_have_consistent_shapes():
    pre = preprocess(synthetic.wound(), PipelineConfig())
    assert pre.resized.shape == pre.corrected.shape == pre.denoised.shape == (384, 512, 3)
    assert pre.lab.shape == (384, 512, 3) and pre.lab.dtype == np.float32
    assert pre.gray.shape == pre.glare.shape == (384, 512)
    assert 0 <= pre.lab[..., 0].min() and pre.lab[..., 0].max() <= 100


# ---------- Segmentación ----------


def test_fill_holes():
    mask = np.zeros((9, 9), bool)
    mask[2:7, 2:7] = True
    mask[4, 4] = False
    assert fill_holes(mask)[4, 4]
    assert not fill_holes(mask)[0, 0]


def test_segmentation_matches_synthetic_lesion():
    pre = preprocess(synthetic.wound(), PipelineConfig())
    segmentation = segment_lesion(pre.lab, ~pre.glare, PipelineConfig())

    truth = cv2.resize(synthetic.ellipse_mask(synthetic.OUTER).astype(np.uint8), (512, 384)) > 0
    iou = (segmentation.mask & truth).sum() / (segmentation.mask | truth).sum()
    assert not segmentation.fallback
    assert iou > 0.95
    assert segmentation.border_contact == 0


def test_uniform_image_falls_back_to_full_image():
    output = analyze_image(synthetic.uniform())
    assert output.result["segmentation"]["fallback_full_image"] is True
    assert output.roi_mask.all()
    assert output.result["shape"] is None
    assert any("No se distinguió una lesión" in w for w in output.result["warnings"])


# ---------- Clasificación de tejido ----------


def test_tissue_composition_of_synthetic_wound():
    composition = analyze_image(synthetic.wound()).result["tissue_composition"]
    for name, expected in synthetic.expected_ratios().items():
        assert composition[name] == pytest.approx(expected, abs=0.03), name
    assert sum(composition.values()) == pytest.approx(1.0, abs=1e-3)


def test_necrotic_ratio_matches_composition():
    output = analyze_image(synthetic.wound())
    assert output.necrotic_area_ratio == output.result["tissue_composition"]["necrotic"]


def test_red_lesion_has_no_necrotic_tissue():
    output = analyze_image(synthetic.single_lesion(synthetic.LIGHT_SKIN, synthetic.RED))
    assert output.necrotic_area_ratio == 0
    assert output.result["tissue_composition"]["granulation"] > 0.9


def test_dark_skin_is_not_classified_as_necrotic():
    """La regla relativa a la piel evita confundir una lesión pigmentada en piel oscura con necrosis."""
    image = synthetic.single_lesion(synthetic.DARK_SKIN, (45, 55, 75))  # marrón oscuro poco saturado
    assert analyze_image(image).necrotic_area_ratio < 0.02

    # Solo con el umbral absoluto (sin exigir que sea más oscura que la piel) sí se marcaría.
    absolute_only = PipelineConfig(tissue=TissueThresholds(necrotic_min_darkening=-100))
    assert analyze_image(image, absolute_only).necrotic_area_ratio > 0.9


def test_black_eschar_is_detected_on_dark_skin():
    output = analyze_image(synthetic.single_lesion(synthetic.DARK_SKIN, (8, 8, 10), axes=(120, 90)))
    assert output.necrotic_area_ratio > 0.9


def test_thin_dark_hairs_are_not_necrotic():
    image = synthetic.single_lesion(synthetic.LIGHT_SKIN, synthetic.RED)
    for x in range(140, 520, 40):
        cv2.line(image, (x, 60), (x + 60, 420), (20, 20, 20), 2)
    assert analyze_image(image).necrotic_area_ratio < 0.01


def test_glare_is_excluded_from_tissue_classification():
    image = synthetic.single_lesion(synthetic.LIGHT_SKIN, synthetic.RED)
    for center in [(280, 220), (350, 260), (320, 200)]:
        cv2.circle(image, center, 12, (255, 255, 255), -1)
    output = analyze_image(image)

    pre = preprocess(image, PipelineConfig())
    assert output.result["quality"]["glare_ratio"] > 0
    assert (output.tissue_labels[pre.glare] == EXCLUDED).all()
    # Los reflejos dentro de la lesión no la parten: la región sigue siendo una sola.
    assert output.result["shape"]["solidity"] > 0.95


# ---------- Características ----------


def test_glcm_of_uniform_and_checkerboard_regions():
    region = np.ones((32, 32), bool)
    uniform = glcm_features(np.full((32, 32), 100, np.uint8), region)
    assert uniform["contrast"] == 0
    assert uniform["energy"] == pytest.approx(1.0)
    assert uniform["homogeneity"] == pytest.approx(1.0)

    checker = (np.indices((32, 32)).sum(axis=0) % 2 * 255).astype(np.uint8)
    assert glcm_features(checker, region)["contrast"] > 100


def test_shape_features_of_circle():
    mask = np.zeros((200, 200), np.uint8)
    cv2.circle(mask, (100, 100), 60, 1, -1)
    shape = shape_features(mask.astype(bool))
    assert shape["circularity"] > 0.85
    assert shape["solidity"] > 0.98
    assert shape["eccentricity"] < 0.1
    assert shape["aspect_ratio"] == pytest.approx(1.0, abs=0.05)


def test_result_is_json_serializable_with_expected_sections():
    output = analyze_image(synthetic.wound())
    result = json.loads(json.dumps(output.result))

    expected = {
        "method",
        "preprocessing",
        "segmentation",
        "tissue_composition",
        "color",
        "texture",
        "edges",
        "shape",
        "quality",
        "warnings",
        "config",
    }
    assert expected <= result.keys()
    assert result["method"]["name"] == "dermai-opencv-heuristic"
    assert result["preprocessing"]["original_size"] == [640, 480]
    assert result["preprocessing"]["processed_size"] == [512, 384]

    def finite(value):
        if isinstance(value, dict):
            return all(finite(v) for v in value.values())
        if isinstance(value, list):
            return all(finite(v) for v in value)
        return not isinstance(value, float) or math.isfinite(value)

    assert finite(result)


def test_overlay_marks_necrotic_region_in_magenta():
    output = analyze_image(synthetic.wound())
    assert output.overlay.shape == (384, 512, 3)
    blue, green, red = output.overlay[192, 256].astype(int)  # centro: tejido negro
    assert output.tissue_labels[192, 256] == NECROTIC
    assert blue > 120 and red > 120 and green < 60


def test_pipeline_is_deterministic_and_accepts_bytes():
    image = synthetic.wound()
    first = analyze_image(image)
    second = analyze_image_bytes(encode_png(image))
    assert first.result == second.result
    assert np.array_equal(first.overlay, second.overlay)


def test_low_resolution_and_blur_warnings():
    small = cv2.resize(synthetic.wound(), (64, 48), interpolation=cv2.INTER_AREA)
    warnings = analyze_image(small).result["warnings"]
    assert any("Resolución baja" in w for w in warnings)


@pytest.mark.parametrize(
    ("color", "expected"),
    [((12, 12, 15), "muy oscura"), ((252, 252, 250), "sobreexpuesta")],
)
def test_exposure_warnings(color, expected):
    warnings = analyze_image(synthetic.uniform(color)).result["warnings"]
    assert any(expected in w for w in warnings)


def test_glare_warning_when_reflections_cover_the_image():
    image = synthetic.single_lesion(synthetic.LIGHT_SKIN, synthetic.RED)
    for y in range(20, 480, 40):  # manchas blancas (≈20 % del área) repartidas por la imagen
        for x in range(20, 640, 40):
            cv2.circle(image, (x, y), 10, (255, 255, 255), -1)
    warnings = analyze_image(image).result["warnings"]
    assert any("reflejos" in w for w in warnings)


def test_analyze_image_rejects_non_bgr_input():
    with pytest.raises(ValueError):
        analyze_image(np.zeros((10, 10), np.uint8))
