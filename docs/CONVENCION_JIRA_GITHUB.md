# Convención de trazabilidad entre Jira y GitHub

Vigente desde el 30/10/2026 (ver `Refinamiento_Sprint2_Sprint3_Compromisos_Jira.md`).
Objetivo: que cualquier commit, rama o Pull Request se pueda rastrear hasta su
tarjeta de Jira sin ambigüedad, y que el panel "Development" de cada tarjeta de
Jira muestre automáticamente los commits y PRs relacionados.

## Nombres de rama

```
feature/pfciii2026-<N>-<descripcion-breve>
```

- `<N>` es el número de la clave de Jira (por ejemplo, para `PFCIII2026-57`, `N` es `57`).
- `<descripcion-breve>` va en minúsculas, separada por guiones, sin tildes.
- Ejemplo real: `feature/pfciii2026-57-pruebas-postgresql`

## Mensajes de commit y títulos de Pull Request

```
PFCIII2026-<N> <CODIGO>: <descripción breve en minúscula inicial>
```

- `<CODIGO>` es el código del plan de sprints (por ejemplo `TR-31`, `HU-06`).
- Ejemplo real: `PFCIII2026-57 TR-31: pruebas del pipeline contra PostgreSQL`

**Por qué la clave de Jira va primero:** Jira reconoce automáticamente la clave
(`PFCIII2026-N`) en el texto del commit y del PR, y los enlaza solos al panel
"Development" de esa tarjeta — sin necesidad de pegar el link a mano.

## Excepción: commits anteriores al 30/10/2026

Los commits de HU-05 a HU-07, TR-11, TR-12 y TR-29 se hicieron antes de que esta
convención existiera, y llevan solo el código del plan (sin la clave de Jira).
No se reescribe su historia. En el informe se incluye una tabla que cruza
manualmente: clave de Jira, código del plan, número de PR y hash de commit.

## Integración Jira-GitHub (conecta el repositorio al panel Development)

1. En GitHub, el repositorio debe tener instalada la app oficial **"GitHub for
   Jira"** (se instala desde el marketplace de GitHub o desde Jira, en
   **Configuración del proyecto → Apps → GitHub**). Requiere permisos de
   administrador del repositorio.
2. Una vez conectado, cada commit o PR que incluya `PFCIII2026-N` en su mensaje
   aparece automáticamente en la sección "Development" de esa tarjeta en Jira,
   mostrando su estado (rama abierta, PR en revisión, PR fusionado).
3. Verificación: entrar a cualquier tarjeta ya trabajada con la convención
   (por ejemplo PFCIII2026-57) y confirmar que el panel "Development" muestra
   el commit y el PR sin haberlos pegado a mano.

## Tabla de equivalencia (commits anteriores a la convención)

| Clave de Jira | Código | PR | Commit |
|---|---|---|---|
| — | HU-05 | #3 | (pendiente de completar con `git log`) |
| — | HU-06 | #4 | (pendiente de completar con `git log`) |
| — | HU-07 | (PR de HU-07) | (pendiente de completar con `git log`) |
| — | TR-11 | #1 | (pendiente de completar con `git log`) |
| — | TR-12 | #2 | (pendiente de completar con `git log`) |
| — | TR-29 | #6 | (pendiente de completar con `git log`) |