# Migración de datos: SQLite → PostgreSQL

Procedimiento para **conservar los datos existentes** (productos, historial, monitores,
informes, usuarios) al pasar de la base SQLite original a PostgreSQL en Docker.

La idea: aplicar la migración nueva sobre SQLite primero (para que los monitores queden
con `owner` asignado), exportar todo con `dumpdata`, levantar Postgres, crear el esquema
y cargar el dump con `loaddata`. La conexión a la DB es por `DATABASE_URL`, así que
cambiar de motor es solo una variable de entorno — no se toca código.

> Comandos en **PowerShell** (shell principal del proyecto). Ejecutar siempre desde la
> raíz del repo, con las dependencias ya instaladas (`pip install -r requirements.txt`).

## 0. Pre-requisitos

- El archivo `db.sqlite3` original debe estar en la raíz del proyecto.
- Debe existir al menos un **superusuario** en esa base (el que usabas en el admin).
  Si no existe, los monitores quedarán sin dueño y los asignás manualmente en el paso 5.

## 1. Aplicar la migración nueva sobre SQLite (asigna `owner`)

```powershell
$env:DATABASE_URL = "sqlite:///db.sqlite3"
python manage.py migrate
```

Esto aplica `monitoring/0005_monitor_owner` sobre SQLite. Su data migration asigna todos
los monitores existentes al primer superusuario.

## 2. Exportar los datos a un archivo JSON

```powershell
python manage.py dumpdata `
  --natural-foreign --natural-primary `
  -e contenttypes -e auth.permission -e sessions -e admin.logentry `
  --indent 2 -o legacy_dump.json
```

(`$env:DATABASE_URL` sigue apuntando a SQLite en esta sesión de PowerShell.)

Se excluyen tablas que Django recrea solo (`contenttypes`, permisos, sesiones, logs del
admin) para evitar choques al cargar. Los usuarios (`auth.user`) **sí** se exportan, con
su hash de contraseña, así que vas a poder entrar con las mismas credenciales.

## 3. Apuntar a Postgres y crear el esquema

```powershell
Remove-Item Env:\DATABASE_URL          # vuelve al default Postgres de settings
docker compose up -d                   # levanta postgres + redis
python manage.py migrate               # crea el esquema en Postgres (vacío)
```

## 4. Cargar los datos en Postgres

```powershell
python manage.py loaddata legacy_dump.json
```

## 5. Verificar

```powershell
python manage.py runserver
```

- Entrá con tu usuario de siempre.
- En **Monitores** deberías ver tus monitores (ya con dueño asignado).
- Revisá **Productos** e **Informes**.

Si algún monitor quedó sin dueño (no había superusuario en el paso 1), asignalo:

```powershell
python manage.py shell
```
```python
from django.contrib.auth import get_user_model
from monitoring.models import Monitor
u = get_user_model().objects.get(username="TU_USUARIO")
Monitor.objects.filter(owner__isnull=True).update(owner=u)
```

## 6. Limpieza

Una vez verificado, podés borrar el dump y archivar el SQLite:

```powershell
Remove-Item legacy_dump.json
Rename-Item db.sqlite3 db.sqlite3.bak   # backup por las dudas; está gitignored
```

## Notas

- `DATABASE_URL` con SQLite es solo para el volcado; el funcionamiento normal usa el
  default Postgres de `settings.py` (o el `DATABASE_URL` de tu `.env`).
- En **git bash** la sintaxis de la variable inline sería
  `DATABASE_URL=sqlite:///db.sqlite3 python manage.py ...` en una sola línea.
