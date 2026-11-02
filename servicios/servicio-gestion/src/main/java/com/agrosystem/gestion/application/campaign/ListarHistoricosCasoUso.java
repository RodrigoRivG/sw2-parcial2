package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.IndicadoresCampania;
import com.agrosystem.gestion.domain.shared.Pagina;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ListarHistoricosCasoUso {

    private final ConsultaHistoricos consulta;

    public ListarHistoricosCasoUso(ConsultaHistoricos consulta) {
        this.consulta = consulta;
    }

    /** Los indicadores siguen las mismas reglas que la consulta por campaña (RQ-INT-04). */
    @Transactional(readOnly = true)
    public Pagina<RegistroHistorico> ejecutar(FiltrosHistoricos filtros, int pagina, int tamanio) {
        Pagina<FilaHistorico> filas = consulta.listar(filtros, pagina, tamanio);
        return new Pagina<>(
                filas.items().stream()
                        .map(fila -> new RegistroHistorico(
                                fila,
                                IndicadoresCampania.calcular(
                                        fila.produccion(),
                                        fila.costoTotal(),
                                        fila.superficie(),
                                        EstadoCampania.FINALIZADA)))
                        .toList(),
                filas.total());
    }
}
