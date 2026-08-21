# Document intake

Jafar accepts `.txt`, `.md`, `.markdown`, `.pdf`, and `.docx` documents up to 20 MB.

The intake layer extracts text only. It does not automatically send email, publish content, or change a legal matter. The extracted text is passed to the legal analysis layer, where the caller explicitly selects the task and matter type.

PDF and DOCX extraction require the optional `pypdf` and `python-docx` dependencies. Scanned/image-only PDFs are not treated as successfully extracted text; OCR is a separate next-stage component.
