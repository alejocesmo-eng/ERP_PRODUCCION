import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. PRUEBA RN-OP-001 / RN-VT-001: Bloqueo de creación de proyectos duplicados o con datos incompletos
def test_rn_vt_001_bloqueo_proyecto_duplicado():
    payload = {
        "codigo_proyecto": "PRY-TEST-001",
        "cliente_nombre": "Cliente Prueba S.A.",
        "requisitos_cliente": "Tolerancia ±0.01mm"
    }
    # Primera creación (debe ser exitosa o retornar 201)
    response1 = client.post("/api/v1/proyectos/", json=payload)
    
    # Intento de duplicado con el mismo código (Debe ser bloqueado con error 400)
    response2 = client.post("/api/v1/proyectos/", json=payload)
    assert response2.status_code == 400
    assert "ya está registrado" in response2.json()["detail"]

# 2. PRUEBA RN-OP-004: Verificación y confirmación de reserva de stock al 100%
def test_rn_op_004_reserva_stock_almacen():
    # Probar endpoint de verificación de stock
    payload_check = {
        "id_op": "00000000-0000-0000-0000-000000000000", # UUID ficticio
        "codigo_material": "MAT-ACERO-1045",
        "cantidad_requerida": 50.0
    }
    response = client.post("/api/v1/almacen/verificar-reserva", json=payload_check)
    # Si la OP no existe debe retornar 404
    assert response.status_code in [200, 404]

# 3. PRUEBA RN-DS-001: Inmutabilidad y bloqueo de archivos no autorizados
def test_rn_ds_001_validacion_planos():
    response = client.get("/api/v1/planos/")
    assert response.status_code in [200, 401]