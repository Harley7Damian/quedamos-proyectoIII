# Quedamos
[![CI](https://github.com/Harley7Damian/quedamos-proyectoIII/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Harley7Damian/quedamos-proyectoIII/actions/workflows/ci.yml)

Espacio compartido donde la asistente de un ejecutivo y la contraparte coordinan una reunión, el sistema propone tres horarios ordenados con el motivo de cada uno y el ejecutivo aprueba con un solo toque.

Proyecto del curso **Proyecto Final de Carrera III** (Ingeniería de Software, Universidad San Ignacio de Loyola, ciclo 2026-II). Docente: Kenny Disney Neira Neira. Enfoque exclusivamente corporativo.

| | |
| --- | --- |
| Estado | Módulo 1 implementado y probado. Módulo 2 (propuesta de horarios y aprobación) en planificación desde el Sprint 2. |
| Stack | Python, Django, HTMX, SQLite en local, PostgreSQL en producción |
| Pruebas | 31 pruebas automáticas (`python manage.py test`) |
| Gestión | Scrum en Jira, sprints de una semana (lunes a domingo) |

## Contenido

1. [Problema y propuesta de valor](#1-problema-y-propuesta-de-valor)
2. [Qué funciona hoy](#2-qué-funciona-hoy)
3. [Cómo se usa (flujo por rol)](#3-cómo-se-usa-flujo-por-rol)
4. [Arquitectura y decisiones](#4-arquitectura-y-decisiones)
5. [Modelo de datos](#5-modelo-de-datos)
6. [Seguridad y permisos](#6-seguridad-y-permisos)
7. [Rutas de la aplicación](#7-rutas-de-la-aplicación)
8. [Instalación y ejecución local](#8-instalación-y-ejecución-local)
9. [Variables de entorno](#9-variables-de-entorno)
10. [Pruebas](#10-pruebas)
11. [Despliegue](#11-despliegue)
12. [Estructura del repositorio](#12-estructura-del-repositorio)
13. [Gestión del proyecto y hoja de ruta](#13-gestión-del-proyecto-y-hoja-de-ruta)
14. [Supuestos e hipótesis no validadas](#14-supuestos-e-hipótesis-no-validadas)
15. [Limitaciones conocidas](#15-limitaciones-conocidas)
16. [Equipo y documentación relacionada](#16-equipo-y-documentación-relacionada)

## 1. Problema y propuesta de valor

Coordinar una reunión entre dos ejecutivos suele resolverse con cadenas de correos o mensajes en los que las asistentes proponen horarios, esperan respuesta y repiten el ciclo. Las herramientas de agendamiento más conocidas (por ejemplo Calendly o Doodle) funcionan bien cuando una persona define sus reglas y la otra elige, pero no están pensadas para que dos asistentes negocien en nombre de dos ejecutivos y para que el ejecutivo solo confirme.

Quedamos propone un espacio compartido con este flujo:

1. La asistente registra la solicitud de reunión en nombre de su ejecutivo.
2. La contraparte entra a un enlace compartido, sin instalar nada, e indica su disponibilidad (Módulo 2).
3. El sistema propone tres horarios ordenados, cada uno con una frase que explica por qué se sugiere (Módulo 2).
4. El ejecutivo aprueba una opción con un toque desde un enlace firmado (Módulo 2).

La propuesta de valor es reducir los mensajes cruzados y el tiempo hasta confirmar. Estas afirmaciones son hipótesis del equipo y todavía no están validadas (ver [sección 14](#14-supuestos-e-hipótesis-no-validadas)).

## 2. Qué funciona hoy

El **Módulo 1** corre de punta a punta, con persistencia y pruebas automáticas:

| Funcionalidad | Detalle |
| --- | --- |
| Registro e ingreso | Cuenta con correo y contraseña, con rol de **asistente** o **ejecutivo**. Contraseñas validadas por las reglas de Django (mínimo 8 caracteres, no comunes, no solo numéricas). |
| Código de vinculación | Cada ejecutivo recibe un código de 6 caracteres, generado una sola vez, sin caracteres ambiguos (0/O, 1/I) para poder dictarlo por teléfono. |
| Vínculo asistente-ejecutivo | La asistente ingresa el código y queda autorizada para actuar en nombre de ese ejecutivo. Una asistente puede atender a varios ejecutivos. Cualquiera de las dos partes puede desvincularse. |
| Solicitudes de reunión | La asistente crea solicitudes en nombre de su ejecutivo, con asunto, contraparte, correo opcional, duración y notas. El ejecutivo las ve en su panel. Estados previstos: pendiente, propuesta, aprobada, cancelada. |
| Panel en casi tiempo real | La lista de solicitudes se actualiza sola cada 5 segundos mediante HTMX, de modo que el ejecutivo ve lo que registra su asistente sin recargar. |
| Reglas de visibilidad | Cada persona ve solo las solicitudes de su propia agenda o de los ejecutivos con los que mantiene un vínculo vigente. |
| Maqueta de la tarjeta de aprobación | La ruta `/demo/tarjeta/` muestra la tarjeta con datos de ejemplo definidos por el contrato de datos del Módulo 2. No usa la base de datos. |

Lo que **todavía no existe**: enlace compartido para la contraparte, cálculo de los tres horarios, aprobación con un toque, aviso por correo, integración con calendarios y métricas de uso. Están planificados en los sprints 2 a 4 ([sección 13](#13-gestión-del-proyecto-y-hoja-de-ruta)).

## 3. Cómo se usa (flujo por rol)

```mermaid
sequenceDiagram
    participant E as Ejecutivo
    participant S as Quedamos
    participant A as Asistente
    E->>S: Crea cuenta con rol ejecutivo
    S-->>E: Muestra su código de 6 caracteres
    E->>A: Comparte el código
    A->>S: Crea cuenta con rol asistente e ingresa el código
    S-->>A: Vínculo creado, ve la agenda del ejecutivo
    A->>S: Crea una solicitud de reunión
    S-->>E: La solicitud aparece en su panel (hasta 5 s)
```

**Cómo completar el formulario "Nueva solicitud de reunión":**

| Campo | Qué ingresar | Ejemplo |
| --- | --- | --- |
| Ejecutivo | La persona cuya agenda se gestiona. Solo aparecen los ejecutivos vinculados. | Rocio Damian Gavino |
| Asunto | Motivo de la reunión, entre 3 y 120 caracteres. | Revisión trimestral de ventas |
| Contraparte | Persona de la otra parte con quien se coordina, entre 2 y 80 caracteres. | Pedro Gómez |
| Correo de la contraparte | Opcional. Se usará para enviar el enlace de disponibilidad en el Módulo 2. | pedro.gomez@empresa.com |
| Duración | 15, 30, 45, 60, 90 o 120 minutos. | 45 minutos |
| Notas | Opcional, hasta 500 caracteres. | Prefiere mañanas, presencial |

Al crear la solicitud queda en estado **pendiente**.

## 4. Arquitectura y decisiones

Aplicación monolítica Django con patrón MVT (modelos, vistas, plantillas) y actualización parcial de la interfaz mediante HTMX. La lógica de horarios vive en un paquete de Python puro que se puede probar sin la web.

```mermaid
flowchart LR
    N["Navegador con HTMX"] -->|HTTP| W["WhiteNoise y gunicorn"]
    W --> U["config/urls.py"]
    U --> AC["accounts: usuario con rol, registro, ingreso"]
    U --> ME["meetings: vínculos y solicitudes"]
    U --> SC["scheduling: contratos y propuesta de horarios"]
    AC --> DB[("SQLite en local, PostgreSQL en producción")]
    ME --> DB
    SC -.->|"contrato de datos"| ME
```

| Capa | Elección | Motivo |
| --- | --- | --- |
| Aplicación | Django (MVT) | Cuentas, ORM con migraciones, protección CSRF, panel de administración y pruebas incluidos. Un solo proyecto desplegable. |
| Lenguaje | Python | Dominio de la desarrolladora principal y librerías de Google Calendar. |
| Base de datos | PostgreSQL en producción, SQLite en local | No requiere cuentas externas para desarrollar. El cambio es la variable `DATABASE_URL`. |
| Interfaz | Plantillas HTML con HTMX | Actualización parcial sin construir una aplicación de una sola página. |
| Lógica de horarios | Paquete `scheduling` en Python puro | Se prueba sin la web. El algoritmo ponderado del prototipo original (`docs/referencia/matching.ts`) se porta aquí. |
| Archivos estáticos | WhiteNoise | Sirve CSS y JavaScript sin un servidor adicional. |
| Despliegue | Render o Railway con gunicorn | Servidor de aplicación tradicional, no funciones sin servidor. |

El razonamiento completo, incluida la alternativa descartada (Next.js con Supabase), está en [`docs/adr/ADR-001-stack.md`](docs/adr/ADR-001-stack.md).

### Contrato del Módulo 2

Para que el desarrollo avance en paralelo, la propuesta de horarios se define como datos inmutables en [`scheduling/contracts.py`](scheduling/contracts.py):

- `ProposedSlot(id, start, end, reason, rank)`: un horario sugerido, con zona horaria, la frase que explica la sugerencia y su posición (1 es la mejor).
- `Proposal(request_id, title, counterpart_name, duration_min, slots)`: la propuesta completa que verá el ejecutivo.

`scheduling/mock.py` entrega una propuesta de ejemplo para construir y probar la interfaz antes de conectar el cálculo real.

## 5. Modelo de datos

```mermaid
erDiagram
    USER ||--o{ ASSISTANT_LINK : "como asistente"
    USER ||--o{ ASSISTANT_LINK : "como ejecutivo"
    USER ||--o{ MEETING_REQUEST : "agenda de"
    USER ||--o{ MEETING_REQUEST : "creada por"
    USER {
        string email
        string full_name
        string role
        string link_code
    }
    ASSISTANT_LINK {
        int assistant_id
        int executive_id
        datetime created_at
    }
    MEETING_REQUEST {
        int executive_id
        int created_by_id
        string title
        int duration_min
        string counterpart_name
        string counterpart_email
        string notes
        string status
    }
```

| Entidad | Aplicación | Reglas de integridad |
| --- | --- | --- |
| `User` | `accounts` | Extiende `AbstractUser`. El correo es también el nombre de usuario. `link_code` es único, solo existe para ejecutivos, se genera una vez y no cambia. |
| `AssistantLink` | `meetings` | Par único (asistente, ejecutivo). Restricción de base de datos que impide vincularse con uno mismo. |
| `MeetingRequest` | `meetings` | Duración restringida a 15, 30, 45, 60, 90 o 120 minutos. Estado por defecto `pendiente`. Índice por ejecutivo y fecha de creación. |

## 6. Seguridad y permisos

La regla "cada persona ve solo lo suyo" está concentrada en un único punto de la capa de aplicación: `MeetingRequest.objects.visible_to(user)` y la función `_executives_of(user)` en `meetings/`.

- Una asistente ve las solicitudes de los ejecutivos con los que mantiene un vínculo vigente. Si el vínculo se elimina, pierde el acceso, incluso a las solicitudes que ella creó.
- El campo `created_by` lo define el servidor, nunca el formulario, por lo que nadie puede suplantar a otro usuario como autor.
- El ejecutivo elegible en el formulario se valida contra los vínculos reales: la lista desplegable y el servidor aplican el mismo filtro.
- Protección CSRF activa en todos los formularios. Cierre de sesión solo por POST.
- El contenido ingresado por usuarios se escapa en las plantillas (hay una prueba específica).
- En producción (`DEBUG=0`) la aplicación se niega a arrancar sin `SECRET_KEY`, fuerza HTTPS y marca como seguras las cookies de sesión y CSRF.
- Privacidad por diseño para las integraciones futuras: solo se leerá disponibilidad (libre u ocupado), nunca el detalle de los eventos.

## 7. Rutas de la aplicación

| Ruta | Método | Descripción | Requiere sesión |
| --- | --- | --- | --- |
| `/` | GET | Redirige al panel | No |
| `/registro/` | GET, POST | Crear cuenta con rol | No |
| `/acceso/` | GET, POST | Ingresar con correo y contraseña | No |
| `/salir/` | POST | Cerrar sesión | Sí |
| `/panel/` | GET | Panel según el rol | Sí |
| `/panel/solicitudes/` | GET | Fragmento HTMX con la lista de solicitudes (consulta cada 5 s) | Sí |
| `/panel/solicitudes/nueva/` | POST | Crear una solicitud | Sí |
| `/panel/vincular/` | POST | Vincular a la asistente con un ejecutivo mediante su código | Sí |
| `/panel/vinculo/<id>/eliminar/` | POST | Eliminar un vínculo | Sí |
| `/demo/tarjeta/` | GET | Maqueta de la tarjeta de aprobación con datos de ejemplo | No |
| `/admin/` | GET | Administración de Django | Superusuario |

## 8. Instalación y ejecución local

Requisito: Python 3.10 o superior (`python --version`). No se necesitan cuentas ni servicios externos.

**Windows (PowerShell):**

```powershell
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DE_LA_CARPETA>
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Si PowerShell bloquea la activación del entorno virtual, ejecutar `Set-ExecutionPolicy -Scope Process Bypass` y repetir el paso de activación.

**macOS o Linux:**

```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DE_LA_CARPETA>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/> en el navegador. La base de datos local se crea en `db.sqlite3` dentro de la carpeta del proyecto, por lo que los datos se conservan al cerrar el servidor con `Ctrl+C`. Para retomar basta activar el entorno y ejecutar `python manage.py runserver`.

### Prueba manual del flujo completo (unos 10 minutos)

1. En una ventana normal, crear una cuenta con rol **Ejecutivo**. Se mostrará su código de 6 caracteres.
2. En una ventana de incógnito, crear una cuenta con rol **Asistente** e ingresar ese código en "Vincularme con un ejecutivo".
3. Crear una solicitud de reunión. Debe aparecer en la lista.
4. Volver a la ventana del ejecutivo. En unos 5 segundos debe aparecer la solicitud junto al nombre de su asistente.
5. Recargar ambas ventanas: la sesión y los datos se mantienen.
6. Opcional: abrir `/demo/tarjeta/` para ver la maqueta de la tarjeta de aprobación.

### Comandos útiles

| Comando | Para qué sirve |
| --- | --- |
| `python manage.py test` | Ejecuta las 31 pruebas automáticas. |
| `python manage.py createsuperuser` | Crea un administrador para entrar a `/admin/` y revisar los datos. |
| `python manage.py makemigrations` y luego `python manage.py migrate` | Después de modificar un modelo. La migración se sube junto con el código. |

## 9. Variables de entorno

En local la aplicación funciona sin ninguna variable. Para personalizar, copiar `.env.example` como `.env` (este archivo no se sube al repositorio).

| Variable | Valor por defecto | Descripción |
| --- | --- | --- |
| `DEBUG` | `1` | `1` en desarrollo, `0` en producción. |
| `SECRET_KEY` | clave de desarrollo | Obligatoria si `DEBUG=0`. Cadena larga y aleatoria. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Dominios permitidos, separados por comas. |
| `CSRF_TRUSTED_ORIGINS` | vacío | En producción, por ejemplo `https://tu-app.onrender.com`. |
| `DATABASE_URL` | SQLite local | En producción, `postgres://usuario:clave@host:5432/base`. |
| `SECURE_SSL_REDIRECT` | `1` (solo con `DEBUG=0`) | Redirige HTTP a HTTPS. |

## 10. Pruebas

```bash
python manage.py test
```

Son 31 pruebas automáticas que se ejecutan en menos de un segundo (las contraseñas usan un hash rápido únicamente durante las pruebas):

| Aplicación | Pruebas | Qué cubren |
| --- | --- | --- |
| `accounts` | 11 | Registro con rol, rol inválido, correo repetido o con mayúsculas, contraseña débil, código de 6 caracteres solo para ejecutivos, códigos únicos e inmutables, ingreso en cualquier capitalización, credenciales incorrectas, panel que exige sesión, cierre de sesión. |
| `meetings` | 20 | Vinculación con código en minúsculas o con espacios, vínculo repetido, código inválido o vacío, ejecutivo que intenta vincularse, desvinculación, tercero que intenta borrar un vínculo ajeno, vínculo con uno mismo, creación de solicitudes y su visibilidad, suplantación del creador, validaciones, errores en pantalla, acceso anónimo, método HTTP, escape de HTML y carga de la maqueta. |

Entornos en los que se verificó la suite completa: Python 3.10 con Django 5.2 y Python 3.13 con Django 6.1. Además se ejecutó un recorrido automatizado de extremo a extremo con navegador (ejecutivo y asistente en dos contextos: vínculo, creación de solicitud y aparición en el panel del ejecutivo en menos de 9 segundos).

Regla del equipo: toda regla de permisos nueva se entrega con su prueba en el mismo cambio.

## 11. Despliegue

El proyecto está preparado para Render o Railway (aún no se publicó una instancia; está planificado en TR-20, Sprint 5).

- Comando de construcción: `./build.sh` (instala `requirements-prod.txt`, ejecuta `collectstatic` y `migrate`).
- Comando de inicio: `gunicorn config.wsgi` (definido en el `Procfile`).
- Variables: `DEBUG=0`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y `DATABASE_URL` con la base PostgreSQL del proveedor.

El plan gratuito de Render duerme la aplicación tras un periodo de inactividad, por lo que la primera visita puede tardar. Conviene abrirla antes de una demostración.

## 12. Estructura del repositorio

```text
.
├── config/                  Ajustes (settings.py), rutas (urls.py), wsgi y asgi
├── accounts/                Usuario con rol, registro e ingreso, 11 pruebas
├── meetings/                Vínculos asistente-ejecutivo y solicitudes, 20 pruebas
├── scheduling/              Contratos de datos y datos de ejemplo del Módulo 2
├── templates/               Plantillas HTML (base, registro, acceso, panel, maqueta)
├── static/                  CSS propio y HTMX incluido localmente
├── docs/
│   ├── adr/ADR-001-stack.md          Decisión de stack y arquitectura
│   ├── PASOS_MODULO1.md              Guía operativa paso a paso
│   ├── Planificacion_Sprints_Quedamos_Jira.md   Plan de sprints y tarjetas
│   └── referencia/matching.ts        Algoritmo de ranking del prototipo original
├── manage.py
├── requirements.txt         Dependencias para desarrollo
├── requirements-prod.txt    Dependencias de producción (gunicorn, psycopg)
├── build.sh y Procfile      Despliegue en Render o Railway
└── .env.example             Plantilla de variables de entorno
```

## 13. Gestión del proyecto y hoja de ruta

El trabajo se gestiona con Scrum en Jira: sprints de una semana (lunes a domingo), planificación el lunes y revisión con retrospectiva el viernes. Cada tarjeta tiene criterios de aceptación, responsable, prioridad, puntos (escala Fibonacci) y fecha límite. El plan completo, con la ficha de las 44 tarjetas, está en [`docs/Planificacion_Sprints_Quedamos_Jira.md`](docs/Planificacion_Sprints_Quedamos_Jira.md).

**Criterio de priorización:** software funcional antes que documentación extensiva (segundo valor del Manifiesto Ágil). Los sprints 1 a 5 son de desarrollo y pruebas; el informe, las plantillas, el modelo de negocio y el flujo de caja se concentran en los sprints 6 y 7.

| Sprint | Fechas | Objetivo |
| --- | --- | --- |
| 0 | 12/10 al 18/10 | Pivote corporativo, propuesta de valor tentativa y tablero de Jira. |
| 1 | 19/10 al 25/10 | Arquitectura decidida y Módulo 1 funcionando de punta a punta con pruebas. |
| 2 | 26/10 al 01/11 | Tres horarios ordenados con el motivo de cada uno y espacio compartido para la contraparte. |
| 3 | 02/11 al 08/11 | Aprobación con un toque desde un enlace firmado, confirmación, aviso por correo y métricas. |
| 4 | 09/11 al 15/11 | Disponibilidad desde Google Calendar (solo libre y ocupado) con plan alterno por archivo `.ics`. |
| 5 | 16/11 al 22/11 | Pruebas con el profesor como usuario, correcciones, pulido y despliegue estable. |
| 6 | 23/11 al 29/11 | Plantillas del curso, benchmark con fuentes primarias, modelo de negocio y flujo de caja corporativos. |
| 7 | 30/11 al 06/12 | Informe final, paper y pitch con demostración ensayada. |

Las fechas de los sprints son un supuesto de planificación pendiente de confirmar con el docente.

**Flujo de estados en Jira:** Backlog, Pendiente, En progreso, En revisión, Cumplida, con Bloqueada como salida lateral. La prioridad Bloqueante es un campo distinto del estado Bloqueada.

**Definition of Done (resumen):** cumple sus criterios de aceptación, fue revisada por una persona distinta a quien la hizo, pasa `python manage.py test`, incluye la prueba de cualquier regla de permisos nueva y se integra mediante un pull request.

**Reglas de trabajo con Git:** una rama y un pull request por tarjeta de Jira, sin cambios directos a `main`; las migraciones se suben con el código y no se editan las ya aplicadas.

Las épicas son: validación con el profesor y supuestos, base técnica, cuentas y vínculos, solicitudes y propuesta de horarios, aprobación y confirmación, integración con calendarios, calidad y despliegue, gestión del proyecto, e informe final con plantillas.

## 14. Supuestos e hipótesis no validadas

El proyecto cambió de segmento (de estudiantes a corporativo) por recomendación del docente. Las hipótesis siguientes se tratan como **supuestos razonables** y no se presentan como validadas. Se contrastarán en las revisiones de sprint con el docente actuando como usuario (TR-10 y TR-17) y con las métricas de uso (HU-10).

| Código | Hipótesis | Cómo se contrasta |
| --- | --- | --- |
| H1 | Coordinar reuniones consume tiempo y genera idas y vueltas por correo. | Revisiones de sprint TR-10 y TR-17. |
| H2 | La asistente opera la coordinación y el ejecutivo solo aprueba. | Revisiones de sprint TR-10 y TR-17. |
| H3 | Una propuesta ordenada reduce los mensajes cruzados. | Métrica de mensajes evitados (HU-10). |
| H4 | El ejecutivo aprueba con un toque sin aprender una herramienta nueva. | Pruebas con el docente (TR-17). |
| H5 | El tiempo hasta confirmar baja frente a la línea base. | Métrica de tiempo hasta confirmar (HU-10). |

El precio por asiento tampoco tiene un dato propio: se contrastará con el benchmark de herramientas (TR-22) y con la consulta al docente.

## 15. Limitaciones conocidas

- El panel consulta cada 5 segundos; no es tiempo real verdadero. Si se necesitara, se evaluaría Django Channels en un sprint posterior.
- En el registro se elige el rol. Es aceptable para la demostración; en producción el rol de ejecutivo debería verificarse, por ejemplo por dominio corporativo.
- El Módulo 2 (cálculo de horarios, enlace para la contraparte, aprobación y correo) y la integración con calendarios aún no están implementados.
- La verificación de permisos de Google Calendar puede exigir usuarios de prueba; por eso existe el plan alterno de importar un archivo `.ics` (TR-14).
- No hay todavía una instancia desplegada; la ejecución actual es local.
- Las menciones a herramientas de la competencia provienen de información de sus propios proveedores y se contrastarán con fuentes primarias en el benchmark (TR-22).

## 16. Equipo y documentación relacionada

| Integrante | Responsabilidades principales |
| --- | --- |
| Mayerly Damián | Producto, base técnica y arquitectura, Módulo 1, enlace y aprobación, integración con calendarios, flujo de caja y modelo de negocio. |
| Rossy | Configuración de Jira, algoritmo de ranking, maqueta de la tarjeta, aviso por correo, verificaciones, plantillas e informe. |

Documentación relacionada dentro del repositorio:

- [`docs/adr/ADR-001-stack.md`](docs/adr/ADR-001-stack.md): decisión de stack y arquitectura.
- [`docs/PASOS_MODULO1.md`](docs/PASOS_MODULO1.md): guía operativa paso a paso.
- [`docs/Planificacion_Sprints_Quedamos_Jira.md`](docs/Planificacion_Sprints_Quedamos_Jira.md): plan de sprints y fichas de tarjetas.
- [`docs/referencia/matching.ts`](docs/referencia/matching.ts): algoritmo de ranking del prototipo original, que se porta a Python en TR-11.
