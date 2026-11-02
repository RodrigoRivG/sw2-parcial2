package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import java.time.Instant;
import java.util.UUID;

public record CultivoRespuesta(
        UUID id,
        String nombre,
        String variedad,
        UnidadProduccion unidadMedida,
        String descripcion,
        Long version,
        Instant fechaCreacion,
        Instant fechaActualizacion) {

    public static CultivoRespuesta de(Cultivo cultivo) {
        return new CultivoRespuesta(
                cultivo.getId(),
                cultivo.getNombre(),
                cultivo.getVariedad(),
                cultivo.getUnidadMedida(),
                cultivo.getDescripcion(),
                cultivo.getVersion(),
                cultivo.getFechaCreacion(),
                cultivo.getFechaActualizacion());
    }
}
