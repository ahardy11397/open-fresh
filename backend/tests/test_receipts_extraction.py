import io
import pytest
from PIL import Image, ImageDraw
from openfresh.receipts import extract_text, extract_text_from_pdf, extract_text_from_image


def _create_minimal_pdf(text: str) -> bytes:
    stream_content = f"BT\n/F1 18 Tf\n50 100 Td\n({text}) Tj\nET\n".encode("latin1")
    stream_len = len(stream_content)

    parts = [
        b"%PDF-1.4\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin1") + stream_content + b"endstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    offsets = [0]
    cur = 0
    for p in parts[:-1]:
        cur += len(p)
        offsets.append(cur)

    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode("latin1")

    startxref = sum(len(p) for p in parts)
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF".encode("latin1")
    return b"".join(parts) + xref + trailer


def test_extract_text_from_pdf_digital():
    pdf_bytes = _create_minimal_pdf("WALMART STORE #1234")
    result = extract_text_from_pdf(pdf_bytes)
    assert "WALMART STORE #1234" in result


def test_extract_text_from_pdf_empty_or_no_text():
    empty_pdf_bytes = _create_minimal_pdf("")
    assert extract_text_from_pdf(empty_pdf_bytes) == ""


def test_extract_text_from_image_real():
    img = Image.new("RGB", (240, 60), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), "GROCERY", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = extract_text_from_image(buf.getvalue())
    assert "GROCERY" in result.upper()


def test_extract_text_detects_pdf_and_image(monkeypatch):
    monkeypatch.setattr("openfresh.receipts.extract_text_from_pdf", lambda b: "PDF TEXT")
    monkeypatch.setattr("openfresh.receipts.extract_text_from_image", lambda b: "OCR TEXT")

    assert extract_text(b"fake_pdf", "receipt.pdf") == "PDF TEXT"
    assert extract_text(b"fake_pdf", "RECEIPT.PDF") == "PDF TEXT"
    assert extract_text(b"fake_image", "receipt.jpg") == "OCR TEXT"
    assert extract_text(b"fake_image", "receipt.jpeg") == "OCR TEXT"
    assert extract_text(b"fake_image", "receipt.png") == "OCR TEXT"
    assert extract_text(b"fake_image", "receipt.webp") == "OCR TEXT"


def test_extract_text_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(b"some_bytes", "receipt.txt")
