# Albion Guild Bot

Bot de Discord para gestionar actividades de un gremio de Albion Online. Incluye
eventos con cupos por rol, builds ilustradas, composiciones reutilizables, emojis
personalizados e inscripciones persistentes aunque el bot o el PC se reinicien.

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
   Message History**, **Use Application Commands**, **Attach Files** y **Mention
   @everyone, @here, and All Roles**.
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

Para usar el bot simultáneamente en el gremio y en la alianza, agrega ambos IDs:

```env
DISCORD_GUILD_IDS=123456789012345678,987654321098765432
```

Cuando uses `DISCORD_GUILD_IDS`, puedes dejar vacío `DISCORD_GUILD_ID`.

## 4. Ejecutar

```powershell
.\run.ps1
```

Mientras esa ventana permanezca abierta y el PC no entre en suspensión, el bot estará
conectado. Para dejarlo 24/7, configura Windows para no suspender el equipo cuando esté
conectado a la corriente.

## Comandos iniciales

Usa `/help` dentro de Discord para ver el listado completo de comandos y el flujo
recomendado de builds, plantillas y eventos.

### Crear un evento

Cada actividad tiene su propio comando y un título fijo:

```text
/evento hellgate
/evento arena
/evento liga
/evento caminos
/evento estatica
/evento grupal
```

Discord muestra solamente los campos de esa actividad. La descripción continúa siendo
libre. También se puede indicar una plantilla opcional para aplicar sus posiciones,
builds y emojis. Cofres y Rastreo en Caminos tienen un máximo de siete participantes.

Solo se escribe la hora UTC que aparece dentro de Albion, por ejemplo `18:45`. El evento
se crea para hoy y Discord muestra automáticamente la hora local de cada miembro y el
tiempo restante. Crear eventos requiere **Gestionar servidor**.

En Liga de Cristal se publican cinco posiciones titulares y dos cupos de suplente. Después
de elegir posición, cada participante debe pulsar **✅ Confirmar asistencia**. El panel
muestra `⏳` mientras esté pendiente y `✅` cuando esté confirmado.

### Cerrar inscripciones

```text
/evento cerrar evento_id:1
```

Puede hacerlo el creador o una persona con **Gestionar servidor**.

## Builds

Crea una build con nombres visibles del juego o con identificadores internos de Albion:

```text
/build crear nombre:Dawnsong Arena arma:Dawnsong casco:Royal Cowl pechera:Feyscale Robe botas:Cleric Sandals ip_minimo:1200
```

El bot consulta el servicio de renderizado de Albion, prueba nombres en español e inglés,
y genera una imagen de 1600×900. Una arma nueva funciona tan pronto como el servicio de
Albion reconozca su nombre o identificador; no depende de una lista fija en el código.

```text
/build ver nombre:Dawnsong Arena
/build listar
/build eliminar nombre:Dawnsong Arena
```

Si un nombre no produce icono, usa el identificador interno del objeto o prueba el nombre
exacto mostrado por el cliente en español o inglés.

## Plantillas de composición

Flujo recomendado:

```text
/plantilla crear nombre:Arena Principal actividad:Arena de Cristal
/plantilla rol plantilla:Arena Principal rol:Martillo cupos:1 build:Martillo Arena emoji:🔨
/plantilla rol plantilla:Arena Principal rol:Dawnsong cupos:1 build:Dawnsong Arena emoji:🔥
/plantilla rol plantilla:Arena Principal rol:Healer cupos:1 build:Holy Arena emoji:💚
/plantilla ver nombre:Arena Principal
```

Después crea una salida sin volver a escribir la composición:

```text
/evento desde-plantilla plantilla:Arena Principal hora:20:00
```

El panel mostrará la build asignada bajo cada rol. Al apuntarse, el jugador recibe
inmediatamente y de forma privada el resumen y la imagen completa de su build. También
puede volver a abrirla con `/build ver`.

Los eventos nuevos mencionan `@everyone`. Para que la mención genere una notificación,
el rol del bot debe tener **Mencionar @everyone, @here y todos los roles** en ese canal.

## Emojis personalizados

Puedes utilizar emojis Unicode o emojis propios del servidor. Para un icono real de
Albion, sube una imagen cuadrada en **Ajustes del servidor → Expresiones → Emoji** y
pégalo como parámetro del comando:

```text
/config emoji rol:Dawnsong emoji:<emoji del servidor>
/config ver-emojis
```

La asociación se aplica automáticamente a eventos nuevos y a roles nuevos de plantillas.
También puedes elegir otro emoji directamente en `/plantilla rol`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

## Datos y copias de seguridad

Los datos quedan en `data/albion_guild_bot.db`. Con el bot apagado, copiar ese archivo es
suficiente para crear una copia de seguridad. Nunca publiques `.env` ni la base de datos.

## Próximos módulos

1. Edición de roles y recordatorios de eventos.
2. Selector visual de habilidades y pasivas.
3. Carteras privadas y libro de movimientos administrativos.
4. Consultas de mercado por servidor y ciudad.
