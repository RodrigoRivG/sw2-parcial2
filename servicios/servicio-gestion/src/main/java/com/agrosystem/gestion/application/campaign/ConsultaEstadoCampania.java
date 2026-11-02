package com.agrosystem.gestion.application.campaign;

import java.util.Optional;
import java.util.UUID;

/** Puerto de lectura: solo los campos del estado resumido, sin cargar costos ni producción. */
public interface ConsultaEstadoCampania {

    Optional<EstadoResumidoCampania> buscar(UUID id);
}
