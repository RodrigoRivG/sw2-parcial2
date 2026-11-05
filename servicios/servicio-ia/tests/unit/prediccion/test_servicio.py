"""ServicioPrediccion: Historias 1 y 2 con dobles (spec-prediccion.md)."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest

from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import UsuarioAutenticado
from app.integracion.datos_agricolas import CampaniaPrediccion, Historicos
from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto
from app.ml.entrenar import (
    Entrenado,
    armar_documento,
    entrenar_patrones,
    entrenar_rendimiento,
    leer_referencia,
)
from app.modelos.cargador import ModeloCargado
from app.modelos.esquemas import VersionModelo
from app.prediccion.esquemas import CostosPorHectarea, SolicitudAnalisis
from app.prediccion.servicio import ServicioPrediccion

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "referencia_pequena.csv"
AHORA = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
GERENCIA = UsuarioAutenticado(id="ger", nombre="Gerencia", roles=frozenset({"gerencia"}))
SUBTOTALES = {
    "INSUMO": "51000.00",
    "MANO_DE_OBRA": "5100.00",
    "MAQUINARIA": "35700.00",
    "OTRO": "10200.00",
}


def _cargado(nombre: str, entrenado: Entrenado, version: int = 1) -> ModeloCargado:
    filas = leer_referencia(FIXTURE)
    documento = armar_documento(nombre, entrenado, filas, f"modelos/{nombre}/x", "0" * 64, 7, AHORA)
    documento.update(version=version, estado="VIGENTE")
    return ModeloCargado(VersionModelo.desde_documento(documento), entrenado.artefacto)


@pytest.fixture(scope="module")
def modelos() -> dict[str, ModeloCargado]:
    filas = leer_referencia(FIXTURE)
    return {
        "rendimiento": _cargado("rendimiento", entrenar_rendimiento(filas, 7)),
        "patrones": _cargado("patrones", entrenar_patrones(filas, 7), version=3),
    }


class CargadorFalso:
    def __init__(self, modelos: dict[str, ModeloCargado]) -> None:
        self.modelos = modelos

    def obtener(self, nombre: str) -> ModeloCargado:
        if nombre not in self.modelos:
            raise ErrorAplicacion(503, "MODELO_NO_DISPONIBLE")
        return self.modelos[nombre]


class DatosFalsos:
    def __init__(self) -> None:
        self.campania = CampaniaPrediccion(
            id="c1",
            nombre_cultivo="Soya",
            estado="EN_CURSO",
            superficie_hectareas=Decimal("25.5000"),
            subtotales_por_categoria={k: Decimal(v) for k, v in SUBTOTALES.items()},
            rendimiento_real=None,
        )
        self.items: list[dict[str, Any]] = []
        self.total: int | None = None
        self.error: Exception | None = None
        self.filtros: Mapping[str, str] | None = None

    async def campania_para_prediccion(self, id_campania: str) -> CampaniaPrediccion:
        if self.error:
            raise self.error
        return self.campania

    async def historicos(self, filtros: Mapping[str, str], maximo: int) -> Historicos:
        self.filtros = filtros
        return Historicos(items=self.items[:maximo], total=self.total or len(self.items))


class ResultadosMemoria:
    def __init__(self) -> None:
        self.guardados: dict[str, list[dict[str, Any]]] = {}

    async def guardar(self, coleccion: str, documento: dict[str, Any]) -> None:
        self.guardados.setdefault(coleccion, []).append(documento)

    async def obtener(self, coleccion: str, id_documento: str) -> dict[str, Any] | None:
        return next((d for d in self.guardados.get(coleccion, []) if d["id"] == id_documento), None)

    async def listar(self, coleccion: str, pagina: int, tamanio: int, igual_a: Any = None) -> Any:
        documentos = [
            d
            for d in self.guardados.get(coleccion, [])
            if igual_a is None or d.get(igual_a[0]) == igual_a[1]
        ]
        return documentos[pagina * tamanio : (pagina + 1) * tamanio], len(documentos)


@pytest.fixture
def datos() -> DatosFalsos:
    return DatosFalsos()


@pytest.fixture
def resultados() -> ResultadosMemoria:
    return ResultadosMemoria()


@pytest.fixture
def servicio(
    modelos: dict[str, ModeloCargado], datos: DatosFalsos, resultados: ResultadosMemoria
) -> ServicioPrediccion:
    return ServicioPrediccion(datos, CargadorFalso(modelos), resultados, reloj=lambda: AHORA)  # type: ignore[arg-type]


# --- Historia 1 ------------------------------------------------------------------------------


async def test_estimar_con_costos_registrados(
    servicio: ServicioPrediccion, resultados: ResultadosMemoria
) -> None:
    prediccion = await servicio.estimar("c1", None, GERENCIA)

    assert prediccion.cultivo == "SOYA"
    assert prediccion.origen_costos.value == "REGISTRADOS"
    assert prediccion.costos_por_hectarea == {
        "INSUMO": Decimal("2000.00"),
        "MANO_DE_OBRA": Decimal("200.00"),
        "MAQUINARIA": Decimal("1400.00"),
        "OTRO": Decimal("400.00"),
    }
    assert (
        prediccion.intervalo.minimo
        <= prediccion.rendimiento_estimado
        <= prediccion.intervalo.maximo
    )
    assert prediccion.produccion_estimada == (
        prediccion.rendimiento_estimado * Decimal("25.5")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert prediccion.version_modelo.version == 1
    assert prediccion.orientativo is True
    (guardado,) = resultados.guardados["predicciones"]
    assert guardado["idSolicitante"] == "ger"
    assert guardado["fecha"] == AHORA
    assert guardado["rendimientoEstimado"] == format(prediccion.rendimiento_estimado, "f")


async def test_finalizada_incluye_el_rendimiento_real(
    servicio: ServicioPrediccion, datos: DatosFalsos
) -> None:
    datos.campania = CampaniaPrediccion(
        **{
            **datos.campania.__dict__,
            "estado": "FINALIZADA",
            "rendimiento_real": Decimal("2850.00"),
        }
    )

    prediccion = await servicio.estimar("c1", None, GERENCIA)

    assert prediccion.rendimiento_real == Decimal("2850.00")


async def test_costos_simulados(servicio: ServicioPrediccion, datos: DatosFalsos) -> None:
    datos.campania = CampaniaPrediccion(
        **{**datos.campania.__dict__, "estado": "PLANIFICADA", "subtotales_por_categoria": {}}
    )
    simulados = CostosPorHectarea.model_validate(
        {"INSUMO": "2100.00", "MANO_DE_OBRA": "350.00", "MAQUINARIA": "900.00", "OTRO": "150.00"}
    )

    prediccion = await servicio.estimar("c1", simulados, GERENCIA)

    assert prediccion.origen_costos.value == "SIMULADOS"
    assert prediccion.costos_por_hectarea["INSUMO"] == Decimal("2100.00")


async def test_sin_costos_es_datos_insuficientes(
    servicio: ServicioPrediccion, datos: DatosFalsos
) -> None:
    datos.campania = CampaniaPrediccion(
        **{
            **datos.campania.__dict__,
            "subtotales_por_categoria": {k: Decimal(0) for k in SUBTOTALES},
        }
    )

    with pytest.raises(ErrorAplicacion) as error:
        await servicio.estimar("c1", None, GERENCIA)

    assert (error.value.estado_http, error.value.codigo) == (422, "DATOS_INSUFICIENTES")


async def test_cultivo_no_soportado(servicio: ServicioPrediccion, datos: DatosFalsos) -> None:
    datos.campania = CampaniaPrediccion(**{**datos.campania.__dict__, "nombre_cultivo": "Trigo"})

    with pytest.raises(ErrorAplicacion) as error:
        await servicio.estimar("c1", None, GERENCIA)

    assert (error.value.estado_http, error.value.codigo) == (422, "CULTIVO_NO_SOPORTADO")
    assert "SOYA, MAIZ, SORGO" in error.value.detalles[0].mensaje


async def test_costos_fuera_de_rango_estima_con_advertencia(
    servicio: ServicioPrediccion,
) -> None:
    simulados = CostosPorHectarea.model_validate(
        {"INSUMO": "90000.00", "MANO_DE_OBRA": "350.00", "MAQUINARIA": "900.00", "OTRO": "150.00"}
    )

    prediccion = await servicio.estimar("c1", simulados, GERENCIA)

    (advertencia,) = prediccion.advertencias
    assert advertencia.codigo == "FUERA_DE_RANGO"
    assert "INSUMO" in advertencia.campos
    assert prediccion.rendimiento_estimado > 0  # se estima igual


async def test_campania_inexistente_es_404(
    servicio: ServicioPrediccion, datos: DatosFalsos
) -> None:
    datos.error = ErrorServicioRemoto(
        "servicio-gestion", TipoErrorRemoto.NO_ENCONTRADO, "CAMPANIA_NO_ENCONTRADA", 404
    )

    with pytest.raises(ErrorAplicacion) as error:
        await servicio.estimar("c1", None, GERENCIA)

    assert (error.value.estado_http, error.value.codigo) == (404, "CAMPANIA_NO_ENCONTRADA")


async def test_sin_version_vigente_es_503(
    datos: DatosFalsos, resultados: ResultadosMemoria
) -> None:
    servicio = ServicioPrediccion(datos, CargadorFalso({}), resultados)  # type: ignore[arg-type]

    with pytest.raises(ErrorAplicacion) as error:
        await servicio.estimar("c1", None, GERENCIA)

    assert (error.value.estado_http, error.value.codigo) == (503, "MODELO_NO_DISPONIBLE")


async def test_listar_predicciones_por_campania(servicio: ServicioPrediccion) -> None:
    await servicio.estimar("c1", None, GERENCIA)
    await servicio.estimar("c1", None, GERENCIA)

    pagina = await servicio.listar_predicciones("c1", 0, 20)

    assert pagina.total == 2
    assert {p.id_campania for p in pagina.items} == {"c1"}


# --- Historia 2 ------------------------------------------------------------------------------


def _historico(
    cultivo: str = "Soya",
    insumo: str = "51000.00",
    rendimiento: str | None = "2900.00",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "idCampania": str(uuid.uuid4()),
        "nombreParcela": "Lote Norte",
        "nombreCultivo": cultivo,
        "superficieHectareas": "25.5000",
        "costosPorCategoria": {**SUBTOTALES, "INSUMO": insumo},
        "rendimientoPorHectarea": rendimiento,
        "motivosNoDisponible": [] if rendimiento else ["SIN_COSTOS"],
        **extra,
    }


async def test_analisis_agrupa_detecta_anomalias_y_excluye(
    servicio: ServicioPrediccion, datos: DatosFalsos, resultados: ResultadosMemoria
) -> None:
    normal = _historico()
    atipica = _historico(insumo="900000.00", rendimiento="400.00")
    sin_costos = _historico(rendimiento=None)
    trigo = _historico(cultivo="Trigo")
    datos.items = [normal, atipica, sin_costos, trigo]

    analisis = await servicio.analizar(SolicitudAnalisis(), GERENCIA)

    assert analisis.cantidad_analizadas == 2
    assert sum(g.cantidad for g in analisis.grupos) == 2
    assert all(g.descripcion for g in analisis.grupos)
    assert {a.id_campania for a in analisis.anomalias} == {atipica["idCampania"]}
    (anomalia,) = analisis.anomalias
    assert anomalia.nombre_parcela == "Lote Norte"
    assert any("veces el típico" in m or "Participación" in m for m in anomalia.motivos)
    assert {(e.id_campania, e.motivo) for e in analisis.excluidas} == {
        (sin_costos["idCampania"], "SIN_COSTOS"),
        (trigo["idCampania"], "CULTIVO_NO_SOPORTADO"),
    }
    assert analisis.version_modelo.version == 3
    assert analisis.truncado is False
    assert resultados.guardados["analisis"][0]["id"] == analisis.id


async def test_una_sola_campania_igual_se_analiza(
    servicio: ServicioPrediccion, datos: DatosFalsos
) -> None:
    datos.items = [_historico()]

    analisis = await servicio.analizar(SolicitudAnalisis(), GERENCIA)

    assert analisis.cantidad_analizadas == 1
    assert len(analisis.grupos) == 1


async def test_sin_campanias_analizables_es_datos_insuficientes(
    servicio: ServicioPrediccion, datos: DatosFalsos
) -> None:
    datos.items = [_historico(rendimiento=None)]

    with pytest.raises(ErrorAplicacion) as error:
        await servicio.analizar(SolicitudAnalisis(), GERENCIA)

    assert error.value.codigo == "DATOS_INSUFICIENTES"


async def test_mas_de_mil_se_marca_truncado_y_pasa_los_filtros(
    servicio: ServicioPrediccion, datos: DatosFalsos
) -> None:
    datos.items = [_historico()]
    datos.total = 1500
    solicitud = SolicitudAnalisis.model_validate(
        {"idCultivo": str(uuid.UUID(int=1)), "fechaFinalizacionDesde": "2025-01-01"}
    )

    analisis = await servicio.analizar(solicitud, GERENCIA)

    assert analisis.truncado is True
    assert datos.filtros == {
        "idCultivo": "00000000-0000-0000-0000-000000000001",
        "fechaFinalizacionDesde": "2025-01-01",
    }


async def test_obtener_analisis_inexistente_es_404(servicio: ServicioPrediccion) -> None:
    for pedido in (str(uuid.uuid4()), "no-uuid"):
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.obtener_analisis(pedido)
        assert error.value.codigo == "ANALISIS_NO_ENCONTRADO"
