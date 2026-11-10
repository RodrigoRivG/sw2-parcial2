"""Estimación de rendimiento y análisis de patrones (spec-prediccion.md 2.7)."""

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np
from fastapi import Request

from app.comun.errores import DetalleError, ErrorAplicacion
from app.comun.seguridad import UsuarioAutenticado
from app.integracion.datos_agricolas import CampaniaPrediccion, DatosAgricolas
from app.integracion.errores import ErrorInfraestructura, ErrorServicioRemoto, TipoErrorRemoto
from app.integracion.repositorio_resultados import RepositorioResultadosMongo
from app.modelos.cargador import CargadorModelos, ModeloCargado
from app.modelos.esquemas import ReferenciaVersion
from app.prediccion.esquemas import (
    Advertencia,
    Analisis,
    Anomalia,
    CostosPorHectarea,
    Excluida,
    Grupo,
    Intervalo,
    OrigenCostos,
    Pagina,
    Prediccion,
    ResumenAnalisis,
    SolicitudAnalisis,
)
from app.prediccion.variables import (
    CATEGORIAS,
    CULTIVOS,
    CategoriaCosto,
    Cultivo,
    Referencia,
    costo_total,
    fuera_de_rango,
    motivos_anomalia,
    normalizar_cultivo,
    perfil_patrones,
    vector_rendimiento,
)

MODELO_RENDIMIENTO = "rendimiento"
MODELO_PATRONES = "patrones"
MAXIMO_ANALISIS = 1000
DOS_DECIMALES = Decimal("0.01")


def _redondear(valor: Decimal | float) -> Decimal:
    return Decimal(str(valor)).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def _ahora() -> datetime:
    return datetime.now(UTC)


def _referencia_de(cargado: ModeloCargado) -> Referencia:
    if cargado.version.referencia is None:
        raise ErrorAplicacion(503, "MODELO_NO_DISPONIBLE")
    return Referencia.desde_dict(cargado.version.referencia)


def _version(cargado: ModeloCargado) -> ReferenciaVersion:
    return ReferenciaVersion(nombre=cargado.version.nombre, version=cargado.version.version)


