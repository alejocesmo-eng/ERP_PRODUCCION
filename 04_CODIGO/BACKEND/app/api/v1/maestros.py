from typing import Optional
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual, requerir_roles
from app.db.database import get_db
from app.db.models import (
    AreaTrabajadorEnum,
    ArticuloInventario,
    CategoriaInventario,
    EstructuraFinanciera,
    SocioNegocio,
    TipoEstructuraFinancieraEnum,
    TrabajadorUsuario,
    UnidadMedida,
    Usuario,
)

router = APIRouter()
ROLES_LECTURA = ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"]


class SocioNegocioCreate(BaseModel):
    nit_cedula: str = Field(min_length=5, max_length=30)
    razon_social: str = Field(min_length=2, max_length=200)
    es_cliente: bool = False
    es_proveedor: bool = False
    direccion: Optional[str] = Field(default=None, max_length=255)
    telefono: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=150)
    condiciones_pago_dias: int = Field(default=30, ge=0, le=365)
    cuenta_contable_por_cobrar: Optional[str] = Field(default=None, max_length=100)
    cuenta_contable_por_pagar: Optional[str] = Field(default=None, max_length=100)
    estado_activo: bool = True

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        if valor and ("@" not in valor or "." not in valor.rsplit("@", 1)[-1]):
            raise ValueError("El correo electrónico no tiene un formato válido.")
        return valor.strip().lower() if valor else valor

    @model_validator(mode="after")
    def validar_tipo_y_cuentas(self):
        if not self.es_cliente and not self.es_proveedor:
            raise ValueError("El socio debe estar marcado como cliente, proveedor o ambos.")
        if self.es_cliente and not self.cuenta_contable_por_cobrar:
            raise ValueError("La cuenta por cobrar es obligatoria para clientes.")
        if self.es_proveedor and not self.cuenta_contable_por_pagar:
            raise ValueError("La cuenta por pagar es obligatoria para proveedores.")
        return self


class TrabajadorCreate(BaseModel):
    cedula: str = Field(min_length=5, max_length=30)
    nombre_completo: str = Field(min_length=2, max_length=150)
    area: AreaTrabajadorEnum
    cargo: str = Field(min_length=2, max_length=100)
    tarifa_hora_mano_obra: Decimal = Field(default=Decimal("0"), ge=0)
    id_usuario_sistema: Optional[UUID] = None


class EstructuraFinancieraCreate(BaseModel):
    tipo: TipoEstructuraFinancieraEnum
    codigo: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=2, max_length=150)
    descripcion: Optional[str] = None
    cuenta_padre: Optional[str] = Field(default=None, max_length=50)
    activo: bool = True

    @model_validator(mode="after")
    def validar_padre(self):
        if self.tipo != TipoEstructuraFinancieraEnum.CUENTA_CONTABLE and self.cuenta_padre:
            raise ValueError("Solo las cuentas contables pueden tener una cuenta padre.")
        return self


class CategoriaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=2, max_length=100)
    icono: Optional[str] = Field(default="📦", max_length=10)
    descripcion: Optional[str] = None


class UnidadMedidaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=100)
    simbolo: str = Field(min_length=1, max_length=20)
    activo: bool = True


def _serializar_socio(socio: SocioNegocio):
    return {
        "id_socio": socio.id_socio,
        "nit_cedula": socio.nit_cedula,
        "razon_social": socio.razon_social,
        "es_cliente": socio.es_cliente,
        "es_proveedor": socio.es_proveedor,
        "direccion": socio.direccion,
        "telefono": socio.telefono,
        "email": socio.email,
        "condiciones_pago_dias": socio.condiciones_pago_dias,
        "cuenta_contable_por_cobrar": socio.cuenta_contable_por_cobrar,
        "cuenta_contable_por_pagar": socio.cuenta_contable_por_pagar,
        "estado_activo": socio.estado_activo,
    }


