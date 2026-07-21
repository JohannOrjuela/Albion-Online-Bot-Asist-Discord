from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
import textwrap
from urllib.parse import quote

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from .domain import AlbionBuild


RENDER_BASE_URL = "https://render.albiononline.com/v1/item"
CANVAS_SIZE = (1600, 900)
SLOT_POSITIONS = {
    "Mano secundaria": (75, 185),
    "Casco": (285, 185),
    "Capa": (495, 185),
    "Arma": (75, 400),
    "Pechera": (285, 400),
    "Poción": (75, 615),
    "Botas": (285, 615),
    "Comida": (495, 615),
}


def item_icon_url(identifier_or_name: str, *, size: int = 180, locale: str = "es") -> str:
    identifier = quote(identifier_or_name.strip(), safe="@")
    return f"{RENDER_BASE_URL}/{identifier}.png?quality=1&size={size}&locale={locale}"


class BuildRenderer:
    def __init__(self, cache_directory: Path) -> None:
        self.cache_directory = cache_directory
        self.cache_directory.mkdir(parents=True, exist_ok=True)

    async def render(self, build: AlbionBuild) -> tuple[BytesIO, list[str]]:
        equipment = [(label, item) for label, item in build.equipment if item]
        results = await asyncio.gather(
            *(self._get_icon(item) for _, item in equipment), return_exceptions=True
        )
        icons: dict[str, Image.Image] = {}
        missing: list[str] = []
        for (label, item), result in zip(equipment, results, strict=True):
            if isinstance(result, BaseException) or result is None:
                missing.append(item)
            else:
                icons[label] = result
        image = await asyncio.to_thread(self._compose, build, icons)
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        output.seek(0)
        return output, missing

    async def _get_icon(self, item: str) -> Image.Image | None:
        cache_key = hashlib.sha256(item.casefold().encode("utf-8")).hexdigest()
        cache_path = self.cache_directory / f"{cache_key}.png"
        if cache_path.exists():
            try:
                return await asyncio.to_thread(self._open_image, cache_path)
            except OSError:
                cache_path.unlink(missing_ok=True)

        timeout = aiohttp.ClientTimeout(total=35, connect=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = None
            for locale in ("es", "en"):
                try:
                    async with session.get(item_icon_url(item, locale=locale)) as response:
                        if response.status == 200 and response.content_type == "image/png":
                            payload = await response.read()
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    continue
            if payload is None:
                return None
        cache_path.write_bytes(payload)
        return await asyncio.to_thread(self._open_image, cache_path)

    @staticmethod
    def _open_image(path: Path) -> Image.Image:
        with Image.open(path) as image:
            return image.convert("RGBA")

    def _compose(self, build: AlbionBuild, icons: dict[str, Image.Image]) -> Image.Image:
        canvas = Image.new("RGB", CANVAS_SIZE, "#0c0f12")
        draw = ImageDraw.Draw(canvas)
        title_font = self._fitted_font(draw, build.name, 620, maximum=52, minimum=28)
        heading_font = self._font(30, bold=True)
        body_font = self._font(25)
        small_font = self._font(21)

        draw.rounded_rectangle((30, 25, 730, 865), radius=28, fill="#13171b", outline="#2d343b", width=3)
        draw.rounded_rectangle((765, 25, 1570, 865), radius=28, fill="#171b20", outline="#2d343b", width=3)
        draw.text((65, 52), build.name, fill="#f5f5f5", font=title_font)
        subtitle = build.activity or "Build de Albion Online"
        if build.minimum_ip:
            subtitle += f"  ·  IP mínimo {build.minimum_ip}"
        draw.text((67, 125), textwrap.shorten(subtitle, width=58, placeholder="…"), fill="#b9c0c8", font=small_font)

        for label, item in build.equipment:
            if not item:
                continue
            x, y = SLOT_POSITIONS[label]
            draw.rounded_rectangle((x, y, x + 170, y + 160), radius=22, fill="#22272d")
            icon = icons.get(label)
            if icon is not None:
                icon.thumbnail((150, 150), Image.Resampling.LANCZOS)
                canvas.paste(icon, (x + 10, y + 5), icon)
            else:
                draw.text((x + 67, y + 61), "?", fill="#6f7882", font=title_font)
            short_name = textwrap.shorten(item, width=22, placeholder="…")
            text_box = draw.textbbox((0, 0), short_name, font=small_font)
            text_width = text_box[2] - text_box[0]
            draw.text((x + 85 - text_width / 2, y + 164), short_name, fill="#d5d9dd", font=small_font)

        draw.text((810, 62), "Equipamiento", fill="#ffffff", font=heading_font)
        y = 120
        for label, item in build.equipment:
            if not item:
                continue
            draw.text((810, y), f"{label}:", fill="#8dc6ff", font=small_font)
            draw.text((1030, y), textwrap.shorten(item, width=38, placeholder="…"), fill="#f1f3f5", font=small_font)
            y += 46

        if build.abilities:
            y += 12
            draw.text((810, y), "Habilidades / orden", fill="#ffffff", font=heading_font)
            y += 54
            for line in textwrap.wrap(build.abilities, width=52):
                draw.text((810, y), line, fill="#d5d9dd", font=body_font)
                y += 38

        if build.notes:
            y += 20
            draw.text((810, y), "Notas", fill="#ffffff", font=heading_font)
            y += 54
            for line in textwrap.wrap(build.notes, width=56)[:5]:
                draw.text((810, y), line, fill="#b9c0c8", font=small_font)
                y += 34
        draw.text((810, 820), "Generado por Albion Guild Bot", fill="#69727c", font=small_font)
        return canvas

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = (
            Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )
        for path in candidates:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        return ImageFont.load_default()

    def _fitted_font(
        self, draw: ImageDraw.ImageDraw, text: str, maximum_width: int,
        *, maximum: int, minimum: int,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for size in range(maximum, minimum - 1, -2):
            font = self._font(size, bold=True)
            box = draw.textbbox((0, 0), text, font=font)
            if box[2] - box[0] <= maximum_width:
                return font
        return self._font(minimum, bold=True)