class ServicioPrediccion:
    def __init__(
        self,
        datos: DatosAgricolas,
        cargador: CargadorModelos,
        resultados: RepositorioResultadosMongo,
        reloj: Callable[[], datetime] = _ahora,
    ) -> None:
        self._datos = datos
        self._cargador = cargador
        self._resultados = resultados
        self._reloj = reloj

    # --- rendimiento -------------------------------------------------------------------------

    async def estimar(
        self,
        id_campania: str,
        costos_simulados: CostosPorHectarea | None,
        solicitante: UsuarioAutenticado,
    ) -> Prediccion:
        cargado = self._cargador.obtener(MODELO_RENDIMIENTO)
        referencia = _referencia_de(cargado)
        campania = await self._campania(id_campania)
        cultivo = self._cultivo_admitido(campania.nombre_cultivo)

        if costos_simulados is not None:
            origen = OrigenCostos.SIMULADOS
            costos = {c: Decimal(getattr(costos_simulados, c.value)) for c in CATEGORIAS}
        else:
            origen = OrigenCostos.REGISTRADOS
            costos = {
                c: campania.subtotales_por_categoria.get(c.value, Decimal(0))
                / campania.superficie_hectareas
                for c in CATEGORIAS
            }
        costos_ha = {c: _redondear(v) for c, v in costos.items()}
        if costo_total({c: float(v) for c, v in costos_ha.items()}) <= 0:
            raise ErrorAplicacion(
                422, "DATOS_INSUFICIENTES", "No hay datos suficientes para realizar la estimación."
            )

        costos_float = {c: float(v) for c, v in costos_ha.items()}
        estimado, minimo, maximo = await asyncio.to_thread(
            _predecir_rendimiento, cargado.modelo, cultivo, costos_float
        )
        advertencias = []
        campos = fuera_de_rango(cultivo, costos_float, referencia)
        if campos:
            advertencias.append(
                Advertencia(
                    codigo="FUERA_DE_RANGO",
                    mensaje="Hay costos fuera del rango de los datos de entrenamiento; "
                    "la estimación es menos confiable.",
                    campos=campos,
                )
            )
        rendimiento = _redondear(estimado)
        prediccion = Prediccion(
            id=str(uuid.uuid4()),
            id_campania=campania.id,
            fecha=self._reloj(),
            cultivo=cultivo.value,
            estado_campania=campania.estado,
            origen_costos=origen,
            costos_por_hectarea={c.value: v for c, v in costos_ha.items()},
            rendimiento_estimado=rendimiento,
            intervalo=Intervalo(minimo=_redondear(minimo), maximo=_redondear(maximo)),
            produccion_estimada=_redondear(rendimiento * campania.superficie_hectareas),
            rendimiento_real=campania.rendimiento_real,
            advertencias=advertencias,
            version_modelo=_version(cargado),
        )
        await self._guardar(
            "predicciones", prediccion.model_dump(mode="json", by_alias=True), solicitante
        )
        return prediccion

    async def _campania(self, id_campania: str) -> CampaniaPrediccion:
        try:
            return await self._datos.campania_para_prediccion(id_campania)
        except ErrorServicioRemoto as error:
            if (
                error.tipo is TipoErrorRemoto.NO_ENCONTRADO
                and error.codigo == "CAMPANIA_NO_ENCONTRADA"
            ):
                raise ErrorAplicacion(
                    404, "CAMPANIA_NO_ENCONTRADA", "La campaña no existe."
                ) from None
            raise

    @staticmethod
    def _cultivo_admitido(nombre: str) -> Cultivo:
        cultivo = normalizar_cultivo(nombre)
        if cultivo is None:
            raise ErrorAplicacion(
                422,
                "CULTIVO_NO_SOPORTADO",
                "El modelo no admite este cultivo.",
                [
                    DetalleError(
                        campo="cultivo",
                        mensaje="Cultivos admitidos: " + ", ".join(c.value for c in CULTIVOS),
                    )
                ],
            )
        return cultivo

    async def listar_predicciones(
        self, id_campania: str | None, pagina: int, tamanio: int
    ) -> Pagina[Prediccion]:
        filtro = ("idCampania", id_campania) if id_campania else None
        documentos, total = await self._listar("predicciones", pagina, tamanio, filtro)
        return Pagina(
            items=[Prediccion.model_validate(d) for d in documentos],
            pagina=pagina,
            tamanio=tamanio,
            total=total,
        )

    # --- patrones ----------------------------------------------------------------------------

    async def analizar(
        self, solicitud: SolicitudAnalisis, solicitante: UsuarioAutenticado
    ) -> Analisis:
        cargado = self._cargador.obtener(MODELO_PATRONES)
        referencia = _referencia_de(cargado)
        filtros = {
            k: str(v) for k, v in solicitud.model_dump(by_alias=True, exclude_none=True).items()
        }
        historicos = await self._datos.historicos(filtros, MAXIMO_ANALISIS)

        analizables: list[tuple[dict[str, Any], Cultivo, list[float]]] = []
        excluidas: list[Excluida] = []
        for item in historicos.items:
            motivo, cultivo, perfil = _preparar_item(item, referencia)
            if motivo is not None or cultivo is None or perfil is None:
                excluidas.append(Excluida(id_campania=str(item["idCampania"]), motivo=motivo or ""))
            else:
                analizables.append((item, cultivo, perfil))
        if not analizables:
            raise ErrorAplicacion(
                422, "DATOS_INSUFICIENTES", "No hay datos suficientes para realizar la estimación."
            )

        grupos_por_item, puntajes, anomalos = await asyncio.to_thread(
            _aplicar_patrones, cargado.modelo, [p for _, _, p in analizables]
        )
        grupos: dict[int, list[str]] = defaultdict(list)
        anomalias: list[Anomalia] = []
        descripciones: dict[str, str] = cargado.modelo["descripciones"]
        for (item, cultivo, perfil), grupo, puntaje, anomalo in zip(
            analizables, grupos_por_item, puntajes, anomalos, strict=True
        ):
            grupos[grupo].append(str(item["idCampania"]))
            if anomalo:
                anomalias.append(
                    Anomalia(
                        id_campania=str(item["idCampania"]),
                        nombre_parcela=item.get("nombreParcela"),
                        cultivo=cultivo.value,
                        puntaje=_redondear(puntaje),
                        motivos=motivos_anomalia(perfil, referencia)
                        or ["Combinación de costos y rendimiento poco común"],
                    )
                )
        analisis = Analisis(
            id=str(uuid.uuid4()),
            fecha=self._reloj(),
            filtros=filtros,
            cantidad_analizadas=len(analizables),
            truncado=historicos.total > MAXIMO_ANALISIS,
            grupos=[
                Grupo(
                    grupo=g, descripcion=descripciones[str(g)], cantidad=len(ids), ids_campania=ids
                )
                for g, ids in sorted(grupos.items())
            ],
            anomalias=anomalias,
            excluidas=excluidas,
            version_modelo=_version(cargado),
        )
        await self._guardar(
            "analisis", analisis.model_dump(mode="json", by_alias=True), solicitante
        )
        return analisis

    async def obtener_analisis(self, id_analisis: str) -> Analisis:
        try:
            documento = await self._resultados.obtener("analisis", str(uuid.UUID(id_analisis)))
        except ValueError:
            documento = None
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        if documento is None:
            raise ErrorAplicacion(
                404, "ANALISIS_NO_ENCONTRADO", "El análisis solicitado no existe."
            )
        return Analisis.model_validate(documento)

    async def listar_analisis(self, pagina: int, tamanio: int) -> Pagina[ResumenAnalisis]:
        documentos, total = await self._listar("analisis", pagina, tamanio, None)
        items = [
            ResumenAnalisis(
                id=d["id"],
                fecha=d["fecha"],
                filtros=d["filtros"],
                cantidad_analizadas=d["cantidadAnalizadas"],
                truncado=d["truncado"],
                cantidad_grupos=len(d["grupos"]),
                cantidad_anomalias=len(d["anomalias"]),
                version_modelo=d["versionModelo"],
            )
            for d in documentos
        ]
        return Pagina(items=items, pagina=pagina, tamanio=tamanio, total=total)

    # --- persistencia ------------------------------------------------------------------------

    async def _guardar(
        self, coleccion: str, documento: dict[str, Any], solicitante: UsuarioAutenticado
    ) -> None:
        documento["fecha"] = (
            self._reloj() if "fecha" not in documento else _fecha(documento["fecha"])
        )
        documento["idSolicitante"] = solicitante.id
        try:
            await self._resultados.guardar(coleccion, documento)
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None

    async def _listar(
        self, coleccion: str, pagina: int, tamanio: int, filtro: tuple[str, Any] | None
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            return await self._resultados.listar(coleccion, pagina, tamanio, filtro)
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None


def _fecha(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def _predecir_rendimiento(
    modelo: Any, cultivo: Cultivo, costos: dict[CategoriaCosto, float]
) -> tuple[float, float, float]:
    """Estimación y percentiles 10 y 90 de los árboles del bosque."""
    x = np.array([vector_rendimiento(cultivo, costos)])
    por_arbol = np.array([arbol.predict(x)[0] for arbol in modelo.estimators_])
    return (
        float(modelo.predict(x)[0]),
        float(np.percentile(por_arbol, 10)),
        float(np.percentile(por_arbol, 90)),
    )


def _preparar_item(
    item: dict[str, Any], referencia: Referencia
) -> tuple[str | None, Cultivo | None, list[float] | None]:
    """Motivo de exclusión, o el cultivo y el perfil de una campaña histórica."""
    cultivo = normalizar_cultivo(str(item.get("nombreCultivo", "")))
    if cultivo is None or cultivo.value not in referencia.cultivos:
        return "CULTIVO_NO_SOPORTADO", None, None
    rendimiento = item.get("rendimientoPorHectarea")
    superficie = Decimal(str(item.get("superficieHectareas") or 0))
    if rendimiento is None or superficie <= 0:
        motivos = item.get("motivosNoDisponible") or ["SIN_INDICADORES"]
        return str(motivos[0]), None, None
    por_categoria = item.get("costosPorCategoria") or {}
    costos = {
        c: float(Decimal(str(por_categoria.get(c.value, "0"))) / superficie) for c in CATEGORIAS
    }
    return (
        None,
        cultivo,
        perfil_patrones(cultivo, costos, float(Decimal(str(rendimiento))), referencia),
    )


def _aplicar_patrones(
    artefacto: dict[str, Any], perfiles: list[list[float]]
) -> tuple[list[int], list[float], list[bool]]:
    escalados = artefacto["escalador"].transform(np.array(perfiles))
    grupos = [int(g) for g in artefacto["kmeans"].predict(escalados)]
    bosque = artefacto["isolationForest"]
    puntajes = [float(p) for p in bosque.decision_function(escalados)]
    anomalos = [bool(a == -1) for a in bosque.predict(escalados)]
    return grupos, puntajes, anomalos


def servicio_prediccion(request: Request) -> ServicioPrediccion:
    servicio: ServicioPrediccion = request.app.state.servicio_prediccion
    return servicio
