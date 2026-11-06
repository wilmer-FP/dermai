"""Privacidad y avisos: metadatos eliminados al subir y aviso incrustado en la imagen procesada."""

import hashlib
import struct
from io import BytesIO

import numpy as np
import pytest
from PIL import Image as PILImage
from PIL import PngImagePlugin

from app.services import metadata
from app.services.metadata import EXIF_ORIENTATION, strip_metadata
from app.services.watermark import stamp_disclaimer

GPS_IFD = 0x8825


def jpeg_with_exif(orientation: int = 1, size=(40, 20)) -> bytes:
    image = PILImage.new("RGB", size, (180, 60, 60))
    image.paste((20, 20, 20), (0, 0, size[0] // 2, size[1]))  # mitad izquierda oscura (para ver rotaciones)
    exif = image.getexif()
    exif[0x010F] = "MarcaDeCamara"  # Make
    exif[EXIF_ORIENTATION] = orientation
    exif.get_ifd(GPS_IFD).update({1: "N", 2: (40.0, 25.0, 0.0)})  # latitud
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif, quality=95)
    return buffer.getvalue()


def png_with_text() -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Nombre del paciente")
    info.add_itxt("Comment", "Ubicación: hospital")
    buffer = BytesIO()
    PILImage.new("RGB", (30, 20), (180, 60, 60)).save(buffer, format="PNG", pnginfo=info)
    return buffer.getvalue()


def decoded(data: bytes) -> np.ndarray:
    with PILImage.open(BytesIO(data)) as image:
        return np.asarray(image.convert("RGB"))


# ---------- Metadatos ----------


def test_jpeg_exif_and_gps_are_removed_without_recompression():
    original = jpeg_with_exif()
    clean = strip_metadata(original, "JPEG")

    with PILImage.open(BytesIO(clean.data)) as image:
        assert len(image.getexif()) == 0
    assert b"MarcaDeCamara" not in clean.data and b"Exif" not in clean.data
    assert np.array_equal(decoded(clean.data), decoded(original))  # mismos píxeles: no se recomprime
    assert (clean.width, clean.height) == (40, 20)


def test_jpeg_with_rotation_is_turned_upright_before_removing_exif():
    clean = strip_metadata(jpeg_with_exif(orientation=6), "JPEG")  # 6 = girar 90° a la derecha

    assert (clean.width, clean.height) == (20, 40)
    with PILImage.open(BytesIO(clean.data)) as image:
        assert len(image.getexif()) == 0
    pixels = decoded(clean.data)
    assert pixels[2, 10].mean() < 60  # la mitad oscura queda arriba tras el giro
    assert pixels[-3, 10].mean() > 60


def test_png_text_chunks_are_removed_and_pixels_kept():
    original = png_with_text()
    clean = strip_metadata(original, "PNG")

    assert b"Nombre del paciente" not in clean.data and b"tEXt" not in clean.data and b"iTXt" not in clean.data
    assert np.array_equal(decoded(clean.data), decoded(original))


def test_unusual_structure_falls_back_to_reencoding(monkeypatch):
    def unparseable(_data):
        raise metadata.MetadataError("estructura inusual")

    monkeypatch.setattr(metadata, "_strip_png_chunks", unparseable)
    clean = strip_metadata(png_with_text(), "PNG")

    assert b"Nombre del paciente" not in clean.data
    assert decoded(clean.data).shape == (20, 30, 3)


@pytest.mark.parametrize(
    "data",
    [
        b"no es un jpeg",
        b"\xff\xd8\xff\xe1\x00",  # segmento truncado
        b"\xff\xd8\xff\xe0\x00\x10" + b"x" * 14,  # sin datos de imagen
    ],
)
def test_jpeg_parser_rejects_broken_structures(data):
    with pytest.raises(metadata.MetadataError):
        metadata._strip_jpeg_segments(data)


@pytest.mark.parametrize("data", [b"no es un png", metadata.PNG_SIGNATURE + struct.pack(">I", 5) + b"IHDR"])
def test_png_parser_rejects_broken_structures(data):
    with pytest.raises(metadata.MetadataError):
        metadata._strip_png_chunks(data)


def test_upload_stores_the_clean_file_and_its_checksum(api_client, storage_dir):
    response = api_client.post("/api/v1/images", files={"file": ("foto.jpg", jpeg_with_exif(), "image/jpeg")})

    assert response.status_code == 201
    body = response.json()
    (stored,) = (storage_dir / "images").iterdir()
    stored_bytes = stored.read_bytes()
    assert b"MarcaDeCamara" not in stored_bytes
    assert body["checksum_sha256"] == hashlib.sha256(stored_bytes).hexdigest()
    assert body["file_size_bytes"] == len(stored_bytes)

    downloaded = api_client.get(f"/api/v1/images/{body['id']}/file").content
    assert downloaded == stored_bytes


# ---------- Aviso en la imagen procesada ----------


@pytest.mark.parametrize("shape", [(384, 512, 3), (60, 80, 3)])
def test_stamp_keeps_size_and_marks_the_bottom_band(shape):
    image = np.full(shape, 200, np.uint8)
    stamped = stamp_disclaimer(image)

    assert stamped.shape == shape
    assert np.array_equal(stamped[: shape[0] // 2], image[: shape[0] // 2])  # la parte superior no cambia
    band = stamped[-8:]
    assert band.min() < 100  # franja oscurecida
    assert band.max() > 200  # con texto blanco


def test_processed_image_from_api_contains_the_stamp(api_client):
    image_id = api_client.post(
        "/api/v1/images", files={"file": ("foto.jpg", jpeg_with_exif(size=(320, 240)), "image/jpeg")}
    ).json()["id"]
    analysis_id = api_client.post(f"/api/v1/images/{image_id}/analyses").json()["id"]

    processed = decoded(api_client.get(f"/api/v1/analyses/{analysis_id}/processed-image").content)
    assert processed[-6:].mean() < processed[: processed.shape[0] // 2].mean()
