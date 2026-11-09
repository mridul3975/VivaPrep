"""Bounded extraction of uploaded text and PDF evidence; uploaded code never runs."""
import hashlib
import io
import logging
import multiprocessing
from pathlib import Path
from threading import BoundedSemaphore

from backend.evidence.read import chunk_text


TEXT_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".txt", ".java", ".c", ".cpp", ".h", ".css", ".html", ".json", ".yaml", ".yml"}
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_BYTES = 256 * 1024
MAX_EXTRACTED_CHARS = 200_000
MAX_PDF_PAGES = 20
PDF_TIMEOUT_SECONDS = 15
pdf_gate = BoundedSemaphore(1)


class DocumentError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _pdf_worker(data, sender):
    """Isolate PDF parsing from the web worker and bound Linux CPU/memory use."""
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        except ImportError:
            pass  # Windows still uses the parent process's wall-time limit.
        from pypdf import PdfReader
        logging.getLogger("pypdf").disabled = True
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            sender.send({"error": "Password-protected PDFs are not supported. Upload an unencrypted copy."})
            return
        if not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
            sender.send({"error": "Choose a PDF with 1 to 20 pages."})
            return
        pages, total = [], 0
        for number, page in enumerate(reader.pages, 1):
            stream = page.get_contents()
            if stream is not None and len(stream.get_data()) > 2 * 1024 * 1024:
                sender.send({"error": "This PDF page is too complex. Upload a simpler or smaller PDF."})
                return
            text = page.extract_text() or ""
            total += len(text)
            if total > MAX_EXTRACTED_CHARS:
                sender.send({"error": "The extracted text is too large. Upload a shorter document."})
                return
            pages.append((number, text))
        sender.send({"pages": pages})
    except Exception:
        sender.send({"error": "The PDF could not be read. Upload a valid, simpler PDF."})
    finally:
        sender.close()


def _extract_pdf(data):
    if not pdf_gate.acquire(blocking=False):
        raise DocumentError("Another PDF is being processed. Please retry shortly.", 503)
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_pdf_worker, args=(data, sender), daemon=True)
    started = False
    try:
        process.start()
        started = True
        sender.close()
        if not receiver.poll(PDF_TIMEOUT_SECONDS):
            raise DocumentError("PDF processing took too long. Upload a smaller or simpler PDF.")
        try:
            result = receiver.recv()
        except EOFError as error:
            raise DocumentError("PDF processing failed. Upload a smaller or simpler PDF.") from error
        if "error" in result:
            raise DocumentError(result["error"])
        return result["pages"]
    finally:
        sender.close()
        receiver.close()
        if started:
            process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            process.close()
        pdf_gate.release()


def extract_document(filename, data):
    extension = Path(filename).suffix.lower()
    if extension not in TEXT_EXTENSIONS and extension != ".pdf":
        raise DocumentError("Choose a supported source/text file or a PDF.", 415)
    if not data:
        raise DocumentError("The uploaded file is empty.")
    if len(data) > MAX_FILE_BYTES or (extension != ".pdf" and len(data) > MAX_TEXT_BYTES):
        raise DocumentError("PDFs must be at most 5 MiB; source/text files at most 256 KiB.", 413)

    warnings = []
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentError("This file is not a valid PDF.", 415)
        pages = _extract_pdf(data)
        snippets = []
        for page, text in pages:
            if not text.strip():
                warnings.append(f"Page {page} has no extractable text and was skipped.")
                continue
            for record in chunk_text(text, filename):
                record.update({"citation_type": "page", "page": page, "start_line": None, "end_line": None})
                snippets.append(record)
        if not snippets:
            raise DocumentError("No readable text was found. Scanned/image-only PDFs need OCR; upload a searchable PDF or text file.")
        metadata = {"kind": "pdf", "page_count": len(pages), "line_count": None}
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DocumentError("Save the source/text file as UTF-8 and upload it again.") from error
        if "\x00" in text or not text.strip():
            raise DocumentError("Choose a non-empty readable text file; binary files are not supported.")
        if len(text) > MAX_EXTRACTED_CHARS:
            raise DocumentError("The source text is too large. Upload a shorter file.", 413)
        snippets = chunk_text(text, filename)
        for record in snippets:
            record.update({"citation_type": "lines", "page": None})
        metadata = {"kind": "text", "page_count": None, "line_count": len(text.splitlines())}

    return {"filename": filename, "revision": hashlib.sha256(data).hexdigest(),
            "snippets": snippets, "snippet_count": len(snippets), "warnings": warnings, **metadata}
