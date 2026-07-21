from pathlib import Path
import tempfile
import unittest

from albion_bot.build_renderer import BuildRenderer, item_icon_url
from albion_bot.domain import AlbionBuild


class BuildRendererTests(unittest.TestCase):
    def test_item_url_encodes_localized_name(self) -> None:
        url = item_icon_url("Báculo de fuego")
        self.assertIn("B%C3%A1culo%20de%20fuego.png", url)
        self.assertIn("locale=es", url)
        self.assertIn("locale=en", item_icon_url("Dawnsong", locale="en"))

    def test_composes_image_without_remote_icons(self) -> None:
        build = AlbionBuild(
            id=1, guild_id=1, name="Prueba", activity="Arena", weapon="Dawnsong",
            offhand="", head="Royal Cowl", chest="Feyscale Robe", shoes="Cleric Sandals",
            cape="", food="", potion="", abilities="Q1, W2, E", minimum_ip=1200,
            notes="Build de prueba",
        )
        with tempfile.TemporaryDirectory() as directory:
            renderer = BuildRenderer(Path(directory))
            image = renderer._compose(build, {})
        self.assertEqual(image.size, (1600, 900))


if __name__ == "__main__":
    unittest.main()
