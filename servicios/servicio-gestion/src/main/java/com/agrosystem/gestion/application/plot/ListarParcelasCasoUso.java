package com.agrosystem.gestion.application.plot;

import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import com.agrosystem.gestion.domain.shared.Pagina;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ListarParcelasCasoUso {

    private final RepositorioParcela repositorio;

    public ListarParcelasCasoUso(RepositorioParcela repositorio) {
        this.repositorio = repositorio;
    }

    @Transactional(readOnly = true)
    public Pagina<Parcela> ejecutar(String filtroNombre, int pagina, int tamanio) {
        return repositorio.listar(filtroNombre, pagina, tamanio);
    }
}
