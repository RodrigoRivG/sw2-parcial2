package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import java.time.Clock;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class EliminarCostoManualCasoUso {

    private final RepositorioCampania campanias;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public EliminarCostoManualCasoUso(RepositorioCampania campanias, RegistroAuditoria auditoria, Clock reloj) {
        this.campanias = campanias;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public void ejecutar(UUID idCampania, UUID idCosto) {
        Campania campania = campanias.buscarPorId(idCampania).orElseThrow(ErroresCampania::noEncontrada);
        campania.eliminarCostoManual(idCosto, reloj.instant());
        campanias.guardar(campania);
        auditoria.registrar(AccionAuditoria.ELIMINAR, "COSTO_CAMPANIA", idCosto);
    }
}
