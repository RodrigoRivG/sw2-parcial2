"""RepositorioTrabajosFirestore contra el emulador (spec-trabajos.md 2.5)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from google.cloud import firestore

from app.integracion.errores import ErrorInfraestructura
from app.integracion.repositorio_trabajos import RepositorioTrabajosFirestore

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _documento(estado: str = "EN_COLA", **cambios: Any) -> dict[str, Any]:
    documento: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "tipo": "PRUEBA",
        "estado": estado,
        "idSolicitante": "ana",
        "idCorrelacion": "corr",
        "parametros": {"a": [1, "dos"], "b": {"c": None}},
        "resultado": None,
        "error": None,
        "fechaCreacion": AHORA,
        "fechaInicio": None,
        "fechaFin": None,
        "fechaLimite": None,
        "fechaExpiracion": None,
    }
    documento.update(cambios)
    return documento


@pytest.fixture
def repositorio(proyecto_firestore: str) -> RepositorioTrabajosFirestore:
    return RepositorioTrabajosFirestore(firestore.AsyncClient(project=proyecto_firestore))


async def test_guardar_y_obtener(repositorio: RepositorioTrabajosFirestore) -> None:
    documento = _documento()

    await repositorio.guardar_nuevo(documento)
    leido = await repositorio.obtener(documento["id"])

    assert leido == documento
    assert await repositorio.obtener(str(uuid.uuid4())) is None


async def test_guardar_dos_veces_el_mismo_id_falla(
    repositorio: RepositorioTrabajosFirestore,
) -> None:
    documento = _documento()
    await repositorio.guardar_nuevo(documento)

    with pytest.raises(ValueError):
        await repositorio.guardar_nuevo(documento)


async def test_cambiar_estado_es_condicional(repositorio: RepositorioTrabajosFirestore) -> None:
    documento = _documento()
    await repositorio.guardar_nuevo(documento)

    assert await repositorio.cambiar_estado(
        documento["id"], "EN_COLA", "PROCESANDO", {"fechaInicio": AHORA}
    )
    assert not await repositorio.cambiar_estado(documento["id"], "EN_COLA", "PROCESANDO", {})
    assert not await repositorio.cambiar_estado(str(uuid.uuid4()), "EN_COLA", "PROCESANDO", {})

    leido = await repositorio.obtener(documento["id"])
    assert leido is not None
    assert leido["estado"] == "PROCESANDO"
    assert leido["fechaInicio"] == AHORA


async def test_cambio_concurrente_lo_gana_uno_solo(proyecto_firestore: str) -> None:
    documento = _documento()
    await RepositorioTrabajosFirestore(
        firestore.AsyncClient(project=proyecto_firestore)
    ).guardar_nuevo(documento)
    repositorios = [
        RepositorioTrabajosFirestore(firestore.AsyncClient(project=proyecto_firestore))
        for _ in range(5)
    ]

    resultados = await asyncio.gather(
        *(r.cambiar_estado(documento["id"], "EN_COLA", "PROCESANDO", {}) for r in repositorios),
        return_exceptions=True,
    )

    # Uno gana; los demás ven el estado ya cambiado o agotan los intentos por contención
    # (falla pasajera que el consumidor reintenta).
    assert resultados.count(True) == 1
    assert all(
        r is False or isinstance(r, ErrorInfraestructura) for r in resultados if r is not True
    )


async def test_listar_vencidos(repositorio: RepositorioTrabajosFirestore) -> None:
    procesando_vencido = _documento("PROCESANDO", fechaLimite=AHORA - timedelta(seconds=1))
    procesando_vigente = _documento("PROCESANDO", fechaLimite=AHORA + timedelta(minutes=1))
    en_cola_vieja = _documento("EN_COLA", fechaCreacion=AHORA - timedelta(minutes=11))
    en_cola_nueva = _documento("EN_COLA", fechaCreacion=AHORA - timedelta(minutes=1))
    completado = _documento("COMPLETADO", fechaCreacion=AHORA - timedelta(days=1))
    for documento in (
        procesando_vencido,
        procesando_vigente,
        en_cola_vieja,
        en_cola_nueva,
        completado,
    ):
        await repositorio.guardar_nuevo(documento)

    vencidos = await repositorio.listar_vencidos(AHORA, AHORA - timedelta(minutes=10))

    assert {d["id"] for d in vencidos} == {procesando_vencido["id"], en_cola_vieja["id"]}
