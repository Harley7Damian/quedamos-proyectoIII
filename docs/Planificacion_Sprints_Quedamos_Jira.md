---
title: Planificación de sprints de Quedamos para Jira
curso: Proyecto Final de Carrera III (USIL, Ingeniería de Software)
docente: Neira Neira, Kenny Disney
track: equipo
creado: 2026-10-14
actualizado: 2026-10-19
estado: versión 2, desarrollo primero y documentación al final
stack: Django, PostgreSQL, HTMX (ADR-001)
uso: Copiar y pegar tarjeta por tarjeta en Jira
---

# Planificación de sprints de Quedamos para Jira

Enfoque vigente: Quedamos como espacio compartido donde las asistentes de dos ejecutivos coordinan reuniones con horarios ordenados y el ejecutivo aprueba en un toque. Enfoque exclusivamente corporativo.

Criterio de la versión 2: se prioriza software que funciona sobre documentación extensiva (segundo valor del Manifiesto Ágil). Los sprints 1 a 5 son de desarrollo y pruebas. Todo lo que es informe, plantillas, BMC, flujo de caja y paper está en los sprints 6 y 7.

> La validación no ocupa un sprint propio: ocurre en las revisiones de sprint con el profesor, que actúa como usuario (TR-10, TR-17). El alcance de los sprints siguientes se ajusta en esas revisiones y no antes.

## Supuestos del proyecto, no validados todavía

El proyecto cambió de segmento (de estudiantes a corporativo) por recomendación del profesor y los siguientes supuestos quedan pendientes de actualización. Se tratan como supuestos razonables y no deben presentarse como validados en el informe.

1. H1: coordinar reuniones consume tiempo y genera idas y vueltas por correo. Se contrasta en TR-10 y TR-17.
2. H2: la asistente opera la coordinación y el ejecutivo solo aprueba. Se contrasta en TR-10 y TR-17.
3. H3: la propuesta ordenada reduce los mensajes cruzados. Se mide con HU-10.
4. H4: el ejecutivo aprueba en un toque sin aprender una herramienta nueva. Se contrasta en TR-17.
5. H5: el tiempo hasta confirmar baja frente a la línea base. Se mide con HU-10.
6. Precio por asiento: sin dato propio. Se contrasta con el benchmark (TR-22) y la pregunta al profesor (TR-10).

## Supuestos de planificación por confirmar

1. Fechas: se asumió que la semana 9 del curso corresponde al 12/10 al 18/10, con sprints de lunes a domingo. Confirmar con el profesor la fecha de inicio, el número de sprints (se recuerda "7", aquí S1 a S7 más un Sprint 0) y la fecha de entrega final.
2. Equipo: Mayerly Damián (base técnica, producto, flujo de caja) y Rossy (configuración de Jira, algoritmo de ranking, maqueta de la tarjeta, aviso por correo, verificaciones, plantillas e informe). Si hay más integrantes, reasignar.
3. Capacidad: el Sprint 1 reúne 27 puntos porque incluye la base técnica construida con asistencia de IA. Desde el Sprint 2 se asumen 12 a 21 puntos (el Sprint 2 es el más cargado, con 21, porque Rossy toma 8 de código) y se recalibra con la velocidad real en la retrospectiva del Sprint 2.
4. Cierre anticipado del Sprint 1: sus tarjetas vencen el 19 y 20/10. Si todas pasan a Cumplida, el sprint puede completarse en Jira antes del 25/10 y quedará registrada su duración real de dos días, que se explica como entrega anticipada. Si se prefiere mantener sprints de una semana completa, queda abierto hasta el domingo.
5. Escala de puntos: Fibonacci (1, 2, 3, 5, 8). Un punto es esfuerzo relativo, no horas.
6. Tipo de tarjeta de notificación y fecha de entrega del informe: por confirmar con el profesor.
7. Google Calendar: la verificación de permisos sensibles puede exigir usuarios de prueba. Por confirmar con la documentación oficial.

## Ceremonias (sprints de una semana)

- Lunes: planificación del sprint. Las tarjetas del sprint pasan de Backlog a Pendiente.
- Lunes a viernes: seguimiento breve asíncrono (qué hice, qué haré, qué me bloquea).
- Viernes: revisión del sprint y retrospectiva. Sábado y domingo quedan como margen.
- Una tarjeta no se parte entre dos sprints: si no cierra, se vuelve a estimar y pasa completa al siguiente, anotando el motivo.

## Definition of Ready (una tarjeta entra al sprint solo si)

- Tiene historia o descripción, criterios de aceptación verificables, responsable, prioridad, puntos y fecha límite.
- Sus dependencias están cerradas o programadas antes que ella.
- Cabe en un sprint (5 puntos o menos).

## Definition of Done (aplica a toda tarjeta, no se repite por tarjeta)

- Cumple todos sus criterios de aceptación y fue revisada por una persona distinta a quien la hizo, salvo las tarjetas de gestión.
- Si es código, pasa las pruebas automáticas (`python manage.py test`), incluye la prueba de cualquier regla de permisos nueva y está integrada a la rama principal mediante un PR.
- Si es documento o plantilla, está en el vault y en el proyecto de Claude, con fuentes citadas y formato editorial USIL cuando aplique.
- Cualquier cifra cuantitativa indica su fuente o está marcada como supuesto.
- Quedó anotada en la bitácora con fecha y se comunicó al equipo por el canal acordado.

## Flujo de estados a configurar en Jira

Configurar estos seis, en este orden:

1. Backlog: la tarjeta existe pero no está comprometida a un sprint en curso.
2. Pendiente: tiene sprint y fechas asignadas, el trabajo no ha arrancado.
3. En progreso: se trabaja activamente.
4. En revisión: el trabajo de fondo está hecho, falta que alguien lo valide o se comunique.
5. Bloqueada: no avanza por una dependencia externa. No es lo mismo que prioridad Bloqueante: son campos distintos.
6. Cumplida: cerrada y cumple la Definition of Done.

Flujo normal: Backlog, Pendiente, En progreso, En revisión, Cumplida. Bloqueada es una salida lateral desde cualquier estado intermedio, no un paso fijo.

## Escalas

- Prioridad (campo Priority de Jira, renombrar los valores): Bloqueante (sin esto se detiene el proyecto o la entrega), Alta, Media, Baja.
- Puntos (campo Story Points): 1, 2, 3, 5, 8. Una tarjeta de 8 debe dividirse antes de entrar a un sprint.
- Etiquetas (Labels): palabras en minúscula sin espacios, tal como aparecen en cada tarjeta.

## Cómo cargar en Jira

1. Crear un proyecto Scrum (clave sugerida: QDM) y configurar los seis estados.
2. Crear las nueve épicas.
3. Crear los sprints 0 a 7 con las fechas de la tabla de sprints.
4. Para cada tarjeta, en el orden de este documento: Resumen = Nombre; Descripción = Historia o Descripción, Criterios de aceptación e Hipótesis (si hay); Epic o Parent = Épica; Priority, Story Points, Assignee, Sprint, Start date y Due date = los campos homónimos; Labels = Etiquetas; en Linked issues, "es bloqueada por" = Depende de.
5. El Estado inicial de cada tarjeta se indica en su ficha. Las tarjetas de sprints futuros se crean en Backlog y pasan a Pendiente en la planificación del lunes.
6. Jira asigna la clave (QDM-1, QDM-2...) en orden de creación. El Código de este documento (HU-01, TR-01) se pone al inicio del Resumen para no perder la correspondencia.

