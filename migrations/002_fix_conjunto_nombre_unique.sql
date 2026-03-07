-- ── Migración 002: Corregir unicidad parcial en conjunto.nombre ────────────────
--
-- Problema: La tabla `conjunto` tiene UNIQUE(nombre) como constraint completo.
-- El sistema usa soft-delete (is_deleted=TRUE), por lo tanto un conjunto eliminado
-- bloquea la creación de uno nuevo con el mismo nombre, causando un IntegrityError
-- no controlado (HTTP 500).
--
-- Solución: Reemplazar el UNIQUE completo por un índice parcial UNIQUE
-- que solo aplique sobre filas activas (is_deleted = FALSE).
--
-- INSTRUCCIONES: Ejecutar este script en Supabase SQL Editor como superuser.
-- ─────────────────────────────────────────────────────────────────────────────

BEGIN;

-- 1. Eliminar el constraint UNIQUE existente en nombre
ALTER TABLE conjunto DROP CONSTRAINT IF EXISTS conjunto_nombre_key;

-- 2. Crear índice parcial: único solo entre conjuntos activos
CREATE UNIQUE INDEX IF NOT EXISTS uq_conjunto_nombre_activo
    ON conjunto (nombre)
    WHERE is_deleted = FALSE;

COMMIT;
