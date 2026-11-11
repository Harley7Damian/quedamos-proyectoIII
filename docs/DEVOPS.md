# DevOps: ciclo de integración y entrega continuas de Quedamos (TR-34)

Este documento explica, de punta a punta, cómo una tarjeta de Jira se convierte en código funcionando en producción: qué hace cada etapa del pipeline, por qué existe, y cómo cualquier integrante puede reproducirla en su propia computadora. Complementa a [`docs/CONVENCION_JIRA_GITHUB.md`](CONVENCION_JIRA_GITHUB.md) (trazabilidad), [`docs/RUTA_SALUD.md`](RUTA_SALUD.md) (monitoreo) y [`docs/CABECERA_HSTS.md`](CABECERA_HSTS.md) (hallazgo de seguridad ya resuelto).

## 1. El flujo completo, de la tarjeta al despliegue

```mermaid
flowchart TD
    J["Tarjeta en Jira<br/>(Pendiente)"] --> B["Rama feature/pfciii2026-N-descripcion<br/>(TR-33)"]
    B --> C["Commits con la clave de Jira<br/>PFCIII2026-N CODIGO: descripcion"]
    C --> PR["Pull Request hacia main"]
    PR --> CI["Workflow CI<br/>(pruebas, seguridad, pruebas-postgres, calidad, navegador)"]
    PR --> SEG["Workflow Seguridad<br/>(secretos, CodeQL, config. produccion)"]
    CI --> GATE{"Todo en verde<br/>y rama actualizada?<br/>(TR-32)"}
    SEG --> GATE
    GATE -- "No" --> FIX["Corregir en la misma rama"]
    FIX --> C
    GATE -- "Si" --> REV["Aprobacion de la otra integrante<br/>(revision cruzada)"]
    REV --> MERGE["Merge a main"]
    MERGE --> DEPLOY["Job Despliegue<br/>solo si push a main"]
    DEPLOY --> RENDER["Render redespliega<br/>el commit verificado"]
    RENDER --> SALUD["/salud/ responde 200<br/>(TR-35)"]
    MERGE --> JIRACLOSE["Tarjeta a Cumplida<br/>con fecha real del merge"]
```

## 2. Etapas del ciclo y dónde se ven

| Etapa | Qué hace | Herramienta | Tarjeta | Se ejecuta en |
| --- | --- | --- | --- | --- |
| Planificar | Épicas, sprints, tarjetas con criterios de aceptación | Jira | TR-02, plan de sprints | — |
| Codificar | Una rama por tarjeta, commits con la clave de Jira | GitHub, pestaña Commits | TR-33 | Cada commit |
| Construir e integrar | Instala dependencias, valida Django, detecta migraciones pendientes, corre las pruebas | GitHub Actions, workflow `CI`, job `pruebas` | TR-29 | Cada PR y cada push a `main` |
| Probar contra PostgreSQL | Corre toda la suite contra una base PostgreSQL real, igual que producción | GitHub Actions, job `pruebas-postgres` | TR-31 | Cada PR y cada push a `main` |
| Seguridad (dependencias y código) | `pip-audit` sobre las dependencias y `bandit` sobre el código propio | GitHub Actions, job `seguridad` (en `ci.yml`) | TR-30 | Cada PR y cada push a `main` |
| Seguridad (secretos, estático, config.) | Gitleaks, CodeQL y `manage.py check --deploy` | GitHub Actions, workflow `Seguridad` | TR-30 | Cada PR, cada push a `main`, y los lunes (CodeQL/config.) |
| Seguridad del sistema desplegado | Escaneo dinámico (OWASP ZAP) contra la URL pública | GitHub Actions, job `sistema-desplegado` | TR-30 | Manual o cada lunes 08:00 (Lima) |
| Calidad | Cobertura de pruebas (mínimo 90%) y estilo de código (`flake8`) | GitHub Actions, job `calidad` | TR-39 | Cada PR y cada push a `main` |
| Recorrido de extremo a extremo | Simula a un usuario real con navegador: vínculo, solicitud, disponibilidad, propuesta, aprobación | GitHub Actions, job `navegador` (Playwright) | TR-38 | Cada PR hacia `main` |
| Revisar | Aprobación de otra persona, con el pipeline en verde como requisito | GitHub, protección de rama | TR-32 | Antes de cada merge |
| Publicar | Trazabilidad automática Jira ↔ GitHub | Jira + GitHub App | TR-33 | Continuo |
| Desplegar | Si todo pasó en `main`, se pide a Render que despliegue el commit verificado | GitHub Actions, job `despliegue` | TR-37 | Cada push a `main` (no en PRs) |
| Operar y monitorear | Ruta `/salud/` y registros de la aplicación | Render, logs | TR-35 | Continuo, tras cada despliegue |
| Documentar | Este documento y la sección correspondiente del README | `docs/DEVOPS.md` | TR-34 | — |

