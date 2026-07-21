from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .activities import ACTIVITIES, ROAD_SLOTS
from .database import Database
from .domain import EventStatus, SlotDefinition
from .parsing import parse_local_datetime
from .views import EventSignupView, build_event_embed


TITLES = {
    "hg": "🔥 Hellgate 5v5",
    "arena": "💎 Arena de Cristal",
    "crystal": "🏆 Liga de Cristal 5v5",
    "avalon": "🌀 Caminos Avalonianos",
    "static": "🏛️ Estática",
    "group": "🗝️ Mazmorra Grupal",
}

TIER_CHOICES = [app_commands.Choice(name=f"Tier {tier}", value=f"T{tier}") for tier in range(4, 9)]
LETHAL_CHOICES = [
    app_commands.Choice(name="Letal", value="Letal"),
    app_commands.Choice(name="No letal", value="No letal"),
]
RANK_CHOICES = [
    app_commands.Choice(name=rank, value=rank)
    for rank in ("Hierro", "Bronce", "Plata", "Oro", "Cristal")
]
ROAD_OBJECTIVES = [
    app_commands.Choice(name="Cofres / PvE", value="pve"),
    app_commands.Choice(name="Roaming PvP", value="pvp"),
    app_commands.Choice(name="Rastreo", value="tracking"),
    app_commands.Choice(name="Transporte", value="transport"),
]
ROAD_LABELS = {choice.value: choice.name for choice in ROAD_OBJECTIVES}
STATIC_MODES = [
    app_commands.Choice(name="Fame farm", value="Fame farm"),
    app_commands.Choice(name="Pull grande", value="Pull grande"),
    app_commands.Choice(name="Facción", value="Facción"),
    app_commands.Choice(name="Fama y PvP", value="Fama y PvP"),
]
SET_TYPES = [
    app_commands.Choice(name="Set de fama", value="Set de fama"),
    app_commands.Choice(name="Set de combate", value="Set de combate"),
]
ENCHANTMENTS = [
    app_commands.Choice(name=f".{level}", value=f".{level}") for level in range(5)
]


def _description(notes: str | None, details: tuple[tuple[str, str], ...]) -> str:
    parts: list[str] = []
    if notes and notes.strip():
        parts.append(notes.strip())
    parts.append("**Detalles del evento**\n" + "\n".join(
        f"• **{label}:** {value}" for label, value in details
    ))
    return "\n\n".join(parts)[:2000]


