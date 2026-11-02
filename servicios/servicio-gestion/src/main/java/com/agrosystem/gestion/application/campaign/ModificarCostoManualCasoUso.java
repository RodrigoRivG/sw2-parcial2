package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.shared.Dinero;
import java.time.Clock;
import java.time.LocalDate;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ModificarCostoManualCasoUso {

    private final RepositorioCampania campanias;
    private final RegistroAuditoria auditoria;
    private final Clock reloj;

    public ModificarCostoManualCasoUso(RepositorioCampania campanias, RegistroAuditoria auditoria, Clock reloj) {
        this.campanias = campanias;
        this.auditoria = auditoria;
        this.reloj = reloj;
    }

    @Transactional
    public CostoCampania ejecutar(UUID idCampania, UUID idCosto, DatosCosto datos) {
        Campania campania = campanias.buscarPorId(idCampania).orElseThrow(ErroresCampania::noEncontrada);
        CostoCampania costo = campania.modificarCostoManual(
                idCosto,
                datos.categoria(),
                new Dinero(datos.monto()),
                datos.fecha(),
                datos.descripcion(),
                LocalDate.now(reloj),
                reloj.instant());
        campanias.guardar(campania);
        auditoria.registrar(AccionAuditoria.MODIFICAR, "COSTO_CAMPANIA", costo.getId());
        return costo;
    }
}
