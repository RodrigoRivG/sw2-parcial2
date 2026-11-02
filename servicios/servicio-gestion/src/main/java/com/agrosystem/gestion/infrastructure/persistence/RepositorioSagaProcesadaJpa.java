package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.domain.saga.RepositorioSagaProcesada;
import com.agrosystem.gestion.domain.saga.ResultadoSagaProcesada;
import com.agrosystem.gestion.domain.saga.SagaProcesada;
import com.agrosystem.gestion.infrastructure.persistence.entity.MensajeProcesadoEntidad;
import com.agrosystem.gestion.infrastructure.persistence.entity.SagaProcesadaEntidad;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.stereotype.Repository;

@Repository
public class RepositorioSagaProcesadaJpa implements RepositorioSagaProcesada {

    private final SagaProcesadaSpringData sagas;
    private final MensajeProcesadoSpringData mensajes;

    public RepositorioSagaProcesadaJpa(SagaProcesadaSpringData sagas, MensajeProcesadoSpringData mensajes) {
        this.sagas = sagas;
        this.mensajes = mensajes;
    }

    @Override
    public void bloquear(UUID idSaga) {
        sagas.bloquear(idSaga.toString());
    }

    @Override
    public Optional<SagaProcesada> buscar(UUID idSaga) {
        return sagas.findById(idSaga).map(this::aDominio);
    }

    private SagaProcesada aDominio(SagaProcesadaEntidad entidad) {
        return new SagaProcesada(
                entidad.getIdSaga(),
                ResultadoSagaProcesada.valueOf(entidad.getResultado()),
                entidad.getIdCampania(),
                entidad.getIdLabor(),
                entidad.getIdCosto(),
                entidad.getMonto(),
                entidad.getCodigo(),
                entidad.getMotivo(),
                entidad.getAnulacionResultado(),
                entidad.getAnulacionSinEfecto(),
                entidad.getAnulacionCodigo(),
                entidad.getFechaProcesamiento(),
                entidad.getFechaActualizacion());
    }

    @Override
    public void guardar(SagaProcesada saga) {
        SagaProcesadaEntidad entidad = sagas.findById(saga.getIdSaga())
                .orElseGet(() -> new SagaProcesadaEntidad(saga.getIdSaga()));
        entidad.actualizar(
                saga.getResultado().name(),
                saga.getIdCampania(),
                saga.getIdLabor(),
                saga.getIdCosto(),
                saga.getMonto(),
                saga.getCodigo(),
                saga.getMotivo(),
                saga.getAnulacionResultado(),
                saga.getAnulacionSinEfecto(),
                saga.getAnulacionCodigo(),
                saga.getFechaProcesamiento(),
                saga.getFechaActualizacion());
        sagas.save(entidad);
    }

    @Override
    public void registrarMensaje(UUID idMensaje, UUID idSaga, Instant ahora) {
        if (!mensajes.existsById(idMensaje)) {
            mensajes.save(new MensajeProcesadoEntidad(idMensaje, idSaga, ahora));
        }
    }
}
