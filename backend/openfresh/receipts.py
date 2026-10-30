"""Receipt ingestion and text extraction utilities."""

import io
from pathlib import Path
from PIL import Image
import pytesseract
from pypdf import PdfReader

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from a PDF document byte stream using pypdf.

    Concatenates text across all pages. Returns an empty string if no
    text is found or if parsing fails.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
        return "\n".join(pages_text).strip()
    except Exception:
        return ""


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from an image byte stream using Tesseract OCR.

    Returns extracted text string, or empty string on failure.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception:
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch text extraction based on file extension.

    Supports PDF documents and common raster image formats (PNG, JPG, WEBP, etc.).
    Raises ValueError for unsupported file extensions.
    """
    ext = Path(filename).suffix.lower()
    if ext in PDF_EXTENSIONS:
        return extract_text_from_pdf(file_bytes)
    if ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(file_bytes)
    raise ValueError(f"Unsupported file type: {filename}")
