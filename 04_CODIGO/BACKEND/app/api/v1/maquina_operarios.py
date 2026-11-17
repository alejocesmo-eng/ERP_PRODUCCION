# app/api/v1/maquina_operarios.py
"""
Operarios asignados a cada máquina (33_MIGRACION_CARGA_TIEMPOS_MANUAL.sql). La carga manual de
tiempos (app/api/v1/tiempos_manuales.py) solo ofrece, para cada máquina, los operarios asignados
aquí.

- Entra quien entra a Configuración de roles: ADMIN con PERM_CONFIGURACION_ROLES, rol leído de la
  base en cada consulta.
- Se asignan usuarios activos con rol OPERARIO, por su usuario. La lista que se envía reemplaza la
  de la máquina.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.configuracion_roles import requerir_configuracion
from app.core import roles
from app.db.database import get_db
from app.db.models import EquipoPlanta, MaquinaOperario, Usuario
from app.services.usuarios import normalizar_usuario

router = APIRouter()


class OperariosMaquina(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuarios: list[str]


def _operarios_disponibles(db: Session) -> list[Usuario]:
    return (
        db.query(Usuario).filter(Usuario.id_rol == roles.OPERARIO, Usuario.activo.isnot(False))
        .order_by(Usuario.nombre_completo).all()
    )


def _asignados(db: Session) -> dict:
    asignados = {}
    for id_equipo, usuario, nombre in (
        db.query(MaquinaOperario.id_equipo, Usuario.usuario, Usuario.nombre_completo)
        .join(Usuario, Usuario.id_usuario == MaquinaOperario.id_usuario)
        .order_by(Usuario.nombre_completo).all()
    ):
        asignados.setdefault(id_equipo, []).append({"usuario": usuario, "nombre": nombre})
    return asignados


@router.get("")
def listar_maquinas(db: Session = Depends(get_db), _: dict = Depends(requerir_configuracion)):
    asignados = _asignados(db)
    return {
        "maquinas": [{
            "codigo_maquina": maquina.codigo_maquina,
            "nombre": maquina.nombre,
            "operarios": asignados.get(maquina.id_equipo, []),
        } for maquina in db.query(EquipoPlanta).order_by(EquipoPlanta.codigo_maquina).all()],
        "operarios_disponibles": [
            {"usuario": usuario.usuario, "nombre": usuario.nombre_completo} for usuario in _operarios_disponibles(db)
        ],
    }


@router.put("/{codigo_maquina}/operarios")
def asignar_operarios(
    codigo_maquina: str,
    datos: OperariosMaquina,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_configuracion),
):
    maquina = db.query(EquipoPlanta).filter(EquipoPlanta.codigo_maquina == codigo_maquina).first()
    if not maquina:
        raise HTTPException(status_code=404, detail="No se encontró la máquina indicada.")
    disponibles = {operario.usuario: operario for operario in _operarios_disponibles(db)}
    elegidos = {normalizar_usuario(usuario) for usuario in datos.usuarios if usuario.strip()}
    ajenos = sorted(elegidos - disponibles.keys())
    if ajenos:
        raise HTTPException(status_code=422, detail=f"Solo se asignan operarios activos: {', '.join(ajenos)}.")

    actuales = {
        fila.id_usuario: fila for fila in db.query(MaquinaOperario).filter(MaquinaOperario.id_equipo == maquina.id_equipo).all()
    }
    nuevos = {disponibles[usuario].id_usuario for usuario in elegidos}
    for id_usuario, fila in actuales.items():
        if id_usuario not in nuevos:
            db.delete(fila)
    for id_usuario in nuevos - actuales.keys():
        db.add(MaquinaOperario(id_equipo=maquina.id_equipo, id_usuario=id_usuario, asignado_por=usuario["id_usuario"]))
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo guardar la asignación de operarios.") from error
    return {"codigo_maquina": maquina.codigo_maquina, "operarios": _asignados(db).get(maquina.id_equipo, [])}
