package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.FiltrosCampania;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.shared.Pagina;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ListarCampaniasCasoUso {

    private final RepositorioCampania campanias;

    public ListarCampaniasCasoUso(RepositorioCampania campanias) {
        this.campanias = campanias;
    }

    @Transactional(readOnly = true)
    public Pagina<Campania> ejecutar(FiltrosCampania filtros, boolean soloTecnico, int pagina, int tamanio) {
        return campanias.listar(filtros.conSoloNoFinalizadas(soloTecnico), pagina, tamanio);
    }
}
