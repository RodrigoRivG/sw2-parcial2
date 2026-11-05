"""Regla de publicación de versiones: funciones puras (constitución §5, spec-prediccion.md 2.6)."""

from app.modelos.esquemas import MetricaPrincipal, Sentido

LARGO_MINIMO_JUSTIFICACION = 20


def es_peor(candidata: MetricaPrincipal, vigente: MetricaPrincipal) -> bool:
    if candidata.sentido is Sentido.MENOR_ES_MEJOR:
        return candidata.valor > vigente.valor
    return candidata.valor < vigente.valor


def justificacion_valida(justificacion: str | None) -> bool:
    return justificacion is not None and len(justificacion.strip()) >= LARGO_MINIMO_JUSTIFICACION


def puede_publicar(
    candidata: MetricaPrincipal, vigente: MetricaPrincipal | None, justificacion: str | None
) -> bool:
    """Sin vigente, o con métricas no peores, se publica; si son peores, solo con justificación."""
    if vigente is None or candidata.nombre != vigente.nombre:
        return True
    return not es_peor(candidata, vigente) or justificacion_valida(justificacion)
