"""Azure hosting helpers (Blob transcript archive for #630)."""

from hosting.azure.transcript_blobs import (
    blob_name_for_video,
    download_transcript_json,
    upload_transcript_file,
)

__all__ = [
    "blob_name_for_video",
    "download_transcript_json",
    "upload_transcript_file",
]
