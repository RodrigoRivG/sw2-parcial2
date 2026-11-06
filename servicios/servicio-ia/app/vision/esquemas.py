"""Clasificación, metadatos para dispositivos y resultado de video (spec-vision.md 2.8)."""

from typing import Any

from app.comun.esquemas import DecimalTexto, FechaHoraUtc, ModeloBase
from app.modelos.esquemas import ReferenciaVersion

AVISO = "Clasificación orientativa. No sustituye una evaluación técnica agrícola."


class ClasificacionIncidencia(ModeloBase):
    """Exactamente el formato de `clasificacion` de una incidencia en servicio-operaciones."""

    categoria: str
    confianza: DecimalTexto
    version_modelo: str
    origen: str = "SERVIDOR"


class Alternativa(ModeloBase):
    categoria: str
    nombre: str
    confianza: DecimalTexto


class RespuestaClasificacion(ModeloBase):
    id: str
    fecha: FechaHoraUtc
    categoria: str
    nombre: str
    cultivo: str | None
    tipo_incidencia_sugerido: str | None
    confianza: DecimalTexto
    alternativas: list[Alternativa]
    clasificacion: ClasificacionIncidencia
    version_modelo: ReferenciaVersion
    orientativo: bool = True
    aviso: str = AVISO


class EtiquetaDispositivo(ModeloBase):
    indice: int
    categoria: str
    nombre: str
    cultivo: str | None
    tipo_incidencia_sugerido: str | None


class ArchivoDispositivo(ModeloBase):
    ruta: str
    tamanio: int
    sha256: str


class ExportacionDispositivo(ModeloBase):
    archivos: list[ArchivoDispositivo]


class MetadatosDispositivo(ModeloBase):
    version_modelo: str
    version: int
    fecha_publicacion: FechaHoraUtc | None
    umbral: DecimalTexto
    entrada: dict[str, Any]
    etiquetas: list[EtiquetaDispositivo]
    exportaciones: dict[str, ExportacionDispositivo]


class ResumenCategoria(ModeloBase):
    categoria: str
    fotogramas_principal: int
    confianza_promedio: DecimalTexto


class Fotograma(ModeloBase):
    segundo: DecimalTexto
    categoria: str
    confianza: DecimalTexto


class ResultadoVideo(ModeloBase):
    categoria_predominante: str
    nombre: str
    confianza: DecimalTexto
    clasificacion: ClasificacionIncidencia
    resumen: list[ResumenCategoria]
    fotogramas: list[Fotograma]
    duracion_segundos: DecimalTexto
    version_modelo: ReferenciaVersion
    orientativo: bool = True
    aviso: str = AVISO
