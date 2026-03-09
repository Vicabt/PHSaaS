-- Migración 003: Agregar campo apellido a tabla usuario
-- Ejecutar en Supabase SQL Editor

ALTER TABLE usuario ADD COLUMN IF NOT EXISTS apellido VARCHAR(100);
