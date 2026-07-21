from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Configuración ausente o inválida."""


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    guild_id: int | None
    timezone: ZoneInfo
    database_path: Path
    log_level: str
    guild_ids: tuple[int, ...] = ()

    @property
    def sync_guild_ids(self) -> tuple[int, ...]:
        if self.guild_ids:
            return self.guild_ids
        return (self.guild_id,) if self.guild_id is not None else ()

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token == "pega_aqui_el_token_del_bot":
            raise ConfigError(
                "Falta DISCORD_TOKEN. Copia .env.example como .env y pega el token del bot."
            )

        raw_guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        raw_guild_ids = os.getenv("DISCORD_GUILD_IDS", "").strip()
        try:
            guild_ids = tuple(
                dict.fromkeys(
                    int(value.strip())
                    for value in (raw_guild_ids or raw_guild_id).split(",")
                    if value.strip()
                )
            )
            guild_id = guild_ids[0] if guild_ids else None
        except ValueError as exc:
            raise ConfigError(
                "DISCORD_GUILD_IDS debe contener identificadores separados por comas."
            ) from exc

        timezone_name = os.getenv("BOT_TIMEZONE", "America/Bogota").strip()
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ConfigError(f"Zona horaria desconocida: {timezone_name}") from exc

        database_path = Path(
            os.getenv("DATABASE_PATH", "data/albion_guild_bot.db")
        ).expanduser()
        database_path.parent.mkdir(parents=True, exist_ok=True)

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        return cls(token, guild_id, timezone, database_path, log_level, guild_ids)
