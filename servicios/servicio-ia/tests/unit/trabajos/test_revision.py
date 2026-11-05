"""Revisión periódica: spec-trabajos.md, Historia 2, escenarios 4 y 5."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.trabajos.revision import revisar_vencidos
from tests.dobles import RepositorioTrabajosMemoria

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _documento(estado: str, creado: datetime, limite: datetime | None = None) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "tipo": "PRUEBA",
        "estado": estado,
        "idSolicitante": "ana",
        "idCorrelacion": None,
        "parametros": {},
        "resultado": None,
        "error": None,
        "fechaCreacion": creado,
        "fechaInicio": None,
        "fechaFin": None,
        "fechaLimite": limite,
        "fechaExpiracion": None,
    }


def _guardar(repositorio: RepositorioTrabajosMemoria, documento: dict[str, Any]) -> str:
    repositorio.documentos[documento["id"]] = documento
    return str(documento["id"])


async def test_cierra_procesando_vencido_y_en_cola_atascado() -> None:
    repositorio = RepositorioTrabajosMemoria()
    procesando = _guardar(
        repositorio,
        _documento("PROCESANDO", AHORA - timedelta(hours=1), AHORA - timedelta(seconds=1)),
    )
    en_cola = _guardar(repositorio, _documento("EN_COLA", AHORA - timedelta(minutes=11)))
    vigente = _guardar(
        repositorio,
        _documento("PROCESANDO", AHORA - timedelta(minutes=1), AHORA + timedelta(minutes=1)),
    )
    reciente = _guardar(repositorio, _documento("EN_COLA", AHORA - timedelta(minutes=2)))

    cerrados = await revisar_vencidos(repositorio, AHORA, 30)

    assert cerrados == 2
    assert repositorio.documentos[procesando]["error"]["codigo"] == "TIEMPO_AGOTADO"
    assert repositorio.documentos[en_cola]["error"]["codigo"] == "TRABAJO_NO_PROCESADO"
    assert repositorio.documentos[en_cola]["fechaFin"] == AHORA
    assert repositorio.documentos[en_cola]["fechaExpiracion"] == AHORA + timedelta(days=30)
    assert repositorio.documentos[vigente]["estado"] == "PROCESANDO"
    assert repositorio.documentos[reciente]["estado"] == "EN_COLA"


async def test_si_otro_proceso_ya_lo_cerro_no_cuenta() -> None:
    repositorio = RepositorioTrabajosMemoria()
    id_trabajo = _guardar(repositorio, _documento("EN_COLA", AHORA - timedelta(minutes=11)))
    original = repositorio.listar_vencidos

    async def listar_y_carrera(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        vencidos = await original(*args, **kwargs)
        repositorio.documentos[id_trabajo]["estado"] = "PROCESANDO"  # otro consumidor lo tomó
        return vencidos

    repositorio.listar_vencidos = listar_y_carrera  # type: ignore[method-assign]

    assert await revisar_vencidos(repositorio, AHORA, 30) == 0
    assert repositorio.documentos[id_trabajo]["estado"] == "PROCESANDO"
