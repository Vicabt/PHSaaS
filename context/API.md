# API.md
> Lista completa de endpoints del sistema.
> Leer antes de crear o modificar routers.
> Roles: SA = SuperAdmin, AD = Administrador, CO = Contador, PO = Portería

---

## Convención de rutas

```
/auth/*           → autenticación (público)
/admin/*          → solo SuperAdmin
/api/*            → usuarios autenticados con rol en conjunto
/internal/*       → solo X-Internal-Token (cron-job.org / APScheduler)
```

---

## Auth — routers/auth.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| POST | `/auth/login` | Público | Login con email/password vía Supabase Auth |
| POST | `/auth/logout` | Autenticado | Invalida sesión |
| GET | `/auth/me` | Autenticado | Datos del usuario actual y sus conjuntos |

---

## Conjuntos — routers/conjuntos.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/admin/conjuntos` | SA | Lista todos los conjuntos |
| POST | `/admin/conjuntos` | SA | Crear nuevo conjunto |
| GET | `/admin/conjuntos/{id}` | SA | Detalle de un conjunto |
| PUT | `/admin/conjuntos/{id}` | SA | Editar conjunto |
| DELETE | `/admin/conjuntos/{id}` | SA | Soft delete conjunto |

---

## Suscripciones SaaS — routers/suscripciones.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/admin/suscripciones` | SA | Lista todas las suscripciones con estado |
| PUT | `/admin/suscripciones/{conjunto_id}/pagar` | SA | Registra pago, extiende un mes |
| PUT | `/admin/suscripciones/{conjunto_id}/suspender` | SA | Suspende acceso |
| PUT | `/admin/suscripciones/{conjunto_id}/activar` | SA | Reactiva acceso |
| GET | `/api/suscripcion/mi-vencimiento` | AD | Fecha de vencimiento (solo lectura) |

---

## Propiedades — routers/propiedades.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/propiedades` | AD, CO | Lista propiedades del conjunto |
| POST | `/api/propiedades` | AD | Crear propiedad |
| GET | `/api/propiedades/{id}` | AD, CO, PO | Detalle de propiedad |
| PUT | `/api/propiedades/{id}` | AD | Editar propiedad |
| DELETE | `/api/propiedades/{id}` | AD | Soft delete propiedad |

---

## Usuarios — routers/conjuntos.py (sub-rutas)

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/usuarios` | AD | Lista usuarios del conjunto |
| POST | `/api/usuarios` | AD | Crear usuario y asignar rol |
| PUT | `/api/usuarios/{id}/rol` | AD | Cambiar rol de usuario |
| DELETE | `/api/usuarios/{id}` | AD | Remover usuario del conjunto (soft delete) |

---

## Configuración — routers/conjuntos.py (sub-rutas)

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/configuracion` | AD, CO | Ver configuración del conjunto |
| PUT | `/api/configuracion` | AD | Actualizar configuración |

> `dia_generacion_cuota` nunca se expone ni edita vía API para roles AD/CO.

---

## Cuotas — routers/cuotas.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/cuotas` | AD, CO | Lista cuotas (filtros: periodo, estado, propiedad) |
| POST | `/api/cuotas/generar` | AD | Generación manual de cuotas para un periodo |
| GET | `/api/cuotas/{id}` | AD, CO | Detalle de cuota |
| GET | `/api/cuotas/propiedad/{id}` | AD, CO, PO | Cuotas de una propiedad |

---

## Pagos — routers/pagos.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/pagos` | AD, CO | Lista pagos del conjunto |
| POST | `/api/pagos` | AD, CO | Registrar pago con detalle por cuota |
| GET | `/api/pagos/{id}` | AD, CO | Detalle de pago con desglose |
| DELETE | `/api/pagos/{id}` | AD | Anular pago (soft delete) |
| GET | `/api/saldos-a-favor` | AD, CO | Lista saldos a favor disponibles |
| POST | `/api/saldos-a-favor/{id}/aplicar` | AD, CO | Aplicar saldo a favor a una cuota |

---

## Cartera — routers/cartera.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/cartera` | AD, CO | Resumen de cartera del conjunto |
| GET | `/api/cartera/propiedad/{id}` | AD, CO, PO | Estado de cuenta de una propiedad |
| GET | `/api/cartera/antiguedad` | AD, CO | Clasificación por antigüedad (30/60/90/90+) |

---

## Reportes y PDFs — routers/reportes.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/reportes/paz-y-salvo/{propiedad_id}` | AD, CO, PO | PDF paz y salvo |
| GET | `/api/reportes/estado-cuenta/{propiedad_id}` | AD, CO, PO | PDF estado de cuenta |
| GET | `/api/reportes/cartera` | AD, CO | PDF cartera general del conjunto |

