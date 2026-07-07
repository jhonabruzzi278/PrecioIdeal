# Roadmap: Precio Ideal como SaaS

Este documento registra el diagnóstico del estado actual y el plan para convertir
Precio Ideal (hoy una app de uso personal) en un SaaS multi-usuario con cobro vía **Flow**
(pasarela de pago chilena). Se actualiza a medida que se avanza — cada sección de
"Hecho" debe moverse a un changelog o cerrarse con fecha cuando se complete.

Última revisión: 2026-06-30.

## 1. Diagnóstico del estado actual

### Riesgos de seguridad / producción (bloqueantes para SaaS)

- `SECRET_KEY` hardcodeada en `pricewatch/settings.py:25` y commiteada al repo. Debe
  moverse a variable de entorno y rotarse antes de exponer la app públicamente.
- `DEBUG = True` fijo (`pricewatch/settings.py:28`) — expone stack traces y variables
  de entorno en producción. Debe depender de `os.environ`.
- `ALLOWED_HOSTS = []` (`pricewatch/settings.py:30`) — bloquea cualquier despliegue
  real; hay que parametrizarlo también por entorno.
- Sin HTTPS/headers de seguridad (`SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE`) — necesarios para cobrar con tarjeta vía Flow.
- Base de datos SQLite (`pricewatch/settings.py:79-84`) no es apta para multi-tenant
  con escrituras concurrentes (los hilos de scraping ya escriben en background). Pasar
  a Postgres antes de escalar a múltiples usuarios.

### Falta de multi-tenancy (requisito central para SaaS)

- No existe `django.contrib.auth` aplicado a nada: las vistas no tienen `@login_required`
  ni scoping por usuario (`monitoring/views.py`, `products/views.py`).
- `Monitor`, `UpdateReport`, `Product` no tienen FK a un usuario/cuenta — todos los
  datos son globales. Para SaaS cada cuenta debe ver solo sus propios monitores y
  productos.
- `UpdateSchedule` es singleton global (`monitoring/models.py:195-198`) — con
  multi-tenant debe pasar a 1 horario por cuenta (o por monitor).

### Ejecución en background no apta para multi-tenant

- Los scrapes corren en `threading.Thread` daemon dentro del mismo proceso web
  (`monitoring/scheduler.py`). Funciona para un usuario; con muchas cuentas
  concurrentes esto satura el proceso de Gunicorn/uWSGI y no es resiliente a
  reinicios. Candidato a migrar a una cola real (Celery + Redis, o Django-RQ) cuando
  haya más de un puñado de cuentas activas.

### Otros hallazgos menores

- No hay tests de pagos ni de auth aún (lógico, no existen esas features).
- `products/tests.py` y `monitoring/tests.py` son archivos únicos — al crecer el
  dominio (planes, suscripciones, pagos) conviene pasar a paquetes `tests/`.
- README.md es un placeholder (`Una app muy buena hecha con amor.`) — sin
  instrucciones de instalación; conviene completarlo cuando el setup tenga pasos
  reales de SaaS (env vars, Flow sandbox, etc).

## 2. Plan de conversión a SaaS

