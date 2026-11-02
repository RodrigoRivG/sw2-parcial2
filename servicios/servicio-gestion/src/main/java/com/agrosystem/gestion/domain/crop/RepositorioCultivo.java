package com.agrosystem.gestion.domain.crop;

import com.agrosystem.gestion.domain.shared.Pagina;
import java.util.Optional;
import java.util.UUID;

public interface RepositorioCultivo {

    Cultivo guardar(Cultivo cultivo);

    Optional<Cultivo> buscarPorId(UUID id);

    Pagina<Cultivo> listar(String filtroNombre, int pagina, int tamanio);
}
