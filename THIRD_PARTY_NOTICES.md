# Third-party notices

This source snapshot declares its Python and JavaScript dependencies in
`requirements.txt` and `next-app/package-lock.json`. Installed distributions
retain their own license files and notices.

The Track D PDF path uses these permissively licensed projects:

- [`pypdf`](https://github.com/py-pdf/pypdf) — BSD-3-Clause. It extracts PDF
  text, page dimensions, and embedded images.
- [`pypdfium2`](https://github.com/pypdfium2-team/pypdfium2) — Apache-2.0 or
  BSD-3-Clause for the Python bindings. Its PDFium binary distribution includes
  additional permissive third-party notices in the installed wheel. It renders
  scanned pages for the existing OCR fallback.

No PyMuPDF or MuPDF code or binary is included in this snapshot.

This notice summarizes relevant dependencies and does not replace their full
license texts. Review the license files shipped with installed packages when
redistributing dependency binaries.
