package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.saga.RepositorioSagaProcesada;
import com.agrosystem.gestion.domain.saga.ResultadoSagaProcesada;
import com.agrosystem.gestion.domain.saga.SagaProcesada;
import com.agrosystem.gestion.domain.shared.Dinero;
import java.time.Clock;
import java.time.Instant;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RegistrarCostoSagaCasoUso {

    private static final Logger LOG = LoggerFactory.getLogger(RegistrarCostoSagaCasoUso.class);

    private final RepositorioCampania campanias;
    private final RepositorioSagaProcesada sagas;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public RegistrarCostoSagaCasoUso(
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
    public RespuestaSaga ejecutar(ComandoRegistrarCosto comando) {
        Instant ahora = reloj.instant();
        sagas.bloquear(comando.idSaga());
        sagas.registrarMensaje(comando.idMensaje(), comando.idSaga(), ahora);
        Optional<SagaProcesada> procesada = sagas.buscar(comando.idSaga());
        return procesada.isPresent() ? repetir(procesada.get(), comando) : procesar(comando, ahora);
    }

    private RespuestaSaga repetir(SagaProcesada saga, ComandoRegistrarCosto comando) {
        if (saga.getResultado() == ResultadoSagaProcesada.ANULADO) {
            return RespuestaSaga.rechazado(
                    comando.idSaga(), comando.idLabor(), comando.idCampania(),
                    "SAGA_ANULADA", "La saga ya fue anulada.");
        }
        if (saga.getResultado() == ResultadoSagaProcesada.RECHAZADO) {
            return RespuestaSaga.rechazado(
                    saga.getIdSaga(), saga.getIdLabor(), saga.getIdCampania(), saga.getCodigo(), saga.getMotivo());
        }
        if (saga.getMonto().compareTo(comando.monto()) != 0 || !saga.getIdCampania().equals(comando.idCampania())) {
            LOG.warn("Comando repetido con datos distintos para la saga {}; se responde el resultado original",
                    saga.getIdSaga());
        }
        return RespuestaSaga.registrado(
                saga.getIdSaga(), saga.getIdLabor(), saga.getIdCampania(), saga.getIdCosto(), saga.getMonto());
    }

    private RespuestaSaga procesar(ComandoRegistrarCosto comando, Instant ahora) {
        Optional<Campania> encontrada = campanias.buscarPorId(comando.idCampania());
        if (encontrada.isEmpty()) {
            return rechazar(comando, "CAMPANIA_NO_ENCONTRADA", "La campaña no existe.", ahora);
        }
        Campania campania = encontrada.get();
        if (campania.getEstado() == EstadoCampania.FINALIZADA) {
            return rechazar(comando, "CAMPANIA_FINALIZADA", "La campaña está finalizada y no admite cambios.", ahora);
        }
        CostoCampania costo = campania.registrarCostoSaga(
                comando.idSaga(), comando.idLabor(), new Dinero(comando.monto()), comando.fecha(), ahora);
        campanias.guardar(campania);
        sagas.guardar(SagaProcesada.registrada(
                comando.idSaga(), comando.idCampania(), comando.idLabor(), costo.getId(), costo.getMonto().valor(), ahora));
        auditoria.registrarServicio(
                comando.origen(), AccionAuditoria.REGISTRAR_COSTO_SAGA, "COSTO_CAMPANIA", costo.getId());
        return RespuestaSaga.registrado(
                comando.idSaga(), comando.idLabor(), comando.idCampania(), costo.getId(), costo.getMonto().valor());
    }

    private RespuestaSaga rechazar(ComandoRegistrarCosto comando, String codigo, String motivo, Instant ahora) {
        sagas.guardar(SagaProcesada.rechazada(
                comando.idSaga(), comando.idCampania(), comando.idLabor(), codigo, motivo, ahora));
        return RespuestaSaga.rechazado(comando.idSaga(), comando.idLabor(), comando.idCampania(), codigo, motivo);
    }
}
