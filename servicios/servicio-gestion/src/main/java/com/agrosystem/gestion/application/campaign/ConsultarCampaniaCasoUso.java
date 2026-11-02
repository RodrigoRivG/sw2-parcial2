package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConsultarCampaniaCasoUso {

    private final RepositorioCampania campanias;

    public ConsultarCampaniaCasoUso(RepositorioCampania campanias) {
        this.campanias = campanias;
    }

    /** Quien solo es técnico de campo no ve campañas finalizadas (RQ-CAM-15). */
    @Transactional(readOnly = true)
    public Campania ejecutar(UUID id, boolean soloTecnico) {
        Campania campania = campanias.buscarPorId(id).orElseThrow(ErroresCampania::noEncontrada);
        if (soloTecnico && campania.getEstado() == EstadoCampania.FINALIZADA) {
            throw ErroresCampania.sinPermiso();
        }
        return campania;
    }
}
