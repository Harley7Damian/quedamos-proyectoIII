# ADR-001: Stack y arquitectura de Quedamos

Estado: aceptada (19/10/2026). Reemplaza la propuesta inicial de Next.js con Supabase, descartada por decisión del equipo de usar un stack clásico con backend propio.

## Contexto

Quedamos pasó de una herramienta para estudiantes a un espacio compartido donde las asistentes de dos ejecutivos coordinan reuniones y el ejecutivo aprueba. El prototipo anterior guardaba todo en `localStorage`, por lo que dos personas no podían ver lo mismo desde dispositivos distintos. Hay poco tiempo y una sola desarrolladora principal, así que se prioriza que funcione sobre que se vea bien, con una arquitectura que se pueda explicar y defender.

## Decisión

| Capa | Elección | Motivo |
| ---- | -------- | ------ |
| Aplicación | Django (patrón MVT: modelos, vistas, plantillas) | Cuentas, ORM con migraciones, protección CSRF, panel de administración y pruebas ya incluidos. Un solo proyecto desplegable. |
| Lenguaje | Python | Es el lenguaje que domina la desarrolladora principal y el de las librerías de Google Calendar. |
| Base de datos | PostgreSQL en producción, SQLite en local | Sin cuentas externas para desarrollar. El cambio es una variable de entorno (`DATABASE_URL`). |
| Interfaz | Plantillas HTML con HTMX | Actualización parcial sin construir una aplicación de una sola página. Cualquier integrante puede editar HTML y CSS. |
| Lógica de horarios | Paquete `scheduling` en Python puro | Se prueba sin la web. El algoritmo ponderado del prototipo se porta aquí. |
| Despliegue | Render o Railway con gunicorn y WhiteNoise | Servidores de aplicación tradicionales, no funciones sin servidor. |

## Estructura

- `config/`: ajustes y rutas. `accounts/`: usuario con rol, registro e ingreso. `meetings/`: vínculos y solicitudes. `scheduling/`: contratos de datos y lógica de propuesta de horarios.
- `templates/` y `static/`: interfaz. `docs/`: decisiones y pasos operativos.

## Seguridad (qué reemplaza a las reglas de la base de datos)

La regla "cada quien ve solo lo suyo" vive en la capa de aplicación, concentrada en un solo lugar: `MeetingRequest.objects.visible_to(user)` y `_executives_of(user)` en `meetings/`. Quien crea una solicitud lo define el servidor, nunca el formulario, y el ejecutivo elegible se valida contra los vínculos reales. Las pruebas automáticas (`python manage.py test`) cubren visibilidad, suplantación, vinculación, validaciones y escape de HTML.

## Reglas de trabajo

- Una rama y un PR por tarjeta de Jira. Nada directo a `main`.
- Cambios de base de datos con `python manage.py makemigrations`; la migración se sube con el código. No se editan migraciones ya aplicadas.
- Toda regla de permisos nueva lleva su prueba en el mismo PR.
- Las pantallas del Módulo 2 se construyen contra `scheduling/contracts.py`.

## Consecuencias y límites conocidos

- El panel consulta cada 5 segundos (HTMX). Si se necesita tiempo real verdadero, se evalúa Django Channels en un sprint posterior.
- El registro permite elegir el rol. Aceptable para la demo; en producción el rol de ejecutivo debería verificarse por dominio corporativo.
- No se guardan detalles de eventos de calendario, solo disponibilidad (libre u ocupado), por privacidad por defecto.
- El plan gratuito de Render duerme la aplicación tras inactividad: la primera visita puede tardar. Para la demo conviene abrirla antes.
