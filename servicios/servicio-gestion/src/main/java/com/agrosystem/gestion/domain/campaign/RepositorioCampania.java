package com.agrosystem.gestion.domain.campaign;

import com.agrosystem.gestion.domain.shared.Pagina;
import java.util.Optional;
import java.util.UUID;

public interface RepositorioCampania {

    Campania guardar(Campania campania);

    Optional<Campania> buscarPorId(UUID id);

    Pagina<Campania> listar(FiltrosCampania filtros, int pagina, int tamanio);

    boolean existeEnCursoEnParcela(UUID idParcela);
}