def _serializar_trabajador(trabajador: TrabajadorUsuario):
    return {
        "id_trabajador": trabajador.id_trabajador,
        "cedula": trabajador.cedula,
        "nombre_completo": trabajador.nombre_completo,
        "area": trabajador.area.value,
        "cargo": trabajador.cargo,
        "tarifa_hora_mano_obra": trabajador.tarifa_hora_mano_obra,
        "id_usuario_sistema": trabajador.id_usuario_sistema,
    }


def _serializar_estructura(elemento: EstructuraFinanciera):
    return {
        "id_elemento": elemento.id_elemento,
        "tipo": elemento.tipo.value,
        "codigo": elemento.codigo,
        "nombre": elemento.nombre,
        "descripcion": elemento.descripcion,
        "cuenta_padre": elemento.cuenta_padre,
        "activo": elemento.activo,
    }


def _serializar_categoria(categoria: CategoriaInventario):
    return {
        "id_categoria": categoria.id_categoria,
        "codigo": categoria.codigo,
        "nombre": categoria.nombre,
        "icono": categoria.icono,
        "descripcion": categoria.descripcion,
        "es_personalizada": categoria.es_personalizada,
    }


def _serializar_unidad(unidad: UnidadMedida):
    return {
        "id_unidad": unidad.id_unidad,
        "codigo": unidad.codigo,
        "nombre": unidad.nombre,
        "simbolo": unidad.simbolo,
        "activo": unidad.activo,
    }


def _guardar(db: Session, entidad, mensaje: str):
    try:
        db.add(entidad)
        db.commit()
        db.refresh(entidad)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="El código o identificador ya existe o está relacionado con otros datos.") from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=mensaje) from error
    return entidad


@router.get("/socios")
def listar_socios(
    activos: bool = True,
    tipo: Optional[str] = Query(default=None, pattern="^(CLIENTE|PROVEEDOR)$"),
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_LECTURA)),
):
    consulta = db.query(SocioNegocio)
    if activos:
        consulta = consulta.filter(SocioNegocio.estado_activo.is_(True))
    if tipo == "CLIENTE":
        consulta = consulta.filter(SocioNegocio.es_cliente.is_(True))
    elif tipo == "PROVEEDOR":
        consulta = consulta.filter(SocioNegocio.es_proveedor.is_(True))
    return [_serializar_socio(socio) for socio in consulta.order_by(SocioNegocio.razon_social).all()]


@router.post("/socios", status_code=status.HTTP_201_CREATED)
def crear_socio(
    datos: SocioNegocioCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    nit = datos.nit_cedula.strip().upper()
    if db.query(SocioNegocio).filter(SocioNegocio.nit_cedula == nit).first():
        raise HTTPException(status_code=409, detail="El NIT o cédula ya está registrado.")
    valores = datos.model_dump()
    valores["nit_cedula"] = nit
    valores["razon_social"] = datos.razon_social.strip()
    socio = SocioNegocio(**valores)
    return _serializar_socio(_guardar(db, socio, "No se pudo registrar el socio de negocio."))


@router.put("/socios/{id_socio}")
def actualizar_socio(
    id_socio: UUID,
    datos: SocioNegocioCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == id_socio).first()
    if not socio:
        raise HTTPException(status_code=404, detail="Socio de negocio no encontrado.")
    nit = datos.nit_cedula.strip().upper()
    duplicado = db.query(SocioNegocio).filter(
        SocioNegocio.nit_cedula == nit,
        SocioNegocio.id_socio != id_socio,
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="El NIT o cédula ya está registrado.")
    for campo, valor in datos.model_dump().items():
        setattr(socio, campo, valor.strip() if isinstance(valor, str) else valor)
    return _serializar_socio(_guardar(db, socio, "No se pudo actualizar el socio de negocio."))


@router.delete("/socios/{id_socio}")
def desactivar_socio(
    id_socio: UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == id_socio).first()
    if not socio:
        raise HTTPException(status_code=404, detail="Socio de negocio no encontrado.")
    socio.estado_activo = False
    return _serializar_socio(_guardar(db, socio, "No se pudo desactivar el socio de negocio."))


@router.get("/personal")
def listar_personal(
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_LECTURA)),
):
    trabajadores = db.query(TrabajadorUsuario).order_by(TrabajadorUsuario.nombre_completo).all()
    usuarios = {usuario.id_usuario: usuario for usuario in db.query(Usuario).all()}
    return [
        {
            **_serializar_trabajador(trabajador),
            "usuario": usuarios[trabajador.id_usuario_sistema].email
            if trabajador.id_usuario_sistema in usuarios else None,
        }
        for trabajador in trabajadores
    ]


