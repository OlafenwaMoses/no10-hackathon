"""Where search jobs are stored.

On Vercel it's the private Vercel Blob store. When LOCAL_DATA_DIR is set, as in
docker-compose.yml, it's a folder with the same create-only-if-missing behaviour.
"""

import os
import uuid
from pathlib import Path
from types import SimpleNamespace

from vercel.blob import AsyncBlobClient, BlobError, BlobNotFoundError

LOCAL_DATA_DIR = os.environ.get("LOCAL_DATA_DIR")


class LocalBlobClient:
    """The part of AsyncBlobClient that service.jobs uses, backed by files in a folder."""

    def __init__(self, root: str):
        self.root = Path(root)

    async def __aenter__(self) -> "LocalBlobClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def get(self, path: str, **options) -> SimpleNamespace:
        try:
            return SimpleNamespace(content=(self.root / path).read_bytes())
        except FileNotFoundError:
            raise BlobNotFoundError() from None

    async def put(self, path: str, body: bytes, *, overwrite: bool = False, **options) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(body)
        try:
            if overwrite:
                os.replace(temporary, target)
            else:
                os.link(temporary, target)  # fails if the file exists, so only one request creates a job
        except FileExistsError:
            raise BlobError(f"{path} already exists") from None
        finally:
            temporary.unlink(missing_ok=True)


def open_store() -> AsyncBlobClient | LocalBlobClient:
    return LocalBlobClient(LOCAL_DATA_DIR) if LOCAL_DATA_DIR else AsyncBlobClient()