### Fase 0 — Hardening de producción (prerequisito, antes de cobrar nada)
- [x] Mover `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, credenciales de DB, Redis y de
      Flow a variables de entorno (`django-environ`). _(settings.py + `.env.example`)_
- [x] Migrar de SQLite a **PostgreSQL**, corriendo en **Docker** (mismo motor en
      local y producción vía `docker-compose.yml`). Conexión por `DATABASE_URL`.
      Runbook para conservar los datos existentes:
      [docs/migrate-sqlite-to-postgres.md](migrate-sqlite-to-postgres.md).
- [x] Agregar servicio **Redis** al `docker-compose.yml` y configurar
      `django-redis` como `CACHES["default"]`.
- [x] Configurar cabeceras de seguridad para producción (HSTS, cookies seguras,
      `SECURE_SSL_REDIRECT`), activadas solo cuando `DEBUG=False`.
- [ ] Definir entornos staging / producción con su propio `.env` (local ya cubierto).

### Fase 1 — Cuentas y multi-tenancy
- [x] `@login_required` en todas las vistas de `monitoring/views.py` y
      `products/views.py`.
- [x] Login/logout con `django.contrib.auth` views + template propio
      (`templates/registration/login.html`) + link de sesión en el sidebar.
- [x] FK `owner` (`User`) en `Monitor` + migración `0005_monitor_owner` con data
      migration que asigna monitores existentes al primer superuser.
- [x] Scopear `monitor_list` / `monitor_create` por `request.user`.
- [x] **Decisión**: el catálogo (`Product`/`PriceHistory`) y los informes
      (`UpdateReport`) son **globales por diseño** — el scraping funciona independiente
      de las cuentas, se ejecuta una vez y todos los usuarios logueados ven los
      dashboards históricos. NO llevan FK de cuenta. Lo único "propio" de cada cuenta
      son los **monitores**, que son el recurso gateado por la suscripción.
- [ ] **Pendiente**: registro de nuevos usuarios (signup) — hoy solo hay login; los
      usuarios se crean por el admin. Necesario para el onboarding self-service del SaaS.
- [ ] **Pendiente**: pasar `UpdateSchedule` de singleton global a uno por cuenta (o
      por monitor) cuando la frecuencia sea un límite de plan.

### Fase 2 — Planes y suscripciones (app `billing/`)
- [ ] App `billing/` con modelos `Plan` (Free/Pro + límites) y `Subscription`
      (cuenta ↔ plan ↔ estado + `trial_ends_at` / `current_period_end`).
- [ ] Estados de `Subscription`: `trialing`, `active`, `past_due`, `expired`,
      `canceled`. Al primer acceso de un usuario se crea su suscripción en `trialing`
      con `trial_ends_at = now + 30 días`.
- [ ] Capa de servicios `billing/services/access.py`: helpers de gating
      (`has_pro_access(user)`, `can_create_monitor(user)`, etc.) que leen el estado.
- [ ] Management command `expire_subscriptions` (corre por schedule): pasa a
      `expired` las que vencieron y **desactiva** sus monitores (`active=False`, sin
      borrarlos); registra qué desactivó para poder reactivar al pagar.
- [ ] Notificaciones de vencimiento próximo (email) — ver Fase 5; aquí queda el hook.
- [ ] Enforcement en vistas: bloquear `monitor_create`, `update_prices` y reactivación
      de monitores para cuentas sin acceso Pro. El histórico global queda accesible.

### Fase 3 — Integración de pago con Flow
Flow (https://www.flow.cl) expone una API REST + webhooks de confirmación. Piezas a
construir:
- [ ] App nueva `billing/` (sigue la convención de capa de servicios del proyecto:
      lógica en `billing/services/flow.py`, no en vistas).
- [ ] `billing/services/flow.py`: cliente HTTP para Flow — crear orden de pago
      (`payment/create`), consultar estado (`payment/getStatus`), firmar requests con
      `apiKey`/`secretKey` (Flow firma con HMAC-SHA256, hay que generar la firma por
      request).
- [ ] Modelo `Payment`/`FlowTransaction`: guarda `flow_order`, `flow_token`, `status`,
      `amount`, `account`, timestamps. Nunca confiar solo en el redirect del usuario —
      el estado real viene del webhook.
- [ ] Endpoint de confirmación (`urlConfirmation` de Flow) — webhook server-to-server
      que Flow llama para confirmar el pago; debe ser `@csrf_exempt` controlado y
      validar la firma de Flow antes de actualizar `Subscription`.
- [ ] Endpoint de retorno (`urlReturn`) — a dónde Flow redirige al usuario tras pagar;
      solo UX, no debe activar la suscripción por sí solo.
- [ ] Manejo de webhooks idempotente (Flow puede reintentar la confirmación).
- [ ] Modo sandbox vs producción de Flow vía variable de entorno (Flow tiene API
      separada para sandbox: `sandbox.flow.cl`).
- [ ] Página de planes + checkout que arma la orden y redirige a Flow.
- [ ] Manejo de cobros recurrentes si se quiere suscripción mensual automática (Flow
      soporta "Cobro Automático" con inscripción de tarjeta — evaluar si el plan
      inicial es pago único renovable manual o suscripción automática real).

### Fase 4 — Jobs en background aptos para multi-tenant
- [ ] Evaluar migrar `monitoring/scheduler.py` de `threading.Thread` a Celery + Redis
      (o Django-RQ) para que el scraping no compita por el mismo proceso web entre
      cuentas, y para poder limitar concurrencia/rate-limit por plan.
- [ ] Mantener `APScheduler` solo si el volumen de cuentas se mantiene bajo; documentar
      el umbral en el que se vuelve necesario migrar.

### Fase 5 — Operación SaaS
- [ ] Página de estado de cuenta/facturación para el usuario (historial de pagos,
      próxima renovación).
- [ ] Notificaciones por email (bienvenida, pago confirmado, pago fallido, monitor
      caído).
- [ ] Logging/observabilidad por cuenta para soporte (quién está usando qué monitor).

## 3. Decisiones confirmadas

- **Modelo de cuenta**: 1 cuenta = 1 usuario (`User` de Django es la cuenta, sin capa
  de organización/equipo por ahora).
- **Cobro**: suscripción recurrente vía Flow (no pago único). Se usa "Cobro
  Automático" de Flow con inscripción de tarjeta.
- **Onboarding**: todo usuario nuevo arranca en **Plan Free** con acceso completo de
  prueba (modo demo) durante **30 días** desde el registro.
- **Al vencer el período de prueba**: si el usuario no agrega método de pago / no
  contrata el Plan Pro, la cuenta **no se bloquea**, pero baja automáticamente a las
  funcionalidades limitadas del Plan Free (ver abajo) — no pierde datos, pierde
  capacidad/features.
- **Base de datos**: se migra a **PostgreSQL corriendo en Docker** (tanto en local
  como en producción), reemplazando SQLite. Se respetan las convenciones existentes
  del proyecto (capa de servicios, sin tocar el ORM desde las vistas).
- **Cache**: se incorpora **Redis** como cache layer (`django.core.cache` con
  `django-redis`). Mismo contenedor/servicio de Redis se reutiliza más adelante como
  broker si en la Fase 4 se migra de `threading.Thread` a Celery — evita correr dos
  brokers distintos.
- **Autenticación**: se usa **`django.contrib.auth`** nativo (no Clerk ni servicios
  externos — añaden costo por usuario y su soporte para Django es de comunidad). Para
  login social opcional se evaluará **`django-allauth`**. Roles/control de acceso por
  plan (Free/Pro) vía decorator/mixin propio que consulta `request.user.subscription`,
  no vía un IdP externo. Todo queda en Postgres.

### Definición de planes

| Funcionalidad | Free / suscripción vencida (tras la prueba) | Pro (trial o pago activo) |
|---|---|---|
| Acceso al **histórico global** (dashboards, productos, precios) | ✅ **Siempre**, nunca se pierde | ✅ |
| Monitores propios activos | **0** — se desactivan al vencer (no se borran) | Ilimitados (o tope alto a definir) |
| Crear monitores nuevos | No | Sí |
| Actualización manual on-demand | No | Sí |
| Notificaciones por email | Solo avisos de vencimiento de suscripción | Cambios de precio + avisos |
| Exportar datos (CSV/futuro) | No | Sí |
| Soporte | Best-effort | Prioritario |

Modelo de ciclo de vida (lo definió el usuario):
- **Trial (primeros 30 días)**: la cuenta opera con **todas las funcionalidades Pro**
  sin pedir tarjeta.
- **Antes de vencer**: se envían **notificaciones** avisando que la suscripción está
  por vencer y que puede perder sus monitores si no renueva.
- **Al vencer sin pago (Free/expirada)**: los **monitores se desactivan** (no se
  eliminan), no puede crear/ejecutar monitores, **pero conserva el acceso completo al
  histórico global** (dashboards, productos, precios). Si luego paga, se reactivan.

Clave de diseño: lo único que se "pierde" al no renovar es la capacidad de **monitorear**
(crear/activar/ejecutar monitores propios). El catálogo y el histórico son un activo
global compartido y siguen accesibles para cualquier usuario logueado.

Notas de implementación (Fase 2):
- Los límites de la tabla son el enforcement mínimo viable; quedan como constantes en
  `billing` (o en el modelo `Plan`) para poder ajustarlos sin tocar lógica de vistas.
- La baja de Pro a Free **no debe borrar** monitores/historial existentes — solo
  restringir qué se puede crear/ver/ejecutar desde ese momento (p. ej. si tenía 3
  monitores activos y baja a Free, se desactivan automáticamente los 2 más nuevos en
  vez de eliminarlos, dejando 1 activo).

## 4. Convenciones a respetar durante la implementación

Ver `CLAUDE.md` para las convenciones existentes del proyecto (capa de servicios,
vistas function-based, `snake_case` en URLs, formato de precios, etc.). Toda la
lógica de Flow y de billing debe seguir el mismo patrón: vistas delgadas, lógica de
negocio en `<app>/services/`.
