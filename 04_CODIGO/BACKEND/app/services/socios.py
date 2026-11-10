# app/services/socios.py
"""
SCRUM-22: el código del socio de negocio (codigo_socio) es su NIT guardado solo con números,
sin puntos, espacios, guion ni dígito de verificación.

Formatos aceptados para el NIT o la cédula: dígitos con puntos o espacios opcionales y, al
final, un guion seguido de un solo dígito (el dígito de verificación, que se descarta).
  800.123.456-1 -> 800123456      900123456 -> 900123456      1 020 304 050 -> 1020304050
Sin guion no se puede distinguir el dígito de verificación: se conservan todos los dígitos.
Debe coincidir con la regla SQL de 05_BASE_DATOS/24_MIGRACION_SOCIOS_CODIGO_NIT.sql.
"""
import re
from typing import Optional

_FORMATO_NIT = re.compile(r"^[0-9][0-9. ]*(-\s*[0-9])?$")
_DIGITO_VERIFICACION = re.compile(r"-\s*[0-9]$")
MIN_DIGITOS = 5
MAX_DIGITOS = 15
MENSAJE_NIT_INVALIDO = (
    f"El NIT debe tener entre {MIN_DIGITOS} y {MAX_DIGITOS} dígitos; solo se admiten puntos, "
    "espacios y un guion antes del dígito de verificación."
)


def normalizar_nit(valor: Optional[str]) -> str:
    """codigo_socio a partir del NIT o cédula. ValueError si falta o no tiene formato de NIT."""
    texto = (valor or "").strip()
    if not texto:
        raise ValueError("El NIT es obligatorio.")
    if not _FORMATO_NIT.match(texto):
        raise ValueError(MENSAJE_NIT_INVALIDO)
    digitos = re.sub(r"[^0-9]", "", _DIGITO_VERIFICACION.sub("", texto))
    if not MIN_DIGITOS <= len(digitos) <= MAX_DIGITOS:
        raise ValueError(MENSAJE_NIT_INVALIDO)
    return digitos


def codigo_socio_o_none(valor: Optional[str]) -> Optional[str]:
    """Igual que normalizar_nit, pero devuelve None en lugar de fallar (para búsquedas)."""
    try:
        return normalizar_nit(valor)
    except ValueError:
        return None
