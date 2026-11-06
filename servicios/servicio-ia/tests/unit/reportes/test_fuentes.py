"""Obtención de cada fuente por MCP con los servicios simulados (spec-reportes.md 2.5)."""

from typing import Any

import httpx
import pytest

from app.reportes.catalogo import FUENTES
from app.reportes.fuentes import DatosFuente, ErrorFuente, Nombres, obtener
from app.reportes.plan import TablaPlan
from tests.unit.mcp_server.conftest import Servicios, conectar, ejemplo

G, INV, OP = "/api/gestion/v1", "/api/inventario/v1", "/api/operaciones/v1"
P1, P2 = (
    "00000000-0000-4000-8000-0000000000p1".replace("p", "a"),
    "00000000-0000-4000-8000-0000000000b2",
)
C1, CU1 = "00000000-0000-4000-8000-0000000000c1", "00000000-0000-4000-8000-0000000000d1"
I1 = "00000000-0000-4000-8000-0000000000e1"


def _pagina(items: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"items": items, "pagina": 0, "tamanio": 500, "total": len(items), **extra}


def _servicios() -> Servicios:
    servicios = Servicios()
    servicios.json(
        f"{G}/parcelas",
        _pagina(
            [
                {**ejemplo("parcela"), "id": P1, "nombre": "Lote Norte"},
                {**ejemplo("parcela"), "id": P2, "nombre": "Lote Sur"},
            ]
        ),
    )
    servicios.json(f"{G}/cultivos", _pagina([{**ejemplo("cultivo"), "id": CU1}]))
    servicios.json(
        f"{G}/campanias",
        _pagina([{**ejemplo("campania"), "id": C1, "idParcela": P1, "idCultivo": CU1}]),
    )
    servicios.json(
        f"{INV}/estado-inventario",
        _pagina(
            [{**ejemplo("estado_inventario")["items"][0], "idInsumo": I1}],
            resumen={"totalInsumos": 1},
        ),
    )
    return servicios


async def _obtener(
    servicios: Servicios, tabla: dict[str, Any], id_campania: str | None = None
) -> DatosFuente:
    fallo: Exception | None = None
    async with conectar(servicios) as sesion:
        try:
            datos = await obtener(
                sesion, TablaPlan.model_validate(tabla), id_campania, Nombres(sesion)
            )
        except ErrorFuente as error:  # dentro del Client saldría en un ExceptionGroup
            fallo = error
    if fallo is not None:
        raise fallo
    return datos


def _campos_del_catalogo(fuente: str, fila: dict[str, Any]) -> None:
    assert set(FUENTES[fuente].nombres) <= set(fila), set(FUENTES[fuente].nombres) - set(fila)


async def test_parcelas_y_cultivos_con_maximo_500() -> None:
    servicios = _servicios()

    parcelas = await _obtener(servicios, {"fuente": "PARCELAS"})
    cultivos = await _obtener(servicios, {"fuente": "CULTIVOS"})

    assert [p["nombre"] for p in parcelas.filas] == ["Lote Norte", "Lote Sur"]
    assert parcelas.total_origen == 2 and not parcelas.recortado
    _campos_del_catalogo("PARCELAS", parcelas.filas[0])
    _campos_del_catalogo("CULTIVOS", cultivos.filas[0])
    assert {s.url.params["tamanio"] for s in servicios.solicitudes} == {
        "100"
    }  # páginas de 100 hasta 500


async def test_campanias_con_nombres_por_id_y_estado_pasado_al_servicio() -> None:
    servicios = _servicios()

    datos = await _obtener(
        servicios,
        {
            "fuente": "CAMPANIAS",
            "filtros": [{"campo": "estado", "operador": "igual", "valor": "en curso"}],
        },
    )

    (fila,) = datos.filas
    assert (fila["nombreParcela"], fila["nombreCultivo"]) == ("Lote Norte", "Soya")
    assert fila["superficieHectareas"] == "25.5000"
    _campos_del_catalogo("CAMPANIAS", fila)
    campanias = [s for s in servicios.solicitudes if s.url.path == f"{G}/campanias"]
    assert campanias[0].url.params["estado"] == "EN_CURSO"


async def test_finalizadas_con_costos_por_categoria_tal_cual() -> None:
    servicios = _servicios()
    servicios.json(
        f"{G}/campanias/historicos", _pagina([{**ejemplo("historico"), "idCampania": C1}])
    )

    (fila,) = (await _obtener(servicios, {"fuente": "CAMPANIAS_FINALIZADAS"})).filas

    assert fila["nombreCampania"] == "Soya verano 2026-2027"
    assert (
        fila["costoInsumo"],
        fila["costoManoDeObra"],
        fila["costoMaquinaria"],
        fila["costoOtro"],
    ) == ("20000.00", "12000.00", "6250.00", "0.00")
    assert fila["costoPorHectarea"] == "1500.00"
    _campos_del_catalogo("CAMPANIAS_FINALIZADAS", fila)


