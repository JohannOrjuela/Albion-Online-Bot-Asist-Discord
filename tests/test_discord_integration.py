from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from albion_bot.app import AlbionGuildBot
from albion_bot.builds import BuildsCog
from albion_bot.configuration import ConfigurationCog
from albion_bot.config import Settings
from albion_bot.events import EventsCog
from albion_bot.templates import TemplatesCog


class DiscordIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings(
            discord_token="test-token",
            guild_id=123,
            timezone=ZoneInfo("America/Bogota"),
            database_path=Path(self.temp_dir.name) / "test.db",
            log_level="INFO",
        )
        self.bot = AlbionGuildBot(settings)

    async def asyncTearDown(self) -> None:
        await self.bot.close()
        self.temp_dir.cleanup()

    async def test_event_command_group_can_be_registered(self) -> None:
        await self.bot.add_cog(EventsCog(self.bot, self.bot.database))
        await self.bot.add_cog(
            BuildsCog(self.bot, self.bot.database, self.bot.build_renderer)
        )
        await self.bot.add_cog(TemplatesCog(self.bot, self.bot.database))
        await self.bot.add_cog(ConfigurationCog(self.bot.database))
        group = self.bot.tree.get_command("evento")
        self.assertIsNotNone(group)
        self.assertEqual(
            {command.name for command in group.commands},
            {"crear", "cerrar", "desde-plantilla"},
        )
        self.assertEqual(
            {command.name for command in self.bot.tree.get_commands()},
            {"evento", "build", "plantilla", "config"},
        )


if __name__ == "__main__":
    unittest.main()