## Épicas

| Épica | Nombre |
| ----- | ------ |
| EP-01 | Validación con el profesor y supuestos |
| EP-02 | Base técnica y arquitectura |
| EP-03 | Cuentas y vínculos |
| EP-04 | Solicitudes y propuesta de horarios |
| EP-05 | Aprobación y confirmación |
| EP-06 | Integración con calendarios |
| EP-07 | Calidad, pruebas y despliegue |
| EP-08 | Gestión del proyecto |
| EP-09 | Informe final y plantillas |

## Sprints

| Sprint | Fechas | Puntos | Objetivo del sprint |
| ------ | ------ | ------ | ------------------- |
| 0 | 12/10/2026 al 18/10/2026 | 6 | Dejar definido el pivote corporativo, la propuesta de valor tentativa y el tablero de Jira configurado. |
| 1 | 19/10/2026 al 25/10/2026 | 27 | Esqueleto funcional: arquitectura decidida y Módulo 1 (cuentas con rol, vínculo asistente-ejecutivo y solicitudes de reunión) corriendo de punta a punta con pruebas. |
| 2 | 26/10/2026 al 01/11/2026 | 21 | La asistente obtiene tres horarios ordenados por las preferencias del ejecutivo y la contraparte participa sin instalar nada. |
| 3 | 02/11/2026 al 08/11/2026 | 15 | El ejecutivo aprueba con un toque desde un enlace firmado y la reunión queda confirmada, con aviso por correo y medida. |
| 4 | 09/11/2026 al 15/11/2026 | 12 | La disponibilidad se obtiene de Google Calendar (solo libre y ocupado) con un plan alterno por archivo de calendario. |
| 5 | 16/11/2026 al 22/11/2026 | 16 | Pruebas con el profesor como usuario, correcciones, pulido de interfaz y despliegue estable. |
| 6 | 23/11/2026 al 29/11/2026 | 18 | Documentación del curso: plantillas rehechas, benchmark con fuentes primarias, BMC y flujo de caja corporativos. |
| 7 | 30/11/2026 al 06/12/2026 | 14 | Entregar el informe final, el paper y el pitch con la demostración ensayada. |

Puntos comprometidos en sprints 0 a 7: 129 (Mayerly Damián: 87; Rossy: 42). Puntos cerrados al día de hoy: 10. Puntos en revisión: 18. Puntos del backlog sin sprint: 21.

## Resumen de tarjetas

| Código | Nombre | Tipo | Épica | Responsable | Prioridad | Puntos | Sprint | Fecha límite | Estado |
| ------ | ------ | ---- | ----- | ----------- | --------- | ------ | ------ | ------------ | ------ |
| TR-01 | Definir el pivote corporativo y la propuesta de valor tentativa | Tarea | EP-01 | Mayerly Damián | Alta | 2 | 0 | 14/10/2026 | Cumplida |
| TR-02 | Configurar el tablero de Jira (estados, épicas, sprints y campos) | Tarea | EP-08 | Rossy | Alta | 2 | 0 | 16/10/2026 | En progreso |
| TR-03 | Resumir los vacíos de Calendly y de las herramientas actuales (versión preliminar) | Tarea | EP-01 | Mayerly Damián | Media | 2 | 0 | 16/10/2026 | Cumplida |
| TR-04 | Decidir el stack y la arquitectura (ADR-001: Django y PostgreSQL) | Tarea | EP-02 | Mayerly Damián | Alta | 2 | 1 | 19/10/2026 | Cumplida |
| TR-05 | Estructura del repositorio, entorno local, variables y guía de despliegue | Tarea | EP-02 | Mayerly Damián | Alta | 2 | 1 | 19/10/2026 | En revisión |
| TR-06 | Contratos de datos y datos de ejemplo para trabajo en paralelo | Tarea | EP-02 | Mayerly Damián | Alta | 2 | 1 | 19/10/2026 | Cumplida |
| HU-01 | Cuentas con rol de asistente y de ejecutivo | Historia | EP-03 | Mayerly Damián | Alta | 3 | 1 | 19/10/2026 | En revisión |
| HU-02 | Vínculo asistente-ejecutivo mediante código | Historia | EP-03 | Mayerly Damián | Alta | 3 | 1 | 19/10/2026 | En revisión |
| HU-03 | Modelo de datos y reglas de visibilidad por rol | Historia | EP-02 | Mayerly Damián | Bloqueante | 5 | 1 | 19/10/2026 | En revisión |
| HU-04 | Crear y ver solicitudes de reunión | Historia | EP-04 | Mayerly Damián | Alta | 5 | 1 | 19/10/2026 | En revisión |
| TR-07 | Pruebas automáticas del Módulo 1 | Tarea | EP-07 | Mayerly Damián | Alta | 2 | 1 | 19/10/2026 | Cumplida |
| TR-08 | Prueba manual del flujo completo del Módulo 1 | Tarea | EP-07 | Mayerly Damián | Alta | 1 | 1 | 19/10/2026 | Pendiente |
| TR-09 | Incorporación de Rossy: instalar, correr el proyecto y enviar captura | Tarea | EP-02 | Rossy | Alta | 1 | 1 | 20/10/2026 | Pendiente |
| TR-10 | Revisión de sprint con el profesor: demostración del Módulo 1 y tres preguntas | Tarea | EP-01 | Mayerly Damián | Alta | 1 | 1 | 20/10/2026 | Pendiente |
| HU-05 | Espacio compartido con la contraparte sin instalación (enlace firmado) | Historia | EP-04 | Mayerly Damián | Alta | 5 | 2 | 29/10/2026 | Backlog |
| HU-06 | Tres horarios ordenados con el motivo de cada uno | Historia | EP-04 | Mayerly Damián | Bloqueante | 5 | 2 | 30/10/2026 | Backlog |
| HU-07 | Preferencias del ejecutivo (horarios protegidos) | Historia | EP-04 | Mayerly Damián | Alta | 3 | 2 | 30/10/2026 | Backlog |
| TR-11 | Portar el algoritmo de ranking a Python con diez escenarios de prueba | Tarea | EP-04 | Rossy | Alta | 5 | 2 | 28/10/2026 | Backlog |
| TR-12 | Maqueta de la tarjeta de aprobación con datos de ejemplo | Tarea | EP-05 | Rossy | Alta | 3 | 2 | 29/10/2026 | Backlog |
| HU-08 | Aprobación en un toque desde un enlace firmado | Historia | EP-05 | Mayerly Damián | Bloqueante | 5 | 3 | 04/11/2026 | Backlog |
| HU-09 | Confirmación de la reunión y archivo de invitación (.ics) | Historia | EP-05 | Mayerly Damián | Alta | 2 | 3 | 05/11/2026 | Backlog |
| HU-10 | Métricas de uso: mensajes evitados y tiempo hasta confirmar | Historia | EP-07 | Mayerly Damián | Alta | 3 | 3 | 05/11/2026 | Backlog |
| HU-11 | Aviso por correo al ejecutivo con el enlace de aprobación | Historia | EP-05 | Rossy | Alta | 3 | 3 | 05/11/2026 | Backlog |
| TR-13 | Verificación independiente del Módulo 2 | Tarea | EP-07 | Rossy | Media | 2 | 3 | 06/11/2026 | Backlog |
| HU-12 | Lectura de libre u ocupado desde Google Calendar | Historia | EP-06 | Mayerly Damián | Alta | 5 | 4 | 12/11/2026 | Backlog |
| TR-14 | Plan alterno: importar disponibilidad desde un archivo de calendario (.ics) | Tarea | EP-06 | Mayerly Damián | Alta | 3 | 4 | 11/11/2026 | Backlog |
| TR-15 | Consentimiento y aviso de privacidad al conectar un calendario | Tarea | EP-06 | Rossy | Media | 2 | 4 | 11/11/2026 | Backlog |
| TR-16 | Verificación independiente de la integración con calendarios | Tarea | EP-07 | Rossy | Media | 2 | 4 | 13/11/2026 | Backlog |
| TR-17 | Pruebas con el profesor como usuario y registro de resultados | Tarea | EP-07 | Rossy | Alta | 3 | 5 | 18/11/2026 | Backlog |
| TR-18 | Corrección de los hallazgos de las pruebas | Tarea | EP-07 | Mayerly Damián | Alta | 5 | 5 | 20/11/2026 | Backlog |
| TR-19 | Pulido visual y de usabilidad de la interfaz | Tarea | EP-07 | Rossy | Media | 5 | 5 | 20/11/2026 | Backlog |
| TR-20 | Despliegue estable en Render con PostgreSQL y datos de demostración | Tarea | EP-07 | Mayerly Damián | Alta | 3 | 5 | 20/11/2026 | Backlog |
| TR-21 | Rehacer árbol de problemas, mapa de empatía, persona y propuesta de valor | Tarea | EP-09 | Rossy | Alta | 5 | 6 | 26/11/2026 | Backlog |
| TR-22 | Benchmark de herramientas corporativas con fuentes primarias | Tarea | EP-09 | Rossy | Alta | 3 | 6 | 25/11/2026 | Backlog |
| TR-23 | BMC corporativo con precio por asiento | Tarea | EP-09 | Mayerly Damián | Alta | 5 | 6 | 27/11/2026 | Backlog |
| TR-24 | Flujo de caja corporativo (VAN, TIR, ROI, PRI y B/C) con escenarios | Tarea | EP-09 | Mayerly Damián | Alta | 5 | 6 | 27/11/2026 | Backlog |
| TR-25 | Informe final con todas las plantillas y formato editorial USIL | Tarea | EP-09 | Rossy | Bloqueante | 5 | 7 | 04/12/2026 | Backlog |
| TR-26 | Borrador del paper de ciencias del diseño | Tarea | EP-09 | Mayerly Damián | Media | 5 | 7 | 04/12/2026 | Backlog |
| TR-27 | Pitch final y demostración ensayada | Tarea | EP-08 | Mayerly Damián | Alta | 3 | 7 | 04/12/2026 | Backlog |
| TR-28 | Retrospectiva final y cierre del tablero en Jira | Tarea | EP-08 | Rossy | Media | 1 | 7 | 04/12/2026 | Backlog |
| HU-13 | Reuniones con tres o más participantes | Historia | EP-04 | Mayerly Damián | Media | 5 | Backlog | Sin asignar | Backlog |
| HU-14 | Integración con Outlook mediante Microsoft Graph | Historia | EP-06 | Mayerly Damián | Media | 8 | Backlog | Sin asignar | Backlog |
| HU-15 | Aprendizaje de preferencias a partir de decisiones pasadas | Historia | EP-04 | Mayerly Damián | Baja | 5 | Backlog | Sin asignar | Backlog |
| HU-16 | Entrevista a una asistente ejecutiva (validación opcional) | Historia | EP-01 | Rossy | Baja | 3 | Backlog | Sin asignar | Backlog |