## 3. Cada etapa en detalle

### 3.1 Pruebas (`pruebas`, TR-29)

- **Qué hace:** instala Python 3.12 y las dependencias de `requirements.txt`, corre `python manage.py check`, `python manage.py makemigrations --check --dry-run` y `python manage.py test`.
- **Por qué existe:** es la red mínima que evita fusionar código que no arranca, con migraciones faltantes, o que rompe una prueba existente.
- **Cómo reproducirlo en local:**
  ```bash
  pip install -r requirements.txt
  python manage.py check
  python manage.py makemigrations --check --dry-run
  python manage.py test
  ```

### 3.2 Pruebas contra PostgreSQL (`pruebas-postgres`, TR-31)

- **Qué hace:** levanta un contenedor de PostgreSQL 16 como servicio del pipeline, instala también `requirements-prod.txt` (incluye el driver `psycopg`) y corre toda la suite apuntando a esa base con `DATABASE_URL`.
- **Por qué existe:** en local se usa SQLite por comodidad, pero producción usa PostgreSQL. Esta etapa detecta diferencias de comportamiento entre ambos motores antes de desplegar.
- **Cómo reproducirlo en local** (requiere Docker):
  ```bash
  docker run -d --name pg-quedamos -e POSTGRES_USER=quedamos -e POSTGRES_PASSWORD=quedamos -e POSTGRES_DB=quedamos_test -p 5432:5432 postgres:16
  pip install -r requirements.txt -r requirements-prod.txt
  export DATABASE_URL=postgres://quedamos:quedamos@localhost:5432/quedamos_test
  python manage.py test
  ```

### 3.3 Seguridad de dependencias y código (`seguridad` en `ci.yml`, TR-30)

- **Qué hace:** `pip-audit -r requirements.txt` busca vulnerabilidades conocidas (CVE) en las dependencias; `bandit -r accounts meetings scheduling config -ll` busca patrones de código inseguros en las aplicaciones propias.
- **Por qué existe:** detecta dependencias con fallas de seguridad conocidas y errores comunes (por ejemplo, uso de `eval`, claves en texto plano) antes de fusionar.
- **Cómo reproducirlo en local:**
  ```bash
  pip install pip-audit bandit
  pip-audit -r requirements.txt
  bandit -r accounts meetings scheduling config -ll
  ```

### 3.4 Secretos expuestos (`secretos`, workflow `Seguridad`, TR-30)

- **Qué hace:** Gitleaks revisa todo el historial de commits en busca de patrones de claves, tokens o credenciales filtradas.
- **Por qué existe:** una clave filtrada en el historial sigue siendo recuperable aunque se borre del código actual; esta etapa la detecta en el momento en que se introduce.
- **Cómo reproducirlo en local:** instalar `gitleaks` (binario) y correr `gitleaks detect --source .`

### 3.5 Análisis estático (`codeql`, workflow `Seguridad`, TR-30)

- **Qué hace:** CodeQL analiza el código Python con consultas de seguridad extendidas (`security-extended`) y publica los hallazgos en la pestaña Security de GitHub.
- **Por qué existe:** detecta patrones de vulnerabilidad más sutiles que bandit (por ejemplo, flujos de datos no confiables) con el motor de análisis de GitHub.
- **Cómo reproducirlo en local:** requiere la CLI de CodeQL; en la práctica se revisa directamente en la pestaña Security de GitHub tras cada PR.

### 3.6 Configuración de producción (`django-produccion`, workflow `Seguridad`, TR-30)

