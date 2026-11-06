"""Herramientas de servicio-inventario (spec-agentes.md, Historia 4; 2.3)."""

from tests.unit.mcp_server.conftest import Servicios, conectar, ejemplo, error, llamar

INV = "/api/inventario/v1"
ID = "00000001-0000-4000-8000-000000000000"


async def test_estado_de_inventario_con_resumen_y_filtro() -> None:
    servicios = Servicios()
    servicios.json(f"{INV}/estado-inventario", {**ejemplo("estado_inventario"), "total": 1})

    async with conectar(servicios) as cliente:
        resultado = await llamar(
            cliente,
            "consultar_estado_inventario",
            {"soloStockBajo": True, "categoria": "FITOSANITARIO"},
        )

    assert servicios.parametros() == {
        "soloStockBajo": "true",
        "categoria": "FITOSANITARIO",
        "pagina": "0",
        "tamanio": "50",
    }
    assert resultado["resumen"] == {"totalInsumos": 3, "totalStockBajo": 2}
    assert resultado["items"][0]["stock"] == "20.000"
    assert (resultado["total"], resultado["truncado"]) == (1, False)
    assert len(servicios.solicitudes) == 1


async def test_obtener_insumo() -> None:
    servicios = Servicios()
    servicios.json(f"{INV}/insumos/{ID}", ejemplo("insumo"))

    async with conectar(servicios) as cliente:
        resultado = await llamar(cliente, "obtener_insumo", {"idInsumo": ID})

    assert resultado["costoUnitario"] == "4.8500"
    assert "version" not in resultado and "fechaCreacion" not in resultado


async def test_insumo_inexistente() -> None:
    servicios = Servicios()
    servicios.json(f"{INV}/insumos/{ID}", {"codigo": "INSUMO_NO_ENCONTRADO"}, estado=404)

    async with conectar(servicios) as cliente:
        texto = await error(cliente, "obtener_insumo", {"idInsumo": ID})

    assert "INSUMO_NO_ENCONTRADO: el insumo no existe" in texto


async def test_servicio_caido() -> None:
    servicios = Servicios()  # sin rutas: el gateway responde RUTA_NO_ENCONTRADA

    async with conectar(servicios) as cliente:
        texto = await error(cliente, "consultar_estado_inventario")

    assert "servicio-inventario no disponible" in texto


async def test_acepta_valores_fijos_en_minusculas() -> None:
    servicios = Servicios()
    servicios.json(f"{INV}/estado-inventario", {**ejemplo("estado_inventario"), "total": 1})

    async with conectar(servicios) as cliente:
        await llamar(cliente, "consultar_estado_inventario", {"categoria": "fitosanitario"})

    assert servicios.parametros()["categoria"] == "FITOSANITARIO"
