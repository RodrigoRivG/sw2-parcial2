"""Endpoints de predicción y análisis (spec-prediccion.md 2.8, CE-PRE-02 y CE-PRE-03)."""

import asyncio
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Configuracion
from app.integracion.datos_agricolas import CampaniaPrediccion, Historicos
from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto
from app.integracion.repositorio_versiones import RepositorioVersionesMongo
from app.modelos.cargador import CargadorModelos, EstadoCarga
from tests.conftest import autorizacion, emitir_token
from tests.integration.conftest import registrar_version

ID_CAMPANIA = str(uuid.UUID(int=7))
SUBTOTALES = {
    "INSUMO": "51000.00",
    "MANO_DE_OBRA": "5100.00",
    "MAQUINARIA": "35700.00",
    "OTRO": "10200.00",
}


class DatosGestionFalsos:
    """Reemplaza las consultas a servicio-gestion (el contrato real se prueba en el gateway)."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def campania_para_prediccion(self, id_campania: str) -> CampaniaPrediccion:
        if id_campania != ID_CAMPANIA:
            raise ErrorServicioRemoto(
                "servicio-gestion", TipoErrorRemoto.NO_ENCONTRADO, "CAMPANIA_NO_ENCONTRADA", 404
            )
        return CampaniaPrediccion(
            id=id_campania,
            nombre_cultivo="Soya",
            estado="FINALIZADA",
            superficie_hectareas=Decimal("25.5000"),
            subtotales_por_categoria={k: Decimal(v) for k, v in SUBTOTALES.items()},
            rendimiento_real=Decimal("2850.00"),
        )

    async def historicos(self, filtros: Mapping[str, str], maximo: int) -> Historicos:
        await asyncio.sleep(0.05)  # dos páginas del gateway
        return Historicos(items=self.items[:maximo], total=len(self.items))


def _historico(indice: int) -> dict[str, Any]:
    return {
        "idCampania": str(uuid.UUID(int=1000 + indice)),
        "nombreParcela": f"Lote {indice}",
        "nombreCultivo": ("Soya", "Maíz", "Sorgo")[indice % 3],
        "superficieHectareas": "25.5000",
        "costosPorCategoria": SUBTOTALES,
        "rendimientoPorHectarea": str(2500 + indice % 700),
        "motivosNoDisponible": [],
    }


@pytest.fixture
def datos() -> DatosGestionFalsos:
    return DatosGestionFalsos()


@pytest.fixture
def cliente(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    base_mongo: str,
    prefijo_s3: str,
    entrenados: dict[str, Any],
    datos: DatosGestionFalsos,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    async def publicar_ambos() -> None:
        from tests.integration.conftest import base_mongo_async

        repositorio = RepositorioVersionesMongo(base_mongo_async(base_mongo))
        for nombre in ("rendimiento", "patrones"):
            version = await registrar_version(base_mongo, prefijo_s3, nombre, entrenados[nombre])
            await repositorio.publicar(nombre, version, lambda c, v: {"justificacion": None})

    asyncio.run(publicar_ambos())
    monkeypatch.setattr("app.main.DatosAgricolasGateway", lambda _gateway: datos)
    cliente = crear_cliente(configuracion=configuracion_infra(trabajos_consumidor_activo=False))
    cargador: CargadorModelos = cliente.app.state.cargador_modelos  # type: ignore[attr-defined]
    cliente.portal.call(cargador.revisar)  # type: ignore[union-attr]
    assert cargador.estado("rendimiento") is EstadoCarga.CARGADO
    assert cargador.estado("patrones") is EstadoCarga.CARGADO
    yield cliente


GERENCIA = autorizacion(emitir_token(["gerencia"], sub="ger"))
GRAPHQL = autorizacion(emitir_token(["lectura_ia"], sub="graphql-server"))
TECNICO = autorizacion(emitir_token(["tecnico_campo"]))


def test_estimar_y_listar_predicciones(cliente: TestClient) -> None:
    inicio = time.monotonic()
    respuesta = cliente.post(
        "/api/ia/v1/predicciones", json={"idCampania": ID_CAMPANIA}, headers=GERENCIA
    )
    duracion = time.monotonic() - inicio

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert duracion < 3.0, f"CE-PRE-02: {duracion:.2f} s"
    assert cuerpo["cultivo"] == "SOYA"
    assert cuerpo["costosPorHectarea"] == {
        "INSUMO": "2000.00",
        "MANO_DE_OBRA": "200.00",
        "MAQUINARIA": "1400.00",
        "OTRO": "400.00",
    }
    assert isinstance(cuerpo["rendimientoEstimado"], str)
    assert cuerpo["rendimientoReal"] == "2850.00"
    assert cuerpo["unidad"] == "kg/ha"
    assert cuerpo["versionModelo"] == {"nombre": "rendimiento", "version": 1}
    assert cuerpo["orientativo"] is True
    assert cuerpo["aviso"].startswith("Estimación orientativa")

    for cabeceras in (GERENCIA, GRAPHQL):
        listado = cliente.get(
            f"/api/ia/v1/predicciones?idCampania={ID_CAMPANIA}", headers=cabeceras
        )
        assert listado.status_code == 200
        pagina = listado.json()
        assert pagina["total"] == 1
        assert pagina["items"][0]["id"] == cuerpo["id"]
        assert (pagina["pagina"], pagina["tamanio"]) == (0, 20)


def test_errores_de_prediccion(cliente: TestClient) -> None:
    inexistente = cliente.post(
        "/api/ia/v1/predicciones", json={"idCampania": str(uuid.uuid4())}, headers=GERENCIA
    )
    numero = cliente.post(
        "/api/ia/v1/predicciones",
        json={
            "idCampania": ID_CAMPANIA,
            "costosPorHectarea": {"INSUMO": 1, "MANO_DE_OBRA": "1", "MAQUINARIA": "1", "OTRO": "1"},
        },
        headers=GERENCIA,
    )
    incompleto = cliente.post(
        "/api/ia/v1/predicciones",
        json={"idCampania": ID_CAMPANIA, "costosPorHectarea": {"INSUMO": "1.00"}},
        headers=GERENCIA,
    )

    assert (inexistente.status_code, inexistente.json()["codigo"]) == (
        404,
        "CAMPANIA_NO_ENCONTRADA",
    )
    assert (numero.status_code, numero.json()["codigo"]) == (400, "DATOS_INVALIDOS")
    assert incompleto.status_code == 400
    assert (
        cliente.post(
            "/api/ia/v1/predicciones", json={"idCampania": ID_CAMPANIA}, headers=GRAPHQL
        ).status_code
        == 403
    )
    assert (
        cliente.post(
            "/api/ia/v1/predicciones", json={"idCampania": ID_CAMPANIA}, headers=TECNICO
        ).status_code
        == 403
    )
    assert cliente.get("/api/ia/v1/predicciones", headers=TECNICO).status_code == 403


def test_analizar_mil_campanias_consultar_y_listar(
    cliente: TestClient, datos: DatosGestionFalsos
) -> None:
    datos.items = [_historico(i) for i in range(1000)]

    inicio = time.monotonic()
    respuesta = cliente.post("/api/ia/v1/analisis", json={}, headers=GERENCIA)
    duracion = time.monotonic() - inicio

    assert respuesta.status_code == 201, respuesta.text
    analisis = respuesta.json()
    assert duracion < 5.0, f"CE-PRE-03: {duracion:.2f} s"
    assert analisis["cantidadAnalizadas"] == 1000
    assert sum(g["cantidad"] for g in analisis["grupos"]) == 1000
    assert analisis["versionModelo"]["nombre"] == "patrones"
    assert analisis["orientativo"] is True

    for cabeceras in (GERENCIA, GRAPHQL):
        detalle = cliente.get(f"/api/ia/v1/analisis/{analisis['id']}", headers=cabeceras)
        assert detalle.status_code == 200
        assert detalle.json()["id"] == analisis["id"]
        listado = cliente.get("/api/ia/v1/analisis", headers=cabeceras).json()
        assert listado["total"] == 1
        assert listado["items"][0]["cantidadGrupos"] == len(analisis["grupos"])
        assert "grupos" not in listado["items"][0]


def test_errores_de_analisis(cliente: TestClient, datos: DatosGestionFalsos) -> None:
    sin_datos = cliente.post("/api/ia/v1/analisis", headers=GERENCIA)
    rango = cliente.post(
        "/api/ia/v1/analisis",
        json={"fechaFinalizacionDesde": "2026-12-01", "fechaFinalizacionHasta": "2026-01-01"},
        headers=GERENCIA,
    )
    no_existe = cliente.get(f"/api/ia/v1/analisis/{uuid.uuid4()}", headers=GERENCIA)

    assert (sin_datos.status_code, sin_datos.json()["codigo"]) == (422, "DATOS_INSUFICIENTES")
    assert (rango.status_code, rango.json()["codigo"]) == (400, "DATOS_INVALIDOS")
    assert (no_existe.status_code, no_existe.json()["codigo"]) == (404, "ANALISIS_NO_ENCONTRADO")
    assert cliente.post("/api/ia/v1/analisis", json={}, headers=GRAPHQL).status_code == 403
