package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.ProduccionCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConsultarProduccionCasoUso {

    private final RepositorioCampania campanias;

    public ConsultarProduccionCasoUso(RepositorioCampania campanias) {
        this.campanias = campanias;
    }

    @Transactional(readOnly = true)
    public ProduccionCampania ejecutar(UUID idCampania) {
        Campania campania = campanias.buscarPorId(idCampania).orElseThrow(ErroresCampania::noEncontrada);
        if (!campania.tieneProduccion()) {
            throw new ExcepcionDominio(
                    "PRODUCCION_NO_REGISTRADA",
                    "La campaña no tiene producción registrada.",
                    ExcepcionDominio.Tipo.NO_ENCONTRADO);
        }
        return campania.getProduccion();
    }
}
