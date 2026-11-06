"""Herramientas de servicio-gestion (spec-agentes.md, Historia 4; 2.3)."""

from typing import Any

import httpx
import pytest

from tests.unit.mcp_server.conftest import Servicios, conectar, ejemplo, error, llamar

G = "/api/gestion/v1"
ID = "00000001-0000-4000-8000-000000000000"


def _pagina(items: list[dict[str, Any]], total: int) -> dict[str, Any]:
    return {"items": items, "pagina": 0, "tamanio": len(items), "total": total}


async def test_listar_parcelas_reduce_campos_y_recorta_textos() -> None:
    servicios = Servicios()
    parcela = {**ejemplo("parcela"), "descripcion": "x" * 300}
    servicios.json(f"{G}/parcelas", _pagina([parcela], 1))

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "listar_parcelas", {"nombre": "Norte"})

    assert servicios.parametros() == {"nombre": "Norte", "pagina": "0", "tamanio": "50"}
    assert servicios.solicitudes[0].headers["Authorization"] == "Bearer token-servicio"
    (item,) = resultado["items"]
    assert set(item) == {"id", "nombre", "superficieHectareas", "ubicacion", "descripcion"}
    assert item["superficieHectareas"] == "25.5000"  # los decimales siguen como texto
    assert len(item["descripcion"]) == 200
    assert (resultado["total"], resultado["truncado"]) == (1, False)


async def test_listar_cultivos() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/cultivos", _pagina([ejemplo("cultivo")], 1))

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "listar_cultivos")

    assert resultado["items"][0]["nombre"] == "Soya"
    assert "version" not in resultado["items"][0]


async def test_listar_campanias_recorta_a_50_y_marca_truncado() -> None:
    servicios = Servicios()
    campania = {k: v for k, v in ejemplo("campania").items() if k != "resumen"}
    servicios.json(f"{G}/campanias", _pagina([campania] * 50, 230))

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "listar_campanias", {"estado": "FINALIZADA"})

    assert len(servicios.solicitudes) == 1
    assert servicios.parametros() == {"estado": "FINALIZADA", "pagina": "0", "tamanio": "50"}
    assert len(resultado["items"]) == 50
    assert (resultado["total"], resultado["truncado"]) == (230, True)


async def test_listar_campanias_con_maximo_pagina_el_servicio() -> None:
    servicios = Servicios()
    campania = {"id": ID, "nombre": "C"}
    servicios.rutas[f"{G}/campanias"] = lambda s: httpx.Response(
        200, json=_pagina([campania] * 100, 230)
    )

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "listar_campanias", {"maximo": 150})

    assert [s.url.params["pagina"] for s in servicios.solicitudes] == ["0", "1"]
    assert {s.url.params["tamanio"] for s in servicios.solicitudes} == {"100"}
    assert len(resultado["items"]) == 150
    assert resultado["truncado"] is True


async def test_obtener_campania_con_resumen() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/campanias/{ID}", ejemplo("campania"))

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "obtener_campania", {"idCampania": ID})

    assert resultado["resumen"] == {"costoTotal": "0.00", "cantidadCostos": 0, "produccion": None}
    assert "version" not in resultado


async def test_obtener_costos_con_totales() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/campanias/{ID}/costos", {**ejemplo("costos"), "total": 1})

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "obtener_costos_campania", {"idCampania": ID})

    assert servicios.parametros() == {"pagina": "0", "tamanio": "50"}
    assert resultado["costoTotal"] == "2320.50"
    assert resultado["subtotalesPorCategoria"]["MANO_DE_OBRA"] == "1500.00"
    assert resultado["items"][0] == {
        "categoria": "MANO_DE_OBRA",
        "monto": "1500.00",
        "fecha": "2026-12-10",
        "descripcion": "Cosecha manual",
        "origen": "MANUAL",
    }
    assert (resultado["total"], resultado["truncado"]) == (1, False)


async def test_obtener_indicadores() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/campanias/{ID}/indicadores", ejemplo("indicadores"))

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "obtener_indicadores_campania", {"idCampania": ID})

    assert resultado["rendimientoPorHectarea"] == "3000.00"


async def test_listar_historicos_ordena_y_recorta() -> None:
    servicios = Servicios()
    base = ejemplo("historico")
    historicos = [{**base, "costoPorHectarea": str(1000 + i)} for i in range(120)]
    historicos[7]["costoPorHectarea"] = None  # sin indicador: al final
    servicios.json(f"{G}/campanias/historicos", _pagina(historicos, 120))

    async with conectar(servicios) as cliente:
        resultado = await llamar(
            cliente,
            "listar_historicos",
            {"ordenarPor": "costoPorHectarea", "fechaFinalizacionDesde": "2026-01-01"},
        )

    assert servicios.parametros() == {"fechaFinalizacionDesde": "2026-01-01", "tamanio": "500"}
    costos = [h["costoPorHectarea"] for h in resultado["items"]]
    assert costos[:2] == ["1119", "1118"] and len(costos) == 50
    assert (resultado["total"], resultado["truncado"]) == (120, True)
    assert resultado["items"][0]["nombreCultivo"] == "Soya"
    assert "idParcela" not in resultado["items"][0]


async def test_listar_historicos_por_fecha_de_finalizacion_por_defecto() -> None:
    servicios = Servicios()
    viejo = {**ejemplo("historico"), "fechaFinalizacion": "2025-01-01T00:00:00Z"}
    nuevo = {**ejemplo("historico"), "fechaFinalizacion": "2027-03-28T18:00:00Z"}
    servicios.json(f"{G}/campanias/historicos", _pagina([viejo, nuevo], 2))

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "listar_historicos")

    assert resultado["items"][0]["fechaFinalizacion"] == "2027-03-28T18:00:00Z"
    assert resultado["truncado"] is False


@pytest.mark.parametrize(
    ("herramienta", "argumentos"),
    [
        ("obtener_campania", {"idCampania": "no-es-uuid"}),
        ("listar_campanias", {"estado": "CANCELADA"}),
        ("listar_campanias", {"maximo": 501}),
        ("listar_historicos", {"fechaFinalizacionDesde": "02/11/2026"}),
    ],
)
async def test_parametros_invalidos_no_llaman_al_servicio(
    herramienta: str, argumentos: dict[str, Any]
) -> None:
    servicios = Servicios()

    async with conectar(servicios) as cliente:
        await error(cliente, herramienta, argumentos)

    assert servicios.solicitudes == []


async def test_404_del_servicio_es_un_error_legible() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/campanias/{ID}", {"codigo": "CAMPANIA_NO_ENCONTRADA"}, estado=404)

    async with conectar(servicios) as cliente:
        texto = await error(cliente, "obtener_campania", {"idCampania": ID})

    assert "CAMPANIA_NO_ENCONTRADA: la campaña no existe" in texto


async def test_servicio_caido_es_un_error_de_herramienta() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/cultivos", {"codigo": "SERVICIO_NO_DISPONIBLE"}, estado=503)

    async with conectar(servicios) as cliente:
        texto = await error(cliente, "listar_cultivos")

    assert "servicio-gestion no disponible" in texto


async def test_consulta_rechazada() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/parcelas", {"codigo": "DATOS_INVALIDOS"}, estado=400)

    async with conectar(servicios) as cliente:
        texto = await error(cliente, "listar_parcelas")

    assert "DATOS_INVALIDOS: servicio-gestion rechazó la consulta" in texto
