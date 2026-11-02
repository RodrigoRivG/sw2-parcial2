package com.agrosystem.gestion.infrastructure.persistence.mapper;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.OrigenCosto;
import com.agrosystem.gestion.domain.campaign.ProduccionCampania;
import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.Hectareas;
import com.agrosystem.gestion.infrastructure.persistence.entity.CampaniaEntidad;
import com.agrosystem.gestion.infrastructure.persistence.entity.CostoCampaniaEntidad;
import com.agrosystem.gestion.infrastructure.persistence.entity.ProduccionCampaniaEntidad;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

public final class MapeadorCampania {

    private MapeadorCampania() {
    }

    public static Campania aDominio(CampaniaEntidad entidad, ProduccionCampaniaEntidad produccion) {
        return aDominio(
                entidad,
                entidad.getCostos().stream().map(MapeadorCampania::costoADominio).toList(),
                produccion == null ? null : produccionADominio(produccion));
    }

    /** Para listados: evita cargar los costos y la producción de cada campaña. */
    public static Campania aDominioResumido(CampaniaEntidad entidad) {
        return aDominio(entidad, List.of(), null);
    }

    private static Campania aDominio(CampaniaEntidad entidad, List<CostoCampania> costos, ProduccionCampania produccion) {
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
                entidad.getFechaActualizacion(),
                costos,
                produccion);
    }

    private static ProduccionCampania produccionADominio(ProduccionCampaniaEntidad entidad) {
        return new ProduccionCampania(
                entidad.getCantidad(),
                UnidadProduccion.valueOf(entidad.getUnidad()),
                entidad.getFechaCosecha(),
                entidad.getObservaciones(),
                entidad.getFechaRegistro(),
                entidad.getUsuarioRegistro());
    }

    public static void copiarProduccion(ProduccionCampania produccion, ProduccionCampaniaEntidad entidad) {
        entidad.actualizar(
                produccion.cantidad(),
                produccion.unidad().name(),
                produccion.fechaCosecha(),
                produccion.observaciones(),
                produccion.fechaRegistro(),
                produccion.usuarioRegistro());
    }

    public static CostoCampania costoADominio(CostoCampaniaEntidad entidad) {
        return CostoCampania.reconstruir(
                entidad.getId(),
                CategoriaCosto.valueOf(entidad.getCategoria()),
                new Dinero(entidad.getMonto()),
                entidad.getFecha(),
                entidad.getDescripcion(),
                OrigenCosto.valueOf(entidad.getOrigen()),
                entidad.getIdSaga(),
                entidad.getIdLabor(),
                entidad.isAnulado(),
                entidad.getFechaAnulacion(),
                entidad.getFechaRegistro());
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
        copiarCostos(campania, entidad);
    }

    private static void copiarCostos(Campania campania, CampaniaEntidad entidad) {
        Set<UUID> vigentes = campania.getCostos().stream().map(CostoCampania::getId).collect(Collectors.toSet());
        entidad.getCostos().removeIf(costo -> !vigentes.contains(costo.getId()));
        Map<UUID, CostoCampaniaEntidad> existentes = entidad.getCostos().stream()
                .collect(Collectors.toMap(CostoCampaniaEntidad::getId, Function.identity()));
        for (CostoCampania costo : campania.getCostos()) {
            CostoCampaniaEntidad destino = existentes.get(costo.getId());
            if (destino == null) {
                destino = new CostoCampaniaEntidad(
                        costo.getId(), costo.getOrigen().name(), costo.getIdSaga(), costo.getIdLabor(), costo.getFechaRegistro());
                entidad.getCostos().add(destino);
            }
            destino.actualizar(
                    costo.getCategoria().name(),
                    costo.getMonto().valor(),
                    costo.getFecha(),
                    costo.getDescripcion(),
                    costo.isAnulado(),
                    costo.getFechaAnulacion());
        }
    }
}
