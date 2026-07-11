"""Convert ECOnnect brand blue (#014999) to deep purple throughout all assets."""
import struct, io, os, sys
from PIL import Image
import colorsys

BRAND_BLUE_H = 212
TARGET_PURPLE_H = 277
HUE_SHIFT = TARGET_PURPLE_H - BRAND_BLUE_H

def pixel_blue_to_purple(r, g, b, a):
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    if 185 <= h * 360 <= 245 and s > 0.3 and v > 0.2:
        new_h = (h * 360 + HUE_SHIFT) / 360
        if new_h > 1: new_h -= 1
        nr, ng, nb = colorsys.hsv_to_rgb(new_h, s, v)
        return (int(nr*255), int(ng*255), int(nb*255), a)
    return (r, g, b, a)

def convert_png(path):
    img = Image.open(path).convert('RGBA')
    data = list(img.getdata())
    new_data = [pixel_blue_to_purple(r,g,b,a) for (r,g,b,a) in data]
    out = Image.new('RGBA', img.size)
    out.putdata(new_data)
    out.save(path)
    print(f"  OK {path}")

def make_ico_png(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()

def make_ico_dib(im):
    w, h = im.size
    rgba = list(im.getdata())
    bgras = bytearray()
    for r, g, b, a in rgba:
        bgras.extend([b, g, r, a])
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(bgras), 0, 0, 0, 0)
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
            byte_val = 0
            for bit in range(8):
                if x + bit < w:
                    byte_val |= (row_bits[x + bit] << (7 - bit))
            and_row.append(byte_val)
        pad = (4 - (len(and_row) % 4)) % 4
        and_row.extend([0] * pad)
        and_rows.extend(and_row)
    return hdr + bytes(xor_rows) + bytes(and_rows)

def png_to_ico(src_png, dst_ico):
    src = Image.open(src_png).convert("RGBA")
    sizes = [16, 32, 48, 64, 128, 256]
    entries = []
    data_blocks = []
    offset = 6 + len(sizes) * 16
    for size in sizes:
        im = src.resize((size, size), Image.LANCZOS) if size != src.size[0] else src
        if size <= 128:
            raw = make_ico_dib(im)
            wf, hf = size, size
        else:
            raw = make_ico_png(im)
            wf, hf = 0, 0
        entries.append((wf, hf, len(raw), offset))
        data_blocks.append(raw)
        offset += len(raw)
    with open(dst_ico, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(sizes)))
        for w, h, sz, off in entries:
            f.write(struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, sz, off))
        for blk in data_blocks:
            f.write(blk)
    print(f"  OK {dst_ico} ({os.path.getsize(dst_ico)}B)")

def convert_bmp(path):
    img = Image.open(path).convert('RGBA')
    data = list(img.getdata())
    new_data = [pixel_blue_to_purple(r,g,b,a) for (r,g,b,a) in data]
    out = Image.new('RGBA', img.size)
    out.putdata(new_data)
    out = out.convert('RGB')
    out.save(path, format='BMP')
    print(f"  OK {path}")

ASSETS = r"C:\Users\Suportee\Documents\Projetos ECO\ECOnnect\frontend\assets"
SCRIPTS = r"C:\Users\Suportee\Documents\Projetos ECO\ECOnnect\scripts\assets"
ROOT = r"C:\Users\Suportee\Documents\Projetos ECO\ECOnnect"

print("=== Converting PNGs ===")
for f in ["app_icon.png", "brand_mark.png",
          "logo_16.png", "logo_32.png", "logo_48.png",
          "logo_64.png", "logo_128.png", "logo_256.png"]:
    p = os.path.join(ASSETS, f)
    if os.path.exists(p):
        convert_png(p)

print("\n=== Regenerating .ico from app_icon.png ===")
png_to_ico(os.path.join(ASSETS, "app_icon.png"),
           os.path.join(ASSETS, "app_icon.ico"))
png_to_ico(os.path.join(ASSETS, "app_icon.png"),
           os.path.join(ROOT, "test_icon", "app_icon.ico"))

# Also convert original_icon.ico and Configurador Ecosis.ico
for src_name, dst_name in [
    (os.path.join(ASSETS, "app_icon.png"),
     os.path.join(ROOT, "original_icon.ico")),
    (os.path.join(ASSETS, "app_icon.png"),
     os.path.join(ROOT, "icons", "Configurador Ecosis.ico")),
]:
    png_to_ico(src_name, dst_name)

print("\n=== Converting wizard BMPs ===")
for f in ["wizard_image.bmp", "wizard_small.bmp"]:
    p = os.path.join(SCRIPTS, f)
    if os.path.exists(p):
        convert_bmp(p)

print("\n=== All done! ===")
