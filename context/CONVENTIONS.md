# CONVENTIONS.md
> Archivo de contexto para desarrollo. Leer antes de crear cualquier archivo o función.
> Extraído de PROYECTO_PH_SAAS.md v2.5

---

## Nombres

### Tablas PostgreSQL → snake_case
```
conjunto, usuario, usuario_conjunto, propiedad
configuracion_conjunto, cuota, pago, pago_detalle
saldo_a_favor, movimiento_contable, proceso_log
cuota_interes_log, suscripcion_saas
```

### Clases SQLAlchemy/Python → PascalCase
```python
Conjunto, Usuario, UsuarioConjunto, Propiedad
ConfiguracionConjunto, Cuota, Pago, PagoDetalle
SaldoAFavor, MovimientoContable, ProcesoLog
CuotaInteresLog, SuscripcionSaaS
```

### Archivos → snake_case con sufijo descriptivo
```
models/conjunto.py
models/usuario.py
models/propiedad.py
models/cuota.py
models/pago.py
models/suscripcion.py
models/proceso_log.py
models/cuota_interes_log.py

routers/conjuntos.py        ← plural para colecciones
routers/propiedades.py
routers/cuotas.py
routers/pagos.py
routers/cartera.py
routers/reportes.py
routers/suscripciones.py
routers/internal.py
routers/auth.py

services/cuota_service.py   ← singular + _service
services/pago_service.py
services/cartera_service.py
services/pdf_service.py
services/whatsapp_service.py
services/suscripcion_service.py
```

### Variables y funciones → snake_case
```python
conjunto_id, propiedad_id, valor_base
get_current_user(), require_role(), calcular_interes()
```

### Constantes → UPPER_SNAKE_CASE
```python
INTERNAL_TOKEN, DATABASE_URL, SUPABASE_URL
```

---

## Tipos de datos

| Concepto | Python | PostgreSQL |
|---|---|---|
| Dinero | `Decimal` | `NUMERIC(18,2)` |
| IDs | `uuid.UUID` | `UUID` |
| Fechas | `date` | `DATE` |
| Timestamps | `datetime` | `TIMESTAMP` |
| Periodos | `str` "YYYY-MM" | `VARCHAR(7)` |
| Booleanos | `bool` | `BOOLEAN` |

**Nunca usar `float` para dinero.**

---

## Estructura de respuestas API

```python
# Éxito
{"data": {...}, "message": "ok"}

# Error de validación
{"detail": "Descripción del error"}

# Error 403 tenant suspendido
{"detail": "Conjunto suspendido. Contacte al administrador del sistema."}
```

---

## Enums (valores exactos)

```python
# Cuota.estado
'Pendiente', 'Parcial', 'Pagada', 'Vencida'

# Pago.metodo_pago
'Efectivo', 'Transferencia', 'PSE', 'Otro'

# SaldoAFavor.estado
'Disponible', 'Aplicado'

# Propiedad.estado
'Activo', 'Inactivo'

# UsuarioConjunto.rol
'Administrador', 'Contador', 'Porteria'

# SuscripcionSaaS.estado
'Activo', 'Suspendido'

# MovimientoContable.tipo
'Ingreso', 'Egreso', 'Ajuste'

# MovimientoContable.referencia_tipo
'PAGO', 'CUOTA', 'AJUSTE_MANUAL'

# ProcesoLog.tipo_proceso
'GENERACION_CUOTAS'
```

---

## Índices parciales (SQLAlchemy)

```python
# usuario_conjunto — evita duplicados activos
Index('uq_usuario_conjunto_activo', 'usuario_id', 'conjunto_id',
      unique=True, postgresql_where=(is_deleted == False))

# propiedad — evita bloqueo por soft delete
Index('uq_propiedad_activa', 'conjunto_id', 'numero_apartamento',
      unique=True, postgresql_where=(is_deleted == False))

# cuota — permite regenerar cuota eliminada
Index('uq_cuota_activa', 'conjunto_id', 'propiedad_id', 'periodo',
      unique=True, postgresql_where=(is_deleted == False))

# movimiento_contable — rendimiento en reportes
Index('ix_movimiento_ref', 'referencia_tipo', 'referencia_id')
```

---

## Formato de periodos

- Siempre `YYYY-MM` (ej. `2026-03`)
- Nunca usar UUID como periodo en `proceso_log`
- `cuota_interes_log.mes_ejecucion` = mes en que corrió el job (no el periodo de la cuota)

---

## Soft delete

```python
# Siempre juntos, nunca uno sin el otro
registro.is_deleted = True
registro.deleted_at = datetime.now(tz=bogota_tz)
db.commit()
```

---

## Zona horaria

```python
import pytz
BOGOTA_TZ = pytz.timezone('America/Bogota')

# Para APScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler(timezone='America/Bogota')
```
