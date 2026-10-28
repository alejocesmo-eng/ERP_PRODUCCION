import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.maestros import (
    CategoriaCreate,
    EstructuraFinancieraCreate,
    SocioNegocioCreate,
    UnidadMedidaCreate,
    TrabajadorCreate,
    actualizar_elemento_financiero,
    crear_categoria,
    crear_elemento_financiero,
    crear_socio,
    crear_trabajador,
    crear_unidad_medida,
    desactivar_socio,
    listar_catalogos,
    listar_estructura_financiera,
    listar_personal,
    listar_socios,
)
from app.db.database import Base
from app.db.models import (
    ArticuloInventario,
    CategoriaInventario,
    EstructuraFinanciera,
    Rol,
    SocioNegocio,
    TrabajadorUsuario,
    UnidadMedida,
    Usuario,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tablas = [
        Rol.__table__,
        Usuario.__table__,
        SocioNegocio.__table__,
        TrabajadorUsuario.__table__,
        EstructuraFinanciera.__table__,
        UnidadMedida.__table__,
        CategoriaInventario.__table__,
        ArticuloInventario.__table__,
    ]
    Base.metadata.create_all(engine, tables=tablas)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tablas)
        engine.dispose()


def test_crear_editar_listar_y_desactivar_socio(db):
    socio = crear_socio(
        SocioNegocioCreate(
            nit_cedula="900123456",
            razon_social="Proveedor y cliente",
            es_cliente=True,
            es_proveedor=True,
            email="CONTACTO@EMPRESA.COM",
            cuenta_contable_por_cobrar="130505",
            cuenta_contable_por_pagar="220505",
        ),
        db=db,
        usuario={"rol": "ADMIN"},
    )

    assert socio["email"] == "contacto@empresa.com"
    assert socio["es_cliente"] and socio["es_proveedor"]
    assert len(listar_socios(db=db, usuario={"rol": "ADMIN"})) == 1

    socio_desactivado = desactivar_socio(
        socio["id_socio"],
        db=db,
        usuario={"rol": "ADMIN"},
    )

    assert socio_desactivado["estado_activo"] is False
    assert listar_socios(db=db, usuario={"rol": "ADMIN"}) == []
    assert len(listar_socios(activos=False, db=db, usuario={"rol": "ADMIN"})) == 1


def test_socio_requiere_cuentas_segun_su_tipo():
    with pytest.raises(ValueError, match="cuenta por cobrar"):
        SocioNegocioCreate(
            nit_cedula="900123456",
            razon_social="Cliente",
            es_cliente=True,
        )


def test_crear_listar_y_editar_estructura_financiera(db):
    cuenta = crear_elemento_financiero(
        EstructuraFinancieraCreate(
            tipo="CUENTA_CONTABLE",
            codigo="143505",
            nombre="Inventarios",
        ),
        db=db,
        usuario={"rol": "ADMIN"},
    )
    centro = crear_elemento_financiero(
        EstructuraFinancieraCreate(
            tipo="CENTRO_COSTO",
            codigo="CC-100-CNC",
            nombre="Centro CNC",
        ),
        db=db,
        usuario={"rol": "ADMIN"},
    )

    actualizado = actualizar_elemento_financiero(
        cuenta["id_elemento"],
        EstructuraFinancieraCreate(
            tipo="CUENTA_CONTABLE",
            codigo="143505",
            nombre="Inventarios Planta",
        ),
        db=db,
        usuario={"rol": "ADMIN"},
    )

    assert actualizado["nombre"] == "Inventarios Planta"
    assert len(listar_estructura_financiera(tipo="CENTRO_COSTO", db=db, usuario={"rol": "ADMIN"})) == 1
    assert centro["codigo"] == "CC-100-CNC"


def test_crear_trabajador_y_unidad_de_medida(db):
    rol = Rol(id_rol="PRODUCCION", nombre_rol="Producción")
    db.add(rol)
    db.flush()
    usuario_sistema = Usuario(
        email="operario@sgi.test",
        password_hash="hash-prueba",
        nombre_completo="Operario de prueba",
        id_rol="PRODUCCION",
    )
    db.add(usuario_sistema)
    db.commit()
    trabajador = crear_trabajador(
        TrabajadorCreate(
            cedula="12345678",
            nombre_completo="Operario de prueba",
            area="PRODUCCION",
            cargo="Operario CNC",
            tarifa_hora_mano_obra=25000,
            id_usuario_sistema=usuario_sistema.id_usuario,
        ),
        db=db,
        usuario={"rol": "ADMIN"},
    )
    crear_unidad_medida(
        UnidadMedidaCreate(codigo="KG", nombre="Kilogramo", simbolo="kg"),
        db=db,
        usuario={"rol": "ADMIN"},
    )
    crear_categoria(
        CategoriaCreate(codigo="MATERIA_PRIMA", nombre="Materia Prima"),
        db=db,
        usuario={"rol": "ADMIN"},
    )

    assert trabajador["area"] == "PRODUCCION"
    personal = listar_personal(db=db, usuario={"rol": "ADMIN"})
    assert len(personal) == 1
    assert personal[0]["usuario"] == "operario@sgi.test"
    catalogos = listar_catalogos(db=db, usuario={"rol": "ADMIN"})
    assert catalogos["unidades_medida"][0]["simbolo"] == "kg"
    assert catalogos["categorias"][0]["codigo"] == "MATERIA_PRIMA"


def test_codigos_maestros_duplicados_se_rechazan(db):
    datos = SocioNegocioCreate(
        nit_cedula="900123456",
        razon_social="Cliente Uno",
        es_cliente=True,
        cuenta_contable_por_cobrar="130505",
    )
    crear_socio(datos, db=db, usuario={"rol": "ADMIN"})
    with pytest.raises(HTTPException) as error:
        crear_socio(datos, db=db, usuario={"rol": "ADMIN"})
    assert error.value.status_code == 409
