package com.agrosystem.gestion.application.plot;

import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConsultarParcelaCasoUso {

    private final RepositorioParcela repositorio;

    public ConsultarParcelaCasoUso(RepositorioParcela repositorio) {
        this.repositorio = repositorio;
    }

    @Transactional(readOnly = true)
    public Parcela ejecutar(UUID id) {
        return repositorio.buscarPorId(id).orElseThrow(ParcelaNoEncontrada::excepcion);
    }
}
