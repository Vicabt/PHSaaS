# SKILLS.md
> Reglas automáticas del proyecto PH SaaS.
> Claude debe leer este archivo en cada sesión junto con los demás archivos de context/.
> Agregar "Lee SKILLS.md" a la instrucción de START.md.

---

## Instrucción obligatoria al inicio de cada tarea

Antes de escribir cualquier código, leer en este orden los archivos de contexto del proyecto
ubicados en la carpeta `context/`:

1. `PROGRESS.md` — fase actual y tareas pendientes
2. `ARCHITECTURE.md` — stack, middleware y estructura
3. `DATABASE.md` — modelo de datos completo
4. `RULES.md` — contratos de services y middleware
5. `CONVENTIONS.md` — nombres, tipos y enums
6. `API.md` — endpoints y permisos por rol
7. `ERRORS.md` — mensajes de error estándar
8. `ENV.md` — variables de entorno

Después de leerlos, confirmar:
- En qué fase está el proyecto y qué tarea se va a realizar
- Qué archivos ya existen para no duplicar código
- Si hay alguna duda antes de empezar

---

## Reglas que NUNCA se rompen

### 1. Estructura de carpetas
Todo archivo nuevo va en su lugar exacto. No crear archivos fuera de esta estructura:

```
ph_saas/
├── main.py
├── config.py
├── database.py
├── scheduler.py
├── dependencies.py
├── errors.py
├── middleware/
│   └── tenant.py
├── models/          ← un archivo por tabla
├── schemas/         ← un archivo por entidad
├── routers/         ← un archivo por módulo
├── services/        ← un archivo por servicio
├── templates/       ← HTML para PDFs (WeasyPrint)
├── static/          ← CSS, JS, imágenes
└── pages/           ← HTML + HTMX del frontend
```

### 2. Convenciones de nombres
- Tablas PostgreSQL → `snake_case`: `pago_detalle`, `cuota_interes_log`
- Clases SQLAlchemy → `PascalCase`: `PagoDetalle`, `CuotaInteresLog`
- Archivos → `snake_case`: `pago_service.py`, `cuotas.py`
- Variables y funciones → `snake_case`: `conjunto_id`, `get_current_user()`
- Constantes → `UPPER_SNAKE_CASE`: `INTERNAL_TOKEN`, `DATABASE_URL`

### 3. Tipos de datos — sin excepciones
- Dinero → `Decimal` en Python, `NUMERIC(18,2)` en PostgreSQL. **Nunca `float`**
- IDs → `uuid.UUID`
- Periodos → `str` formato `YYYY-MM`
- Timestamps → siempre en zona horaria `America/Bogota`

### 4. Seguridad — middleware/tenant.py
El middleware es el componente más crítico del sistema. Flujo obligatorio:
```
JWT (Supabase Auth)
      ↓
¿rol == superadmin? → SÍ: bypass completo, acceso sin restricción
                    → NO: extraer conjunto_id del JWT
                          ↓
                          verificar suscripcion_saas.estado == 'Activo'
                          → Suspendido: HTTP 403
                          → Activo: inyectar conjunto_id en contexto del request
```
- **Todos** los queries de usuarios no-superadmin filtran por `conjunto_id`
- Endpoints `/internal/*` requieren header `X-Internal-Token`
- La validación del token se implementa como dependencia compartida en `routers/internal.py`, no por endpoint individual

### 5. Reglas contables (contratos para pago_service.py y cuota_service.py)

**Imputación de abonos — orden obligatorio:**
```
interes_ya_pagado = suma(pago_detalle.monto_a_interes) de esa cuota
interes_pendiente = cuota.interes_generado - interes_ya_pagado

si abono <= interes_pendiente:
    monto_a_interes = abono
    monto_a_capital = 0
si abono > interes_pendiente:
    monto_a_interes = interes_pendiente
    monto_a_capital = abono - interes_pendiente

# Invariante obligatorio — nunca violar:
monto_aplicado = monto_a_interes + monto_a_capital
```

**Fórmula de interés mensual:**
```
saldo_capital = valor_base - suma(pago_detalle.monto_a_capital)
interes_mes   = saldo_capital * (tasa_interes_mora / 100)
interes_generado += interes_mes   ← acumulativo, NUNCA sobreescribir
```

**Cuota Pagada:** no puede recibir más `pago_detalle`. Validar antes de guardar.

### 6. Transiciones de estado de Cuota
```
Pendiente → Parcial   : abono parcial registrado
Pendiente → Pagada    : abono completa la deuda
Parcial   → Pagada    : abono cubre el saldo restante
Pendiente → Vencida   : job diario, fecha_vencimiento < hoy, sin abonos
Parcial   → Vencida   : job diario, fecha_vencimiento < hoy, saldo pendiente
Vencida   → Parcial   : abono parcial sobre cuota vencida  ← válido
Vencida   → Pagada    : abono completa deuda vencida       ← válido
```

### 7. Idempotencia — dos mecanismos distintos
- `GENERACION_CUOTAS` → verificar `proceso_log` con `(conjunto_id, tipo_proceso, periodo)`
- `CALCULO_INTERESES` → verificar `cuota_interes_log` con `(cuota_id, mes_ejecucion)`
- `proceso_log` NO se usa para intereses

### 8. Soft delete
```python
# Siempre las dos líneas juntas, nunca una sin la otra
registro.is_deleted = True
registro.deleted_at = datetime.now(tz=BOGOTA_TZ)
db.commit()
```

### 9. Mensajes de error
Siempre usar las constantes de `errors.py`. Nunca escribir strings de error directamente en routers o services.

---

## Al terminar cada tarea — obligatorio

Actualizar `context/PROGRESS.md`:
1. Marcar con ✅ las tareas completadas
2. Agregar decisiones nuevas tomadas durante el desarrollo
3. Registrar archivos nuevos en la tabla de archivos del proyecto

---

## Referencia rápida

| Necesito saber sobre... | Leer |
|---|---|
| Qué hacer hoy | `PROGRESS.md` |
| Estructura del proyecto | `ARCHITECTURE.md` |
| Campos de una tabla | `DATABASE.md` |
| Implementar un service | `RULES.md` |
| Cómo nombrar algo | `CONVENTIONS.md` |
| Endpoints existentes | `API.md` |
| Mensajes de error | `ERRORS.md` |
| Variables de entorno | `ENV.md` |
