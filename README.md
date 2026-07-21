# Albion Guild Bot

Bot de Discord para gestionar actividades de un gremio de Albion Online. La primera
versión incluye eventos con cupos por rol, inscripciones mediante botones y datos
persistentes aunque el bot o el PC se reinicien.

## Requisitos

- Windows 10 u 11.
- Python 3.11 o superior, instalado desde [python.org](https://www.python.org/downloads/).
- Una aplicación de Discord y un servidor en el que tengas permisos administrativos.

## 1. Crear el bot en Discord

1. Entra al [Discord Developer Portal](https://discord.com/developers/applications).
2. Pulsa **New Application**, ponle un nombre y abre la sección **Bot**.
3. Crea el bot y copia su token. El token es una contraseña: no lo publiques ni lo
   envíes por Discord.
4. En **OAuth2 → URL Generator**, selecciona `bot` y `applications.commands`.
5. Concede al bot: **View Channels**, **Send Messages**, **Embed Links**, **Read
   Message History** y **Use Application Commands**.
6. Abre la URL generada e invita el bot a tu servidor.

No hace falta activar `Message Content Intent`: esta versión usa comandos `/` y botones.

## 2. Instalar

Abre PowerShell en esta carpeta y ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

El instalador crea `.venv`, instala las dependencias y copia `.env.example` a `.env`.

## 3. Configurar

Activa **Modo desarrollador** en Discord, haz clic derecho sobre tu servidor y selecciona
**Copiar ID del servidor**. Después abre `.env`:

```env
DISCORD_TOKEN=tu_token_real
DISCORD_GUILD_ID=123456789012345678
BOT_TIMEZONE=America/Bogota
DATABASE_PATH=data/albion_guild_bot.db
```

`DISCORD_GUILD_ID` hace que los comandos aparezcan inmediatamente durante el desarrollo.

## 4. Ejecutar

```powershell
.\run.ps1
```

Mientras esa ventana permanezca abierta y el PC no entre en suspensión, el bot estará
conectado. Para dejarlo 24/7, configura Windows para no suspender el equipo cuando esté
conectado a la corriente.

## Comandos iniciales

### Crear un evento

```text
/evento crear actividad:Caminos Avalonianos fecha:25/07/2026 20:00
```

Opcionalmente puedes escribir cupos personalizados:

```text
caller:1, offtank:1, healer:2, soporte:2, dps:6
```

La fecha se interpreta en `BOT_TIMEZONE`; Discord la muestra automáticamente en la zona
horaria de cada miembro. Crear eventos requiere **Gestionar servidor**.

### Cerrar inscripciones

```text
/evento cerrar evento_id:1
```

Puede hacerlo el creador o una persona con **Gestionar servidor**.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

## Datos y copias de seguridad

Los datos quedan en `data/albion_guild_bot.db`. Con el bot apagado, copiar ese archivo es
suficiente para crear una copia de seguridad. Nunca publiques `.env` ni la base de datos.

## Próximos módulos

1. Plantillas editables y recordatorios de eventos.
2. Creador de builds con iconos de Albion y generación de imágenes.
3. Carteras privadas y libro de movimientos administrativos.
4. Consultas de mercado por servidor y ciudad.

