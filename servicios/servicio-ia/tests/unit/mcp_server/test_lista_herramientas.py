"""`tools/list` (spec-agentes.md, Historia 4, escenario 1)."""

from app.mcp_server.herramientas import NOMBRES
from tests.unit.mcp_server.conftest import Servicios, conectar


async def test_once_herramientas_de_solo_lectura_con_descripcion_y_esquema() -> None:
    async with conectar(Servicios()) as cliente:
        herramientas = {h.name: h for h in (await cliente.list_tools()).tools}

    assert set(herramientas) == set(NOMBRES) and len(NOMBRES) == 11
    for herramienta in herramientas.values():
        assert herramienta.description and herramienta.description[0].isupper()
        assert herramienta.annotations is not None
        assert herramienta.annotations.read_only_hint is True
        assert herramienta.input_schema["type"] == "object"

    labores = herramientas["listar_labores"].input_schema["properties"]
    assert set(labores) == {"idCampania", "estado", "fechaDesde", "fechaHasta", "maximo"}
    assert labores["maximo"]["maximum"] == 500
    campania = herramientas["obtener_campania"].input_schema
    assert campania["required"] == ["idCampania"]
    assert campania["properties"]["idCampania"]["format"] == "uuid"
    historicos = herramientas["listar_historicos"].input_schema["properties"]
    assert historicos["ordenarPor"]["enum"] == [
        "costoPorHectarea",
        "rendimientoPorHectarea",
        "fechaFinalizacion",
    ]