## Mapa de dependencias principales

- Sprint 1: TR-04 habilita TR-05, TR-06 y HU-03; HU-01 habilita HU-02; HU-02 y HU-03 habilitan HU-04; HU-04 habilita TR-07; TR-08 habilita TR-10.
- Sprint 2: HU-04 habilita HU-05; HU-05 y TR-11 habilitan HU-06; HU-06 habilita HU-07; TR-09 habilita TR-11 y TR-12.
- Sprint 3: HU-06 y TR-12 habilitan HU-08; HU-08 habilita HU-09, HU-10, HU-11 y TR-13.
- Sprint 4: HU-06 y TR-15 habilitan HU-12; HU-06 habilita TR-14; HU-12 y TR-14 habilitan TR-16.
- Sprint 5: HU-09 habilita TR-17; TR-13, TR-16 y TR-17 habilitan TR-18; TR-12 habilita TR-19.
- Sprints 6 y 7: TR-17 habilita TR-21; TR-03 habilita TR-22; TR-22 habilita TR-23; TR-23 habilita TR-24; TR-21, TR-23 y TR-24 alimentan TR-25.

## Riesgos del plan

| Riesgo | Efecto | Respuesta |
| ------ | ------ | --------- |
| Rossy aún no tiene el contexto del código y de las decisiones | Retraso en las tareas de código del Sprint 2 | Nota de arranque, sesión corta de 30 minutos con Mayerly, criterios de aceptación claros en cada tarjeta y revisión en cada PR |
| Una sola persona concentra el desarrollo | Cuello de botella en los sprints 2 a 5 | Recortar alcance con base en la revisión del profesor; repartir más código a Rossy desde el Sprint 3; mantener HU-13 y HU-15 fuera del plan |
| Verificación de permisos de Google no lista a tiempo | HU-12 no se completa | Plan alterno por archivo .ics (TR-14) |
| El profesor no puede actuar como usuario | Sin evidencia de uso | Probar con otro docente y declarar la limitación en el informe |
| Plan gratuito de Render duerme la aplicación | Demostración lenta | Abrirla antes de cada presentación |
| Una sola fuente de validación | Hipótesis débiles | Reportar la limitación; activar HU-16 si hay un contacto |

---

# Registro de tarjetas, listas para copiar en Jira

## Sprint 0: 12/10/2026 al 18/10/2026

Objetivo: Dejar definido el pivote corporativo, la propuesta de valor tentativa y el tablero de Jira configurado.

### TR-01

Código: TR-01
Nombre: Definir el pivote corporativo y la propuesta de valor tentativa
Tipo Jira: Tarea
Épica: EP-01, Validación con el profesor y supuestos
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 2
Sprint: 0
Fecha de inicio: 12/10/2026
Fecha límite: 14/10/2026
Estado inicial: Cumplida
Depende de: Ninguna
Etiquetas: pivote, propuesta-de-valor

Descripción: Reorientar Quedamos al mundo corporativo tras el feedback del pitch y dejar por escrito la propuesta de valor tentativa y las hipótesis de diferenciación.

Criterios de aceptación:
- Existe un texto de propuesta de valor con usuario (asistente), beneficiario (ejecutivo), problema y resultado medible.
- Las diferenciaciones frente a la competencia están marcadas como hipótesis por verificar, no como hechos.
- El alcance corporativo exclusivo quedó registrado en la bitácora del equipo con fecha.

Nota o riesgo: La dirección se confirma con el profesor en TR-10.

---

### TR-02

Código: TR-02
Nombre: Configurar el tablero de Jira (estados, épicas, sprints y campos)
Tipo Jira: Tarea
Épica: EP-08, Gestión del proyecto
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 2
Sprint: 0
Fecha de inicio: 14/10/2026
Fecha límite: 16/10/2026
Estado inicial: En progreso
Depende de: Ninguna
Etiquetas: jira, gestion

Descripción: Crear el proyecto Scrum en Jira con los seis estados acordados, las nueve épicas, los ocho sprints de una semana y los campos necesarios.

