from PIL import Image, ImageDraw
from pathlib import Path

ASSETS = Path(__file__).parent.parent / "frontend" / "assets"
OUTPUT = Path(__file__).parent / "assets"

BG_COLOR = (1, 73, 153)       # #014999 - azul Eco Centauro
ACCENT_COLOR = (248, 137, 29)  # #f8891d - laranja Eco Centauro


def create_wizard_image():
    img = Image.new("RGBA", (164, 314), BG_COLOR)
    logo_path = ASSETS / "logo_256.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((120, 120))
        x = (164 - logo.width) // 2
        y = 50
        img.paste(logo, (x, y), logo)
    draw = ImageDraw.Draw(img)
    bar_y = 314 - 4
    draw.rectangle((0, bar_y, 164, 314), fill=ACCENT_COLOR)
    img.save(OUTPUT / "wizard_image.bmp")


def create_wizard_small():
    img = Image.new("RGBA", (55, 55), BG_COLOR)
    logo_path = ASSETS / "brand_mark.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((44, 44))
        x = (55 - logo.width) // 2
        y = (55 - logo.height) // 2
        img.paste(logo, (x, y), logo)
    img.save(OUTPUT / "wizard_small.bmp")


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    create_wizard_image()
    create_wizard_small()
    print("Installer images generated successfully.")
