# Ruta de salud y registros (TR-35)

## Ruta `/salud/`

- Es pública (no pide inicio de sesión) y acepta GET y HEAD. Otros métodos devuelven 405.
- Ejecuta `SELECT 1` contra la base de datos.
- Base disponible: responde 200 con `{"estado": "ok", "aplicacion": "ok", "base_de_datos": "ok"}`.
- Base no disponible: responde 503 con `{"estado": "error", "aplicacion": "ok", "base_de_datos": "error"}` y escribe una línea de error en los registros.
- No incluye datos de usuarios, credenciales ni el texto de la excepción. Envía `Cache-Control: no-store`.
- En producción está exenta de la redirección a HTTPS (`SECURE_REDIRECT_EXEMPT`), porque la verificación de Render llega por HTTP interno.

## Uso en Render

1. Abrir el servicio en Render, sección Settings.
2. En Health Check Path escribir `/salud/` y guardar.
3. Render considerará sano el despliegue solo si la ruta responde con éxito, y no enviará tráfico a una versión que falle.

Verificación manual: `curl -i https://quedamos-proyectoiii.onrender.com/salud/`. Con el plan gratuito, la primera respuesta puede tardar hasta un minuto si el servicio estaba dormido.

## Registros

- Salida: consola, que Render recoge en la pestaña Logs.
- Formato: `fecha hora nivel origen mensaje`, por ejemplo `2026-11-08 20:15:03,412 ERROR config.health Verificacion de salud fallida: la base de datos no responde (OperationalError)`.
- Nivel mínimo mostrado: `INFO` por defecto. Se cambia con la variable de entorno `LOG_LEVEL` (por ejemplo `WARNING`).
- Los registros no deben incluir contraseñas, enlaces firmados ni correos de usuarios.
