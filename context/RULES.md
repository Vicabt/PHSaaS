# RULES.md
> Archivo de contexto para desarrollo. Leer antes de implementar cualquier service.
> Contratos explícitos que DEBEN respetarse en la implementación.
> Extraído de PROYECTO_PH_SAAS.md v2.5

---

## Reglas generales

- Moneda: COP. Siempre `NUMERIC(18,2)` en BD y `Decimal` en Python. **Nunca `float`**
- Zona horaria: `America/Bogota` en todo el sistema
- Soft delete: nunca eliminar físicamente datos contables
- Multi-tenant: todo query debe filtrar por `conjunto_id`

---

## Contrato: cuota_service.py

### Generación de cuotas
- Solo para propiedades con `estado = 'Activo'` AND `is_deleted = FALSE`
- Propiedades `Inactivo` no generan cuotas
- `fecha_vencimiento` = último día del mes del periodo:
  ```python
  from dateutil.relativedelta import relativedelta
  from datetime import date, timedelta
  fecha_vencimiento = date(year, month, 1) + relativedelta(months=1) - timedelta(days=1)
  ```
- Idempotencia: verificar `proceso_log` antes de generar. Si existe `(conjunto_id, 'GENERACION_CUOTAS', periodo)` → no ejecutar

### Cálculo de intereses
- Aplica a cuotas con `fecha_vencimiento < hoy` en estados `Pendiente`, `Parcial` o `Vencida`
- Solo si `configuracion_conjunto.permitir_interes = TRUE`
- Tasa en `configuracion_conjunto.tasa_interes_mora` es **porcentaje mensual** (ej. `2.00` = 2% mensual)
- Base de cálculo: **saldo de capital pendiente**
  ```
  saldo_capital = valor_base - suma(pago_detalle.monto_a_capital)
  interes_mes = saldo_capital * (tasa / 100)
  interes_generado += interes_mes   # acumulativo, nunca sobreescribir
  ```
- Idempotencia: verificar `cuota_interes_log`. Si existe `(cuota_id, mes_ejecucion)` → no ejecutar
- Registrar en `cuota_interes_log`: `monto_aplicado = interes_mes`, `saldo_capital = saldo_capital`

### Marcado como Vencida (APScheduler diario, medianoche Bogotá)
- Marcar `Vencida` todas las cuotas con `fecha_vencimiento < hoy` en estado `Pendiente` o `Parcial`

---

## Contrato: pago_service.py

### Imputación de abonos (orden obligatorio)
**Primero a interés, luego a capital** (estándar contable colombiano):
```
interes_ya_pagado = suma(pago_detalle.monto_a_interes) de esa cuota
interes_pendiente = cuota.interes_generado - interes_ya_pagado

si abono <= interes_pendiente:
    monto_a_interes = abono
    monto_a_capital = 0

si abono > interes_pendiente:
    monto_a_interes = interes_pendiente
    monto_a_capital = abono - interes_pendiente

# Invariante obligatorio:
monto_aplicado = monto_a_interes + monto_a_capital
```

### Transiciones de estado de Cuota
```
Pendiente → Parcial  : suma(monto_aplicado) > 0 pero < valor_base + interes_generado
Pendiente → Pagada   : suma(monto_aplicado) >= valor_base + interes_generado
Parcial   → Pagada   : nuevo abono completa el saldo restante
Pendiente → Vencida  : fecha_actual > fecha_vencimiento, sin abonos (job automático)
Parcial   → Vencida  : fecha_actual > fecha_vencimiento, saldo pendiente (job automático)
Vencida   → Parcial  : abono registrado que no cubre el total
Vencida   → Pagada   : pago que cubre valor_base + interes_generado completo
```
> Una cuota `Pagada` NO puede recibir más `pago_detalle`. Validar antes de guardar.
> `Vencida → Parcial/Pagada` es válido: una deuda vencida siempre puede pagarse.

### Movimiento contable
Al registrar un pago, siempre crear un `movimiento_contable`:
- `tipo = 'Ingreso'`
- `referencia_tipo = 'PAGO'`
- `referencia_id = pago.id`
- Validar que `referencia_id` exista antes de insertar (no hay FK en BD)

### Saldo a favor
- Se crea cuando `pago.valor_total > suma(pago_detalle.monto_aplicado)`
- Al aplicar un `saldo_a_favor` a una cuota, si el saldo supera la deuda:
  1. Aplicar el monto exacto para cubrir la cuota → cuota pasa a `Pagada`
  2. `excedente = saldo_disponible - deuda_total_cuota`
  3. Crear nuevo `saldo_a_favor` con `monto = excedente`, `estado = 'Disponible'`
  4. Marcar el original como `Aplicado`, llenar `cuota_aplicada_id`
  5. Todo en una sola transacción atómica

---

## Contrato: middleware/tenant.py

- SuperAdmin (`role: superadmin` en JWT) → bypass completo, sin restricción
- Otros roles → extraer `conjunto_id` del JWT → verificar `suscripcion_saas.estado == 'Activo'`
- Si `Suspendido` → HTTP 403
- Inyectar `conjunto_id` en el contexto del request

---

## Contrato: routers/internal.py

- Todos los endpoints bajo `/internal/` deben validar `X-Internal-Token`
- El secreto viene de `config.py` → variable de entorno `INTERNAL_TOKEN`
- Validación como dependencia compartida (no por endpoint individual)

---

## Idempotencia

| Proceso | Mecanismo | Clave única |
|---|---|---|
| GENERACION_CUOTAS | `proceso_log` | `(conjunto_id, tipo_proceso, periodo)` |
| CALCULO_INTERESES | `cuota_interes_log` | `(cuota_id, mes_ejecucion)` |

---

## UI: campos con comportamiento especial

| Campo | Comportamiento |
|---|---|
| `configuracion_conjunto.dia_generacion_cuota` | Oculto en UI. Solo visible para SuperAdmin. No editable |
| `configuracion_conjunto.dia_notificacion_mora` | Etiqueta: "Día de envío de recordatorio por WhatsApp" |
| `suscripcion_saas.fecha_vencimiento` | Administrador puede ver (solo lectura). Solo SuperAdmin modifica |
