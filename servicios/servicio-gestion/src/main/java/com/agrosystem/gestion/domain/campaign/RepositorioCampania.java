package com.agrosystem.gestion.domain.campaign;

import com.agrosystem.gestion.domain.shared.Pagina;
import java.util.Optional;
import java.util.UUID;

public interface RepositorioCampania {

    Campania guardar(Campania campania);

    Optional<Campania> buscarPorId(UUID id);

    /** Las campañas devueltas no traen sus costos y no deben volver a guardarse. */
    Pagina<Campania> listar(FiltrosCampania filtros, int pagina, int tamanio);

    boolean existeEnCursoEnParcela(UUID idParcela);

    /** Costos vigentes de la campaña, del más reciente al más antiguo. */
    Pagina<CostoCampania> listarCostos(
            UUID idCampania, CategoriaCosto categoria, OrigenCosto origen, int pagina, int tamanio);
}
