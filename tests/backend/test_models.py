from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Analysis, AnalysisStatus, Base, Image, ModelVersion

from db_utils import make_sqlite_engine


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def make_image(**overrides) -> Image:
    data = {
        "original_filename": "lesion.jpg",
        "stored_filename": "3f2a.jpg",
        "content_type": "image/jpeg",
        "file_size_bytes": 2048,
        "width": 640,
        "height": 480,
        "checksum_sha256": "a" * 64,
    }
    return Image(**(data | overrides))


def test_create_image_with_analysis_and_model_version(session):
    model = ModelVersion(name="necrosis-seg", version="0.1.0", metrics={"dice": 0.71})
    image = make_image()
    image.analyses.append(
        Analysis(
            model_version=model,
            status=AnalysisStatus.COMPLETED,
            necrotic_area_ratio=0.25,
            confidence=0.8,
            result={"regions": 3},
        )
    )
    session.add(image)
    session.commit()

    analysis = session.scalars(select(Analysis)).one()
    assert analysis.image.stored_filename == "3f2a.jpg"
    assert analysis.model_version.name == "necrosis-seg"
    assert analysis.result == {"regions": 3}
    assert analysis.created_at is not None
    assert model.is_active is False


def test_analysis_defaults_to_pending(session):
    image = make_image()
    image.analyses.append(Analysis())
    session.add(image)
    session.commit()

    assert session.scalars(select(Analysis)).one().status is AnalysisStatus.PENDING


def test_deleting_image_deletes_its_analyses(session):
    image = make_image()
    image.analyses.extend([Analysis(), Analysis()])
    session.add(image)
    session.commit()

    session.delete(image)
    session.commit()

    assert session.scalars(select(Analysis)).all() == []


def test_stored_filename_must_be_unique(session):
    session.add_all([make_image(), make_image()])

    with pytest.raises(IntegrityError):
        session.commit()


def test_model_name_and_version_must_be_unique(session):
    session.add_all([ModelVersion(name="m", version="1"), ModelVersion(name="m", version="1")])

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("field", ["necrotic_area_ratio", "confidence"])
@pytest.mark.parametrize("value", [-0.1, 1.5])
def test_ratios_must_be_between_0_and_1(session, field, value):
    image = make_image()
    image.analyses.append(Analysis(**{field: value}))
    session.add(image)

    with pytest.raises(IntegrityError):
        session.commit()


def test_file_size_must_be_positive(session):
    session.add(make_image(file_size_bytes=0))

    with pytest.raises(IntegrityError):
        session.commit()
