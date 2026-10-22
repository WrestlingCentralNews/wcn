import struct, zlib, imgmeta
def _png(W, H, box):
    """RGBA PNG: opaque inside box (x0, y0, x1, y1), transparent elsewhere; mixed filters to exercise the decoder."""
    x0, y0, x1, y1 = box; raw = b""
    for y in range(H):
        row = bytes(b for x in range(W) for b in ((200, 50, 10, 255) if x0 <= x < x1 and y0 <= y < y1 else (0, 0, 0, 0)))
        raw += b"\x00" + row
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")
def test_padded_canvas():
    # Fightful 2026-10-22: 1920x1280 sheet with a 775x434 photo in the middle -> rejected; the -e crop is kept
    b = _png(96, 64, (28, 11, 67, 33))
    assert imgmeta.alpha_box(b) == (96, 64, 28, 11, 67, 33)
    assert imgmeta.is_padded(imgmeta.alpha_box(b))
    assert not imgmeta.is_padded(imgmeta.alpha_box(_png(40, 24, (1, 1, 40, 24))))
def test_too_small_and_fill(monkeypatch=None):
    imgmeta._C = {"https://x/logo.png": {"best": ["https://x/logo.png", 220, 100], "v": 3},
                  "https://x/sheet.png": {"best": ["https://x/sheet.png", None, None, "padded"], "v": 3},
                  "https://x/ok.jpg": {"best": ["https://x/ok-big.jpg", 1600, 900], "v": 3}}
    cl = [{"image": "https://x/logo.png"}, {"image": "https://x/sheet.png"}, {"image": "https://x/ok.jpg"},
          {"image": "https://x/logo.png", "image_status": "override"}]
    imgmeta.apply(cl)
    assert cl[0]["image"] is None and cl[0]["image_status"] == "too-small"
    assert cl[1]["image"] is None and cl[1]["image_status"] == "padded"
    assert cl[2]["image"] == "https://x/ok-big.jpg" and cl[2]["img_w"] == 1600
    assert cl[3]["image"] == "https://x/logo.png"
    assert imgmeta.fill_cls(1600, 900) == " fill" and imgmeta.fill_cls(800, 1000) == "" and imgmeta.fill_cls(None, 5) == ""
    imgmeta._C = None
