package com.agrosystem.gestion.infrastructure.persistence.mapper;

import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.shared.Hectareas;
import com.agrosystem.gestion.infrastructure.persistence.entity.ParcelaEntidad;

public final class MapeadorParcela {

    private MapeadorParcela() {
    }

    public static Parcela aDominio(ParcelaEntidad entidad) {
        return Parcela.reconstruir(
                entidad.getId(),
                entidad.getNombre(),
                new Hectareas(entidad.getSuperficieHectareas()),
                entidad.getUbicacion(),
                entidad.getDescripcion(),
                entidad.getVersion(),
                entidad.getFechaCreacion(),
                entidad.getFechaActualizacion());
    }

    public static void copiarDatos(Parcela parcela, ParcelaEntidad entidad) {
        entidad.actualizar(
                parcela.getNombre(),
                parcela.getSuperficie().valor(),
                parcela.getUbicacion(),
                parcela.getDescripcion(),
                parcela.getFechaActualizacion());
    }
}
