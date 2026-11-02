package com.agrosystem.gestion.infrastructure.persistence.mapper;

import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.agrosystem.gestion.infrastructure.persistence.entity.CultivoEntidad;

public final class MapeadorCultivo {

    private MapeadorCultivo() {
    }

    public static Cultivo aDominio(CultivoEntidad entidad) {
        return Cultivo.reconstruir(
                entidad.getId(),
                entidad.getNombre(),
                entidad.getVariedad(),
                UnidadProduccion.valueOf(entidad.getUnidadMedida()),
                entidad.getDescripcion(),
                entidad.getVersion(),
                entidad.getFechaCreacion(),
                entidad.getFechaActualizacion());
    }

    public static void copiarDatos(Cultivo cultivo, CultivoEntidad entidad) {
        entidad.actualizar(
                cultivo.getNombre(),
                cultivo.getVariedad(),
                cultivo.getDescripcion(),
                cultivo.getFechaActualizacion());
    }
}
