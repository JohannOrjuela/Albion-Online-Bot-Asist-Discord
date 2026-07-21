from __future__ import annotations

import logging

import discord
from discord.ext import commands

from .config import ConfigError, Settings
from .database import Database
from .events import EventsCog
from .views import EventSignupView


LOGGER = logging.getLogger(__name__)


class AlbionGuildBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings
        self.database = Database(settings.database_path)

    async def setup_hook(self) -> None:
        self.database.initialize()
        await self.add_cog(EventsCog(self, self.database))
        for event in self.database.get_open_events():
            if event.message_id is not None:
                self.add_view(EventSignupView(self.database, event), message_id=event.message_id)

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            LOGGER.info("Sincronizados %s comandos en el servidor de desarrollo.", len(synced))
        else:
            synced = await self.tree.sync()
            LOGGER.info("Sincronizados %s comandos globales.", len(synced))

    async def on_ready(self) -> None:
        if self.user is not None:
            LOGGER.info("Bot conectado como %s (%s)", self.user, self.user.id)


def run() -> None:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        raise SystemExit(f"Error de configuración: {exc}") from exc
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    AlbionGuildBot(settings).run(settings.discord_token, log_handler=None)

