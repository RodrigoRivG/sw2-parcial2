package com.agrosystem.gestion.infrastructure.persistence.mapper;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.shared.Hectareas;
import com.agrosystem.gestion.infrastructure.persistence.entity.CampaniaEntidad;

public final class MapeadorCampania {

    private MapeadorCampania() {
    }

    public static Campania aDominio(CampaniaEntidad entidad) {
        return Campania.reconstruir(
                entidad.getId(),
                entidad.getNombre(),
                entidad.getIdParcela(),
                entidad.getIdCultivo(),
                entidad.getFechaInicio(),
                entidad.getFechaFin(),
                new Hectareas(entidad.getSuperficieHectareas()),
                EstadoCampania.valueOf(entidad.getEstado()),
                entidad.getFechaInicioEjecucion(),
                entidad.getFechaFinalizacion(),
                entidad.getVersion(),
                entidad.getFechaCreacion(),
                entidad.getFechaActualizacion());
    }

    public static void copiarDatos(Campania campania, CampaniaEntidad entidad) {
        entidad.actualizar(
                campania.getNombre(),
                campania.getIdParcela(),
                campania.getIdCultivo(),
                campania.getFechaInicio(),
                campania.getFechaFin(),
                campania.getSuperficie().valor(),
                campania.getEstado().name(),
                campania.getFechaInicioEjecucion(),
                campania.getFechaFinalizacion(),
                campania.getFechaActualizacion());
    }
}