---

## Vistas HTML — routers/views.py

> Rutas del panel web. Auth via cookie `ph_token` (JWT). Responden HTML, no JSON.
> Todos los POST usan PRG (Post-Redirect-Get). Flash messages en query params `?success=` / `?error=`.

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/` | Público | Pantalla de login |
| POST | `/panel/login` | Público | Procesar login, setear cookies |
| GET | `/panel/logout` | Autenticado | Limpiar cookies, redirigir a `/` |
| GET | `/panel/sa/conjuntos` | SA | Lista conjuntos con suscripción |
| POST | `/panel/sa/conjuntos/crear` | SA | Crear conjunto |
| POST | `/panel/sa/conjuntos/{id}/editar` | SA | Editar conjunto |
| POST | `/panel/sa/conjuntos/{id}/eliminar` | SA | Soft delete conjunto |
| GET | `/panel/sa/suscripciones` | SA | Gestión suscripciones |
| POST | `/panel/sa/suscripciones/{id}/crear` | SA | Crear suscripción |
| POST | `/panel/sa/suscripciones/{id}/editar` | SA | Editar suscripción (estado, fecha, valor, observaciones) |
| POST | `/panel/sa/suscripciones/{id}/pagar` | SA | +1 mes vencimiento |
| POST | `/panel/sa/suscripciones/{id}/suspender` | SA | Suspender |
| POST | `/panel/sa/suscripciones/{id}/activar` | SA | Activar |
| GET | `/panel/sa/usuarios` | SA | Lista todos los usuarios por conjunto |
| POST | `/panel/sa/usuarios/crear` | SA | Crear usuario y asignar rol a un conjunto |
| POST | `/panel/sa/usuarios/{uc_id}/rol` | SA | Cambiar rol de usuario en su conjunto |
| POST | `/panel/sa/usuarios/{uc_id}/eliminar` | SA | Remover usuario de un conjunto (soft delete) |
| GET | `/panel/app/propiedades` | AD | Lista propiedades del conjunto |
| POST | `/panel/app/propiedades/crear` | AD | Crear propiedad |
| POST | `/panel/app/propiedades/{id}/editar` | AD | Editar propiedad |
| POST | `/panel/app/propiedades/{id}/eliminar` | AD | Soft delete propiedad |
| GET | `/panel/app/usuarios` | AD | Lista usuarios del conjunto |
| POST | `/panel/app/usuarios/crear` | AD | Crear usuario (crea en Supabase Auth + local) |
| POST | `/panel/app/usuarios/{id}/rol` | AD | Cambiar rol |
| POST | `/panel/app/usuarios/{id}/eliminar` | AD | Remover del conjunto (soft delete) |
| GET | `/panel/app/configuracion` | AD | Ver configuración del conjunto |
| POST | `/panel/app/configuracion` | AD | Guardar configuración |
| GET | `/panel/app/propietarios` | AD | Lista propietarios/residentes del conjunto |
| POST | `/panel/app/propietarios/crear` | AD | Crear propietario (usuario local sin Supabase Auth) |
| POST | `/panel/app/propietarios/{id}/editar` | AD | Editar datos del propietario |
| POST | `/panel/app/propietarios/{id}/eliminar` | AD | Soft delete propietario y desasignar unidades |

---

## Endpoints internos — routers/internal.py

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| POST | `/internal/generar-cuotas` | X-Internal-Token | Genera cuotas para todos los conjuntos activos |
| POST | `/internal/calcular-intereses` | X-Internal-Token | Calcula intereses para todas las cuotas vencidas |

> Ambos endpoints validan `X-Internal-Token` como dependencia compartida.
> Ambos son idempotentes: verifican `proceso_log` / `cuota_interes_log` antes de ejecutar.

---

## Resumen de acceso por rol

| Recurso | SA | AD | CO | PO |
|---|---|---|---|---|
| Conjuntos (CRUD) | ✅ | ❌ | ❌ | ❌ |
| Suscripciones (gestión) | ✅ | 👁 solo ver vencimiento | ❌ | ❌ |
| Propiedades (CRUD) | ❌ | ✅ | 👁 | 👁 |
| Usuarios (CRUD) | ❌ | ✅ | ❌ | ❌ |
| Propietarios/Residentes (CRUD) | ❌ | ✅ | ❌ | ❌ |
| Configuración | ❌ | ✅ | 👁 | ❌ |
| Cuotas | ❌ | ✅ | 👁 | 👁 solo su propiedad |
| Pagos | ❌ | ✅ | ✅ | ❌ |
| Cartera | ❌ | ✅ | ✅ | 👁 solo su propiedad |
| Reportes PDF | ❌ | ✅ | ✅ | ✅ |
