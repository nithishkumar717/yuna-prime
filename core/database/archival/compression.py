import gzip
import zipfile
import io
from typing import Union


class CompressionUtil:
    """Provides high-performance buffer and file stream compression utilities for backup archives."""

    @staticmethod
    def compress_gzip(data: Union[str, bytes]) -> bytes:
        """Compresses input string or bytes using Gzip compression."""
        raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(raw_bytes)
        return buf.getvalue()

    @staticmethod
    def decompress_gzip(compressed_data: bytes) -> bytes:
        """Decompresses Gzip-compressed byte buffer back to raw bytes."""
        buf = io.BytesIO(compressed_data)
        with gzip.GzipFile(fileobj=buf, mode="rb") as f:
            return f.read()

    @staticmethod
    def compress_zip(file_dict: dict[str, str]) -> bytes:
        """Compresses a dictionary mapping {filename: content} into a Zip archive byte buffer."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, content in file_dict.items():
                zf.writestr(filename, content)
        return buf.getvalue()

    @staticmethod
    def decompress_zip(zip_bytes: bytes) -> dict[str, str]:
        """Decompresses a Zip byte buffer into a dictionary mapping {filename: text_content}."""
        buf = io.BytesIO(zip_bytes)
        result = {}
        with zipfile.ZipFile(buf, mode="r") as zf:
            for name in zf.namelist():
                result[name] = zf.read(name).decode("utf-8")
        return result
