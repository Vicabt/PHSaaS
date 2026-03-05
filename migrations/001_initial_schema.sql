-- =============================================================================
-- migrations/001_initial_schema.sql
-- Migración inicial — crea todas las tablas del sistema PH SaaS.
-- Ejecutar UNA SOLA VEZ en Supabase → SQL Editor.
-- =============================================================================

-- ── TIPOS ENUM ─────────────────────────────────────────────────────────────────

CREATE TYPE rol_conjunto_enum       AS ENUM ('Administrador', 'Contador', 'Porteria');
CREATE TYPE estado_propiedad_enum   AS ENUM ('Activo', 'Inactivo');
CREATE TYPE estado_cuota_enum       AS ENUM ('Pendiente', 'Parcial', 'Pagada', 'Vencida');
CREATE TYPE metodo_pago_enum        AS ENUM ('Efectivo', 'Transferencia', 'PSE', 'Otro');
CREATE TYPE estado_saldo_enum       AS ENUM ('Disponible', 'Aplicado');
CREATE TYPE tipo_movimiento_enum    AS ENUM ('Ingreso', 'Egreso', 'Ajuste');
CREATE TYPE estado_suscripcion_enum AS ENUM ('Activo', 'Suspendido');


-- ── TABLA: conjunto ────────────────────────────────────────────────────────────
-- Estado activo/suspendido vive en suscripcion_saas.estado, NO aquí.

CREATE TABLE conjunto (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre      VARCHAR(100) NOT NULL UNIQUE,
    nit         VARCHAR(20),
    direccion   VARCHAR(200),
    ciudad      VARCHAR(100),
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    is_deleted  BOOLEAN     NOT NULL DEFAULT FALSE
);


-- ── TABLA: usuario ─────────────────────────────────────────────────────────────
-- id = mismo UUID de Supabase Auth (auth.users.id).
-- No declaramos FK a auth.users porque está en schema diferente;
-- la integridad se garantiza en la lógica de negocio.

CREATE TABLE usuario (
    id          UUID        PRIMARY KEY,  -- igual a auth.users.id
    cedula      VARCHAR(20) UNIQUE,
    nombre      VARCHAR(100) NOT NULL,
    correo      VARCHAR(100) NOT NULL UNIQUE,
    telefono_ws VARCHAR(20),
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    is_deleted  BOOLEAN     NOT NULL DEFAULT FALSE
);


-- ── TABLA: suscripcion_saas ────────────────────────────────────────────────────
-- Un solo registro por conjunto. El middleware verifica estado aquí.

CREATE TABLE suscripcion_saas (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conjunto_id         UUID        NOT NULL UNIQUE REFERENCES conjunto(id),
    estado              estado_suscripcion_enum NOT NULL,
    fecha_vencimiento   DATE        NOT NULL,
    valor_mensual       NUMERIC(18,2) NOT NULL,
    observaciones       TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP   NOT NULL DEFAULT NOW()
);


-- ── TABLA: usuario_conjunto ────────────────────────────────────────────────────
-- N:M usuario <-> conjunto con rol. Soft delete con deleted_at.

CREATE TABLE usuario_conjunto (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id  UUID            NOT NULL REFERENCES usuario(id),
    conjunto_id UUID            NOT NULL REFERENCES conjunto(id),
    rol         rol_conjunto_enum NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    is_deleted  BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMP
);

-- Único índice parcial: un usuario solo puede tener un rol activo por conjunto
CREATE UNIQUE INDEX uq_usuario_conjunto_activo
    ON usuario_conjunto (usuario_id, conjunto_id)
    WHERE is_deleted = FALSE;


-- ── TABLA: propiedad ───────────────────────────────────────────────────────────
-- estado = 'Inactivo' → no genera cuotas pero sigue visible.
-- is_deleted = TRUE → eliminada lógicamente.

