"""File storage helper for documents (spec §8.2 / §14.12).

Files are written under ``UPLOAD_FOLDER`` using FAB's ``FileManager`` for the
actual write. Stored names follow FAB's ``<uuid>_sep_<filename>`` convention so
``flask_appbuilder.filemanager.get_file_original_name`` can recover the
original name.
"""

import hashlib
import os
import uuid

from flask_appbuilder.filemanager import FileManager
from werkzeug.utils import secure_filename

from app.services.exceptions import ValidationError

SEP = "_sep_"


def is_allowed(filename: str, allowed_extensions) -> bool:
    if not allowed_extensions:
        return True
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in allowed_extensions


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_file_storage(file_storage, upload_folder: str, allowed_extensions=None) -> dict:
    """Persist a ``FileStorage`` and return its document metadata.

    Raises :class:`ValidationError` for a missing/empty or disallowed file.
    """
    if file_storage is None or not getattr(file_storage, "filename", None):
        raise ValidationError("A file is required")

    original_name = file_storage.filename
    safe_name = secure_filename(original_name)
    if not safe_name:
        raise ValidationError(f"Invalid file name '{original_name}'")
    if not is_allowed(safe_name, allowed_extensions):
        raise ValidationError(f"File type of '{original_name}' is not allowed")

    os.makedirs(upload_folder, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{SEP}{safe_name}"
    manager = FileManager(base_path=upload_folder)
    stored_name = manager.save_file(file_storage, stored_name)
    path = manager.get_path(stored_name)

    return {
        "file_name": original_name,
        "file_path": stored_name,
        "file_size": os.path.getsize(path),
        "mime_type": getattr(file_storage, "mimetype", None),
        "checksum_sha256": sha256_of(path),
    }


def delete_stored(stored_name: str, upload_folder: str) -> None:
    """Best-effort removal of a stored file (used to undo failed writes)."""
    if not stored_name:
        return
    path = os.path.join(upload_folder, stored_name)
    if os.path.exists(path):
        os.remove(path)
