import hashlib
import uuid

import pytest

from conftest import make_image_bytes

URL = "/api/v1/images"


def upload(client, data: bytes, filename: str = "lesion.png", content_type: str = "image/png"):
    return client.post(URL, files={"file": (filename, data, content_type)})


def test_upload_png(api_client, storage_dir):
    data = make_image_bytes("PNG", (32, 24))

    response = upload(api_client, data)

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "lesion.png"
    assert body["content_type"] == "image/png"
    assert (body["width"], body["height"]) == (32, 24)
    assert body["file_size_bytes"] == len(data)
    assert body["checksum_sha256"] == hashlib.sha256(data).hexdigest()
    assert "stored_filename" not in body
    assert len(list((storage_dir / "images").iterdir())) == 1


def test_upload_jpeg_with_jpeg_extension(api_client):
    response = upload(api_client, make_image_bytes("JPEG"), "foto.jpeg", "image/jpeg")

    assert response.status_code == 201
    assert response.json()["content_type"] == "image/jpeg"


def test_content_type_is_detected_not_trusted(api_client):
    # El cliente declara PNG pero el contenido real es JPEG.
    response = upload(api_client, make_image_bytes("JPEG"), "foto.png", "image/png")

    assert response.status_code == 201
    assert response.json()["content_type"] == "image/jpeg"


def test_filename_path_is_stripped(api_client):
    response = upload(api_client, make_image_bytes(), "..\\..\\carpeta/secreta/lesion.png")

    assert response.status_code == 201
    assert response.json()["original_filename"] == "lesion.png"


def test_rejects_non_image_content(api_client, storage_dir):
    response = upload(api_client, b"esto no es una imagen", "falsa.png")

    assert response.status_code == 422
    assert "imagen" in response.json()["detail"]
    assert not (storage_dir / "images").exists()


def test_rejects_disallowed_extension(api_client):
    response = upload(api_client, make_image_bytes("GIF"), "anim.gif", "image/gif")

    assert response.status_code == 415


def test_rejects_disallowed_real_format_with_allowed_extension(api_client):
    response = upload(api_client, make_image_bytes("GIF"), "anim.png")

    assert response.status_code == 415


def test_rejects_empty_file(api_client):
    assert upload(api_client, b"").status_code == 422


def test_rejects_file_over_size_limit(api_client):
    # Límite de pruebas: 1 MB
    response = upload(api_client, b"\x89PNG" + b"0" * (1024 * 1024))

    assert response.status_code == 413


def test_requires_file_field(api_client):
    assert api_client.post(URL).status_code == 422


def test_list_images_paginates(api_client):
    for _ in range(3):
        upload(api_client, make_image_bytes())

    response = api_client.get(URL, params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert (body["limit"], body["offset"]) == (2, 0)


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_images_validates_pagination(api_client, params):
    assert api_client.get(URL, params=params).status_code == 422


def test_get_image_and_file(api_client):
    data = make_image_bytes()
    image_id = upload(api_client, data).json()["id"]

    assert api_client.get(f"{URL}/{image_id}").json()["id"] == image_id

    file_response = api_client.get(f"{URL}/{image_id}/file")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == "image/png"
    assert file_response.content == data


def test_get_unknown_image_returns_404(api_client):
    response = api_client.get(f"{URL}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Imagen no encontrada."}


def test_invalid_uuid_returns_422(api_client):
    assert api_client.get(f"{URL}/no-es-un-uuid").status_code == 422


def test_file_missing_from_storage_returns_404(api_client, storage_dir):
    image_id = upload(api_client, make_image_bytes()).json()["id"]
    for path in (storage_dir / "images").iterdir():
        path.unlink()

    assert api_client.get(f"{URL}/{image_id}/file").status_code == 404


def test_delete_image_removes_file_and_analyses(api_client, storage_dir):
    image_id = upload(api_client, make_image_bytes()).json()["id"]
    analysis_id = api_client.post(f"{URL}/{image_id}/analyses").json()["id"]

    response = api_client.delete(f"{URL}/{image_id}")

    assert response.status_code == 204
    assert api_client.get(f"{URL}/{image_id}").status_code == 404
    assert api_client.get(f"/api/v1/analyses/{analysis_id}").status_code == 404
    assert list((storage_dir / "images").iterdir()) == []


def test_delete_unknown_image_returns_404(api_client):
    assert api_client.delete(f"{URL}/{uuid.uuid4()}").status_code == 404
