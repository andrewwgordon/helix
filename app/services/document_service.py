"""Document service (spec §14.5)."""

from app.models.audit import EVENT_CREATE, EVENT_REVISE
from app.models.business import Document
from app.services.base import Actor
from app.services.business_base import BusinessObjectService
from app.services.exceptions import ValidationError
from app.services.storage import delete_stored, save_file_storage

CLONE_COLUMNS = [
    "file_name",
    "mime_type",
    "file_size",
    "file_path",
    "checksum_sha256",
]


class DocumentService(BusinessObjectService):
    item_type_code = "Document"
    version_attr = "document"

    def __init__(
        self,
        session,
        actor: Actor = None,
        *,
        upload_folder: str = None,
        allowed_extensions=None,
    ):
        super().__init__(session, actor)
        self._upload_folder = upload_folder
        self._allowed_extensions = allowed_extensions

    @property
    def upload_folder(self) -> str:
        if self._upload_folder:
            return self._upload_folder
        from flask import current_app

        folder = current_app.config.get("UPLOAD_FOLDER")
        if not folder:
            raise ValidationError("UPLOAD_FOLDER is not configured")
        return folder

    @property
    def allowed_extensions(self):
        if self._allowed_extensions is not None:
            return self._allowed_extensions
        from flask import current_app

        return current_app.config.get("FILE_ALLOWED_EXTENSIONS")

    def create_document(
        self,
        item_number: str,
        actor: Actor = None,
        *,
        uploaded_file,
        description: str = None,
    ) -> Document:
        actor = self._actor(actor)
        metadata = save_file_storage(
            uploaded_file, self.upload_folder, self.allowed_extensions
        )
        try:
            item = self.items.create_item(
                self.item_type_code, item_number, actor, commit=False
            )
            version = self.items.create_version(
                item.id, actor, description=description, commit=False
            )
            document = Document(
                item_version_id=version.id,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
                **metadata,
            )
            self.session.add(document)
            self.session.flush()
            self.audit.record(
                EVENT_CREATE,
                "Document",
                version.id,
                actor,
                item_id=item.id,
                to_value=metadata["file_name"],
            )
            self.session.commit()
        except Exception:
            delete_stored(metadata["file_path"], self.upload_folder)
            self.session.rollback()
            raise
        return document

    def revise_document(
        self,
        item_id: int,
        change_type: str,
        actor: Actor = None,
        *,
        new_file=None,
        description: str = None,
        copy_relationships: bool = True,
        **overrides,
    ) -> Document:
        actor = self._actor(actor)
        current = self.items.get_current_version(item_id)
        current_document = self._require_subtype(current)

        data = self._clone_columns(current_document, CLONE_COLUMNS)
        data.update(overrides)

        new_metadata = None
        if new_file is not None:
            new_metadata = save_file_storage(
                new_file, self.upload_folder, self.allowed_extensions
            )
            data.update(new_metadata)

        try:
            new_version = self.items.revise_item(
                item_id,
                change_type,
                actor,
                copy_relationships=copy_relationships,
                description=description,
                commit=False,
            )
            document = Document(
                item_version_id=new_version.id,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
                **data,
            )
            self.session.add(document)
            self.audit.record(
                EVENT_REVISE, "Document", new_version.id, actor, item_id=item_id
            )
            self.session.commit()
        except Exception:
            if new_metadata is not None:
                delete_stored(new_metadata["file_path"], self.upload_folder)
            self.session.rollback()
            raise
        return document
