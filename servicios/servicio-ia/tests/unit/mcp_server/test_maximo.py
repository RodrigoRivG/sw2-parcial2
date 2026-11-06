"""`maximo` en las herramientas que usan los reportes (spec-reportes.md 2.3)."""

from typing import Any

import httpx

from app.agentes.herramientas import a_ollama
from tests.unit.mcp_server.conftest import Servicios, conectar, ejemplo, llamar

G = "/api/gestion/v1"
ID = "00000001-0000-4000-8000-000000000000"


def _paginado(item: dict[str, Any], total: int, **extra: Any) -> Any:
    def responder(solicitud: httpx.Request) -> httpx.Response:
        tamanio = int(solicitud.url.params["tamanio"])
        pagina = int(solicitud.url.params["pagina"])
        cantidad = max(0, min(tamanio, total - pagina * tamanio))
        cuerpo = {"items": [item] * cantidad, "pagina": pagina, "tamanio": tamanio, "total": total}
        return httpx.Response(200, json={**cuerpo, **extra})

    return responder


async def test_parcelas_cultivos_y_costos_paginan_hasta_el_maximo() -> None:
    servicios = Servicios()
    servicios.rutas[f"{G}/parcelas"] = _paginado(ejemplo("parcela"), 230)
    servicios.rutas[f"{G}/cultivos"] = _paginado(ejemplo("cultivo"), 120)
    servicios.rutas[f"{G}/campanias/{ID}/costos"] = _paginado(
        ejemplo("costos")["items"][0],
        130,
        costoTotal="99.00",
        subtotalesPorCategoria={"OTRO": "99.00"},
    )

    async with conectar(servicios) as cliente:
        parcelas = await llamar(cliente, "listar_parcelas", {"maximo": 500})
        cultivos = await llamar(cliente, "listar_cultivos", {"maximo": 500})
        costos = await llamar(cliente, "obtener_costos_campania", {"idCampania": ID, "maximo": 500})

    assert (len(parcelas["items"]), parcelas["truncado"]) == (230, False)
    assert (len(cultivos["items"]), cultivos["truncado"]) == (120, False)
    assert (len(costos["items"]), costos["costoTotal"]) == (130, "99.00")
    rutas = [(s.url.path.rsplit("/", 1)[-1], s.url.params["pagina"]) for s in servicios.solicitudes]
    assert rutas.count(("parcelas", "2")) == 1 and rutas.count(("costos", "1")) == 1


async def test_maximo_oculto_para_los_agentes_conversacionales() -> None:
    async with conectar(Servicios()) as cliente:
        herramientas = (await cliente.list_tools()).tools

    for herramienta in herramientas:
        parametros = a_ollama(herramienta)["function"]["parameters"]
        assert "maximo" not in parametros.get("properties", {})
    con_maximo = {h.name for h in herramientas if "maximo" in h.input_schema.get("properties", {})}
    assert {"listar_parcelas", "listar_cultivos", "obtener_costos_campania"} <= con_maximo
