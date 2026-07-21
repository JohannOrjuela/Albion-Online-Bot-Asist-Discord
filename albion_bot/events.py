from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .activities import ACTIVITIES
from .database import Database
from .domain import EventStatus
from .parsing import parse_local_datetime, parse_slots
from .views import EventSignupView, build_event_embed


ACTIVITY_CHOICES = [
    app_commands.Choice(name=preset.label, value=preset.key)
    for preset in ACTIVITIES.values()
]


class EventsCog(commands.Cog):
    event_group = app_commands.Group(name="evento", description="Gestiona actividades del gremio")

    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    @event_group.command(name="crear", description="Publica un evento con inscripciones por rol")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(actividad=ACTIVITY_CHOICES)
    @app_commands.describe(
        actividad="Tipo de actividad",
        fecha="Hora de Colombia: 20/07/2026 15:30",
        titulo="Nombre personalizado; si se omite se usa la actividad",
        descripcion="Información como mapas, IP mínimo o requisitos",
        cupos="Opcional: caller:1, healer:2, dps:6",
    )
    async def create_event(
        self,
        interaction: discord.Interaction,
        actividad: app_commands.Choice[str],
        fecha: str,
        titulo: str | None = None,
        descripcion: str | None = None,
        cupos: str | None = None,
    ) -> None:
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.", ephemeral=True)
            return
        try:
            starts_at = parse_local_datetime(fecha, self.bot.settings.timezone)  # type: ignore[attr-defined]
            if starts_at <= datetime.now(timezone.utc):
                raise ValueError("La fecha del evento debe estar en el futuro.")
            preset = ACTIVITIES[actividad.value]
            slots = parse_slots(cupos) if cupos else preset.slots
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        event = self.database.create_event(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            creator_id=interaction.user.id,
            activity=actividad.value,
            title=(titulo or preset.label).strip()[:256],
            description=(descripcion or "").strip()[:2000],
            starts_at=starts_at,
            slots=slots,
        )
        view = EventSignupView(self.database, event)
        try:
            assert interaction.channel is not None
            message = await interaction.channel.send(embed=build_event_embed(event), view=view)
        except Exception:
            self.database.set_event_status(event.id, EventStatus.CANCELLED)
            raise
        self.database.set_event_message(event.id, message.id)
        self.bot.add_view(view, message_id=message.id)
        await interaction.followup.send(f"Evento creado: {message.jump_url}", ephemeral=True)

    @event_group.command(name="cerrar", description="Cierra las inscripciones de un evento")
    @app_commands.guild_only()
    @app_commands.describe(evento_id="Número mostrado al pie del evento")
    async def close_event(self, interaction: discord.Interaction, evento_id: int) -> None:
        event = self.database.get_event(evento_id)
        if event is None or event.guild_id != interaction.guild_id:
            await interaction.response.send_message("No encontré ese evento.", ephemeral=True)
            return
        permissions = getattr(interaction.user, "guild_permissions", None)
        can_manage = bool(permissions and permissions.manage_guild)
        if interaction.user.id != event.creator_id and not can_manage:
            await interaction.response.send_message(
                "Solo el organizador o un administrador puede cerrar este evento.", ephemeral=True
            )
            return
        self.database.set_event_status(event.id, EventStatus.CLOSED)
        event = self.database.get_event(event.id)
        await interaction.response.send_message("Inscripciones cerradas.", ephemeral=True)
        if event is not None and event.message_id:
            try:
                channel = self.bot.get_channel(event.channel_id) or await self.bot.fetch_channel(event.channel_id)
                message = await channel.fetch_message(event.message_id)  # type: ignore[union-attr]
                view = EventSignupView(self.database, event)
                await message.edit(embed=build_event_embed(event), view=view)
            except discord.HTTPException:
                pass

    @create_event.error
    async def create_event_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        if isinstance(error, app_commands.MissingPermissions):
            message = "Necesitas el permiso **Gestionar servidor** para crear eventos."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return
        if isinstance(original, discord.Forbidden):
            message = (
                "No puedo publicar el evento en este canal. Revisa que mi rol tenga "
                "**Ver canal**, **Enviar mensajes** e **Insertar enlaces** en los permisos "
                "del canal o de su categoría."
            )
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return
        if isinstance(original, discord.HTTPException):
            message = "Discord rechazó la publicación del evento. Inténtalo nuevamente en otro canal."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return
        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventsCog(bot, bot.database))  # type: ignore[attr-defined]
