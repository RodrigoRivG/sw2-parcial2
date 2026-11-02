package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.OrigenCosto;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ListarCostosCasoUso {

    private final RepositorioCampania campanias;

    public ListarCostosCasoUso(RepositorioCampania campanias) {
        this.campanias = campanias;
    }

    /** Los totales cubren todos los costos vigentes de la campaña, sin importar los filtros. */
    @Transactional(readOnly = true)
    public ResultadoCostos ejecutar(UUID idCampania, CategoriaCosto categoria, OrigenCosto origen, int pagina, int tamanio) {
        Campania campania = campanias.buscarPorId(idCampania).orElseThrow(ErroresCampania::noEncontrada);
        return new ResultadoCostos(
                campanias.listarCostos(idCampania, categoria, origen, pagina, tamanio),
                campania.costoTotal(),
                campania.subtotalesPorCategoria());
    }
}
