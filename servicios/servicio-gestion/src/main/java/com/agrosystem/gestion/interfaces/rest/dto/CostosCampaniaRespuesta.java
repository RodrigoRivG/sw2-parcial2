package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.campaign.ResultadoCostos;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

public record CostosCampaniaRespuesta(
        List<CostoRespuesta> items,
        int pagina,
        int tamanio,
        long total,
        String costoTotal,
        Map<CategoriaCosto, String> subtotalesPorCategoria) {

    public static CostosCampaniaRespuesta de(ResultadoCostos resultado, int pagina, int tamanio) {
        Map<CategoriaCosto, String> subtotales = new EnumMap<>(CategoriaCosto.class);
        resultado.subtotales().forEach((categoria, monto) -> subtotales.put(categoria, monto.valor().toPlainString()));
        return new CostosCampaniaRespuesta(
                resultado.pagina().items().stream().map(CostoRespuesta::de).toList(),
                pagina,
                tamanio,
                resultado.pagina().total(),
                resultado.costoTotal().valor().toPlainString(),
                subtotales);
    }
}
