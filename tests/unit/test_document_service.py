"""Document upload service tests (spec §8.2 / §14.5)."""

import io

import pytest
from werkzeug.datastructures import FileStorage

from app.models.core import Item
from app.services import DocumentService
from app.services.exceptions import ValidationError


def _file(content=b"hello", name="spec.txt", mime="text/plain"):
    return FileStorage(stream=io.BytesIO(content), filename=name, content_type=mime)


def test_create_document_stores_file(session, admin, tmp_path):
    svc = DocumentService(session, upload_folder=str(tmp_path))
    doc = svc.create_document("T-DOC-001", admin, uploaded_file=_file())

    assert doc.file_name == "spec.txt"
    assert doc.file_size == 5
    assert doc.mime_type == "text/plain"
    assert doc.file_path.endswith("spec.txt")
    assert "_sep_" in doc.file_path
    assert doc.checksum_sha256 is not None
    assert (tmp_path / doc.file_path).exists()


def test_missing_file_rejected(session, admin, tmp_path):
    svc = DocumentService(session, upload_folder=str(tmp_path))
    with pytest.raises(ValidationError):
        svc.create_document("T-DOC-002", admin, uploaded_file=None)


def test_disallowed_extension_rejected(session, admin, tmp_path):
    svc = DocumentService(
        session, upload_folder=str(tmp_path), allowed_extensions=["pdf"]
    )
    with pytest.raises(ValidationError):
        svc.create_document(
            "T-DOC-003", admin, uploaded_file=_file(name="evil.exe")
        )
    assert session.query(Item).filter_by(item_number="T-DOC-003").first() is None
    assert list(tmp_path.iterdir()) == []


def test_revise_document_with_new_file(session, admin, tmp_path):
    svc = DocumentService(session, upload_folder=str(tmp_path))
    doc = svc.create_document("T-DOC-004", admin, uploaded_file=_file(b"one"))

    revised = svc.revise_document(
        doc.item_version.item_id,
        "minor",
        admin,
        new_file=_file(b"two-two", name="spec_v2.txt"),
    )

    assert revised.item_version.revision_label == "A.1"
    assert revised.file_name == "spec_v2.txt"
    assert revised.file_size == 7
    # Both files remain (history is immutable).
    assert len(list(tmp_path.iterdir())) == 2


def test_revise_document_without_new_file_clones_metadata(session, admin, tmp_path):
    svc = DocumentService(session, upload_folder=str(tmp_path))
    doc = svc.create_document("T-DOC-005", admin, uploaded_file=_file())

    revised = svc.revise_document(doc.item_version.item_id, "minor", admin)
    assert revised.file_path == doc.file_path
    assert revised.file_name == doc.file_name
    assert len(list(tmp_path.iterdir())) == 1
