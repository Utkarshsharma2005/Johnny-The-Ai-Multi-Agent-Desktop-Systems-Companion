import math
from typing import NamedTuple, Optional
from PIL import Image, ImageChops, ImageStat

class ScreenDiffResult(NamedTuple):
    has_changed: bool
    diff_score: float  # Normalized difference score between 0.0 (identical) and 1.0 (completely different)
    description: str

class ScreenChangeDetector:
    """
    Computes fast local perceptual differences between consecutive screen frame captures
    to detect meaningful visual changes while filtering out minor UI noise.
    """

    DEFAULT_THRESHOLD = 0.02  # 2% difference required to trigger visual change event

    @classmethod
    def compute_diff(
        cls,
        current_frame: Image.Image,
        previous_frame: Optional[Image.Image],
        threshold: float = DEFAULT_THRESHOLD,
        sample_size: tuple = (128, 128)
    ) -> ScreenDiffResult:
        """
        Compares current_frame against previous_frame.
        If previous_frame is None, treats as initial frame (changed = True).
        """
        if previous_frame is None:
            return ScreenDiffResult(
                has_changed=True,
                diff_score=1.0,
                description="Initial frame capture"
            )

        try:
            # Resize both to small grayscale thumbnails for fast comparison
            curr_thumb = current_frame.convert("L").resize(sample_size, Image.Resampling.BILINEAR)
            prev_thumb = previous_frame.convert("L").resize(sample_size, Image.Resampling.BILINEAR)

            # Compute pixel absolute difference
            diff = ImageChops.difference(curr_thumb, prev_thumb)
            stat = ImageStat.Stat(diff)
            mean_diff = stat.mean[0]  # Mean pixel difference (0 to 255)

            # Normalize to 0.0 - 1.0
            normalized_score = round(mean_diff / 255.0, 4)
            has_changed = normalized_score >= threshold

            if not has_changed:
                desc = f"No meaningful visual change (score: {normalized_score:.4f} < threshold: {threshold})"
            else:
                desc = f"Visual change detected (score: {normalized_score:.4f} >= threshold: {threshold})"

            return ScreenDiffResult(
                has_changed=has_changed,
                diff_score=normalized_score,
                description=desc
            )
        except Exception as e:
            # Fallback on comparison error
            return ScreenDiffResult(
                has_changed=True,
                diff_score=1.0,
                description=f"Diff calculation fallback: {str(e)}"
            )

    @classmethod
    def compute_dhash(cls, img: Image.Image, hash_size: int = 8) -> str:
        """
        Computes a difference hash (dHash) string for visual identification.
        """
        resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
        if hasattr(resized, "get_flattened_data"):
            pixels = list(resized.get_flattened_data())
        else:
            pixels = list(resized.getdata())
        
        difference = []
        for row in range(hash_size):
            for col in range(hash_size):
                pixel_left = pixels[row * (hash_size + 1) + col]
                pixel_right = pixels[row * (hash_size + 1) + col + 1]
                difference.append(pixel_left > pixel_right)
                
        decimal_value = 0
        hex_string = []
        for i, val in enumerate(difference):
            if val:
                decimal_value += 2 ** (i % 4)
            if (i % 4) == 3:
                hex_string.append(hex(decimal_value)[2:])
                decimal_value = 0
        return "".join(hex_string)
