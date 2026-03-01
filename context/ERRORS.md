# ERRORS.md
> Códigos de error estándar y mensajes del sistema.
> Usar estos mensajes exactos en toda la aplicación para consistencia.
> Leer antes de implementar validaciones o manejo de errores.

---

## Formato estándar de error (FastAPI)

```json
{
  "detail": "Mensaje legible para el usuario"
}
```

Para errores con múltiples campos (validación Pydantic):
```json
{
  "detail": [
    {"loc": ["body", "campo"], "msg": "descripción", "type": "tipo_error"}
  ]
}
```

---

## Errores HTTP y sus usos

| Código | Nombre | Cuándo usarlo |
|---|---|---|
| 400 | Bad Request | Datos inválidos, regla de negocio violada |
| 401 | Unauthorized | Sin token o token inválido |
| 403 | Forbidden | Token válido pero sin permiso |
| 404 | Not Found | Recurso no existe o fue soft-eliminado |
| 409 | Conflict | Duplicado (ej. apartamento ya existe) |
| 422 | Unprocessable Entity | Validación Pydantic fallida (automático) |
| 500 | Internal Server Error | Error inesperado del servidor |

---

## Mensajes estándar por categoría

### Autenticación y autorización
```python
AUTH_INVALID_CREDENTIALS  = "Credenciales inválidas"
AUTH_TOKEN_EXPIRED        = "Sesión expirada. Por favor inicia sesión nuevamente"
AUTH_NO_TOKEN             = "Se requiere autenticación"
AUTH_INSUFFICIENT_ROLE    = "No tienes permisos para realizar esta acción"
AUTH_CONJUNTO_SUSPENDED   = "El acceso a este conjunto está suspendido. Contacta al administrador del sistema"
AUTH_SUPERADMIN_ONLY      = "Esta acción es exclusiva del administrador del sistema"
```

### Conjunto / Tenant
```python
CONJUNTO_NOT_FOUND        = "Conjunto no encontrado"
CONJUNTO_ALREADY_EXISTS   = "Ya existe un conjunto con ese nombre"
CONJUNTO_SUSPENDED        = "Conjunto suspendido"
```

### Propiedad
```python
PROPIEDAD_NOT_FOUND       = "Propiedad no encontrada"
PROPIEDAD_DUPLICATE       = "Ya existe un apartamento con ese número en este conjunto"
PROPIEDAD_INACTIVE        = "La propiedad está inactiva y no puede recibir operaciones"
```

### Cuota
```python
CUOTA_NOT_FOUND           = "Cuota no encontrada"
CUOTA_YA_PAGADA           = "Esta cuota ya está pagada y no puede recibir abonos"
CUOTA_YA_GENERADA         = "Las cuotas para este periodo ya fueron generadas"
CUOTA_PERIODO_INVALIDO    = "El formato del periodo debe ser YYYY-MM"
```

### Pago
```python
PAGO_NOT_FOUND            = "Pago no encontrado"
PAGO_MONTO_INVALIDO       = "El monto del pago debe ser mayor a cero"
PAGO_EXCEDE_DEUDA         = "El monto aplicado excede la deuda de la cuota"
PAGO_CUOTA_OTRO_CONJUNTO  = "La cuota no pertenece a este conjunto"
```

### Saldo a favor
```python
SALDO_NOT_FOUND           = "Saldo a favor no encontrado"
SALDO_YA_APLICADO         = "Este saldo ya fue aplicado"
SALDO_INSUFICIENTE        = "Saldo insuficiente para cubrir esta operación"
```

### Suscripción SaaS
```python
SUSCRIPCION_NOT_FOUND     = "Suscripción no encontrada para este conjunto"
SUSCRIPCION_YA_ACTIVA     = "La suscripción ya está activa"
SUSCRIPCION_YA_SUSPENDIDA = "La suscripción ya está suspendida"
```

### Endpoints internos
```python
INTERNAL_TOKEN_INVALIDO   = "Token interno inválido"
INTERNAL_TOKEN_REQUERIDO  = "Se requiere X-Internal-Token"
```

### Errores generales
```python
NOT_FOUND                 = "Recurso no encontrado"
OPERACION_NO_PERMITIDA    = "Operación no permitida"
ERROR_INTERNO             = "Error interno del servidor. Intenta nuevamente"
```

---

## Implementación recomendada

### Archivo de constantes: `errors.py`
```python
# errors.py — en la raíz del proyecto
class ErrorMsg:
    # Auth
    AUTH_INVALID_CREDENTIALS  = "Credenciales inválidas"
    AUTH_TOKEN_EXPIRED        = "Sesión expirada. Por favor inicia sesión nuevamente"
    AUTH_NO_TOKEN             = "Se requiere autenticación"
    AUTH_INSUFFICIENT_ROLE    = "No tienes permisos para realizar esta acción"
    AUTH_CONJUNTO_SUSPENDED   = "El acceso a este conjunto está suspendido. Contacta al administrador del sistema"
    AUTH_SUPERADMIN_ONLY      = "Esta acción es exclusiva del administrador del sistema"
    # Conjunto
    CONJUNTO_NOT_FOUND        = "Conjunto no encontrado"
    CONJUNTO_ALREADY_EXISTS   = "Ya existe un conjunto con ese nombre"
    # Propiedad
    PROPIEDAD_NOT_FOUND       = "Propiedad no encontrada"
    PROPIEDAD_DUPLICATE       = "Ya existe un apartamento con ese número en este conjunto"
    PROPIEDAD_INACTIVE        = "La propiedad está inactiva y no puede recibir operaciones"
    # Cuota
    CUOTA_NOT_FOUND           = "Cuota no encontrada"
    CUOTA_YA_PAGADA           = "Esta cuota ya está pagada y no puede recibir abonos"
    CUOTA_YA_GENERADA         = "Las cuotas para este periodo ya fueron generadas"
    # Pago
    PAGO_NOT_FOUND            = "Pago no encontrado"
    PAGO_MONTO_INVALIDO       = "El monto del pago debe ser mayor a cero"
    # Saldo a favor
    SALDO_NOT_FOUND           = "Saldo a favor no encontrado"
    SALDO_YA_APLICADO         = "Este saldo ya fue aplicado"
    # Suscripción
    SUSCRIPCION_NOT_FOUND     = "Suscripción no encontrada para este conjunto"
    # Internos
    INTERNAL_TOKEN_INVALIDO   = "Token interno inválido"
    # General
    NOT_FOUND                 = "Recurso no encontrado"
    ERROR_INTERNO             = "Error interno del servidor. Intenta nuevamente"
```

### Uso en routers y services
```python
from fastapi import HTTPException
from errors import ErrorMsg

# En un router
@router.get("/propiedades/{id}")
async def get_propiedad(id: UUID, ...):
    propiedad = await propiedad_service.get_by_id(id, conjunto_id)
    if not propiedad:
        raise HTTPException(status_code=404, detail=ErrorMsg.PROPIEDAD_NOT_FOUND)
    return propiedad

# En middleware/tenant.py
if suscripcion.estado == "Suspendido":
    raise HTTPException(status_code=403, detail=ErrorMsg.AUTH_CONJUNTO_SUSPENDED)
```

---

## Regla general

- **400** para errores de negocio (cuota ya pagada, periodo duplicado)
- **403** para problemas de permisos o conjunto suspendido
- **404** para recursos que no existen o fueron soft-eliminados
- **409** para duplicados detectados antes de intentar insertar
- Nunca exponer stack traces al cliente en producción (`DEBUG=false`)
