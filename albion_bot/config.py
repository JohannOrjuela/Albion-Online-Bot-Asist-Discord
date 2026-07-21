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

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token == "pega_aqui_el_token_del_bot":
            raise ConfigError(
                "Falta DISCORD_TOKEN. Copia .env.example como .env y pega el token del bot."
            )

        raw_guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        try:
            guild_id = int(raw_guild_id) if raw_guild_id else None
        except ValueError as exc:
            raise ConfigError("DISCORD_GUILD_ID debe ser un número entero.") from exc

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
        return cls(token, guild_id, timezone, database_path, log_level)

