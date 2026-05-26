"""从 app_icon.png 生成带白底的多尺寸 ICO（Windows 桌面不透明）。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

ASSETS = Path(__file__).resolve().parent
SRC = ASSETS / "app_icon.png"
ICO = ASSETS / "app_icon.ico"
PNG256 = ASSETS / "app_icon_256.png"
PNG512 = ASSETS / "app_icon_512.png"
MASTER_SIZE = 1024
WHITE = (255, 255, 255)


def _prepare_source(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, WHITE)
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB")


def _fit_in_square(img: Image.Image, side: int, fill_ratio: float = 0.92) -> Image.Image:
    canvas = Image.new("RGB", (side, side), WHITE)
    max_side = int(side * fill_ratio)
    width, height = img.size
    scale = min(max_side / width, max_side / height)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    resized = img.resize(new_size, Image.Resampling.LANCZOS)
    x = (side - new_size[0]) // 2
    y = (side - new_size[1]) // 2
    canvas.paste(resized, (x, y))
    return canvas


def _compact_mark(img: Image.Image) -> Image.Image:
    width, height = img.size
    compact = img.crop((0, 0, int(width * 0.36), height))
    return _fit_in_square(compact, MASTER_SIZE, fill_ratio=0.98)


def _full_wordmark(img: Image.Image) -> Image.Image:
    return _fit_in_square(img, MASTER_SIZE, fill_ratio=0.94)


def _render_size(master: Image.Image, size: int, *, sharpen: bool) -> Image.Image:
    out = master.resize((size, size), Image.Resampling.LANCZOS)
    if sharpen:
        out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=150, threshold=1))
    return out


def _as_opaque_icon(img: Image.Image) -> Image.Image:
    """Windows 桌面图标：全不透明 RGBA，白底 alpha=255。"""
    rgb = img.convert("RGB")
    opaque = Image.new("RGBA", rgb.size, (255, 255, 255, 255))
    opaque.paste(rgb, (0, 0))
    return opaque


def _save_ico(path: Path, images: list[Image.Image]) -> None:
    frames = [_as_opaque_icon(image) for image in images]
    sizes = [(frame.width, frame.height) for frame in frames]
    frames[0].save(path, format="ICO", sizes=sizes, append_images=frames[1:])


def build_icon() -> None:
    source = _prepare_source(Image.open(SRC))
    full_master = _full_wordmark(source)
    compact_master = _compact_mark(source)

    full_master.resize((512, 512), Image.Resampling.LANCZOS).save(PNG512, format="PNG", optimize=False)
    full_master.resize((256, 256), Image.Resampling.LANCZOS).save(PNG256, format="PNG", optimize=False)

    size_plan: list[tuple[int, bool, Image.Image]] = [
        (256, False, full_master),
        (128, False, full_master),
        (64, True, full_master),
        (48, True, compact_master),
        (32, True, compact_master),
        (24, True, compact_master),
        (16, True, compact_master),
    ]

    frames = [_render_size(master, size, sharpen=sharpen) for size, sharpen, master in size_plan]
    _save_ico(ICO, frames)
    print(f"saved {ICO} ({ICO.stat().st_size} bytes), {len(frames)} sizes")


if __name__ == "__main__":
    build_icon()