class EventsCog(commands.Cog):
    event_group = app_commands.Group(name="evento", description="Crea contenido para la alianza")

    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    def _guild_emojis(
        self, guild_id: int, slots: tuple[SlotDefinition, ...]
    ) -> tuple[SlotDefinition, ...]:
        configured = self.database.get_role_emojis(guild_id)
        return tuple(
            SlotDefinition(
                slot.key, slot.label, configured.get(slot.key, slot.emoji), slot.capacity,
                slot.build_id, slot.build_name,
            )
            for slot in slots
        )

    def _template_slots(
        self,
        guild_id: int,
        activity: str,
        template_name: str | None,
        default: tuple[SlotDefinition, ...],
    ) -> tuple[SlotDefinition, ...]:
        if not template_name:
            return self._guild_emojis(guild_id, default)
        template = self.database.get_template(guild_id, template_name)
        if template is None:
            raise ValueError("No encontré esa plantilla.")
        if template.activity != activity:
            raise ValueError("La plantilla pertenece a otra actividad.")
        if not template.slots:
            raise ValueError("La plantilla no tiene posiciones configuradas.")
        return template.slots

    async def _publish(
        self,
        interaction: discord.Interaction,
        *,
        activity: str,
        date_text: str,
        description: str,
        slots: tuple[SlotDefinition, ...],
    ) -> None:
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message(
                "Este comando solo funciona en un servidor.", ephemeral=True
            )
            return
        try:
            starts_at = parse_local_datetime(date_text, self.bot.settings.timezone)  # type: ignore[attr-defined]
            if starts_at <= datetime.now(timezone.utc):
                raise ValueError("La fecha del evento debe estar en el futuro.")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        event = self.database.create_event(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            creator_id=interaction.user.id,
            activity=activity,
            title=TITLES[activity],
            description=description,
            starts_at=starts_at,
            slots=slots,
        )
        view = EventSignupView(self.database, event, self.bot.build_renderer)  # type: ignore[attr-defined]
        try:
            assert interaction.channel is not None
            message = await interaction.channel.send(
                content="@everyone",
                embed=build_event_embed(event),
                view=view,
                allowed_mentions=discord.AllowedMentions(everyone=True),
            )
        except Exception:
            self.database.set_event_status(event.id, EventStatus.CANCELLED)
            raise
        self.database.set_event_message(event.id, message.id)
        self.bot.add_view(view, message_id=message.id)
        await interaction.followup.send(f"Evento creado: {message.jump_url}", ephemeral=True)

    @event_group.command(name="hellgate", description="Crea una Hellgate 5v5")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(letalidad=LETHAL_CHOICES, tier=TIER_CHOICES)
    @app_commands.describe(
        fecha="Hora de Colombia: 25/07/2026 20:00",
        sets="Número de sets obligatorios por jugador",
        punto="Ciudad o punto de reunión",
        plantilla="Plantilla opcional con posiciones y builds",
        descripcion="Texto libre del organizador",
    )
    async def hellgate(
        self, interaction: discord.Interaction, fecha: str,
        letalidad: app_commands.Choice[str], tier: app_commands.Choice[str],
        sets: app_commands.Range[int, 1, 10], punto: str,
        plantilla: str | None = None, descripcion: str | None = None,
    ) -> None:
        try:
            slots = self._template_slots(
                interaction.guild_id or 0, "hg", plantilla, ACTIVITIES["hg"].slots
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._publish(
            interaction, activity="hg", date_text=fecha, slots=slots,
            description=_description(descripcion, (
                ("Modalidad", letalidad.value), ("Tier mínimo", tier.value),
                ("Sets obligatorios", str(sets)), ("Punto de reunión", punto),
            )),
        )

    @event_group.command(name="arena", description="Crea una Arena de Cristal 5v5")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(rango=RANK_CHOICES, tier=TIER_CHOICES)
    @app_commands.describe(
        rango="Rango objetivo del grupo", tier="Tier mínimo requerido",
        composicion="Composición; se usa la recomendada si se omite",
        plantilla="Plantilla opcional con posiciones y builds",
        descripcion="Texto libre del organizador",
    )
    async def arena(
        self, interaction: discord.Interaction, fecha: str,
        rango: app_commands.Choice[str], tier: app_commands.Choice[str],
        composicion: str = "1 Healer · 1 Frontline · 3 DPS/Support",
        plantilla: str | None = None, descripcion: str | None = None,
    ) -> None:
        try:
            slots = self._template_slots(
                interaction.guild_id or 0, "arena", plantilla, ACTIVITIES["arena"].slots
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._publish(
            interaction, activity="arena", date_text=fecha, slots=slots,
            description=_description(descripcion, (
                ("Rango objetivo", rango.value), ("Tier mínimo", tier.value),
                ("Composición", composicion),
            )),
        )

    @event_group.command(name="liga", description="Crea una Liga de Cristal 5v5")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(letalidad=LETHAL_CHOICES, tier=TIER_CHOICES)
    @app_commands.describe(
        nivel_token="Nivel o token de la partida", horario_oficial="Horario oficial indicado",
        plantilla="Plantilla opcional; úsala para asignar una build a cada posición",
        descripcion="Texto libre del organizador",
    )
    async def league(
        self, interaction: discord.Interaction, fecha: str, nivel_token: str,
        letalidad: app_commands.Choice[str], tier: app_commands.Choice[str],
        horario_oficial: str, plantilla: str | None = None,
        descripcion: str | None = None,
    ) -> None:
        try:
            slots = self._template_slots(
                interaction.guild_id or 0, "crystal", plantilla, ACTIVITIES["crystal"].slots
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._publish(
            interaction, activity="crystal", date_text=fecha, slots=slots,
            description=_description(descripcion, (
                ("Modalidad", "5v5"), ("Nivel / token", nivel_token),
                ("Riesgo", letalidad.value), ("Tier mínimo", tier.value),
                ("Horario oficial", horario_oficial),
                ("Equipo", "5 titulares · hasta 2 suplentes"),
            )),
        )

    @event_group.command(name="caminos", description="Crea contenido en Caminos Avalonianos")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(objetivo=ROAD_OBJECTIVES, tier=TIER_CHOICES)
    @app_commands.describe(
        objetivo="Actividad principal", punto="Entrada o punto de reunión",
        loot_split="Cómo se reparten costes y botín",
        plantilla="Plantilla opcional con posiciones y builds",
        descripcion="Texto libre del organizador",
    )
    async def roads(
        self, interaction: discord.Interaction, fecha: str,
        objetivo: app_commands.Choice[str], tier: app_commands.Choice[str],
        punto: str, loot_split: str, plantilla: str | None = None,
        descripcion: str | None = None,
    ) -> None:
        try:
            slots = self._template_slots(
                interaction.guild_id or 0, "avalon", plantilla, ROAD_SLOTS[objetivo.value]
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._publish(
            interaction, activity="avalon", date_text=fecha, slots=slots,
            description=_description(descripcion, (
                ("Objetivo", ROAD_LABELS[objetivo.value]), ("Tier mínimo", tier.value),
                ("Punto de reunión", punto), ("Loot split", loot_split),
                ("Tamaño máximo", "7 jugadores"),
            )),
        )

    @event_group.command(name="estatica", description="Crea una salida de Estática")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(modalidad=STATIC_MODES, tipo_set=SET_TYPES)
    @app_commands.describe(
        tier_zona="Tier y nombre de la zona", tipo_set="Set de fama o combate",
        punto="Punto de reunión", plantilla="Plantilla opcional con posiciones y builds",
        descripcion="Texto libre del organizador",
    )
    async def static(
        self, interaction: discord.Interaction, fecha: str,
        modalidad: app_commands.Choice[str], tier_zona: str,
        tipo_set: app_commands.Choice[str], punto: str,
        plantilla: str | None = None, descripcion: str | None = None,
    ) -> None:
        try:
            slots = self._template_slots(
                interaction.guild_id or 0, "static", plantilla, ACTIVITIES["static"].slots
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._publish(
            interaction, activity="static", date_text=fecha, slots=slots,
            description=_description(descripcion, (
                ("Modalidad", modalidad.value), ("Tier y zona", tier_zona),
                ("Equipamiento", tipo_set.value), ("Punto de reunión", punto),
            )),
        )

    @event_group.command(name="grupal", description="Crea una Mazmorra Grupal")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(tier=TIER_CHOICES, encantamiento=ENCHANTMENTS)
    @app_commands.describe(
        mapas="Número de mapas que harán", reparto="Repartición del coste y del loot",
        plantilla="Plantilla opcional con posiciones y builds",
        descripcion="Texto libre del organizador",
    )
    async def group_dungeon(
        self, interaction: discord.Interaction, fecha: str,
        tier: app_commands.Choice[str], encantamiento: app_commands.Choice[str],
        mapas: app_commands.Range[int, 1, 50], reparto: str,
        plantilla: str | None = None, descripcion: str | None = None,
    ) -> None:
        try:
            slots = self._template_slots(
                interaction.guild_id or 0, "group", plantilla, ACTIVITIES["group"].slots
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._publish(
            interaction, activity="group", date_text=fecha, slots=slots,
            description=_description(descripcion, (
                ("Mapa", f"{tier.value}{encantamiento.value}"),
                ("Número de mapas", str(mapas)), ("Coste y loot", reparto),
            )),
        )

    @event_group.command(name="desde-plantilla", description="Crea un evento desde una plantilla")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        plantilla="Nombre exacto de la plantilla", fecha="Hora de Colombia: 25/07/2026 20:00",
        descripcion="Información adicional para esta salida",
    )
    async def create_from_template(
        self, interaction: discord.Interaction, plantilla: str,
        fecha: str, descripcion: str | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.", ephemeral=True)
            return
        template = self.database.get_template(interaction.guild_id, plantilla)
        if template is None:
            await interaction.response.send_message("No encontré esa plantilla.", ephemeral=True)
            return
        if template.activity not in TITLES:
            await interaction.response.send_message(
                "Esa actividad ya no está disponible para eventos nuevos.", ephemeral=True
            )
            return
        if not template.slots:
            await interaction.response.send_message(
                "La plantilla no tiene posiciones. Añádelas con `/plantilla rol`.", ephemeral=True
            )
            return
        await self._publish(
            interaction, activity=template.activity, date_text=fecha,
            description=(descripcion or template.description).strip()[:2000],
            slots=template.slots,
        )

    @create_from_template.autocomplete("plantilla")
    async def template_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        needle = current.casefold()
        return [
            app_commands.Choice(name=template.name, value=template.name)
            for template in self.database.list_templates(interaction.guild_id)
            if needle in template.name.casefold() and template.activity in TITLES
        ][:25]

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
                view = EventSignupView(
                    self.database, event, self.bot.build_renderer  # type: ignore[attr-defined]
                )
                await message.edit(embed=build_event_embed(event), view=view)
            except discord.HTTPException:
                pass

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        if isinstance(error, app_commands.MissingPermissions):
            message = "Necesitas el permiso **Gestionar servidor** para crear eventos."
        elif isinstance(original, discord.Forbidden):
            message = (
                "No puedo publicar en este canal. Necesito **Ver canal**, "
                "**Enviar mensajes** e **Insertar enlaces**."
            )
        elif isinstance(original, discord.HTTPException):
            message = "Discord rechazó la publicación. Inténtalo nuevamente en otro canal."
        else:
            raise error
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventsCog(bot, bot.database))  # type: ignore[attr-defined]
