import os
import io
import base64
from typing import Tuple, Optional
from PIL import Image, ImageOps

# Constants
MAX_AVATAR_SIZE = 4 * 1024 * 1024  # 4 MB
MAX_BANNER_SIZE = 8 * 1024 * 1024  # 8 MB
ALLOWED_MIME_TYPES = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/gif': '.gif',
    'image/webp': '.webp'
}

BASE_ASSET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'profiles'))

class ProfileStorageError(Exception):
    """Custom exception for profile storage and image validation errors."""
    pass

def detect_mime_type(data: bytes) -> Optional[str]:
    """Detects image mime type using native magic byte signatures."""
    if len(data) < 12:
        return None
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return 'image/gif'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'image/webp'
    return None

class ProfileStorage:
    @staticmethod
    def get_guild_dir(guild_id: int) -> str:
        """
        Returns and ensures directory path for guild asset storage.
        Strictly guarantees isolation to per-server directories.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ProfileStorageError(f"Invalid guild_id ({guild_id}). Global bot profile assets are protected and cannot be modified.")
        guild_dir = os.path.join(BASE_ASSET_DIR, str(guild_id))
        os.makedirs(guild_dir, exist_ok=True)
        return guild_dir

    @staticmethod
    def optimize_image(data: bytes, asset_type: str = 'avatar') -> Tuple[bytes, str]:
        """
        Optimizes and resizes image bytes for Discord API compatibility.
        Avatars are resized to max 512x512. Banners are resized to max 1024x576.
        Returns (optimized_bytes, mime_type).
        """
        try:
            with Image.open(io.BytesIO(data)) as img:
                is_animated = getattr(img, "is_animated", False) and img.n_frames > 1
                if is_animated:
                    mime = "image/gif" if img.format == "GIF" else "image/webp"
                    return data, mime

                img = ImageOps.exif_transpose(img)
                max_dim = (512, 512) if asset_type == 'avatar' else (1024, 576)

                img.thumbnail(max_dim, Image.Resampling.LANCZOS)

                output = io.BytesIO()
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    img.save(output, format="PNG", optimize=True)
                    return output.getvalue(), "image/png"
                else:
                    img.save(output, format="JPEG", quality=90, optimize=True)
                    return output.getvalue(), "image/jpeg"
        except Exception:
            mime = detect_mime_type(data) or "image/png"
            return data, mime

    @staticmethod
    def validate_image_bytes(data: bytes, asset_type: str = 'avatar') -> Tuple[str, str]:
        """
        Validates magic byte header and size of image data.
        Returns tuple of (mime_type, extension).
        Raises ProfileStorageError on validation failure.
        """
        max_size = MAX_AVATAR_SIZE if asset_type == 'avatar' else MAX_BANNER_SIZE
        if len(data) > max_size:
            max_mb = 4 if asset_type == 'avatar' else 8
            raise ProfileStorageError(f"{asset_type.capitalize()} size exceeds maximum allowed size of {max_mb}MB.")

        mime = detect_mime_type(data)
        if not mime or mime not in ALLOWED_MIME_TYPES:
            raise ProfileStorageError(
                f"Unsupported image format. Allowed formats: PNG, JPEG, GIF, WEBP."
            )

        ext = ALLOWED_MIME_TYPES[mime]
        return mime, ext

    @staticmethod
    def save_asset(guild_id: int, asset_type: str, data: bytes) -> str:
        """
        Validates, saves raw image bytes locally to assets/profiles/{guild_id}/{asset_type}.{ext},
        and purges any old asset of different extension for the same asset type.
        Returns the absolute local filepath.
        """
        if asset_type not in ('avatar', 'banner'):
            raise ProfileStorageError("Invalid asset type. Must be 'avatar' or 'banner'.")

        mime, ext = ProfileStorage.validate_image_bytes(data, asset_type)
        guild_dir = ProfileStorage.get_guild_dir(guild_id)

        # Purge existing asset files for this asset_type
        for existing_ext in ALLOWED_MIME_TYPES.values():
            existing_file = os.path.join(guild_dir, f"{asset_type}{existing_ext}")
            if os.path.exists(existing_file):
                try:
                    os.remove(existing_file)
                except OSError:
                    pass

        file_path = os.path.join(guild_dir, f"{asset_type}{ext}")
        with open(file_path, 'wb') as f:
            f.write(data)

        return file_path

    @staticmethod
    def delete_asset(guild_id: int, asset_type: str) -> None:
        """
        Removes local asset file for a given guild and asset type.
        Only affects assets in assets/profiles/{guild_id}/.
        Global bot assets are never touched.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            return
        guild_dir = os.path.join(BASE_ASSET_DIR, str(guild_id))
        if not os.path.exists(guild_dir):
            return

        for ext in ALLOWED_MIME_TYPES.values():
            target_path = os.path.join(guild_dir, f"{asset_type}{ext}")
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except OSError:
                    pass

    @staticmethod
    def get_asset_file(guild_id: int, asset_type: str) -> Optional[str]:
        """Returns the existing local filepath of asset if present, else None."""
        if not isinstance(guild_id, int) or guild_id <= 0:
            return None
        guild_dir = os.path.join(BASE_ASSET_DIR, str(guild_id))
        if not os.path.exists(guild_dir):
            return None

        for ext in ALLOWED_MIME_TYPES.values():
            target_path = os.path.join(guild_dir, f"{asset_type}{ext}")
            if os.path.exists(target_path):
                return target_path
        return None

    @staticmethod
    def bytes_to_data_uri(data: bytes, mime_type: str) -> str:
        """Converts raw bytes and mime_type into standard Base64 Data URI string."""
        encoded = base64.b64encode(data).decode('utf-8')
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def data_uri_to_bytes(data_uri: str) -> Tuple[bytes, str]:
        """
        Parses a Base64 Data URI string into raw bytes and mime_type.
        Format: data:<mime_type>;base64,<encoded_data>
        """
        if not data_uri.startswith('data:'):
            raise ProfileStorageError("Invalid Data URI format.")
        
        header, encoded = data_uri.split(',', 1)
        mime = header.split(';')[0].replace('data:', '').strip()
        data = base64.b64decode(encoded)
        return data, mime
