from __future__ import annotations


def test_image_records_caches_xref_digest_across_pages():
    import pymupdf as fitz

    from app.core.illustrations import _image_records

    doc = fitz.open()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 16, 16))
    pixmap.clear_with(180)
    png = pixmap.tobytes("png")

    doc.new_page()
    doc.new_page()
    xref = doc[0].insert_image(fitz.Rect(20, 20, 80, 80), stream=png)
    doc[1].insert_image(fitz.Rect(20, 20, 80, 80), xref=xref)
    first_page = doc[0]
    second_page = doc[1]

    class TrackingCache(dict):
        def __init__(self):
            super().__init__()
            self.missed_keys = []

        def get(self, key, default=None):
            if key not in self:
                self.missed_keys.append(key)
            return super().get(key, default)

    xref_digest_cache = TrackingCache()
    first_records = _image_records(first_page, xref_digest_cache)
    second_records = _image_records(second_page, xref_digest_cache)

    assert xref_digest_cache.missed_keys == [xref]
    assert [record[0] for record in first_records] == [xref]
    assert [record[0] for record in second_records] == [xref]
    assert first_records[0][1] == second_records[0][1]
    doc.close()
