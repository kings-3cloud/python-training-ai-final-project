"""
PdfExtractor — extracts plain text from PDF bytes.

Single Responsibility: only responsible for PDF-to-text extraction.
"""
import io

import PyPDF2

DEFAULT_MAX_CHARS = 4000


class PdfExtractor:
    """Extracts plain text from in-memory PDF bytes."""

    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS) -> None:
        self.max_chars = max_chars

    def extract(self, file_bytes: bytes) -> tuple[str, bool]:
        """
        Extract text from PDF bytes.

        Args:
            file_bytes: Raw PDF content.

        Returns:
            A tuple of (extracted_text, truncated) where truncated is True
            if the text was longer than max_chars and was cut.

        Raises:
            ValueError: If the bytes are not a valid PDF or contain no
                        extractable text (e.g. image-only PDFs).
        """
        if not file_bytes.startswith(b'%PDF'):
            raise ValueError("File does not appear to be a valid PDF.")

        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or '' for page in reader.pages]
        text = '\n'.join(pages).strip()

        if not text:
            raise ValueError(
                "No text could be extracted — the PDF may be image-only."
            )

        truncated = len(text) > self.max_chars
        return text[:self.max_chars], truncated
