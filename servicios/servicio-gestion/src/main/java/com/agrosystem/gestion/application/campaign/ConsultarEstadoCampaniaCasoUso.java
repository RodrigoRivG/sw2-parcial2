package com.agrosystem.gestion.application.campaign;

import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConsultarEstadoCampaniaCasoUso {

    private final ConsultaEstadoCampania consulta;

    public ConsultarEstadoCampaniaCasoUso(ConsultaEstadoCampania consulta) {
        this.consulta = consulta;
    }

    @Transactional(readOnly = true)
    public EstadoResumidoCampania ejecutar(UUID id) {
        return consulta.buscar(id).orElseThrow(ErroresCampania::noEncontrada);
    }
}