- **Qué hace:** corre `python manage.py check --deploy --fail-level WARNING` simulando variables de producción (`DEBUG=0`), y publica el resultado completo en el resumen de la ejecución.
- **Por qué existe:** detecta configuraciones inseguras para producción (cookies sin `Secure`, falta de HSTS, `DEBUG` encendido, etc.) antes de desplegar.
- **Estado actual:** con `--fail-level WARNING`, este chequeo sigue marcando advertencia por `security.W021` (HSTS sin preload), que es una decisión consciente y no un pendiente (ver sección 4). Por eso el paso usa `continue-on-error: true`: de lo contrario bloquearía el merge por una advertencia que ya se evaluó y se decidió no resolver todavía.
- **Cómo reproducirlo en local:**
  ```bash
  DEBUG=0 ALLOWED_HOSTS=localhost SECRET_KEY=clave-de-prueba python manage.py check --deploy
  ```

### 3.7 Seguridad del sistema desplegado (`sistema-desplegado`, workflow `Seguridad`, TR-30)

- **Qué hace:** OWASP ZAP (escaneo base, sin sesión iniciada) ataca la URL pública real en busca de cabeceras faltantes, configuración insegura expuesta, etc.
- **Por qué existe:** las etapas anteriores analizan el código fuente; esta analiza el sistema ya corriendo, como lo vería un atacante externo.
- **Cuándo corre:** manual (`workflow_dispatch`) o automático cada lunes a las 08:00 (hora de Lima), nunca en cada PR (consume minutos y tráfico de la instancia gratuita).
- **Cómo reproducirlo en local:** correr el contenedor `ghcr.io/zaproxy/zaproxy` apuntando a la URL desplegada, o a `http://localhost:8000` con el servidor local corriendo.

### 3.8 Calidad: cobertura y estilo (`calidad`, TR-39)

- **Qué hace:** mide la cobertura de pruebas con `coverage` y falla si baja de 90%; revisa el estilo del código con `flake8` (sin bloquear el merge: `continue-on-error: true`).
- **Por qué existe:** asegura que el código nuevo venga acompañado de pruebas, y dejar visible (sin bloquear aún) el estilo del código para ir mejorándolo gradualmente.
- **Cómo reproducirlo en local:**
  ```bash
  pip install coverage flake8
  coverage run manage.py test
  coverage report -m --fail-under=90
  flake8 .
  ```

### 3.9 Recorrido de extremo a extremo (`navegador`, TR-38)

- **Qué hace:** levanta la aplicación con una base de datos temporal y un navegador Chromium real (Playwright), y simula el recorrido completo: cuentas, vínculo, solicitud, disponibilidad de ambas partes, propuesta de horarios y aprobación con un toque. Guarda capturas de pantalla como artefacto descargable.
- **Por qué existe:** las pruebas unitarias verifican piezas aisladas; esta prueba verifica que el flujo completo funcione de punta a punta, como lo usaría una persona real.
- **Cuándo corre:** solo en pull requests hacia `main` (consume más minutos que las demás etapas).
- **Cómo reproducirlo en local:**
  ```bash
  pip install -r requirements.txt
  playwright install --with-deps chromium
  mkdir -p capturas
  python manage.py test meetings.e2e_navegador
  ```

### 3.10 Dependencias actualizadas (Dependabot)

- **Qué hace:** `dependabot.yml` revisa semanalmente las dependencias de `pip` y de las propias GitHub Actions, y abre un pull request automático por cada actualización disponible (máximo 5 abiertos a la vez por ecosistema).
- **Por qué existe:** mantiene las dependencias al día sin depender de que alguien se acuerde de revisarlas manualmente, reduciendo el tiempo en que una versión con vulnerabilidades conocidas queda sin actualizar.
- **Cómo verlo:** pestaña *Pull requests* de GitHub, PRs etiquetados por Dependabot; cada uno pasa por el mismo pipeline de CI antes de poder fusionarse.

### 3.11 Protección de rama (`TR-32`)

- **Qué hace:** exige que los checks del pipeline estén en verde y la rama esté actualizada con `main` antes de habilitar el botón de fusionar, además de exigir la aprobación de otra persona.
- **Por qué existe:** evita que código roto o sin revisar llegue a `main`, que es justamente lo que dispara el despliegue automático.
- **Cómo verificarlo:** al intentar fusionar un pull request sin la aprobación requerida, GitHub muestra el aviso "Merging is blocked".

