"""
models/__init__.py — Importa todos los modelos para que SQLAlchemy los registre.
Siempre importar este módulo antes de llamar Base.metadata.create_all().
"""

from ph_saas.models.base import Base
from ph_saas.models.conjunto import Conjunto
from ph_saas.models.usuario import Usuario
from ph_saas.models.usuario_conjunto import UsuarioConjunto
from ph_saas.models.suscripcion import SuscripcionSaaS
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.cuota import Cuota
from ph_saas.models.pago import Pago
from ph_saas.models.pago_detalle import PagoDetalle
from ph_saas.models.saldo_a_favor import SaldoAFavor
from ph_saas.models.movimiento_contable import MovimientoContable
from ph_saas.models.proceso_log import ProcesoLog
from ph_saas.models.cuota_interes_log import CuotaInteresLog

__all__ = [
    "Base",
    "Conjunto",
    "Usuario",
    "UsuarioConjunto",
    "SuscripcionSaaS",
    "Propiedad",
    "ConfiguracionConjunto",
    "Cuota",
    "Pago",
    "PagoDetalle",
    "SaldoAFavor",
    "MovimientoContable",
    "ProcesoLog",
    "CuotaInteresLog",
]
