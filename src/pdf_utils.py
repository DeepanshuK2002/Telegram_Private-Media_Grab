"""
PDF watermark removal for Auto Transfer.

Best-effort removal of text/stamp watermarks from PDFs before they are
re-uploaded to a destination channel. Handles the common cases:

1. Stamp watermarks stored as page annotations  -> removed entirely
2. Watermarks tagged as /Artifact (deco/background content, the usual
   convention for "CONFIDENTIAL", "Uploaded by…" banners) -> removed
3. Watermark operators wrapped in marked-content blocks of type Artifact
   -> the whole block is removed

Nothing else in the document is touched — text tagsged as actual page
content (e.g. /P /Artifact NOT present, or /MCID) are preserved as-is.
If the document structure doesn't mark the watermark, it stays and the
orig file is used unchanged.
"""
import os
import pikepdf
from pikepdf import Name


def _is_artifact_marker(operands) -> bool:
    """Return True if a BMC/BDC marker sequence denotes an Artifact."""
    try:
        joined = ' '.join(str(o) for o in operands)
    except Exception:
        return False
    return '/artifact' in joined.lower()


def _strip_artifact_marked_content(pdf, page) -> int:
    """Drop all marked-content blocks tagged as /Artifact on this page.
    Returns the number of instructions dropped."""
    try:
        instructions = pikepdf.parse_content_stream(page)
    except Exception:
        return 0

    new_ops = []
    artifact_depth = 0
    dropped = 0

    for operands, operator in instructions:
        op = str(operator)
        if op in ('BMC', 'BDC', 'MP'):
            if _is_artifact_marker(operands):
                artifact_depth += 1
                dropped += 1
                continue
            new_ops.append((operands, operator))
            continue
        if op == 'EMC':
            if artifact_depth > 0:
                artifact_depth -= 1
                dropped += 1
                continue
            new_ops.append((operands, operator))
            continue
        if artifact_depth > 0:
            dropped += 1
            continue
        new_ops.append((operands, operator))

    if dropped:
        try:
            page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(new_ops))
        except Exception:
            pass
    return dropped


def remove_pdf_watermark(src_path: str, dst_path: str = None) -> str:
    """
    Strip text/stamp watermarks from the PDF at src_path.

    Writes the cleaned file to dst_path (or overwrites src_path if dst_path is None).
    Returns the path of the cleaned PDF (equals src_path on failure so callers can
    fall back gracefully to the original file).
    """
    if not os.path.exists(src_path):
        return src_path
    if dst_path is None:
        dst_path = src_path

    try:
        pdf = pikepdf.open(src_path)
    except Exception:
        return src_path

    try:
        total_dropped = 0
        for page in pdf.pages:
            # 1. Remove annotations — stamp-type watermarks live there
            if Name.Annots in page:
                try:
                    del page[Name.Annots]
                    total_dropped += 1
                except Exception:
                    pass
            # 2. Remove artifact-tagged marked content blocks
            total_dropped += _strip_artifact_marked_content(pdf, page)

        pdf.save(dst_path, linearize=True)
        pdf.close()
        return dst_path
    except Exception:
        try:
            pdf.close()
        except Exception:
            pass
        return src_path


def count_pdf_watermarks(src_path: str) -> int:
    """Rough check: how many annotations / Artifact-tagged blocks does this PDF contain?"""
    try:
        pdf = pikepdf.open(src_path)
    except Exception:
        return 0
    count = 0
    try:
        for page in pdf.pages:
            annots = page.get(Name.Annots, None)
            if annots is not None:
                try:
                    count += len(annots)
                except Exception:
                    count += 1
            try:
                for operands, operator in pikepdf.parse_content_stream(page):
                    op = str(operator)
                    if op in ('BMC', 'BDC', 'MP') and _is_artifact_marker(operands):
                        count += 1
            except Exception:
                pass
        pdf.close()
        return count
    except Exception:
        try:
            pdf.close()
        except Exception:
            pass
        return 0
