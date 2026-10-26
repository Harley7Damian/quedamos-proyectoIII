# Pasos para poner a correr el Módulo 1 (unos 15 minutos, sin cuentas externas)

Requisito: Python 3.10 o superior (`python --version`). En Windows, desde PowerShell en la carpeta del proyecto:

1. `python -m venv .venv`
2. `.venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. `python manage.py migrate`
5. `python manage.py runserver`
6. Abre http://127.0.0.1:8000/ en el navegador.

Si PowerShell bloquea la activación del entorno: `Set-ExecutionPolicy -Scope Process Bypass` y repite el paso 2.

## Prueba del flujo completo (10 minutos)

1. En una ventana normal, crea una cuenta con rol Ejecutivo. Verás tu código de 6 caracteres.
2. En una ventana de incógnito, crea una cuenta con rol Asistente. Escribe el código en "Vincularme con un ejecutivo".
3. Crea una solicitud de reunión. Debe aparecer en la lista.
4. Vuelve a la ventana del ejecutivo. En unos 5 segundos debe aparecer la solicitud y el nombre de su asistente.
5. Recarga ambas ventanas: la sesión y los datos se mantienen.

Si algo falla, copia el mensaje que aparece en pantalla o en la terminal y envíamelo.

## Comandos útiles

- `python manage.py test`: ejecuta las 31 pruebas automáticas (menos de un segundo).
- `python manage.py createsuperuser`: crea un administrador para entrar a http://127.0.0.1:8000/admin/ y ver los datos.
- `python manage.py makemigrations` y luego `migrate`: después de cambiar un modelo.

## Publicarlo (Render, cuando toque)

Servicio web con comando de construcción `./build.sh` y de inicio `gunicorn config.wsgi`. Variables: `DEBUG=0`, `SECRET_KEY` (una cadena larga aleatoria), `ALLOWED_HOSTS` (el dominio de Render), `CSRF_TRUSTED_ORIGINS` (https://ese-dominio) y `DATABASE_URL` (la base PostgreSQL de Render).

## Subirlo a GitHub

Crea una rama (`git checkout -b feature/modulo-1-cuentas`), agrega esta carpeta al repositorio y abre un PR. No subas `.venv` ni `db.sqlite3` (ya están en `.gitignore`).
