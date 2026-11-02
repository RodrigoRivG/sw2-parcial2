package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import java.time.Clock;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CambiarEstadoCampaniaCasoUso {

    private final RepositorioCampania campanias;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public CambiarEstadoCampaniaCasoUso(RepositorioCampania campanias, RegistroAuditoria auditoria, Clock reloj) {
        this.campanias = campanias;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public Campania ejecutar(UUID id, EstadoCampania destino, long version) {
        Campania campania = campanias.buscarPorId(id).orElseThrow(ErroresCampania::noEncontrada);
        if (campania.getVersion() != version) {
            throw ErroresCampania.conflictoVersion();
        }
        campania.cambiarEstado(destino, reloj.instant());
        if (destino == EstadoCampania.EN_CURSO && campanias.existeEnCursoEnParcela(campania.getIdParcela())) {
            throw ErroresCampania.parcelaConCampaniaEnCurso();
        }
        Campania guardada = campanias.guardar(campania);
        auditoria.registrar(AccionAuditoria.CAMBIAR_ESTADO, "CAMPANIA", guardada.getId());
        return guardada;
    }
}
