from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class HelpCog(commands.Cog):
    @app_commands.command(name="help", description="Muestra todos los comandos del bot")
    @app_commands.guild_only()
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="📖 Ayuda · Albion Alliance Bot",
            description=(
                "Los eventos usan la **hora UTC del juego** para hoy. "
                "Los comandos marcados con 🔐 requieren **Gestionar servidor**."
            ),
            color=0x6C5CE7,
        )
        embed.add_field(
            name="📅 Eventos",
            value=(
                "🔐 `/evento hellgate` — Hellgate 5v5\n"
                "🔐 `/evento arena` — Arena de Cristal\n"
                "🔐 `/evento liga` — Liga 5v5 con confirmación\n"
                "🔐 `/evento caminos` — PvE, PvP, Rastreo o Transporte\n"
                "🔐 `/evento estatica` — Fame farm, pulls o PvP\n"
                "🔐 `/evento grupal` — Mazmorras grupales\n"
                "🔐 `/evento desde-plantilla` — Publica una composición guardada\n"
                "`/evento cerrar` — Cierra las inscripciones"
            ),
            inline=False,
        )
        embed.add_field(
            name="🧩 Plantillas",
            value=(
                "🔐 `/plantilla crear` — Crea una composición\n"
                "🔐 `/plantilla rol` — Añade o actualiza un rol/build\n"
                "🔐 `/plantilla quitar-rol` — Quita un rol\n"
                "`/plantilla ver` — Muestra una plantilla\n"
                "`/plantilla listar` — Lista las plantillas\n"
                "🔐 `/plantilla eliminar` — Elimina una plantilla"
            ),
            inline=False,
        )
        embed.add_field(
            name="🛡️ Builds",
            value=(
                "🔐 `/build crear` — Guarda o actualiza una build\n"
                "`/build ver` — Muestra la build y su imagen\n"
                "`/build listar` — Lista las builds\n"
                "🔐 `/build eliminar` — Elimina una build"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Configuración",
            value=(
                "🔐 `/config emoji` — Configura el emoji de un rol\n"
                "`/config ver-emojis` — Muestra los emojis configurados\n"
                "`/help` — Abre este panel"
            ),
            inline=False,
        )
        embed.add_field(
            name="🚀 Flujo recomendado",
            value=(
                "1. Crea las builds con `/build crear`.\n"
                "2. Crea una composición con `/plantilla crear`.\n"
                "3. Asigna roles y builds con `/plantilla rol`.\n"
                "4. Selecciona esa plantilla al usar `/evento liga` u otro evento."
            ),
            inline=False,
        )
        embed.set_footer(text="El panel es privado: solamente tú puedes verlo.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog())