Criterios de aceptación:
- Los seis estados existen en el flujo de trabajo en el orden definido en este documento.
- Las nueve épicas EP-01 a EP-09 están creadas con su nombre.
- Los sprints 0 a 7 están creados con fecha de inicio y fin de una semana cada uno.
- Las tarjetas de los sprints 0 a 7 y las del backlog están cargadas con todos sus campos.

Nota o riesgo: Jira asigna la clave (por ejemplo QDM-1) en orden de creación. Cargar las tarjetas en el orden de este documento y poner el código al inicio del resumen.

---

### TR-03

Código: TR-03
Nombre: Resumir los vacíos de Calendly y de las herramientas actuales (versión preliminar)
Tipo Jira: Tarea
Épica: EP-01, Validación con el profesor y supuestos
Responsable: Mayerly Damián
Prioridad: Media
Puntos: 2
Sprint: 0
Fecha de inicio: 13/10/2026
Fecha límite: 16/10/2026
Estado inicial: Cumplida
Depende de: Ninguna
Etiquetas: competencia, benchmark

Descripción: Resumir cómo funciona Calendly (el anfitrión define reglas, el invitado elige) y qué vacíos deja frente a la negociación entre asistentes.

Criterios de aceptación:
- El resumen distingue lo que Calendly hace (sondeos, enlaces de reserva) de lo que no hace.
- Las afirmaciones sin respaldo oficial quedan marcadas como no verificadas.

Nota o riesgo: Es una versión preliminar. La verificación con fuentes primarias se hace en TR-23.

---

## Sprint 1: 19/10/2026 al 25/10/2026

Objetivo: Esqueleto funcional: arquitectura decidida y Módulo 1 (cuentas con rol, vínculo asistente-ejecutivo y solicitudes de reunión) corriendo de punta a punta con pruebas.

### TR-04

Código: TR-04
Nombre: Decidir el stack y la arquitectura (ADR-001: Django y PostgreSQL)
Tipo Jira: Tarea
Épica: EP-02, Base técnica y arquitectura
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 2
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: Cumplida
Depende de: Ninguna
Etiquetas: arquitectura, adr

Descripción: Elegir un stack clásico con backend propio y dejar la decisión, sus motivos y sus límites en una página.

Criterios de aceptación:
- El documento ADR-001 explica la elección por capa, la estructura del proyecto y las consecuencias conocidas.
- La decisión fue aprobada por Mayerly antes de construir.

Nota o riesgo: Alternativas descartadas: Next.js con Supabase (backend oculto en un servicio externo), FastAPI con React y Node con React (dos proyectos).

---

### TR-05

Código: TR-05
Nombre: Estructura del repositorio, entorno local, variables y guía de despliegue
Tipo Jira: Tarea
Épica: EP-02, Base técnica y arquitectura
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 2
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: En revisión
Depende de: TR-04
Etiquetas: repositorio, entorno

Descripción: Dejar un proyecto que cualquier integrante pueda correr en minutos y que ya tenga lo necesario para publicarse.

Criterios de aceptación:
- Dado un equipo con Python, cuando se siguen los pasos de docs/PASOS_MODULO1.md, entonces la aplicación corre sin cuentas externas.
- Existen archivos de dependencias, ejemplo de variables de entorno, .gitignore y comandos de construcción para Render.
- El proyecto se probó en dos entornos distintos (Python 3.10 con Django 5.2 y Python 3.13 con Django 6.1).

Nota o riesgo: Pasa a Cumplida cuando Mayerly lo corra en su computador.

---

### TR-06

Código: TR-06
Nombre: Contratos de datos y datos de ejemplo para trabajo en paralelo
Tipo Jira: Tarea
Épica: EP-02, Base técnica y arquitectura
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 2
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: Cumplida
Depende de: TR-04
Etiquetas: contratos, equipo

Descripción: Definir las estructuras de la propuesta de horarios y datos de ejemplo para que Rossy construya pantallas sin esperar la base de datos.

Criterios de aceptación:
- scheduling/contracts.py define la propuesta y sus tres opciones.
- scheduling/mock.py trae un caso de ejemplo y /demo/tarjeta/ lo muestra.

Nota o riesgo: Cambiar los nombres de los contratos requiere avisar a quien conecta los datos.

---

### HU-01

Código: HU-01
Nombre: Cuentas con rol de asistente y de ejecutivo
Tipo Jira: Historia
Épica: EP-03, Cuentas y vínculos
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 3
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: En revisión
Depende de: TR-05
Etiquetas: cuentas, roles

Historia: Como asistente ejecutiva, quiero crear mi cuenta e ingresar con mi correo, para coordinar las reuniones de mi ejecutivo sin compartir su contraseña.

Criterios de aceptación:
- Dado un usuario nuevo, cuando se registra, entonces elige rol de asistente o ejecutivo y entra a su panel.
- Solo el ejecutivo recibe un código de vinculación de 6 caracteres, que no cambia.
- El correo no puede repetirse, aunque cambie la capitalización, y las contraseñas débiles se rechazan.
- Sin sesión, el panel redirige al ingreso.

Nota o riesgo: El rol se elige libremente en el registro. En producción, el de ejecutivo debería verificarse por dominio de empresa.

---

### HU-02

Código: HU-02
Nombre: Vínculo asistente-ejecutivo mediante código
Tipo Jira: Historia
Épica: EP-03, Cuentas y vínculos
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 3
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: En revisión
Depende de: HU-01
Etiquetas: vinculos

Historia: Como asistente, quiero vincularme con mi ejecutivo usando el código que él me comparte, para que el sistema sepa a quién represento.

Criterios de aceptación:
- Dado un código válido, con cualquier capitalización o espacios, cuando la asistente lo ingresa, entonces queda vinculada.
- Un código inválido muestra un mensaje claro y vincularse dos veces no duplica el vínculo.
- Un ejecutivo no puede usar la vinculación y nadie puede quitar un vínculo ajeno.
- Al desvincularse, la asistente deja de ver las solicitudes de ese ejecutivo.

---

### HU-03

Código: HU-03
Nombre: Modelo de datos y reglas de visibilidad por rol
Tipo Jira: Historia
Épica: EP-02, Base técnica y arquitectura
Responsable: Mayerly Damián
Prioridad: Bloqueante
Puntos: 5
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: En revisión
Depende de: TR-04
Etiquetas: datos, seguridad

Historia: Como Director del proyecto, quiero que cada persona vea solo la información que le corresponde, para proteger las agendas de los ejecutivos.

Criterios de aceptación:
- Existen los modelos de usuario, vínculo y solicitud, con restricciones de base de datos (un vínculo único y nadie puede vincularse consigo mismo).
- La regla de visibilidad está en un solo lugar del código y tiene pruebas.
- Quien crea una solicitud lo define el servidor, no el formulario.
- Las migraciones están versionadas.

Nota o riesgo: Reemplaza las reglas de base de datos de la propuesta inicial por permisos en la capa de aplicación.

---

### HU-04

Código: HU-04
Nombre: Crear y ver solicitudes de reunión
Tipo Jira: Historia
Épica: EP-04, Solicitudes y propuesta de horarios
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 5
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: En revisión
Depende de: HU-02, HU-03
Etiquetas: solicitudes, nucleo

Historia: Como asistente ejecutiva, quiero registrar una solicitud de reunión de mi ejecutivo, para iniciar la coordinación con la otra parte.

