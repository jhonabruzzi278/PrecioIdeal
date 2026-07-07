# Precio Ideal

App de monitoreo de precios que compara categorías de productos en [knasta.cl](https://knasta.cl), guarda el historial de precios y genera reportes de actualización.

## Deploy en Railway

1. Crear un proyecto en Railway a partir de este repo.
2. Agregar el plugin **Postgres** y el plugin **Redis** — Railway inyecta `DATABASE_URL` y `REDIS_URL` automáticamente, no hace falta configurarlos a mano.
3. Configurar las variables de entorno del servicio web:
   - `SECRET_KEY` — string largo y aleatorio.
   - `DEBUG=False`
   - `ALLOWED_HOSTS=<tu-servicio>.up.railway.app` (o tu dominio propio).
   - `CSRF_TRUSTED_ORIGINS=https://<tu-servicio>.up.railway.app`
   - `EMAIL_URL` — si vas a enviar emails reales de recuperación de contraseña (sino usa la consola por defecto).
4. Railway detecta el `Procfile`: en cada deploy corre `migrate`, `collectstatic` y levanta `gunicorn` con un solo worker (necesario porque el scheduler de actualizaciones automáticas corre como un hilo en el mismo proceso — no usar más de 1 worker).
5. Primer deploy: crear un superusuario desde la consola de Railway (`Run command` → `python manage.py createsuperuser`).
