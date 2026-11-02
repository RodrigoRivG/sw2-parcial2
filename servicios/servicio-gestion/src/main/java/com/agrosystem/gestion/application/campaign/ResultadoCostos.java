package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.Pagina;
import java.util.Map;

public record ResultadoCostos(Pagina<CostoCampania> pagina, Dinero costoTotal, Map<CategoriaCosto, Dinero> subtotales) {
}