Criterios de aceptación:
- Dado una asistente vinculada, cuando crea una solicitud con asunto, contraparte y duración, entonces queda guardada con estado pendiente.
- El ejecutivo la ve en su panel sin recargar, en unos 5 segundos.
- No se puede crear una solicitud para un ejecutivo sin vínculo ni con datos inválidos, y el error se muestra en pantalla.
- El texto ingresado se escapa y no ejecuta código.

---

### TR-07

Código: TR-07
Nombre: Pruebas automáticas del Módulo 1
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 2
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: Cumplida
Depende de: HU-04
Etiquetas: pruebas, calidad

Descripción: Cubrir con pruebas automáticas registro, ingreso, vínculos, visibilidad, validaciones y suplantación.

Criterios de aceptación:
- python manage.py test ejecuta 31 pruebas y todas pasan.
- Se verificó el flujo completo con dos usuarios reales en un navegador.

---

### TR-08

Código: TR-08
Nombre: Prueba manual del flujo completo del Módulo 1
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 1
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 19/10/2026
Estado inicial: Pendiente
Depende de: TR-05
Etiquetas: pruebas, validacion

Descripción: Seguir la prueba de docs/PASOS_MODULO1.md en el computador propio.

Criterios de aceptación:
- Los cinco pasos de la prueba se completan sin errores o los errores quedan registrados.
- Al terminar, las tarjetas del Módulo 1 pasan a Cumplida.

---

### TR-09

Código: TR-09
Nombre: Incorporación de Rossy: instalar, correr el proyecto y enviar captura
Tipo Jira: Tarea
Épica: EP-02, Base técnica y arquitectura
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 1
Sprint: 1
Fecha de inicio: 19/10/2026
Fecha límite: 20/10/2026
Estado inicial: Pendiente
Depende de: TR-05
Etiquetas: onboarding, equipo

Descripción: Leer docs/NOTA_ROSSY.md, instalar el proyecto, correrlo y enviar una captura del panel funcionando.

Criterios de aceptación:
- La captura muestra el panel con un usuario de prueba.
- Los problemas de instalación quedan anotados con el mensaje exacto.

Nota o riesgo: Si no se completa el martes 20/10, pasa al Sprint 2 y se registra el motivo.

---

### TR-10

Código: TR-10
Nombre: Revisión de sprint con el profesor: demostración del Módulo 1 y tres preguntas
Tipo Jira: Tarea
Épica: EP-01, Validación con el profesor y supuestos
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 1
Sprint: 1
Fecha de inicio: 20/10/2026
Fecha límite: 20/10/2026
Estado inicial: Pendiente
Depende de: TR-08
Etiquetas: validacion, revision-sprint

Descripción: Mostrar al profesor lo que corre y registrar sus respuestas a tres preguntas sobre los supuestos del proyecto.

Criterios de aceptación:
- Se muestra el flujo completo funcionando.
- Quedan registradas sus respuestas a: ¿la asistente es quien coordina las reuniones?, ¿aprobar con un toque le serviría? y ¿cuánto pagaría por asiento?
- El alcance de los siguientes sprints se ajusta según sus respuestas.

Hipótesis y métrica: H1: coordinar reuniones consume tiempo y genera idas y vueltas. H2: la asistente opera la coordinación y el ejecutivo solo aprueba. Se registran como respaldo parcial: es un solo informante.

---

## Sprint 2: 26/10/2026 al 01/11/2026

Objetivo: La asistente obtiene tres horarios ordenados por las preferencias del ejecutivo y la contraparte participa sin instalar nada.

### HU-05

Código: HU-05
Nombre: Espacio compartido con la contraparte sin instalación (enlace firmado)
Tipo Jira: Historia
Épica: EP-04, Solicitudes y propuesta de horarios
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 5
Sprint: 2
Fecha de inicio: 26/10/2026
Fecha límite: 29/10/2026
Estado inicial: Backlog
Depende de: HU-04
Etiquetas: nucleo, colaboracion

Historia: Como asistente ejecutiva, quiero compartir un enlace con la asistente de la otra parte para que indique su disponibilidad sin crear cuenta, y así negociar sin intercambiar correos.

Criterios de aceptación:
- Dado una solicitud, cuando la asistente genera el enlace, entonces la contraparte abre una página y marca su disponibilidad sin crear cuenta.
- El enlace es firmado, expira y solo da acceso a esa solicitud.
- La contraparte no ve información del ejecutivo salvo el asunto.

Nota o riesgo: La contraparte sin instalación es la hipótesis más frágil. Se verifica en las pruebas.

---

### HU-06

Código: HU-06
Nombre: Tres horarios ordenados con el motivo de cada uno
Tipo Jira: Historia
Épica: EP-04, Solicitudes y propuesta de horarios
Responsable: Mayerly Damián
Prioridad: Bloqueante
Puntos: 5
Sprint: 2
Fecha de inicio: 27/10/2026
Fecha límite: 30/10/2026
Estado inicial: Backlog
Depende de: HU-05, TR-11
Etiquetas: nucleo, algoritmo, diferenciador

Historia: Como asistente ejecutiva, quiero que el sistema proponga tres horarios ordenados según las preferencias de mi ejecutivo y me explique por qué, para decidir rápido y con respaldo.

Criterios de aceptación:
- Dado la disponibilidad de ambas partes, cuando se genera la propuesta, entonces se muestran tres opciones ordenadas con una explicación breve de cada una.
- Si no hay coincidencia, el sistema lo indica y sugiere ampliar el rango.
- Usa el módulo de ranking de TR-11 y agrega la explicación de cada opción.

Hipótesis y métrica: H3: la propuesta ordenada reduce el intercambio de mensajes. Meta propuesta: al menos 2 de las 3 opciones son aceptables para el ejecutivo.

Nota o riesgo: Es la funcionalidad que sostiene el diferenciador. No recortar sin decisión del equipo.

---

### HU-07

Código: HU-07
Nombre: Preferencias del ejecutivo (horarios protegidos)
Tipo Jira: Historia
Épica: EP-04, Solicitudes y propuesta de horarios
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 3
Sprint: 2
Fecha de inicio: 28/10/2026
Fecha límite: 30/10/2026
Estado inicial: Backlog
Depende de: HU-06
Etiquetas: nucleo, preferencias

Historia: Como asistente ejecutiva, quiero registrar las reglas de mi ejecutivo (por ejemplo, nada antes de las 10 o viernes protegido), para que las propuestas las respeten.

Criterios de aceptación:
- Dado una regla registrada, cuando se genera una propuesta, entonces ninguna opción la viola.
- Las reglas se pueden editar y desactivar, y cada opción indica cuáles cumple.

Nota o riesgo: Alcance mínimo: bloques horarios y días.

---

### TR-11

Código: TR-11
Nombre: Portar el algoritmo de ranking a Python con diez escenarios de prueba
Tipo Jira: Tarea
Épica: EP-04, Solicitudes y propuesta de horarios
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 5
Sprint: 2
Fecha de inicio: 26/10/2026
Fecha límite: 28/10/2026
Estado inicial: Backlog
Depende de: TR-09
Etiquetas: algoritmo, pruebas, nucleo

Descripción: Portar la lógica de puntuación de bloques horarios de docs/referencia/matching.ts a scheduling/matching.py y cubrirla con diez escenarios de prueba.

Criterios de aceptación:
- scheduling/matching.py reproduce el comportamiento de la referencia: puntúa cada bloque por cantidad de disponibles y desempata por preferencia alta.
- scheduling/tests.py ejecuta diez escenarios, con al menos uno sin coincidencia y uno con empate, y todos pasan con python manage.py test.
- El módulo no depende de Django ni de la base de datos, para poder probarse solo.

