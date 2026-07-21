from __future__ import annotations

from collections import defaultdict
from datetime import timezone

import discord

from .activities import ACTIVITIES
from .build_renderer import BuildRenderer
from .builds import build_summary_embed, safe_filename
from .database import Database
from .domain import ConfirmationResult, EventStatus, GuildEvent, SignupResult, SlotDefinition


def build_event_embed(event: GuildEvent) -> discord.Embed:
    preset = ACTIVITIES.get(event.activity)
    color = preset.color if preset else 0xE74C3C
    state = {
        EventStatus.OPEN: "🟢 Inscripciones abiertas",
        EventStatus.CLOSED: "🔒 Inscripciones cerradas",
        EventStatus.CANCELLED: "⛔ Evento cancelado",
    }[event.status]
    timestamp = int(event.starts_at.timestamp())
    description = event.description.strip() or "Sin descripción adicional."
    embed = discord.Embed(title=event.title, description=description, color=color)
    embed.add_field(name="Actividad", value=preset.label if preset else event.activity, inline=True)
    embed.add_field(name="Organiza", value=f"<@{event.creator_id}>", inline=True)
    embed.add_field(name="Estado", value=state, inline=True)
    game_time = event.starts_at.astimezone(timezone.utc).strftime("%H:%M")
    embed.add_field(
        name="Hora",
        value=(
            f"🌐 Juego: **{game_time} UTC**\n"
            f"🕒 Tu hora: <t:{timestamp}:t>\n"
            f"⏳ <t:{timestamp}:R>"
        ),
        inline=False,
    )

    by_role: dict[str, list[int]] = defaultdict(list)
    signup_by_user = {signup.user_id: signup for signup in event.signups}
    for signup in event.signups:
        by_role[signup.slot_key].append(signup.user_id)
    for slot in event.slots:
        members = by_role[slot.key]
        names = "\n".join(
            f"{index}. <@{user_id}>"
            + (
                (" ✅" if signup_by_user[user_id].confirmed else " ⏳")
                if event.activity == "crystal"
                else ""
            )
            for index, user_id in enumerate(members, 1)
        )
        build_line = f"📜 `{slot.build_name}`\n" if slot.build_name else ""
        embed.add_field(
            name=f"{slot.emoji} {slot.label} ({len(members)}/{slot.capacity})",
            value=build_line + (names or "— Disponible —"),
            inline=True,
        )
    footer = "Usa los botones para elegir o cambiar tu rol"
    if event.activity == "crystal":
        footer += " · En Liga también debes confirmar asistencia"
    embed.set_footer(text=f"Evento #{event.id} · {footer}")
    return embed


class RoleButton(discord.ui.Button["EventSignupView"]):
    def __init__(self, event_id: int, slot: SlotDefinition, row: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=slot.label,
            emoji=slot.emoji,
            custom_id=f"event:{event_id}:join:{slot.key}",
            row=row,
        )
        self.event_id = event_id
        self.role_key = slot.key

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await self.view.join(interaction, self.role_key)


class LeaveButton(discord.ui.Button["EventSignupView"]):
    def __init__(self, event_id: int, row: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Retirarme",
            emoji="🚪",
            custom_id=f"event:{event_id}:leave",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await self.view.leave(interaction)


class ConfirmButton(discord.ui.Button["EventSignupView"]):
    def __init__(self, event_id: int, row: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Confirmar asistencia",
            emoji="✅",
            custom_id=f"event:{event_id}:confirm",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await self.view.confirm(interaction)


class EventSignupView(discord.ui.View):
    def __init__(
        self, database: Database, event: GuildEvent, renderer: BuildRenderer | None = None
    ) -> None:
        super().__init__(timeout=None)
        self.database = database
        self.renderer = renderer
        self.event_id = event.id
        for index, slot in enumerate(event.slots):
            self.add_item(RoleButton(event.id, slot, index // 5))
        action_row = min(len(event.slots) // 5, 4)
        self.add_item(LeaveButton(event.id, action_row))
        if event.activity == "crystal":
            self.add_item(ConfirmButton(event.id, action_row))
        if event.status is not EventStatus.OPEN:
            self.disable_all()

    def disable_all(self) -> None:
        for item in self.children:
            item.disabled = True

    async def join(self, interaction: discord.Interaction, role_key: str) -> None:
        await interaction.response.defer(ephemeral=True)
        result = self.database.signup(self.event_id, interaction.user.id, role_key)
        messages = {
            SignupResult.JOINED: "Te apuntaste correctamente.",
            SignupResult.MOVED: "Cambiaste de rol correctamente.",
            SignupResult.ALREADY_JOINED: "Ya estabas apuntado en ese rol.",
            SignupResult.FULL: "Ese rol ya no tiene cupos disponibles.",
            SignupResult.EVENT_CLOSED: "Las inscripciones de este evento están cerradas.",
            SignupResult.SLOT_NOT_FOUND: "Ese rol ya no existe en el evento.",
        }
        event = self.database.get_event(self.event_id)
        build_name = None
        if event is not None:
            build_name = next(
                (slot.build_name for slot in event.slots if slot.key == role_key), None
            )
        if result in {SignupResult.JOINED, SignupResult.MOVED}:
            await self._refresh_message(interaction)
        message = messages[result]
        if event and event.activity == "crystal" and result in {
            SignupResult.JOINED, SignupResult.MOVED
        }:
            message += "\nAhora pulsa **✅ Confirmar asistencia** cuando estés seguro."
        if build_name:
            message += f"\nTu build asignada es **{build_name}**."
        await interaction.followup.send(message, ephemeral=True)
        if (
            build_name
            and self.renderer is not None
            and result in {SignupResult.JOINED, SignupResult.MOVED, SignupResult.ALREADY_JOINED}
        ):
            build = self.database.get_build(event.guild_id, build_name) if event else None
            if build is not None:
                image, missing = await self.renderer.render(build)
                warning = None
                if missing:
                    warning = "⚠️ No encontré iconos para: " + ", ".join(missing)
                await interaction.followup.send(
                    content=warning,
                    embed=build_summary_embed(build),
                    file=discord.File(image, filename=f"{safe_filename(build.name)}.png"),
                    ephemeral=True,
                )

    async def leave(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        removed = self.database.leave_event(self.event_id, interaction.user.id)
        if removed:
            await self._refresh_message(interaction)
        message = "Saliste del evento." if removed else "No estabas apuntado en este evento."
        await interaction.followup.send(message, ephemeral=True)

    async def confirm(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        result = self.database.confirm_signup(self.event_id, interaction.user.id)
        messages = {
            ConfirmationResult.CONFIRMED: "✅ Asistencia confirmada.",
            ConfirmationResult.NOT_SIGNED_UP: "Primero elige una posición en el evento.",
            ConfirmationResult.EVENT_CLOSED: "Las inscripciones de este evento están cerradas.",
        }
        if result is ConfirmationResult.CONFIRMED:
            await self._refresh_message(interaction)
        await interaction.followup.send(messages[result], ephemeral=True)

    async def _refresh_message(self, interaction: discord.Interaction) -> None:
        event = self.database.get_event(self.event_id)
        if event is not None and interaction.message is not None:
            await interaction.message.edit(embed=build_event_embed(event), view=self)
