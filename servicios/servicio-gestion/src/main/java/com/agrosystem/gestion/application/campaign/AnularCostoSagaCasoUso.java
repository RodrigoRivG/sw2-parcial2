package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.saga.RepositorioSagaProcesada;
import com.agrosystem.gestion.domain.saga.SagaProcesada;
import java.time.Clock;
import java.time.Instant;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Aplica la tabla de RQ-SAG-06. */
@Service
public class AnularCostoSagaCasoUso {

    private static final Logger LOG = LoggerFactory.getLogger(AnularCostoSagaCasoUso.class);
    private static final String CAMPANIA_FINALIZADA = "CAMPANIA_FINALIZADA";
    private static final String MOTIVO_FINALIZADA = "La campaña ya está finalizada; el costo se conserva.";

    private final RepositorioCampania campanias;
    private final RepositorioSagaProcesada sagas;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public AnularCostoSagaCasoUso(
            RepositorioCampania campanias,
            RepositorioSagaProcesada sagas,
            RegistroAuditoria auditoria,
            Clock reloj) {
        this.campanias = campanias;
        this.sagas = sagas;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public RespuestaSaga ejecutar(ComandoAnularCosto comando) {
        Instant ahora = reloj.instant();
        sagas.bloquear(comando.idSaga());
        sagas.registrarMensaje(comando.idMensaje(), comando.idSaga(), ahora);
        Optional<SagaProcesada> procesada = sagas.buscar(comando.idSaga());
        if (procesada.isEmpty()) {
            sagas.guardar(SagaProcesada.anuladaSinRegistro(
                    comando.idSaga(), comando.idCampania(), comando.idLabor(), ahora));
            return RespuestaSaga.anulado(comando.idSaga(), comando.idLabor(), comando.idCampania(), null, true);
        }
        SagaProcesada saga = procesada.get();
        return switch (saga.getResultado()) {
            case ANULADO -> RespuestaSaga.anulado(
                    saga.getIdSaga(), saga.getIdLabor(), saga.getIdCampania(), saga.getIdCosto(),
                    Boolean.TRUE.equals(saga.getAnulacionSinEfecto()));
            case RECHAZADO -> {
                saga.marcarAnulacionSinEfecto(ahora);
                sagas.guardar(saga);
                yield RespuestaSaga.anulado(saga.getIdSaga(), saga.getIdLabor(), saga.getIdCampania(), null, true);
            }
            case REGISTRADO -> anularRegistrada(saga, comando, ahora);
        };
    }

    private RespuestaSaga anularRegistrada(SagaProcesada saga, ComandoAnularCosto comando, Instant ahora) {
        if (!saga.getIdCampania().equals(comando.idCampania())) {
            LOG.warn("Anulación con otra campaña para la saga {}; manda el idSaga", saga.getIdSaga());
        }
        Campania campania = campanias.buscarPorId(saga.getIdCampania()).orElseThrow();
        if (campania.getEstado() == EstadoCampania.FINALIZADA) {
            saga.marcarAnulacionRechazada(CAMPANIA_FINALIZADA, ahora);
            sagas.guardar(saga);
            return RespuestaSaga.anulacionRechazada(
                    saga.getIdSaga(), saga.getIdLabor(), saga.getIdCampania(), saga.getIdCosto(),
                    CAMPANIA_FINALIZADA, MOTIVO_FINALIZADA);
        }
        campania.anularCostoSaga(saga.getIdSaga(), ahora);
        campanias.guardar(campania);
        saga.marcarAnulada(ahora);
        sagas.guardar(saga);
        auditoria.registrarServicio(
                comando.origen(), AccionAuditoria.ANULAR_COSTO_SAGA, "COSTO_CAMPANIA", saga.getIdCosto());
        return RespuestaSaga.anulado(saga.getIdSaga(), saga.getIdLabor(), saga.getIdCampania(), saga.getIdCosto(), false);
    }
}