Nota o riesgo: Mayerly construye sobre este módulo la propuesta de tres horarios con su motivo (HU-06).

---

### TR-12

Código: TR-12
Nombre: Maqueta de la tarjeta de aprobación con datos de ejemplo
Tipo Jira: Tarea
Épica: EP-05, Aprobación y confirmación
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 3
Sprint: 2
Fecha de inicio: 26/10/2026
Fecha límite: 29/10/2026
Estado inicial: Backlog
Depende de: TR-09
Etiquetas: interfaz, aprobacion

Descripción: Construir en templates/demo/tarjeta.html la tarjeta que verá el ejecutivo, usando los datos de scheduling/mock.py.

Criterios de aceptación:
- Muestra título, contraparte, duración y tres opciones con su motivo.
- Cada opción tiene un botón Aprobar y existe un botón Ninguna me sirve.
- Se entiende en cinco segundos y se ve correctamente en el celular.

---

## Sprint 3: 02/11/2026 al 08/11/2026

Objetivo: El ejecutivo aprueba con un toque desde un enlace firmado y la reunión queda confirmada, con aviso por correo y medida.

### HU-08

Código: HU-08
Nombre: Aprobación en un toque desde un enlace firmado
Tipo Jira: Historia
Épica: EP-05, Aprobación y confirmación
Responsable: Mayerly Damián
Prioridad: Bloqueante
Puntos: 5
Sprint: 3
Fecha de inicio: 02/11/2026
Fecha límite: 04/11/2026
Estado inicial: Backlog
Depende de: HU-06, TR-12
Etiquetas: aprobacion, diferenciador

Historia: Como ejecutivo, quiero recibir un enlace con tres opciones y aprobar una con un solo toque, sin iniciar sesión, para confirmar sin intercambiar mensajes.

Criterios de aceptación:
- Dado el enlace, cuando el ejecutivo lo abre, entonces ve las tres opciones con el motivo de cada una.
- Con un solo toque la opción queda aprobada y la asistente lo ve reflejado.
- El ejecutivo puede rechazar todas y pedir otras sin escribir un mensaje largo.
- Un enlace vencido o alterado es rechazado.

Hipótesis y métrica: H4: el ejecutivo aprueba en un toque sin aprender una herramienta nueva.

Nota o riesgo: Responde al requerimiento del profesor sobre notificaciones.

---

### HU-09

Código: HU-09
Nombre: Confirmación de la reunión y archivo de invitación (.ics)
Tipo Jira: Historia
Épica: EP-05, Aprobación y confirmación
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 2
Sprint: 3
Fecha de inicio: 04/11/2026
Fecha límite: 05/11/2026
Estado inicial: Backlog
Depende de: HU-08
Etiquetas: confirmacion, ics

Historia: Como asistente ejecutiva, quiero que al aprobar se genere la invitación para ambas partes, para que la reunión quede en sus calendarios.

Criterios de aceptación:
- Dado una opción aprobada, entonces se genera un archivo .ics válido y la reunión pasa a estado aprobada.
- La reunión confirmada aparece en el historial.

---

### HU-10

Código: HU-10
Nombre: Métricas de uso: mensajes evitados y tiempo hasta confirmar
Tipo Jira: Historia
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 3
Sprint: 3
Fecha de inicio: 04/11/2026
Fecha límite: 05/11/2026
Estado inicial: Backlog
Depende de: HU-08
Etiquetas: metricas, validacion

Historia: Como equipo, quiero medir cuánto tarda una reunión en confirmarse y cuántos pasos requiere, para demostrar el resultado con datos.

Criterios de aceptación:
- Por cada reunión se registran la fecha de solicitud, la de confirmación y el número de interacciones.
- Existe una vista simple que lo muestra y no se guardan detalles de los eventos del calendario.

Hipótesis y métrica: H5: el tiempo hasta confirmar y los mensajes cruzados disminuyen respecto a la línea base declarada en las entrevistas y pruebas.

---

### HU-11

Código: HU-11
Nombre: Aviso por correo al ejecutivo con el enlace de aprobación
Tipo Jira: Historia
Épica: EP-05, Aprobación y confirmación
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 3
Sprint: 3
Fecha de inicio: 04/11/2026
Fecha límite: 05/11/2026
Estado inicial: Backlog
Depende de: HU-08
Etiquetas: correo, notificacion

Historia: Como ejecutivo, quiero recibir un correo con las opciones y el botón de aprobación, para decidir desde el celular.

Criterios de aceptación:
- Dado una propuesta lista, entonces se envía un correo con el enlace de aprobación.
- En desarrollo el correo se imprime en la terminal y en producción usa un servidor de correo configurado por variables de entorno.

---

### TR-13

Código: TR-13
Nombre: Verificación independiente del Módulo 2
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Rossy (apellido por confirmar)
Prioridad: Media
Puntos: 2
Sprint: 3
Fecha de inicio: 05/11/2026
Fecha límite: 06/11/2026
Estado inicial: Backlog
Depende de: HU-08
Etiquetas: pruebas, validacion

Descripción: Probar el flujo completo del Módulo 2 siguiendo una lista de pasos y registrar hallazgos en Jira.

Criterios de aceptación:
- Cada hallazgo incluye pasos, resultado esperado, resultado obtenido y captura.
- El informe de hallazgos está en Jira, aunque no haya hallazgos.

---

## Sprint 4: 09/11/2026 al 15/11/2026

Objetivo: La disponibilidad se obtiene de Google Calendar (solo libre y ocupado) con un plan alterno por archivo de calendario.

### HU-12

Código: HU-12
Nombre: Lectura de libre u ocupado desde Google Calendar
Tipo Jira: Historia
Épica: EP-06, Integración con calendarios
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 5
Sprint: 4
Fecha de inicio: 09/11/2026
Fecha límite: 12/11/2026
Estado inicial: Backlog
Depende de: HU-06, TR-15
Etiquetas: calendario, google, integracion

Historia: Como asistente ejecutiva, quiero conectar el calendario de mi ejecutivo para que el sistema lea solo cuándo está libre u ocupado, sin ver los detalles de sus eventos.

Criterios de aceptación:
- Dado un calendario conectado, cuando se consulta, entonces solo se obtienen intervalos de libre u ocupado.
- La conexión se puede revocar y la demo funciona con cuentas de prueba autorizadas.

Nota o riesgo: Riesgo: la verificación de Google para permisos sensibles puede no completarse a tiempo. El plan alterno es TR-14. Por confirmar con la documentación oficial.

---

### TR-14

Código: TR-14
Nombre: Plan alterno: importar disponibilidad desde un archivo de calendario (.ics)
Tipo Jira: Tarea
Épica: EP-06, Integración con calendarios
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 3
Sprint: 4
Fecha de inicio: 09/11/2026
Fecha límite: 11/11/2026
Estado inicial: Backlog
Depende de: HU-06
Etiquetas: calendario, ics

Descripción: Permitir cargar un archivo .ics exportado del calendario para calcular la disponibilidad sin depender de Google.

Criterios de aceptación:
- Dado un archivo .ics válido, entonces se calculan los intervalos ocupados.
- Un archivo inválido muestra un mensaje claro.

---

### TR-15