async def test_fuentes_de_una_campania() -> None:
    servicios = _servicios()
    servicios.json(f"{G}/campanias/{C1}/costos", {**ejemplo("costos"), "total": 1})
    servicios.json(f"{G}/campanias/{C1}", {**ejemplo("campania"), "id": C1})
    servicios.json(f"{G}/campanias/{C1}/indicadores", ejemplo("indicadores"))

    costos = await _obtener(servicios, {"fuente": "COSTOS_CAMPANIA", "campania": C1}, C1)
    subtotales = await _obtener(servicios, {"fuente": "SUBTOTALES_CAMPANIA", "campania": C1}, C1)
    indicadores = await _obtener(servicios, {"fuente": "INDICADORES_CAMPANIA", "campania": C1}, C1)

    assert costos.filas[0]["monto"] == "1500.00"
    assert {"categoria": "INSUMO", "subtotal": "820.50"} in subtotales.filas and len(
        subtotales.filas
    ) == 4
    (fila,) = indicadores.filas
    assert (fila["nombre"], fila["estado"], fila["rendimientoPorHectarea"], fila["definitivo"]) == (
        "Soya verano 2026-2027",
        "EN_CURSO",
        "3000.00",
        True,
    )
    for datos, fuente in (
        (costos, "COSTOS_CAMPANIA"),
        (subtotales, "SUBTOTALES_CAMPANIA"),
        (indicadores, "INDICADORES_CAMPANIA"),
    ):
        _campos_del_catalogo(fuente, datos.filas[0])


@pytest.mark.parametrize(
    ("filtros", "parametros"),
    [
        ([{"campo": "stockBajo", "operador": "igual", "valor": True}], {"soloStockBajo": "true"}),
        (
            [{"campo": "categoria", "operador": "igual", "valor": "fitosanitario"}],
            {"categoria": "FITOSANITARIO"},
        ),
        (
            [{"campo": "stockBajo", "operador": "igual", "valor": False}],
            {},
        ),  # no se pasa: el servicio solo filtra los bajos
    ],
)
async def test_inventario_pasa_los_filtros_seguros(
    filtros: list[dict[str, Any]], parametros: dict[str, str]
) -> None:
    servicios = _servicios()

    datos = await _obtener(servicios, {"fuente": "INVENTARIO", "filtros": filtros})

    enviados = servicios.parametros()
    assert {k: enviados[k] for k in ("soloStockBajo", "categoria") if k in enviados} == parametros
    _campos_del_catalogo("INVENTARIO", datos.filas[0])


async def test_labores_recorren_cada_estado_y_unen_los_insumos_en_texto() -> None:
    servicios = _servicios()
    labor = {
        **ejemplo("labor"),
        "idCampania": C1,
        "idParcela": P2,
        "insumos": [
            {"idInsumo": I1, "cantidad": "100.000"},
            {"idInsumo": "otro", "cantidad": "2.500"},
        ],
    }

    def responder(solicitud: httpx.Request) -> httpx.Response:
        items = [labor] if solicitud.url.params["estado"] == "PENDIENTE" else []
        return httpx.Response(200, json={"items": items, "siguienteCursor": None})

    servicios.rutas[f"{OP}/labores"] = responder

    datos = await _obtener(servicios, {"fuente": "LABORES"})
    filtrada = await _obtener(
        servicios,
        {
            "fuente": "LABORES",
            "filtros": [{"campo": "estado", "operador": "igual", "valor": "CONFIRMADA"}],
        },
    )

    estados = [
        s.url.params["estado"] for s in servicios.solicitudes if s.url.path == f"{OP}/labores"
    ]
    assert estados == [
        "PROGRAMADA",
        "PENDIENTE",
        "CONFIRMADA",
        "RECHAZADA",
        "PENDIENTE_REVISION",
        "CONFIRMADA",
    ]
    (fila,) = datos.filas
    assert (fila["nombreCampania"], fila["nombreParcela"], fila["responsable"]) == (
        "Soya verano 2026-2027",
        "Lote Sur",
        "Ana Quispe",
    )
    assert fila["insumos"] == "Glifosato: 100.000 LITRO; Insumo desconocido: 2.500"
    _campos_del_catalogo("LABORES", fila)
    assert filtrada.filas == []


async def test_incidencias_recorren_cada_parcela() -> None:
    servicios = _servicios()
    incidencia = {**ejemplo("incidencia"), "idParcela": P1, "idCampania": C1}

    def responder(solicitud: httpx.Request) -> httpx.Response:
        items = [incidencia] if solicitud.url.params["idParcela"] == P1 else []
        return httpx.Response(200, json={"items": items, "siguienteCursor": None})

    servicios.rutas[f"{OP}/incidencias"] = responder

    datos = await _obtener(
        servicios,
        {
            "fuente": "INCIDENCIAS",
            "filtros": [{"campo": "tipo", "operador": "igual", "valor": "plaga"}],
        },
    )

    llamadas = [s.url.params for s in servicios.solicitudes if s.url.path == f"{OP}/incidencias"]
    assert [(p["idParcela"], p["tipo"]) for p in llamadas] == [(P1, "PLAGA"), (P2, "PLAGA")]
    (fila,) = datos.filas
    assert (fila["nombreParcela"], fila["clasificacion"], fila["confianzaClasificacion"]) == (
        "Lote Norte",
        "roya",
        "0.8731",
    )
    _campos_del_catalogo("INCIDENCIAS", fila)


async def test_nombres_se_piden_una_sola_vez_por_reporte() -> None:
    servicios = _servicios()

    async with conectar(servicios) as sesion:
        nombres = Nombres(sesion)
        await nombres.parcelas()
        await nombres.parcelas()

    assert len([s for s in servicios.solicitudes if s.url.path == f"{G}/parcelas"]) == 1


async def test_herramienta_que_falla_es_error_de_fuente() -> None:
    servicios = Servicios()
    servicios.json(f"{G}/parcelas", {"codigo": "X"}, estado=503)

    with pytest.raises(ErrorFuente, match="servicio-gestion no disponible"):
        await _obtener(servicios, {"fuente": "PARCELAS"})
