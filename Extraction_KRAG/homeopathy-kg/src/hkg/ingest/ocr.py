from __future__ import annotations

from pathlib import Path
from typing import Any


def ocr_page_image(image_path: Path) -> dict[str, Any]:
    """Fallback OCR extraction for scanned pages using pytesseract.

    Note per plan §9: OCR loses bold/italic; flag those pages.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {
            "text": "",
            "grade_unreliable": True,
            "error": "pytesseract/Pillow not installed",
        }

    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return {
            "text": text,
            "grade_unreliable": True,
            "emphasis": "plain",
        }
    except Exception as e:
        return {
            "text": "",
            "grade_unreliable": True,
            "error": str(e),
        }