Código: TR-15
Nombre: Consentimiento y aviso de privacidad al conectar un calendario
Tipo Jira: Tarea
Épica: EP-06, Integración con calendarios
Responsable: Rossy (apellido por confirmar)
Prioridad: Media
Puntos: 2
Sprint: 4
Fecha de inicio: 09/11/2026
Fecha límite: 11/11/2026
Estado inicial: Backlog
Depende de: Ninguna
Etiquetas: privacidad, legal

Descripción: Redactar el texto de consentimiento y el aviso de privacidad según la Ley 29733, dejando marcado lo que requiere revisión profesional.

Criterios de aceptación:
- El texto indica qué datos se leen (solo libre y ocupado) y cuáles nunca se almacenan.
- Se muestra antes de conectar el calendario.

Nota o riesgo: No es asesoría legal.

---

### TR-16

Código: TR-16
Nombre: Verificación independiente de la integración con calendarios
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Rossy (apellido por confirmar)
Prioridad: Media
Puntos: 2
Sprint: 4
Fecha de inicio: 12/11/2026
Fecha límite: 13/11/2026
Estado inicial: Backlog
Depende de: HU-12, TR-14
Etiquetas: pruebas, validacion

Descripción: Probar la conexión con Google Calendar y la importación de .ics, y registrar hallazgos.

Criterios de aceptación:
- Cada hallazgo incluye pasos, resultado esperado, resultado obtenido y captura.

---

## Sprint 5: 16/11/2026 al 22/11/2026

Objetivo: Pruebas con el profesor como usuario, correcciones, pulido de interfaz y despliegue estable.

### TR-17

Código: TR-17
Nombre: Pruebas con el profesor como usuario y registro de resultados
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 3
Sprint: 5
Fecha de inicio: 16/11/2026
Fecha límite: 18/11/2026
Estado inicial: Backlog
Depende de: HU-09
Etiquetas: pruebas, validacion

Descripción: Aplicar un protocolo breve con el profesor (y su asistente si es posible) y registrar tiempos, errores y citas textuales.

Criterios de aceptación:
- Se registran tareas realizadas, tiempos, errores y comentarios textuales.
- Cada hipótesis H1 a H5 queda marcada como sostenida, no sostenida o sin evidencia suficiente, con un solo informante indicado como limitación.

Hipótesis y métrica: Si el profesor no puede, se prueba con otro docente y se deja la limitación escrita.

---

### TR-18

Código: TR-18
Nombre: Corrección de los hallazgos de las pruebas
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 5
Sprint: 5
Fecha de inicio: 17/11/2026
Fecha límite: 20/11/2026
Estado inicial: Backlog
Depende de: TR-13, TR-16, TR-17
Etiquetas: correcciones

Descripción: Priorizar y corregir los problemas que impiden completar el recorrido principal.

Criterios de aceptación:
- Los hallazgos se clasifican por impacto y se corrigen los que bloquean el recorrido principal.
- Los no corregidos quedan en backlog con su justificación.

---

### TR-19

Código: TR-19
Nombre: Pulido visual y de usabilidad de la interfaz
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Rossy (apellido por confirmar)
Prioridad: Media
Puntos: 5
Sprint: 5
Fecha de inicio: 16/11/2026
Fecha límite: 20/11/2026
Estado inicial: Backlog
Depende de: TR-12
Etiquetas: diseno, interfaz

Descripción: Mejorar la presentación de las pantallas ya funcionales: espaciado, jerarquía, textos y uso en celular.

Criterios de aceptación:
- Las pantallas principales se ven correctamente en el celular y en el computador.
- Ningún cambio altera el comportamiento ni rompe las pruebas automáticas.

Nota o riesgo: El diseño se trabaja después de que funcione.

---

### TR-20

Código: TR-20
Nombre: Despliegue estable en Render con PostgreSQL y datos de demostración
Tipo Jira: Tarea
Épica: EP-07, Calidad, pruebas y despliegue
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 3
Sprint: 5
Fecha de inicio: 18/11/2026
Fecha límite: 20/11/2026
Estado inicial: Backlog
Depende de: TR-05
Etiquetas: despliegue, demo

Descripción: Publicar una versión estable con una base PostgreSQL y un caso de demostración precargado.

Criterios de aceptación:
- Existe una URL pública estable y un caso de demostración.
- Las variables sensibles no están en el repositorio.
- Se verificó el recorrido completo en un equipo distinto al de desarrollo.

Nota o riesgo: El plan gratuito duerme la aplicación tras inactividad. Abrirla antes de cada demostración.

---

## Sprint 6: 23/11/2026 al 29/11/2026

Objetivo: Documentación del curso: plantillas rehechas, benchmark con fuentes primarias, BMC y flujo de caja corporativos.

### TR-21

Código: TR-21
Nombre: Rehacer árbol de problemas, mapa de empatía, persona y propuesta de valor
Tipo Jira: Tarea
Épica: EP-09, Informe final y plantillas
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 5
Sprint: 6
Fecha de inicio: 23/11/2026
Fecha límite: 26/11/2026
Estado inicial: Backlog
Depende de: TR-17
Etiquetas: plantillas, informe

Descripción: Rehacer las plantillas con el enfoque corporativo y la evidencia de las pruebas, para incluirlas en el informe final.

Criterios de aceptación:
- Las plantillas usan evidencia registrada en las tarjetas TR-10 y TR-17, y los supuestos están marcados como tales.
- El formato respeta el estilo editorial de la USIL.

Nota o riesgo: El encaje de la propuesta de valor es la herramienta de mayor peso según las notas de clase.

---

### TR-22

Código: TR-22
Nombre: Benchmark de herramientas corporativas con fuentes primarias
Tipo Jira: Tarea
Épica: EP-09, Informe final y plantillas
Responsable: Rossy (apellido por confirmar)
Prioridad: Alta
Puntos: 3
Sprint: 6
Fecha de inicio: 23/11/2026
Fecha límite: 25/11/2026
Estado inicial: Backlog
Depende de: TR-03
Etiquetas: benchmark, competencia

Descripción: Comparar Calendly, Reclaim, Motion, Clockwise, Microsoft FindTime, Carly y Gemini en Google Calendar por funciones, precio por asiento y enfoque.

Criterios de aceptación:
- Cada celda cita la página oficial y la fecha de consulta.
- Se marca qué diferenciaciones de Quedamos siguen siendo hipótesis.

Nota o riesgo: Los datos de proveedores son fuentes interesadas. Contrastar cuando exista fuente independiente.

---

### TR-23

Código: TR-23
Nombre: BMC corporativo con precio por asiento
Tipo Jira: Tarea
Épica: EP-09, Informe final y plantillas
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 5
Sprint: 6
Fecha de inicio: 24/11/2026
Fecha límite: 27/11/2026
Estado inicial: Backlog
Depende de: TR-22
Etiquetas: plantillas, bmc, negocio

Descripción: Rehacer los bloques del BMC con cliente corporativo, precio por asiento, canales y costos completos del stack elegido.

Criterios de aceptación:
- Los parámetros indican si cada dato es validado, estimado o supuesto.
- El precio por asiento se compara con al menos tres herramientas del benchmark.
- Los costos de infraestructura corresponden al despliegue real (Render y PostgreSQL), no a la propuesta inicial.

---

### TR-24

Código: TR-24
Nombre: Flujo de caja corporativo (VAN, TIR, ROI, PRI y B/C) con escenarios
Tipo Jira: Tarea
Épica: EP-09, Informe final y plantillas
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 5
Sprint: 6
Fecha de inicio: 24/11/2026
Fecha límite: 27/11/2026
Estado inicial: Backlog
Depende de: TR-23
Etiquetas: flujo-de-caja, negocio

