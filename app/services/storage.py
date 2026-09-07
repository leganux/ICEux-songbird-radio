from pathlib import Path

from minio import Minio

from app.config import Settings


class ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = Minio(
            settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_use_ssl,
        )

    def upload_file(self, object_name: str, path: Path, content_type: str) -> None:
        self.client.fput_object(
            self.settings.s3_bucket,
            object_name,
            str(path),
            content_type=content_type,
        )
