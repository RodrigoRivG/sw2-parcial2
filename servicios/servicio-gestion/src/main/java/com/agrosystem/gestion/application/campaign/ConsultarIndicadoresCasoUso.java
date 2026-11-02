package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.IndicadoresCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import java.math.BigDecimal;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConsultarIndicadoresCasoUso {

    private final RepositorioCampania campanias;

    public ConsultarIndicadoresCasoUso(RepositorioCampania campanias) {
        this.campanias = campanias;
    }

    @Transactional(readOnly = true)
    public ResultadoIndicadores ejecutar(UUID idCampania) {
        Campania campania = campanias.buscarPorId(idCampania).orElseThrow(ErroresCampania::noEncontrada);
        BigDecimal produccion = campania.tieneProduccion() ? campania.getProduccion().cantidad() : null;
        return new ResultadoIndicadores(
                campania,
                IndicadoresCampania.calcular(
                        produccion, campania.costoTotal(), campania.getSuperficie(), campania.getEstado()));
    }
}
