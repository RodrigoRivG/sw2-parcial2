package com.agrosystem.gestion.application.crop;

import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConsultarCultivoCasoUso {

    private final RepositorioCultivo repositorio;

    public ConsultarCultivoCasoUso(RepositorioCultivo repositorio) {
        this.repositorio = repositorio;
    }

    @Transactional(readOnly = true)
    public Cultivo ejecutar(UUID id) {
        return repositorio.buscarPorId(id).orElseThrow(CultivoNoEncontrado::excepcion);
    }
}
