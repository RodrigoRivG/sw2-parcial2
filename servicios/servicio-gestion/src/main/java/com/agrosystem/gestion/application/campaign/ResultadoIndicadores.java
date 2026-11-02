package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.IndicadoresCampania;

public record ResultadoIndicadores(Campania campania, IndicadoresCampania indicadores) {
}
