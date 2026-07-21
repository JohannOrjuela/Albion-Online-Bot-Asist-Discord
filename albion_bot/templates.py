from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .activities import ACTIVITIES
from .database import Database
from .domain import CompositionTemplate
from .parsing import SLOT_EMOJIS, slugify


ACTIVITY_CHOICES = [
    app_commands.Choice(name=preset.label, value=preset.key)
    for preset in ACTIVITIES.values()
]


def template_embed(template: CompositionTemplate) -> discord.Embed:
    preset = ACTIVITIES.get(template.activity)
    embed = discord.Embed(
        title=f"Plantilla · {template.name}",
        description=template.description or "Composición reutilizable del gremio.",
        color=preset.color if preset else 0x5865F2,
    )
    embed.add_field(
        name="Actividad", value=preset.label if preset else template.activity, inline=False
    )
    if template.slots:
        lines = []
        for slot in template.slots:
            build = f" → `{slot.build_name}`" if slot.build_name else ""
            lines.append(f"{slot.emoji} **{slot.label}** × {slot.capacity}{build}")
        embed.add_field(name="Composición", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Composición", value="Aún no tiene roles.", inline=False)
    embed.set_footer(text=f"Plantilla #{template.id}")
    return embed


def normalized_emoji(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 100:
        raise ValueError("El emoji está vacío o es demasiado largo.")
    parsed = discord.PartialEmoji.from_str(cleaned)
    if parsed.name is None:
        raise ValueError("No pude reconocer ese emoji.")
    return str(parsed)


class TemplatesCog(commands.Cog):
    template_group = app_commands.Group(
        name="plantilla", description="Gestiona composiciones reutilizables"
    )

    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    @template_group.command(name="crear", description="Crea una plantilla de composición")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(actividad=ACTIVITY_CHOICES)
    async def create_template(
        self,
        interaction: discord.Interaction,
        nombre: str,
        actividad: app_commands.Choice[str],
        descripcion: str | None = None,
        incluir_roles_base: bool = False,
    ) -> None:
        assert interaction.guild_id is not None
        template = self.database.create_template(
            interaction.guild_id, nombre[:80], actividad.value, (descripcion or "")[:1000]
        )
        if incluir_roles_base:
            configured = self.database.get_role_emojis(interaction.guild_id)
            for slot in ACTIVITIES[actividad.value].slots:
                template = self.database.upsert_template_slot(
                    guild_id=interaction.guild_id, template_name=template.name,
                    role_key=slot.key, label=slot.label,
                    emoji=configured.get(slot.key, slot.emoji), capacity=slot.capacity,
                    build_id=None,
                ) or template
        await interaction.response.send_message(embed=template_embed(template), ephemeral=True)

    @template_group.command(name="rol", description="Añade o actualiza un rol de una plantilla")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        plantilla="Nombre exacto de la plantilla",
        rol="Martillo, Dawnsong, Healer, etc.",
        cupos="Cantidad de jugadores para este rol",
        build="Nombre exacto de una build guardada",
        emoji="Emoji normal o personalizado del servidor",
    )
    async def set_template_role(
        self,
        interaction: discord.Interaction,
        plantilla: str,
        rol: str,
        cupos: app_commands.Range[int, 1, 99],
        build: str | None = None,
        emoji: str | None = None,
    ) -> None:
        assert interaction.guild_id is not None
        template = self.database.get_template(interaction.guild_id, plantilla)
        if template is None:
            await interaction.response.send_message("No encontré esa plantilla.", ephemeral=True)
            return
        selected_build = None
        if build:
            selected_build = self.database.get_build(interaction.guild_id, build)
            if selected_build is None:
                await interaction.response.send_message(
                    "No encontré esa build. Créala primero con `/build crear`.", ephemeral=True
                )
                return
        key = slugify(rol)
        configured = self.database.get_role_emojis(interaction.guild_id)
        try:
            selected_emoji = normalized_emoji(emoji) if emoji else configured.get(
                key, SLOT_EMOJIS.get(key, "⭐")
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        updated = self.database.upsert_template_slot(
            guild_id=interaction.guild_id, template_name=template.name,
            role_key=key, label=rol.strip()[:80], emoji=selected_emoji,
            capacity=cupos, build_id=selected_build.id if selected_build else None,
        )
        assert updated is not None
        await interaction.response.send_message(embed=template_embed(updated), ephemeral=True)

    @template_group.command(name="ver", description="Muestra una plantilla guardada")
    @app_commands.guild_only()
    async def view_template(self, interaction: discord.Interaction, nombre: str) -> None:
        assert interaction.guild_id is not None
        template = self.database.get_template(interaction.guild_id, nombre)
        if template is None:
            await interaction.response.send_message("No encontré esa plantilla.", ephemeral=True)
            return
        await interaction.response.send_message(embed=template_embed(template), ephemeral=True)

    @template_group.command(name="listar", description="Lista las plantillas del gremio")
    @app_commands.guild_only()
    async def list_templates(self, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        templates = self.database.list_templates(interaction.guild_id)
        if not templates:
            await interaction.response.send_message("Todavía no hay plantillas.", ephemeral=True)
            return
        lines = [f"• **{item.name}** — {len(item.slots)} roles" for item in templates]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @template_group.command(name="eliminar", description="Elimina una plantilla")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_template(self, interaction: discord.Interaction, nombre: str) -> None:
        assert interaction.guild_id is not None
        deleted = self.database.delete_template(interaction.guild_id, nombre)
        await interaction.response.send_message(
            "Plantilla eliminada." if deleted else "No encontré esa plantilla.", ephemeral=True
        )

    async def _template_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        needle = current.casefold()
        return [
            app_commands.Choice(name=template.name, value=template.name)
            for template in self.database.list_templates(interaction.guild_id)
            if needle in template.name.casefold()
        ][:25]

    @set_template_role.autocomplete("plantilla")
    async def role_template_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._template_autocomplete(interaction, current)

    @set_template_role.autocomplete("build")
    async def role_build_autocomplete(
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

    @view_template.autocomplete("nombre")
    async def view_template_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._template_autocomplete(interaction, current)

    @delete_template.autocomplete("nombre")
    async def delete_template_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._template_autocomplete(interaction, current)
