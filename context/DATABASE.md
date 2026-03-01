# DATABASE.md
> Archivo de contexto para desarrollo. Leer antes de escribir cualquier modelo o migración.
> Extraído de PROYECTO_PH_SAAS.md v2.5

---

## Convención de nombres

- Tablas PostgreSQL → `snake_case` (ej. `pago_detalle`)
- Clases SQLAlchemy → `PascalCase` (ej. `PagoDetalle`)
- Tipos de dinero → siempre `NUMERIC(18,2)` en BD y `Decimal` en Python. Nunca `float`

## Soft delete global

Todas las tablas contables tienen:
```python
is_deleted  BOOLEAN DEFAULT FALSE
deleted_at  TIMESTAMP (nullable)  # solo en tablas que lo usan
```
Nunca se elimina físicamente información contable. Global Query Filter en SQLAlchemy.

## Tablas

### conjunto
```
id              UUID PK
nombre          VARCHAR(100) UNIQUE
nit             VARCHAR(20)
direccion       VARCHAR(200)
ciudad          VARCHAR(100)
created_at      TIMESTAMP
is_deleted      BOOLEAN DEFAULT FALSE
```
> Estado activo/suspendido vive en `suscripcion_saas.estado`, NO aquí.

### usuario
```
id              UUID PK  ← mismo UUID de Supabase Auth
cedula          VARCHAR(20) UNIQUE
nombre          VARCHAR(100)
correo          VARCHAR(100) UNIQUE
telefono_ws     VARCHAR(20)
created_at      TIMESTAMP
is_deleted      BOOLEAN DEFAULT FALSE
```

### usuario_conjunto
```
id              UUID PK
usuario_id      UUID FK → usuario
conjunto_id     UUID FK → conjunto
rol             ENUM('Administrador', 'Contador', 'Porteria')
created_at      TIMESTAMP
is_deleted      BOOLEAN DEFAULT FALSE
deleted_at      TIMESTAMP (nullable)
```
> Índice parcial SQLAlchemy:
> `Index('uq_usuario_conjunto_activo', 'usuario_id', 'conjunto_id', unique=True, postgresql_where=(is_deleted == False))`
> Regla: `is_deleted = TRUE` y `deleted_at = now()` SIEMPRE juntos en la misma operación.

### propiedad
```
id                  UUID PK
conjunto_id         UUID FK
propietario_id      UUID FK → usuario (nullable)
numero_apartamento  VARCHAR(20)
estado              ENUM('Activo', 'Inactivo')
created_at          TIMESTAMP
is_deleted          BOOLEAN DEFAULT FALSE
```
> Índice parcial:
> `Index('uq_propiedad_activa', 'conjunto_id', 'numero_apartamento', unique=True, postgresql_where=(is_deleted == False))`
> `estado = 'Inactivo'` → no genera cuotas pero sigue visible.
> `is_deleted = TRUE` → eliminada lógicamente, no aparece en ninguna vista.

### configuracion_conjunto
```
conjunto_id             UUID PK FK
valor_cuota_estandar    NUMERIC(18,2)
dia_generacion_cuota    INTEGER DEFAULT 1   ← OCULTO en UI, reservado fase futura
dia_notificacion_mora   INTEGER DEFAULT 5   ← solo para WhatsApp, etiqueta: "Día de envío de recordatorio por WhatsApp"
tasa_interes_mora       NUMERIC(5,2)        ← porcentaje mensual (ej. 2.00 = 2% mensual)
permitir_interes        BOOLEAN DEFAULT TRUE
created_at              TIMESTAMP
updated_at              TIMESTAMP
```

### cuota
```
id                  UUID PK
conjunto_id         UUID FK
propiedad_id        UUID FK
periodo             VARCHAR(7)            ← formato YYYY-MM
valor_base          NUMERIC(18,2)
interes_generado    NUMERIC(18,2) DEFAULT 0   ← acumulativo, nunca se sobreescribe
estado              ENUM('Pendiente', 'Parcial', 'Pagada', 'Vencida')
fecha_vencimiento   DATE                  ← último día del mes del periodo
created_at          TIMESTAMP
is_deleted          BOOLEAN DEFAULT FALSE
```
> Índice parcial:
> `Index('uq_cuota_activa', 'conjunto_id', 'propiedad_id', 'periodo', unique=True, postgresql_where=(is_deleted == False))`

