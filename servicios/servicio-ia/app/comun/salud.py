"""Salud del servicio: liveness y readiness con comprobaciones críticas e informativas."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

_TIEMPO_LIMITE = 2.0
_logger = logging.getLogger("app.salud")

Comprobacion = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class _Registro:
    nombre: str
    comprobar: Comprobacion
    critica: bool


class RegistroSalud:
    def __init__(self) -> None:
        self._registros: list[_Registro] = []

    def registrar(self, nombre: str, comprobar: Comprobacion, critica: bool) -> None:
        if any(r.nombre == nombre for r in self._registros):
            raise ValueError(f"Comprobación de salud duplicada: {nombre}")
        self._registros.append(_Registro(nombre, comprobar, critica))

    async def evaluar(self) -> tuple[bool, dict[str, str], dict[str, str]]:
        resultados = await asyncio.gather(*(self._ejecutar(r) for r in self._registros))
        componentes: dict[str, str] = {}
        informativos: dict[str, str] = {}
        for registro, sano in zip(self._registros, resultados, strict=True):
            destino = componentes if registro.critica else informativos
            destino[registro.nombre] = "UP" if sano else "DOWN"
        return all(v == "UP" for v in componentes.values()), componentes, informativos

    @staticmethod
    async def _ejecutar(registro: _Registro) -> bool:
        try:
            await asyncio.wait_for(registro.comprobar(), _TIEMPO_LIMITE)
        except Exception as error:  # cualquier falla deja el componente en DOWN
            _logger.warning(
                "Comprobación de salud fallida",
                extra={"componente": registro.nombre, "motivo": repr(error)},
            )
            return False
        return True


router_salud = APIRouter(tags=["salud"])


@router_salud.get("/salud/liveness", summary="El proceso está vivo")
async def liveness() -> dict[str, str]:
    return {"estado": "UP"}


async def _readiness(request: Request) -> JSONResponse:
    registro: RegistroSalud = request.app.state.registro_salud
    listo, componentes, informativos = await registro.evaluar()
    return JSONResponse(
        status_code=200 if listo else 503,
        content={
            "estado": "UP" if listo else "DOWN",
            "componentes": componentes,
            "informativos": informativos,
        },
    )


@router_salud.get("/salud/readiness", summary="El servicio puede recibir solicitudes")
async def readiness(request: Request) -> JSONResponse:
    return await _readiness(request)


@router_salud.get("/salud", summary="Igual que readiness")
async def salud(request: Request) -> JSONResponse:
    return await _readiness(request)
