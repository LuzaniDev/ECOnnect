"""Build .ico with BMP DIB for <=128px and PNG for 256px (Windows PE compatible)."""
import struct
import io
from PIL import Image

SRC = "frontend/assets/app_icon.png"
DST = "frontend/assets/app_icon.ico"
SIZES = [16, 32, 48, 64, 128, 256]

def _make_png(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()

def _make_bmp_dib(im):
    w, h = im.size
    rgba = list(im.getdata())
    bgras = bytearray()
    for r, g, b, a in rgba:
        bgras.extend([b, g, r, a])
    hdr = struct.pack(
        "<IiiHHIIiiII",
        40, w, h * 2, 1, 32, 0, len(bgras), 0, 0, 0, 0,
    )
    xor_rows = bytearray()
    for y in range(h - 1, -1, -1):
        xor_rows.extend(bgras[y * w * 4 : (y + 1) * w * 4])
    and_rows = bytearray()
    for y in range(h - 1, -1, -1):
        row_bits = bytearray()
        for x in range(w):
            _, _, _, a = rgba[y * w + x]
            row_bits.append(0 if a >= 128 else 1)
        and_row = bytearray()
        for x in range(0, w, 8):
            byte = 0
            for bit in range(8):
                if x + bit < w:
                    byte |= (row_bits[x + bit] << (7 - bit))
            and_row.append(byte)
        pad = (4 - (len(and_row) % 4)) % 4
        and_row.extend([0] * pad)
        and_rows.extend(and_row)
    return hdr + bytes(xor_rows) + bytes(and_rows)

def main():
    src = Image.open(SRC).convert("RGBA")
    entries = []
    data_blocks = []
    offset = 6 + len(SIZES) * 16
    for size in SIZES:
        im = src.resize((size, size), Image.LANCZOS) if size != src.size[0] else src
        if size <= 128:
            raw = _make_bmp_dib(im)
            wf, hf = size, size
        else:
            raw = _make_png(im)
            wf, hf = 0, 0
        entries.append((wf, hf, len(raw), offset))
        data_blocks.append(raw)
        offset += len(raw)
    with open(DST, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(SIZES)))
        for w, h, sz, off in entries:
            f.write(struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, sz, off))
        for blk in data_blocks:
            f.write(blk)
    print(f"ICO written: {len(open(DST,'rb').read())}B")
    with open(DST, "rb") as f:
        raw = f.read()
        cnt = struct.unpack_from("<H", raw, 4)[0]
        pos = 6
        for i in range(cnt):
            w = raw[pos]; h = raw[pos+1]
            sz = struct.unpack_from("<I", raw, pos+8)[0]
            off = struct.unpack_from("<I", raw, pos+12)[0]
            magic = raw[off:off+4]
            fmt = "PNG" if magic[:2]==b'\x89P' else "DIB"
            print(f"  {i}: {w}x{h} {sz}B [{fmt}]")
            pos += 16

if __name__ == "__main__":
    main()