@router.get("/personal/usuarios-disponibles")
def listar_usuarios_disponibles(
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    vinculados = db.query(TrabajadorUsuario.id_usuario_sistema).filter(
        TrabajadorUsuario.id_usuario_sistema.is_not(None)
    )
    return [
        {"id_usuario": cuenta.id_usuario, "nombre": cuenta.nombre_completo, "email": cuenta.email, "rol": cuenta.id_rol}
        for cuenta in db.query(Usuario).filter(
            Usuario.activo.is_(True),
            ~Usuario.id_usuario.in_(vinculados),
        ).order_by(Usuario.nombre_completo).all()
    ]


@router.post("/personal", status_code=status.HTTP_201_CREATED)
def crear_trabajador(
    datos: TrabajadorCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    cedula = datos.cedula.strip()
    if db.query(TrabajadorUsuario).filter(TrabajadorUsuario.cedula == cedula).first():
        raise HTTPException(status_code=409, detail="La cédula ya está registrada.")
    if datos.id_usuario_sistema and not db.query(Usuario).filter(
        Usuario.id_usuario == datos.id_usuario_sistema,
        Usuario.activo.is_(True),
    ).first():
        raise HTTPException(status_code=422, detail="El usuario de sistema no existe o está inactivo.")
    trabajador = TrabajadorUsuario(**datos.model_dump(exclude={"cedula"}), cedula=cedula)
    return _serializar_trabajador(_guardar(db, trabajador, "No se pudo registrar el trabajador."))


@router.put("/personal/{id_trabajador}")
def actualizar_trabajador(
    id_trabajador: UUID,
    datos: TrabajadorCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    trabajador = db.query(TrabajadorUsuario).filter(
        TrabajadorUsuario.id_trabajador == id_trabajador
    ).first()
    if not trabajador:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado.")
    cedula = datos.cedula.strip()
    duplicado = db.query(TrabajadorUsuario).filter(
        TrabajadorUsuario.cedula == cedula,
        TrabajadorUsuario.id_trabajador != id_trabajador,
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="La cédula ya está registrada.")
    if datos.id_usuario_sistema and not db.query(Usuario).filter(
        Usuario.id_usuario == datos.id_usuario_sistema,
        Usuario.activo.is_(True),
    ).first():
        raise HTTPException(status_code=422, detail="El usuario de sistema no existe o está inactivo.")
    for campo, valor in datos.model_dump().items():
        setattr(trabajador, campo, valor.strip() if isinstance(valor, str) else valor)
    return _serializar_trabajador(_guardar(db, trabajador, "No se pudo actualizar el trabajador."))


@router.delete("/personal/{id_trabajador}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_trabajador(
    id_trabajador: UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    trabajador = db.query(TrabajadorUsuario).filter(
        TrabajadorUsuario.id_trabajador == id_trabajador
    ).first()
    if not trabajador:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado.")
    try:
        db.delete(trabajador)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo eliminar el trabajador.") from error


@router.get("/cuentas-costos")
def listar_estructura_financiera(
    tipo: Optional[TipoEstructuraFinancieraEnum] = None,
    activos: bool = True,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_LECTURA)),
):
    consulta = db.query(EstructuraFinanciera)
    if tipo:
        consulta = consulta.filter(EstructuraFinanciera.tipo == tipo)
    if activos:
        consulta = consulta.filter(EstructuraFinanciera.activo.is_(True))
    elementos = consulta.order_by(EstructuraFinanciera.codigo).all()
    return [_serializar_estructura(elemento) for elemento in elementos]


@router.post("/cuentas-costos", status_code=status.HTTP_201_CREATED)
def crear_elemento_financiero(
    datos: EstructuraFinancieraCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    codigo = datos.codigo.strip().upper()
    if db.query(EstructuraFinanciera).filter(EstructuraFinanciera.codigo == codigo).first():
        raise HTTPException(status_code=409, detail="El código financiero ya existe.")
    if datos.cuenta_padre and not db.query(EstructuraFinanciera).filter(
        EstructuraFinanciera.codigo == datos.cuenta_padre.strip(),
        EstructuraFinanciera.tipo == TipoEstructuraFinancieraEnum.CUENTA_CONTABLE,
    ).first():
        raise HTTPException(status_code=422, detail="La cuenta padre no existe o no es una cuenta contable.")
    elemento = EstructuraFinanciera(
        **datos.model_dump(exclude={"codigo", "cuenta_padre"}),
        codigo=codigo,
        cuenta_padre=datos.cuenta_padre.strip() if datos.cuenta_padre else None,
    )
    return _serializar_estructura(_guardar(db, elemento, "No se pudo registrar la estructura financiera."))


@router.put("/cuentas-costos/{id_elemento}")
def actualizar_elemento_financiero(
    id_elemento: UUID,
    datos: EstructuraFinancieraCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    elemento = db.query(EstructuraFinanciera).filter(
        EstructuraFinanciera.id_elemento == id_elemento
    ).first()
    if not elemento:
        raise HTTPException(status_code=404, detail="Elemento financiero no encontrado.")
    codigo = datos.codigo.strip().upper()
    duplicado = db.query(EstructuraFinanciera).filter(
        EstructuraFinanciera.codigo == codigo,
        EstructuraFinanciera.id_elemento != id_elemento,
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="El código financiero ya existe.")
    if datos.cuenta_padre:
        padre = db.query(EstructuraFinanciera).filter(
            EstructuraFinanciera.codigo == datos.cuenta_padre.strip(),
            EstructuraFinanciera.tipo == TipoEstructuraFinancieraEnum.CUENTA_CONTABLE,
            EstructuraFinanciera.id_elemento != id_elemento,
        ).first()
        if not padre:
            raise HTTPException(status_code=422, detail="La cuenta padre no existe o no es válida.")
    for campo, valor in datos.model_dump().items():
        setattr(elemento, campo, valor.strip() if isinstance(valor, str) else valor)
    return _serializar_estructura(_guardar(db, elemento, "No se pudo actualizar el elemento financiero."))


@router.delete("/cuentas-costos/{id_elemento}")
def desactivar_elemento_financiero(
    id_elemento: UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    elemento = db.query(EstructuraFinanciera).filter(
        EstructuraFinanciera.id_elemento == id_elemento
    ).first()
    if not elemento:
        raise HTTPException(status_code=404, detail="Elemento financiero no encontrado.")
    elemento.activo = False
    return _serializar_estructura(_guardar(db, elemento, "No se pudo desactivar el elemento financiero."))


@router.get("/catalogos")
def listar_catalogos(
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_LECTURA)),
):
    categorias = db.query(CategoriaInventario).order_by(CategoriaInventario.nombre).all()
    unidades = db.query(UnidadMedida).filter(UnidadMedida.activo.is_(True)).order_by(UnidadMedida.codigo).all()
    return {
        "categorias": [_serializar_categoria(categoria) for categoria in categorias],
        "unidades_medida": [_serializar_unidad(unidad) for unidad in unidades],
    }


@router.get("/catalogos/categorias")
def listar_categorias(
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_LECTURA)),
):
    return [
        _serializar_categoria(categoria)
        for categoria in db.query(CategoriaInventario).order_by(CategoriaInventario.nombre).all()
    ]


@router.post("/catalogos/categorias", status_code=status.HTTP_201_CREATED)
def crear_categoria(
    datos: CategoriaCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    codigo = datos.codigo.strip().upper().replace(" ", "_")
    if db.query(CategoriaInventario).filter(CategoriaInventario.codigo == codigo).first():
        raise HTTPException(status_code=409, detail="El código de categoría ya existe.")
    categoria = CategoriaInventario(
        codigo=codigo,
        nombre=datos.nombre.strip(),
        icono=datos.icono or "📦",
        descripcion=datos.descripcion,
        es_personalizada=True,
    )
    return _serializar_categoria(_guardar(db, categoria, "No se pudo registrar la categoría."))


@router.put("/catalogos/categorias/{id_categoria}")
def actualizar_categoria(
    id_categoria: UUID,
    datos: CategoriaCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    categoria = db.query(CategoriaInventario).filter(
        CategoriaInventario.id_categoria == id_categoria
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría de insumos no encontrada.")
    codigo = datos.codigo.strip().upper().replace(" ", "_")
    duplicado = db.query(CategoriaInventario).filter(
        CategoriaInventario.codigo == codigo,
        CategoriaInventario.id_categoria != id_categoria,
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="El código de categoría ya existe.")
    for campo, valor in datos.model_dump().items():
        setattr(categoria, campo, valor.strip() if isinstance(valor, str) else valor)
    categoria.codigo = codigo
    return _serializar_categoria(_guardar(db, categoria, "No se pudo actualizar la categoría."))


@router.delete("/catalogos/categorias/{id_categoria}")
def eliminar_categoria(
    id_categoria: UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    categoria = db.query(CategoriaInventario).filter(
        CategoriaInventario.id_categoria == id_categoria
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría de insumos no encontrada.")
    if db.query(ArticuloInventario).filter(ArticuloInventario.categoria == categoria.codigo).first():
        raise HTTPException(status_code=409, detail="La categoría está asignada a insumos y no puede eliminarse.")
    try:
        db.delete(categoria)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo eliminar la categoría.") from error
    return {"eliminada": True, "codigo": categoria.codigo}


@router.get("/catalogos/unidades")
def listar_unidades_medida(
    activas: bool = True,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_LECTURA)),
):
    consulta = db.query(UnidadMedida)
    if activas:
        consulta = consulta.filter(UnidadMedida.activo.is_(True))
    return [_serializar_unidad(unidad) for unidad in consulta.order_by(UnidadMedida.codigo).all()]


@router.post("/catalogos/unidades", status_code=status.HTTP_201_CREATED)
def crear_unidad_medida(
    datos: UnidadMedidaCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    codigo = datos.codigo.strip().upper()
    if db.query(UnidadMedida).filter(UnidadMedida.codigo == codigo).first():
        raise HTTPException(status_code=409, detail="El código de unidad de medida ya existe.")
    unidad = UnidadMedida(
        codigo=codigo,
        nombre=datos.nombre.strip(),
        simbolo=datos.simbolo.strip(),
        activo=datos.activo,
    )
    return _serializar_unidad(_guardar(db, unidad, "No se pudo registrar la unidad de medida."))


@router.put("/catalogos/unidades/{id_unidad}")
def actualizar_unidad_medida(
    id_unidad: UUID,
    datos: UnidadMedidaCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    unidad = db.query(UnidadMedida).filter(UnidadMedida.id_unidad == id_unidad).first()
    if not unidad:
        raise HTTPException(status_code=404, detail="Unidad de medida no encontrada.")
    codigo = datos.codigo.strip().upper()
    duplicado = db.query(UnidadMedida).filter(
        UnidadMedida.codigo == codigo,
        UnidadMedida.id_unidad != id_unidad,
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="El código de unidad de medida ya existe.")
    unidad.codigo = codigo
    unidad.nombre = datos.nombre.strip()
    unidad.simbolo = datos.simbolo.strip()
    unidad.activo = datos.activo
    return _serializar_unidad(_guardar(db, unidad, "No se pudo actualizar la unidad de medida."))


@router.delete("/catalogos/unidades/{id_unidad}")
def desactivar_unidad_medida(
    id_unidad: UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    unidad = db.query(UnidadMedida).filter(UnidadMedida.id_unidad == id_unidad).first()
    if not unidad:
        raise HTTPException(status_code=404, detail="Unidad de medida no encontrada.")
    unidad.activo = False
    return _serializar_unidad(_guardar(db, unidad, "No se pudo desactivar la unidad de medida."))
