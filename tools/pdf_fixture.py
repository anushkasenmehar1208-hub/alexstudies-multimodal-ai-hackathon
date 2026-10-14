"""Build tiny deterministic PDFs for local tests and evaluation fixtures."""

from __future__ import annotations

from io import BytesIO
import zlib

from PIL import Image


def _pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(
    pages: list[tuple[float, float, str, bytes | None]],
) -> bytes:
    """Return a small PDF with extractable text and an optional PNG per page."""
    page_count = len(pages)
    font_id = 3 + page_count
    content_ids = [font_id + 1 + index for index in range(page_count)]
    next_id = font_id + 1 + page_count
    image_ids: list[int | None] = []
    image_payloads: list[tuple[int, bytes, int, int]] = []

    for _width, _height, _text, png in pages:
        if png is None:
            image_ids.append(None)
            continue
        image = Image.open(BytesIO(png)).convert("RGB")
        image_id = next_id
        next_id += 1
        image_ids.append(image_id)
        image_payloads.append((image_id, zlib.compress(image.tobytes()), image.width, image.height))

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            f"<< /Type /Pages /Count {page_count} /Kids "
            f"[{' '.join(f'{3 + index} 0 R' for index in range(page_count))}] >>"
        ).encode("ascii"),
        font_id: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }

    for index, (width, height, text, _png) in enumerate(pages):
        image_id = image_ids[index]
        resources = f"/Font << /F1 {font_id} 0 R >>"
        if image_id is not None:
            resources += f" /XObject << /Im1 {image_id} 0 R >>"
        objects[3 + index] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:g} {height:g}] "
            f"/Resources << {resources} >> /Contents {content_ids[index]} 0 R >>"
        ).encode("ascii")

        lines = text.splitlines() or [""]
        commands = [f"BT /F1 12 Tf 36 {height - 52:g} Td 15 TL"]
        commands.extend(f"({_pdf_text(line)}) Tj T*" for line in lines)
        commands.append("ET")
        if image_id is not None:
            commands.append("q 90 0 0 60 40 150 cm /Im1 Do Q")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        objects[content_ids[index]] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

    for image_id, payload, width, height in image_payloads:
        objects[image_id] = (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
            f"/Length {len(payload)} >>\nstream\n".encode("ascii")
            + payload
            + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, next_id):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {next_id}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {next_id} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)