Descripción: Construir el flujo de caja con el modelo por asiento, reutilizando la lógica del flujo de la Semana 5 y declarando qué parámetros están validados.

Criterios de aceptación:
- Se calculan VAN, TIR, ROI, PRI y B/C a una tasa de descuento del 15%, años 0 a 3.
- Hay tres escenarios y el punto de equilibrio en asientos.
- El veredicto es el que resulte del cálculo, sin ajustar supuestos para forzar la viabilidad.

Nota o riesgo: Si no es viable, se presenta como tal con las palancas legítimas (precio, asientos, costos).

---

## Sprint 7: 30/11/2026 al 06/12/2026

Objetivo: Entregar el informe final, el paper y el pitch con la demostración ensayada.

### TR-25

Código: TR-25
Nombre: Informe final con todas las plantillas y formato editorial USIL
Tipo Jira: Tarea
Épica: EP-09, Informe final y plantillas
Responsable: Rossy (apellido por confirmar)
Prioridad: Bloqueante
Puntos: 5
Sprint: 7
Fecha de inicio: 30/11/2026
Fecha límite: 04/12/2026
Estado inicial: Backlog
Depende de: TR-21, TR-23, TR-24
Etiquetas: informe, entrega

Descripción: Ensamblar el informe con las plantillas rehechas, los resultados de las pruebas y las conclusiones.

Criterios de aceptación:
- Contiene todas las plantillas del proyecto con el enfoque corporativo.
- Cumple el formato editorial de la USIL.
- Cada afirmación cuantitativa tiene fuente o está marcada como supuesto, y el texto no afirma validaciones que no se hicieron.

Nota o riesgo: Fecha de entrega real por confirmar con el cronograma del curso.

---

### TR-26

Código: TR-26
Nombre: Borrador del paper de ciencias del diseño
Tipo Jira: Tarea
Épica: EP-09, Informe final y plantillas
Responsable: Mayerly Damián
Prioridad: Media
Puntos: 5
Sprint: 7
Fecha de inicio: 30/11/2026
Fecha límite: 04/12/2026
Estado inicial: Backlog
Depende de: TR-17
Etiquetas: paper, publicacion

Descripción: Redactar el borrador con la estructura diseño, construcción y evaluación del artefacto, para la revista candidata.

Criterios de aceptación:
- El borrador sigue la estructura del paper modelo del curso.
- La evaluación usa los resultados de TR-17 sin exagerar el alcance.

Nota o riesgo: Revista candidata: Strategic Design Research Journal. Confirmar vigencia y requisitos antes de enviar.

---

### TR-27

Código: TR-27
Nombre: Pitch final y demostración ensayada
Tipo Jira: Tarea
Épica: EP-08, Gestión del proyecto
Responsable: Mayerly Damián
Prioridad: Alta
Puntos: 3
Sprint: 7
Fecha de inicio: 02/12/2026
Fecha límite: 04/12/2026
Estado inicial: Backlog
Depende de: TR-20, TR-24
Etiquetas: pitch, demo

Descripción: Preparar el guion final, las respuestas a preguntas probables y un ensayo cronometrado de la demostración.

Criterios de aceptación:
- El pitch cabe en el tiempo asignado y presenta problema, solución, evidencia y modelo de negocio.
- Hay un plan alterno si la demostración en vivo falla.

---

### TR-28

Código: TR-28
Nombre: Retrospectiva final y cierre del tablero en Jira
Tipo Jira: Tarea
Épica: EP-08, Gestión del proyecto
Responsable: Rossy (apellido por confirmar)
Prioridad: Media
Puntos: 1
Sprint: 7
Fecha de inicio: 04/12/2026
Fecha límite: 04/12/2026
Estado inicial: Backlog
Depende de: Ninguna
Etiquetas: retrospectiva, cierre

Descripción: Realizar la retrospectiva del proyecto y dejar el tablero ordenado.

Criterios de aceptación:
- Se registran qué funcionó, qué no y qué cambiaría el equipo.
- Todas las tarjetas tienen estado final y las pendientes están en backlog con motivo.

---

## Backlog sin sprint

### HU-13

Código: HU-13
Nombre: Reuniones con tres o más participantes
Tipo Jira: Historia
Épica: EP-04, Solicitudes y propuesta de horarios
Responsable: Mayerly Damián
Prioridad: Media
Puntos: 5
Sprint: Sin asignar
Fecha de inicio: Sin asignar
Fecha límite: Sin asignar
Estado inicial: Backlog
Depende de: HU-06
Etiquetas: nucleo, grupo

Historia: Como asistente ejecutiva, quiero coordinar una reunión con varias partes a la vez, para no negociar por pares.

Criterios de aceptación:
- El sistema propone horarios que consideren las preferencias de todas las partes.
- Muestra qué parte queda sin coincidencia cuando no hay horario común.

Nota o riesgo: Retoma el núcleo original de Quedamos.

---

### HU-14

Código: HU-14
Nombre: Integración con Outlook mediante Microsoft Graph
Tipo Jira: Historia
Épica: EP-06, Integración con calendarios
Responsable: Mayerly Damián
Prioridad: Media
Puntos: 8
Sprint: Sin asignar
Fecha de inicio: Sin asignar
Fecha límite: Sin asignar
Estado inicial: Backlog
Depende de: HU-12
Etiquetas: calendario, outlook

Historia: Como asistente en una empresa que usa Microsoft 365, quiero conectar el calendario de mi ejecutivo, para usar Quedamos sin cambiar de plataforma.

Criterios de aceptación:
- Dado un calendario de Outlook conectado, entonces solo se obtienen intervalos de libre u ocupado.
- Se documenta qué aprobación de TI requiere la organización.

Nota o riesgo: Puede requerir consentimiento del administrador del dominio. Por confirmar.

---

### HU-15

Código: HU-15
Nombre: Aprendizaje de preferencias a partir de decisiones pasadas
Tipo Jira: Historia
Épica: EP-04, Solicitudes y propuesta de horarios
Responsable: Mayerly Damián
Prioridad: Baja
Puntos: 5
Sprint: Sin asignar
Fecha de inicio: Sin asignar
Fecha límite: Sin asignar
Estado inicial: Backlog
Depende de: HU-10
Etiquetas: nucleo, mejora

Historia: Como asistente ejecutiva, quiero que el sistema sugiera reglas según las reuniones que mi ejecutivo aprobó o rechazó, para no configurarlas a mano.

Criterios de aceptación:
- El sistema sugiere reglas con su fundamento y la asistente las acepta o rechaza.
- Ninguna regla se aplica sin aprobación.

---

### HU-16

Código: HU-16
Nombre: Entrevista a una asistente ejecutiva (validación opcional)
Tipo Jira: Historia
Épica: EP-01, Validación con el profesor y supuestos
Responsable: Rossy (apellido por confirmar)
Prioridad: Baja
Puntos: 3
Sprint: Sin asignar
Fecha de inicio: Sin asignar
Fecha límite: Sin asignar
Estado inicial: Backlog
Depende de: Ninguna
Etiquetas: validacion, entrevista

Historia: Como equipo, quiero conversar con una asistente que coordina agendas, para contrastar los supuestos con una segunda fuente.

Criterios de aceptación:
- Se reconstruye su proceso para una reunión reciente (mensajes, tiempo, herramientas).
- Se registran sus tres mayores fricciones.

Nota o riesgo: Se activa si el profesor lo pide o si hay un contacto disponible. No bloquea el desarrollo.

---

