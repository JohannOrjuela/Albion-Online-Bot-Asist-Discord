from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .database import Database
from .parsing import slugify
from .templates import normalized_emoji


class ConfigurationCog(commands.Cog):
    config_group = app_commands.Group(name="config", description="Configura el bot del gremio")

    def __init__(self, database: Database) -> None:
        self.database = database

    @config_group.command(name="emoji", description="Asocia un emoji predeterminado a un rol")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        rol="Nombre del rol, por ejemplo Dawnsong o Healer",
        emoji="Emoji Unicode o emoji personalizado del servidor",
    )
    async def set_emoji(
        self, interaction: discord.Interaction, rol: str, emoji: str
    ) -> None:
        assert interaction.guild_id is not None
        try:
            value = normalized_emoji(emoji)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        key = slugify(rol)
        self.database.set_role_emoji(interaction.guild_id, key, value)
        await interaction.response.send_message(
            f"Emoji configurado: {value} **{rol.strip()}**", ephemeral=True
        )

    @config_group.command(name="ver-emojis", description="Muestra los emojis configurados")
    @app_commands.guild_only()
    async def view_emojis(self, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        values = self.database.get_role_emojis(interaction.guild_id)
        if not values:
            await interaction.response.send_message("No hay emojis personalizados.", ephemeral=True)
            return
        lines = [f"{emoji} `{role}`" for role, emoji in sorted(values.items())]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