CREATE TABLE propiedad (
    id                  UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    conjunto_id         UUID                    NOT NULL REFERENCES conjunto(id),
    propietario_id      UUID                    REFERENCES usuario(id),
    numero_apartamento  VARCHAR(20)             NOT NULL,
    estado              estado_propiedad_enum   NOT NULL DEFAULT 'Activo',
    created_at          TIMESTAMP               NOT NULL DEFAULT NOW(),
    is_deleted          BOOLEAN                 NOT NULL DEFAULT FALSE
);

-- Evita duplicados activos de número de apartamento en el mismo conjunto
CREATE UNIQUE INDEX uq_propiedad_activa
    ON propiedad (conjunto_id, numero_apartamento)
    WHERE is_deleted = FALSE;


-- ── TABLA: configuracion_conjunto ─────────────────────────────────────────────
-- PK = conjunto_id. Una fila por conjunto.
-- dia_generacion_cuota: OCULTO en UI, reservado fase futura.

CREATE TABLE configuracion_conjunto (
    conjunto_id             UUID            PRIMARY KEY REFERENCES conjunto(id),
    valor_cuota_estandar    NUMERIC(18,2)   NOT NULL,
    dia_generacion_cuota    INTEGER         NOT NULL DEFAULT 1,   -- oculto en UI
    dia_notificacion_mora   INTEGER         NOT NULL DEFAULT 5,
    tasa_interes_mora       NUMERIC(5,2)    NOT NULL DEFAULT 0.00,
    permitir_interes        BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP       NOT NULL DEFAULT NOW()
);


-- ── TABLA: cuota ───────────────────────────────────────────────────────────────
-- interes_generado: ACUMULATIVO — nunca sobreescribir, solo sumar.
-- fecha_vencimiento: último día del mes del periodo.

CREATE TABLE cuota (
    id                  UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    conjunto_id         UUID                NOT NULL REFERENCES conjunto(id),
    propiedad_id        UUID                NOT NULL REFERENCES propiedad(id),
    periodo             VARCHAR(7)          NOT NULL,  -- formato YYYY-MM
    valor_base          NUMERIC(18,2)       NOT NULL,
    interes_generado    NUMERIC(18,2)       NOT NULL DEFAULT 0.00,
    estado              estado_cuota_enum   NOT NULL DEFAULT 'Pendiente',
    fecha_vencimiento   DATE                NOT NULL,
    created_at          TIMESTAMP           NOT NULL DEFAULT NOW(),
    is_deleted          BOOLEAN             NOT NULL DEFAULT FALSE
);

-- Una sola cuota activa por propiedad + periodo (permite regenerar cuota eliminada)
CREATE UNIQUE INDEX uq_cuota_activa
    ON cuota (conjunto_id, propiedad_id, periodo)
    WHERE is_deleted = FALSE;


-- ── TABLA: pago ────────────────────────────────────────────────────────────────
-- Encabezado del pago. Los detalles van en pago_detalle.

CREATE TABLE pago (
    id              UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    conjunto_id     UUID                NOT NULL REFERENCES conjunto(id),
    propiedad_id    UUID                NOT NULL REFERENCES propiedad(id),
    fecha_pago      DATE                NOT NULL,
    valor_total     NUMERIC(18,2)       NOT NULL,
    metodo_pago     metodo_pago_enum    NOT NULL,
    referencia      VARCHAR(100),
    created_at      TIMESTAMP           NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN             NOT NULL DEFAULT FALSE
);


-- ── TABLA: pago_detalle ────────────────────────────────────────────────────────
-- Invariante: monto_aplicado = monto_a_interes + monto_a_capital (siempre).

