from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

from .build_renderer import BuildRenderer, item_icon_url
from .database import Database
from .domain import AlbionBuild


def build_summary_embed(build: AlbionBuild) -> discord.Embed:
    description = build.notes or "Build guardada del gremio."
    embed = discord.Embed(title=f"Build · {build.name}", description=description, color=0xD6A84B)
    equipment = [f"**{label}:** {item}" for label, item in build.equipment if item]
    embed.add_field(name="Equipamiento", value="\n".join(equipment), inline=False)
    if build.abilities:
        embed.add_field(name="Habilidades / orden", value=build.abilities[:1024], inline=False)
    details = []
    if build.activity:
        details.append(build.activity)
    if build.minimum_ip:
        details.append(f"IP mínimo {build.minimum_ip}")
    if details:
        embed.add_field(name="Uso", value=" · ".join(details), inline=False)
    embed.set_thumbnail(url=item_icon_url(build.weapon, size=128))
    embed.set_footer(text=f"Build #{build.id}")
    return embed


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return (cleaned or "build")[:80]


class BuildsCog(commands.Cog):
    build_group = app_commands.Group(name="build", description="Crea y consulta builds del gremio")

    def __init__(self, bot: commands.Bot, database: Database, renderer: BuildRenderer) -> None:
        self.bot = bot
        self.database = database
        self.renderer = renderer

    @build_group.command(name="crear", description="Guarda o actualiza una build y genera su imagen")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        nombre="Nombre único, por ejemplo Dawnsong Arena",
        arma="Nombre o identificador de Albion, por ejemplo Dawnsong",
        casco="Nombre o identificador del casco",
        pechera="Nombre o identificador de la pechera",
        botas="Nombre o identificador de las botas",
        secundaria="Mano secundaria; déjalo vacío para armas de dos manos",
        capa="Capa de la build",
        comida="Comida",
        pocion="Poción",
        habilidades="Habilidades elegidas u orden de uso",
        ip_minimo="IP mínimo solicitado",
        actividad="Arena, Avalon, HG, etc.",
        notas="Indicaciones adicionales",
    )
    async def create_build(
        self,
        interaction: discord.Interaction,
        nombre: str,
        arma: str,
        casco: str,
        pechera: str,
        botas: str,
        secundaria: str | None = None,
        capa: str | None = None,
        comida: str | None = None,
        pocion: str | None = None,
        habilidades: str | None = None,
        ip_minimo: app_commands.Range[int, 0, 3000] | None = None,
        actividad: str | None = None,
        notas: str | None = None,
    ) -> None:
        assert interaction.guild_id is not None
        await interaction.response.defer(ephemeral=True)
        build = self.database.save_build(
            guild_id=interaction.guild_id,
            name=nombre[:80], activity=(actividad or "")[:80], weapon=arma[:120],
            offhand=(secundaria or "")[:120], head=casco[:120], chest=pechera[:120],
            shoes=botas[:120], cape=(capa or "")[:120], food=(comida or "")[:120],
            potion=(pocion or "")[:120], abilities=(habilidades or "")[:1000],
            minimum_ip=ip_minimo, notes=(notas or "")[:1000],
        )
        image, missing = await self.renderer.render(build)
        warning = ""
        if missing:
            warning = "\n⚠️ Sin icono: " + ", ".join(missing)
        await interaction.followup.send(
            content=f"Build guardada correctamente.{warning}",
            embed=build_summary_embed(build),
            file=discord.File(image, filename=f"{safe_filename(build.name)}.png"),
            ephemeral=True,
        )

    @build_group.command(name="ver", description="Muestra una build guardada y su imagen")
    @app_commands.guild_only()
    @app_commands.describe(nombre="Nombre exacto de la build", privado="Mostrarla solo para ti")
    async def view_build(
        self, interaction: discord.Interaction, nombre: str, privado: bool = False
    ) -> None:
        assert interaction.guild_id is not None
        build = self.database.get_build(interaction.guild_id, nombre)
        if build is None:
            await interaction.response.send_message("No encontré esa build.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=privado)
        image, missing = await self.renderer.render(build)
        content = None
        if missing:
            content = "⚠️ No encontré iconos para: " + ", ".join(missing)
        await interaction.followup.send(
            content=content,
            embed=build_summary_embed(build),
            file=discord.File(image, filename=f"{safe_filename(build.name)}.png"),
            ephemeral=privado,
        )

    @build_group.command(name="listar", description="Lista las builds guardadas del gremio")
    @app_commands.guild_only()
    async def list_builds(self, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        builds = self.database.list_builds(interaction.guild_id)
        if not builds:
            await interaction.response.send_message("Todavía no hay builds guardadas.", ephemeral=True)
            return
        lines = [
            f"• **{build.name}**" + (f" — {build.activity}" if build.activity else "")
            for build in builds[:50]
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @build_group.command(name="eliminar", description="Elimina una build guardada")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_build(self, interaction: discord.Interaction, nombre: str) -> None:
        assert interaction.guild_id is not None
        deleted = self.database.delete_build(interaction.guild_id, nombre)
        message = "Build eliminada." if deleted else "No encontré esa build."
        await interaction.response.send_message(message, ephemeral=True)

    async def _build_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        needle = current.casefold()
        return [
            app_commands.Choice(name=build.name, value=build.name)
            for build in self.database.list_builds(interaction.guild_id)
            if needle in build.name.casefold()
        ][:25]

    @view_build.autocomplete("nombre")
    async def view_build_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._build_autocomplete(interaction, current)

    @delete_build.autocomplete("nombre")
    async def delete_build_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._build_autocomplete(interaction, current)
