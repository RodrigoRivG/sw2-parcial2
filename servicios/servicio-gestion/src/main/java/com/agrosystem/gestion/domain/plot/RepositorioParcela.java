package com.agrosystem.gestion.domain.plot;

import com.agrosystem.gestion.domain.shared.Pagina;
import java.util.Optional;
import java.util.UUID;

public interface RepositorioParcela {

    Parcela guardar(Parcela parcela);

    Optional<Parcela> buscarPorId(UUID id);

    Pagina<Parcela> listar(String filtroNombre, int pagina, int tamanio);
}
