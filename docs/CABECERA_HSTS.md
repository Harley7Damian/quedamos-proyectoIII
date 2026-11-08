# Cabecera HSTS y tipografía autoalojada (TR-49)

## Tipografía

- La aplicación sirve la tipografía Inter desde `static/fonts/inter-latin-wght-normal.woff2` (variable, subconjunto latino, 48 KB). No pide fuentes a Google ni a ningún otro dominio.
- La declaración `@font-face` está al inicio de `static/css/app.css` y la plantilla base precarga el archivo.
- Licencia SIL Open Font License 1.1, copiada en `static/fonts/LICENSE-Inter.txt`.
- Si el archivo no carga, el navegador usa la tipografía del sistema (`system-ui`).

## HSTS

- En producción (`DEBUG=0`) toda respuesta HTTPS incluye `Strict-Transport-Security: max-age=3600; includeSubDomains`.
- Con esa cabecera el navegador exige HTTPS en este sitio durante una hora. Se empieza con un valor corto porque uno largo es difícil de revertir: una vez enviado, el navegador lo recuerda aunque se quite de la aplicación.
- La vigencia se define con la variable de entorno `HSTS_SECONDS` (por defecto 3600).
- `includeSubDomains` solo alcanza a subdominios de este mismo sitio, no a `onrender.com`.
- La cabecera solo se envía por HTTPS. La ruta `/salud/` queda exenta de la redirección a HTTPS y no la envía.

### Cómo subir la vigencia

Hacerlo solo después de comprobar que el sitio funciona bien por HTTPS, y por etapas:

1. Una hora (3600), valor inicial.
2. Un día (86400).
3. Una semana (604800).
4. Un año (31536000), solo si el sitio va a seguir en HTTPS.

En Render: Environment, variable `HSTS_SECONDS`, nuevo valor y guardar. Se aplica con el siguiente despliegue.

### Cómo revertir

Django no envía `max-age=0` cuando `HSTS_SECONDS` vale 0: en ese caso simplemente deja de enviar la cabecera, y los navegadores que ya la recibieron conservan la regla hasta que venza. Para revertir de verdad:

1. Poner `HSTS_SECONDS=1`. El navegador reemplaza la regla por una de un segundo la siguiente vez que visite el sitio por HTTPS.
2. Esperar a que los usuarios vuelvan a entrar y, si se desea, poner `HSTS_SECONDS=0` para dejar de enviar la cabecera.

### Advertencias de `check --deploy`

- La advertencia `security.W004` (sin HSTS) desaparece.
- Queda `security.W021` (preload). No se activa a propósito: el preload exige una vigencia mínima de un año y compromete al dominio de forma casi irreversible. Se revisará cuando la vigencia llegue a un año y el sitio tenga dominio propio.
