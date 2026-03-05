"""
errors.py — Constantes de mensajes de error del sistema.
Usar SIEMPRE estas constantes. Nunca escribir strings de error directamente en routers o services.
"""

from fastapi import HTTPException
import http


class ErrorMsg:
    # ── Autenticación y autorización ──────────────────────────────────────────
    AUTH_INVALID_CREDENTIALS  = "Credenciales inválidas"
    AUTH_TOKEN_EXPIRED        = "Sesión expirada. Por favor inicia sesión nuevamente"
    AUTH_NO_TOKEN             = "Se requiere autenticación"
    AUTH_INSUFFICIENT_ROLE    = "No tienes permisos para realizar esta acción"
    AUTH_CONJUNTO_SUSPENDED   = "El acceso a este conjunto está suspendido. Contacta al administrador del sistema"
    AUTH_SUPERADMIN_ONLY      = "Esta acción es exclusiva del administrador del sistema"

    # ── Conjunto / Tenant ──────────────────────────────────────────────────────
    CONJUNTO_NOT_FOUND        = "Conjunto no encontrado"
    CONJUNTO_ALREADY_EXISTS   = "Ya existe un conjunto con ese nombre"
    CONJUNTO_SUSPENDED        = "Conjunto suspendido"

    # ── Propiedad ──────────────────────────────────────────────────────────────
    PROPIEDAD_NOT_FOUND       = "Propiedad no encontrada"
    PROPIEDAD_DUPLICATE       = "Ya existe un apartamento con ese número en este conjunto"
    PROPIEDAD_INACTIVE        = "La propiedad está inactiva y no puede recibir operaciones"

    # ── Cuota ──────────────────────────────────────────────────────────────────
    CUOTA_NOT_FOUND           = "Cuota no encontrada"
    CUOTA_YA_PAGADA           = "Esta cuota ya está pagada y no puede recibir abonos"
    CUOTA_YA_GENERADA         = "Las cuotas para este periodo ya fueron generadas"
    CUOTA_PERIODO_INVALIDO    = "El formato del periodo debe ser YYYY-MM"

    # ── Pago ───────────────────────────────────────────────────────────────────
    PAGO_NOT_FOUND            = "Pago no encontrado"
    PAGO_MONTO_INVALIDO       = "El monto del pago debe ser mayor a cero"
    PAGO_EXCEDE_DEUDA         = "El monto aplicado excede la deuda de la cuota"
    PAGO_CUOTA_OTRO_CONJUNTO  = "La cuota no pertenece a este conjunto"

    # ── Saldo a favor ──────────────────────────────────────────────────────────
    SALDO_NOT_FOUND           = "Saldo a favor no encontrado"
    SALDO_YA_APLICADO         = "Este saldo ya fue aplicado"
    SALDO_INSUFICIENTE        = "Saldo insuficiente para cubrir esta operación"

    # ── Suscripción SaaS ───────────────────────────────────────────────────────
    SUSCRIPCION_NOT_FOUND     = "Suscripción no encontrada para este conjunto"
    SUSCRIPCION_YA_ACTIVA     = "La suscripción ya está activa"
    SUSCRIPCION_YA_SUSPENDIDA = "La suscripción ya está suspendida"

    # ── Endpoints internos ─────────────────────────────────────────────────────
    INTERNAL_TOKEN_INVALIDO   = "Token interno inválido"
    INTERNAL_TOKEN_REQUERIDO  = "Se requiere X-Internal-Token"

    # ── General ────────────────────────────────────────────────────────────────
    NOT_FOUND                 = "Recurso no encontrado"
    OPERACION_NO_PERMITIDA    = "Operación no permitida"
    ERROR_INTERNO             = "Error interno del servidor. Intenta nuevamente"


# ── Helpers para lanzar errores estándar rápidamente ──────────────────────────

def http_400(msg: str) -> HTTPException:
    return HTTPException(status_code=400, detail=msg)

def http_401(msg: str = ErrorMsg.AUTH_NO_TOKEN) -> HTTPException:
    return HTTPException(status_code=401, detail=msg)

def http_403(msg: str = ErrorMsg.AUTH_INSUFFICIENT_ROLE) -> HTTPException:
    return HTTPException(status_code=403, detail=msg)

def http_404(msg: str = ErrorMsg.NOT_FOUND) -> HTTPException:
    return HTTPException(status_code=404, detail=msg)

def http_409(msg: str) -> HTTPException:
    return HTTPException(status_code=409, detail=msg)

def http_500(msg: str = ErrorMsg.ERROR_INTERNO) -> HTTPException:
    return HTTPException(status_code=500, detail=msg)
