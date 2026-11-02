package com.agrosystem.gestion.application.crop;

import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import com.agrosystem.gestion.domain.shared.Pagina;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ListarCultivosCasoUso {

    private final RepositorioCultivo repositorio;

    public ListarCultivosCasoUso(RepositorioCultivo repositorio) {
        this.repositorio = repositorio;
    }

    @Transactional(readOnly = true)
    public Pagina<Cultivo> ejecutar(String filtroNombre, int pagina, int tamanio) {
        return repositorio.listar(filtroNombre, pagina, tamanio);
    }
}
