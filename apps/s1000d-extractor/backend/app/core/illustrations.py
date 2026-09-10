"""Extraction des illustrations d'un PDF -> fichiers JPG nommes.

On enregistre TOUTES les images du PDF (l'utilisateur veut pouvoir les
recuperer), en les nommant d'apres la legende voisine ("Figure 3 ..." ->
`figure-3-....jpg`) quand elle existe, sinon `illustration_<doc>_<n>.jpg`. Chaque
figure de l'IR recoit alors son ICN (nom de fichier) que le serialiseur
reference dans `<graphic infoEntityIdent=...>` au lieu du placeholder TODO.

PDF uniquement (via PyMuPDF). DOCX / OCR : no-op gracieux (aucune image extraite,
les figures gardent leur placeholder ICN).
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from app.core.ir import IRNode

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def slugify(text: str, *, maxlen: int = 60) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:maxlen].strip("-") or "illustration"


def _save_pixmap(doc, xref: int, dest: Path) -> bool:
    """Enregistre l'image `xref` en JPG. Convertit CMYK/alpha en RGB. Best-effort."""
    import fitz

    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n >= 5 or pix.alpha:            # CMYK ou canal alpha -> RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(str(dest), jpg_quality=85)
        return True
    except Exception:
        return False


def _image_digest(doc, xref: int) -> str | None:
    """Return a stable digest of the decoded image pixels."""
    import fitz

    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n >= 5 or pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return hashlib.sha256(pix.samples).hexdigest()
    except Exception:
        return None


def attach_illustrations(root: IRNode, *, pdf_path: str, out_dir: Path, doc_id: str) -> int:
    """Extrait les images du PDF, les enregistre en JPG et pose l'ICN sur les
    figures de l'IR (appariement par page + ordre de lecture). Renvoie le nombre
    d'images enregistrees. No-op si PyMuPDF echoue ou s'il n'y a pas d'image."""
    try:
        import fitz
    except Exception:
        return 0
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return 0

    # Figures de l'IR par page (dans l'ordre), pour le nommage.
    figs_by_page: dict[int, list[IRNode]] = {}
    for n in root.walk():
        if n.kind == "figure" and n.page is not None:
            figs_by_page.setdefault(n.page, []).append(n)

    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    # `seen` est GLOBAL au document : une meme image (xref) reutilisee sur
    # plusieurs pages (logo, bandeau, figure repetee) ne doit etre extraite
    # qu'UNE fois, sinon le dossier se remplit de doublons.
    seen: set[int] = set()
    seen_digests: set[str] = set()
    try:
        for pidx, page in enumerate(doc, start=1):
            figs = list(figs_by_page.get(pidx, []))
            for img in page.get_images(full=True):
                xref = int(img[0])
                if xref in seen:
                    continue
                seen.add(xref)
                digest = _image_digest(doc, xref)
                if digest is not None and digest in seen_digests:
                    continue
                if digest is not None:
                    seen_digests.add(digest)
                fig = figs.pop(0) if figs else None
                base = slugify(fig.text) if fig and fig.text else f"illustration-{doc_id[:8]}-p{pidx}-{xref}"
                name = _unique_name(out_dir, base)
                if _save_pixmap(doc, xref, out_dir / name):
                    saved += 1
                    if fig is not None:
                        fig.icn = name
        return saved
    finally:
        doc.close()


def rename_illustration(out_dir: Path, current_name: str, target_name: str) -> str | None:
    """Renomme une image extraite, en convertissant son format si necessaire."""
    current = Path(current_name)
    target = Path(target_name)
    if current.name != current_name or target.name != target_name:
        return None
    if current.suffix.lower() not in _IMAGE_SUFFIXES or target.suffix.lower() not in _IMAGE_SUFFIXES:
        return None

    source = out_dir / current_name
    if not source.exists():
        return None
    if _same_path(source, out_dir / target_name):
        return source.name

    final_name = _unique_filename(out_dir, target_name, exclude=source)
    destination = out_dir / final_name
    try:
        if current.suffix.lower() == target.suffix.lower():
            source.replace(destination)
        else:
            import fitz

            pix = fitz.Pixmap(str(source))
            if pix.n >= 5 or pix.alpha:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if target.suffix.lower() == ".png":
                pix.save(str(destination), output="png")
            else:
                pix.save(str(destination), output="jpg", jpg_quality=85)
            source.unlink()
    except Exception:
        destination.unlink(missing_ok=True)
        return None
    return final_name


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


def _unique_filename(out_dir: Path, filename: str, *, exclude: Path | None = None) -> str:
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix
    name = filename
    n = 2
    while (out_dir / name).exists() and not (exclude and _same_path(out_dir / name, exclude)):
        name = f"{stem}-{n}{suffix}"
        n += 1
    return name


def _unique_name(out_dir: Path, base: str) -> str:
    """Nom de fichier libre : deux legendes identiques ne doivent pas s'ecraser."""
    return _unique_filename(out_dir, f"{base}.jpg")
