import os
from typing import Dict, Any, Tuple
from PIL import Image
from backend.core.security import SecuritySandbox

class LocalImageInspector:
    """
    Perception module for loading and inspecting local image files.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit for V0.1

    @classmethod
    def inspect_image_file(cls, file_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates path security, file size, and extracts image dimensions, format, and color mode.
        """
        valid, msg, path = SecuritySandbox.validate_file_path(file_path)
        if not valid:
            return False, msg, {}

        ext = path.suffix.lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            return False, f"Unsupported image extension '{ext}'. Supported: {cls.SUPPORTED_EXTENSIONS}", {}

        try:
            file_size_bytes = path.stat().st_size
            if file_size_bytes > cls.MAX_FILE_SIZE_BYTES:
                size_mb = file_size_bytes / (1024 * 1024)
                max_mb = cls.MAX_FILE_SIZE_BYTES / (1024 * 1024)
                return False, f"Image size ({size_mb:.2f} MB) exceeds maximum allowed size of {max_mb:.0f} MB.", {}

            with Image.open(path) as img:
                width, height = img.size
                format_name = img.format
                mode = img.mode

            metadata = {
                "file_name": path.name,
                "absolute_path": str(path),
                "extension": ext,
                "file_size_bytes": file_size_bytes,
                "width": width,
                "height": height,
                "format": format_name,
                "color_mode": mode
            }
            return True, "Image inspected successfully", metadata
        except Exception as e:
            return False, f"Failed to load image file: {str(e)}", {}
