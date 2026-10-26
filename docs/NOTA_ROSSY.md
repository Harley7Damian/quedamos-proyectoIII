# Nota de arranque para Rossy

Rossy, esta nota te pone al día de lo que cambió mientras no pudimos coordinarnos. Como conoces el proyecto desde las plantillas, la idea es que entres de lleno al código con piezas que puedas llevar de principio a fin.

## Dónde estamos

Quedamos pasó a un enfoque corporativo: la asistente de un ejecutivo coordina reuniones con la asistente de otra persona, el sistema propone tres horarios ordenados y el ejecutivo aprueba con un toque. Rehicimos la base técnica con un stack clásico: Django (Python), PostgreSQL en producción y SQLite en local, plantillas HTML con HTMX. El Módulo 1 (cuentas con rol, vínculo asistente-ejecutivo por código y solicitudes de reunión) ya está hecho y tiene 31 pruebas automáticas. Las razones de cada decisión están en `docs/adr/ADR-001-stack.md`. Si algo no te convence, anótalo con tu argumento y lo conversamos: la arquitectura se puede ajustar.

El plan de sprints (con todas las tarjetas, criterios de aceptación y fechas) está en `docs/Planificacion_Sprints_Quedamos_Jira.md`. Es el archivo que usas para cargar las tarjetas en Jira; sigue la sección "Cómo cargar en Jira".

## Plan de arranque (una hora)

1. Sigue `docs/PASOS_MODULO1.md`: instala y corre el proyecto en unos 15 minutos, sin cuentas externas. Haz la prueba del flujo completo con dos ventanas.
2. Lee `docs/adr/ADR-001-stack.md` (5 minutos).
3. Recorre el código en este orden: `meetings/models.py`, `meetings/views.py`, `templates/panel/panel.html` y `meetings/tests.py`. Con eso entiendes cómo está armado todo; las demás partes siguen el mismo patrón.
4. Ejecuta `python manage.py test` y confirma que pasan las 31 pruebas.
5. Si algo falla, envía el mensaje de error exacto. Lo resolvemos el mismo día.

## Tus piezas de código

1. **Algoritmo de ranking en Python (TR-11).** Porta la lógica de `docs/referencia/matching.ts` a `scheduling/matching.py` y cúbrela con diez escenarios en `scheduling/tests.py`. Es el núcleo del producto y sobre tu módulo construyo la propuesta de tres horarios. Criterios en la tarjeta.
2. **Maqueta de la tarjeta de aprobación (TR-12).** En `templates/demo/tarjeta.html`, que se ve en http://127.0.0.1:8000/demo/tarjeta/. Usa los datos de `scheduling/mock.py`.
3. **Aviso por correo con el enlace de aprobación (HU-11, Sprint 3).** Se define cuando termine la propuesta de horarios.

También te corresponde la configuración de Jira (TR-02), que ya empezaste.

## Cómo trabajamos

- Una rama por tarjeta: `feature/<codigo-de-la-tarjeta>` (por ejemplo `feature/TR-11`). Se integra con un PR, no directo a `main`.
- Cada tarjeta trae sus criterios de aceptación. Antes de pedir revisión, anota en el PR cuáles cumples. Yo reviso cada PR.
- Si cambias o agregas un modelo de base de datos, corre `python manage.py makemigrations` y sube la migración con el código.
- Toda regla nueva de permisos o de cálculo lleva su prueba en el mismo PR.
- Decide sola lo visual, los nombres internos y cómo organizas tu módulo. Consulta antes de agregar una dependencia, cambiar un modelo existente o cambiar `scheduling/contracts.py`, porque otras piezas se apoyan en ellos.
- Si algo te toma más de medio día, avisa ese día con lo que ya probaste y lo resolvemos juntas.