![Pull request bloqueado por falta de aprobación](evidencias/pr-bloqueado.png)
*Ejemplo real: PFCIII2026-73 (TR-46) bloqueado por falta de una revisión aprobatoria.*

### 3.12 Despliegue automático (`despliegue`, TR-37)

- **Qué hace:** solo si los jobs `pruebas`, `seguridad` y `pruebas-postgres` terminaron bien, y solo en un push directo a `main` (no en pull requests), pide a Render que despliegue el commit verificado mediante un *deploy hook* guardado como secreto (`RENDER_DEPLOY_HOOK_URL`). Luego comprueba que la página principal responda.
- **Por qué existe:** cierra el ciclo sin intervención manual: lo que pasa todas las verificaciones en `main` llega a producción solo.
- **Cómo probar que bloquea un despliegue roto:** ejecutar el workflow `CI` manualmente sobre `main` con la opción `simular_fallo` activada; el job `pruebas` falla a propósito y el job `despliegue` se omite por completo.
- **Retroceso:** workflow `Retroceso` (ver sección 11 del README) con el SHA del commit anterior.

### 3.13 Operar y monitorear (`/salud/`, TR-35)

- **Qué hace:** ruta pública que verifica que la aplicación y la base de datos respondan (`200`) o no (`503`), usada por Render como *health check*. Los registros de la aplicación salen por consola con nivel y fecha.
- **Por qué existe:** detecta automáticamente un despliegue roto antes de que Render le envíe tráfico real.
- **Más detalle:** [`docs/RUTA_SALUD.md`](RUTA_SALUD.md).

## 4. Hallazgos de seguridad: registro y resolución

| Hallazgo | Herramienta | Estado | Resolución o justificación |
| --- | --- | --- | --- |
| `security.W004` (sin HSTS) | `manage.py check --deploy` | Resuelto | Se activó `SECURE_HSTS_SECONDS` (empezando en 1 hora, subida gradual documentada). Ver [`docs/CABECERA_HSTS.md`](CABECERA_HSTS.md). |
| `security.W021` (sin HSTS preload) | `manage.py check --deploy` | Descartado a propósito | El preload exige una vigencia mínima de un año y compromete el dominio de forma casi irreversible. Se reconsiderará cuando el sitio tenga dominio propio y HSTS lleve un año estable. |
| Clave de desarrollo local hardcodeada (`config/settings.py`) | Revisión manual / posible alerta de `bandit` | Descartado (falso positivo) | El valor `"clave-solo-para-desarrollo-local"` solo se usa cuando `DEBUG=1`; en producción (`DEBUG=0`) sin la variable `SECRET_KEY` la aplicación **no arranca** (`RuntimeError` explícito). No es una clave real ni alcanzable en producción. |
| `URL redirection from remote source` (`meetings/views.py:376`) | CodeQL (Code scanning) | Descartado (falso positivo) | `redirect(request.path)` solo reutiliza la ruta interna de la petición actual (sin dominio), para recargar la misma página tras guardar un formulario. No puede redirigir a un dominio externo, así que no habilita un *open redirect*. |
| _(agregar aquí cualquier hallazgo nuevo que reporte pip-audit, bandit, CodeQL o ZAP, con fecha y quién lo resolvió)_ | | | |

## 5. Capturas de evidencia

![Pull request en verde, todos los checks pasados](evidencias/pr-verde.png)
*Pull request en verde: todos los checks del pipeline pasados antes de fusionar.*

![Pull request bloqueado por falta de aprobación](evidencias/pr-bloqueado.png)
*Pull request bloqueado: la protección de rama impide fusionar sin una aprobación.*

![Resultado de seguridad: hallazgo de CodeQL](evidencias/resultado-seguridad.png)
*Resultado de seguridad (Code scanning / CodeQL).*

![Cobertura de pruebas](evidencias/cobertura.png)
*Cobertura de pruebas obtenida por el job `calidad`.*

![Grafo de commits de ambas integrantes](evidencias/grafo-commits.png)
*Red de commits mostrando los aportes de ambas integrantes.*

## 6. Antes del Sprint 5

- [ ] Mayerly revisa este documento.
- [ ] Ambas ensayan en voz alta la explicación de cada etapa (qué hace, por qué existe), sin depender de leer el documento.
- [ ] Si TR-37 cambia de estado o aparece un hallazgo de seguridad nuevo, actualizar este documento en el mismo pull request.