CREATE TABLE pago_detalle (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    pago_id         UUID            NOT NULL REFERENCES pago(id),
    cuota_id        UUID            NOT NULL REFERENCES cuota(id),
    monto_aplicado  NUMERIC(18,2)   NOT NULL,  -- = monto_a_interes + monto_a_capital
    monto_a_interes NUMERIC(18,2)   NOT NULL DEFAULT 0.00,
    monto_a_capital NUMERIC(18,2)   NOT NULL DEFAULT 0.00,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_monto_aplicado CHECK (
        monto_aplicado = monto_a_interes + monto_a_capital
    )
);


-- ── TABLA: saldo_a_favor ───────────────────────────────────────────────────────
-- Se crea cuando pago.valor_total > suma(pago_detalle.monto_aplicado).

CREATE TABLE saldo_a_favor (
    id                  UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    conjunto_id         UUID                NOT NULL REFERENCES conjunto(id),
    propiedad_id        UUID                NOT NULL REFERENCES propiedad(id),
    monto               NUMERIC(18,2)       NOT NULL,
    estado              estado_saldo_enum   NOT NULL DEFAULT 'Disponible',
    origen_pago_id      UUID                NOT NULL REFERENCES pago(id),
    cuota_aplicada_id   UUID                REFERENCES cuota(id),
    created_at          TIMESTAMP           NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP           NOT NULL DEFAULT NOW()
);


-- ── TABLA: movimiento_contable ─────────────────────────────────────────────────
-- referencia_id es polimórfico — sin FK en BD. Validar que exista en pago_service.py.
-- referencia_tipo: 'PAGO', 'CUOTA', 'AJUSTE_MANUAL'

CREATE TABLE movimiento_contable (
    id              UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    conjunto_id     UUID                    NOT NULL,
    tipo            tipo_movimiento_enum    NOT NULL,
    concepto        VARCHAR(200)            NOT NULL,
    referencia_tipo VARCHAR(30)             NOT NULL,
    referencia_id   UUID                    NOT NULL,
    monto           NUMERIC(18,2)           NOT NULL,
    fecha           DATE                    NOT NULL,
    created_at      TIMESTAMP               NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_movimiento_ref ON movimiento_contable (referencia_tipo, referencia_id);


-- ── TABLA: proceso_log ─────────────────────────────────────────────────────────
-- SOLO para idempotencia de GENERACION_CUOTAS.
-- Los intereses usan cuota_interes_log — NO esta tabla.

CREATE TABLE proceso_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conjunto_id     UUID        NOT NULL REFERENCES conjunto(id),
    tipo_proceso    VARCHAR(50) NOT NULL,  -- solo 'GENERACION_CUOTAS'
    periodo         VARCHAR(7)  NOT NULL,  -- YYYY-MM — nunca un UUID
    ejecutado_en    TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_proceso_log UNIQUE (conjunto_id, tipo_proceso, periodo)
);


-- ── TABLA: cuota_interes_log ───────────────────────────────────────────────────
-- Idempotencia para CALCULO_INTERESES.
-- Si existe (cuota_id, mes_ejecucion) → no ejecutar de nuevo.

CREATE TABLE cuota_interes_log (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    cuota_id        UUID            NOT NULL REFERENCES cuota(id),
    conjunto_id     UUID            NOT NULL REFERENCES conjunto(id),
    mes_ejecucion   VARCHAR(7)      NOT NULL,  -- YYYY-MM del mes en que corrió el job
    monto_aplicado  NUMERIC(18,2)   NOT NULL,
    saldo_capital   NUMERIC(18,2)   NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cuota_interes_log UNIQUE (cuota_id, mes_ejecucion)
);


-- =============================================================================
-- FUNCIÓN: actualizar updated_at automáticamente
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_suscripcion_saas_updated_at
    BEFORE UPDATE ON suscripcion_saas
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_configuracion_conjunto_updated_at
    BEFORE UPDATE ON configuracion_conjunto
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_saldo_a_favor_updated_at
    BEFORE UPDATE ON saldo_a_favor
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- VERIFICACIÓN FINAL — ejecutar después de la migración para confirmar
-- =============================================================================
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
-- ORDER BY table_name;