### pago
```
id              UUID PK
conjunto_id     UUID FK
propiedad_id    UUID FK
fecha_pago      DATE
valor_total     NUMERIC(18,2)
metodo_pago     ENUM('Efectivo', 'Transferencia', 'PSE', 'Otro')
referencia      VARCHAR(100)
created_at      TIMESTAMP
is_deleted      BOOLEAN DEFAULT FALSE
```

### pago_detalle
```
id                  UUID PK
pago_id             UUID FK → pago
cuota_id            UUID FK → cuota
monto_aplicado      NUMERIC(18,2)   ← = monto_a_interes + monto_a_capital (invariante)
monto_a_interes     NUMERIC(18,2)   ← porción imputada a interés
monto_a_capital     NUMERIC(18,2)   ← porción imputada a capital
created_at          TIMESTAMP
```
> Invariante: `monto_aplicado = monto_a_interes + monto_a_capital` siempre.

### saldo_a_favor
```
id                  UUID PK
conjunto_id         UUID FK
propiedad_id        UUID FK
monto               NUMERIC(18,2)
estado              ENUM('Disponible', 'Aplicado')
origen_pago_id      UUID FK → pago
cuota_aplicada_id   UUID FK → cuota (nullable)
created_at          TIMESTAMP
updated_at          TIMESTAMP
```
> Se genera cuando `pago.valor_total > suma(pago_detalle.monto_aplicado)`.

### movimiento_contable
```
id                  UUID PK
conjunto_id         UUID FK
tipo                ENUM('Ingreso', 'Egreso', 'Ajuste')
concepto            VARCHAR(200)
referencia_tipo     VARCHAR(30)    ← 'PAGO', 'CUOTA', 'AJUSTE_MANUAL'
referencia_id       UUID           ← polimórfico, sin FK en BD
monto               NUMERIC(18,2)
fecha               DATE
created_at          TIMESTAMP
```
> Índice: `Index('ix_movimiento_ref', 'referencia_tipo', 'referencia_id')`
> `pago_service.py` debe validar que `referencia_id` exista antes de insertar.

### proceso_log
```
id              UUID PK
conjunto_id     UUID FK
tipo_proceso    VARCHAR(50)    ← solo 'GENERACION_CUOTAS'
periodo         VARCHAR(7)     ← YYYY-MM, nunca un UUID
ejecutado_en    TIMESTAMP
UNIQUE(conjunto_id, tipo_proceso, periodo)
```
> Solo para `GENERACION_CUOTAS`. Los intereses usan `cuota_interes_log`.

### cuota_interes_log
```
id              UUID PK
cuota_id        UUID FK → cuota
conjunto_id     UUID FK
mes_ejecucion   VARCHAR(7)     ← YYYY-MM del mes en que corrió el job
monto_aplicado  NUMERIC(18,2)  ← interés sumado ese mes
saldo_capital   NUMERIC(18,2)  ← valor_base - suma(pago_detalle.monto_a_capital) al momento del cálculo
created_at      TIMESTAMP
UNIQUE(cuota_id, mes_ejecucion)
```
> Idempotencia: si existe `(cuota_id, mes_ejecucion)` → no ejecutar.

### suscripcion_saas
```
id                  UUID PK
conjunto_id         UUID FK UNIQUE   ← un solo registro por conjunto
estado              ENUM('Activo', 'Suspendido')
fecha_vencimiento   DATE
valor_mensual       NUMERIC(18,2)
observaciones       TEXT
created_at          TIMESTAMP
updated_at          TIMESTAMP
```

## Timezone

```python
# En database.py — obligatorio para evitar desfase UTC vs Bogotá
from sqlalchemy import create_engine, event

engine = create_engine(DATABASE_URL)

@event.listens_for(engine, "connect")
def set_timezone(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET timezone = 'America/Bogota'")
    cursor.close()
```
