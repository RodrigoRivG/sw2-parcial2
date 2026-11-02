package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.crop.RepositorioCultivo;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Pagina;
import com.agrosystem.gestion.infrastructure.persistence.entity.CultivoEntidad;
import com.agrosystem.gestion.infrastructure.persistence.mapper.MapeadorCultivo;
import java.util.Optional;
import java.util.UUID;
import org.springframework.core.NestedExceptionUtils;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Repository;

@Repository
public class RepositorioCultivoJpa implements RepositorioCultivo {

    private static final String INDICE_NOMBRE_VARIEDAD = "ux_cultivo_nombre_variedad";

    private final CultivoSpringData springData;

    public RepositorioCultivoJpa(CultivoSpringData springData) {
        this.springData = springData;
    }

    @Override
    public Cultivo guardar(Cultivo cultivo) {
        CultivoEntidad entidad = cultivo.getVersion() == null
                ? new CultivoEntidad(cultivo.getId(), cultivo.getUnidadMedida().name(), cultivo.getFechaCreacion())
                : springData.findById(cultivo.getId()).orElseThrow();
        MapeadorCultivo.copiarDatos(cultivo, entidad);
        try {
            return MapeadorCultivo.aDominio(springData.saveAndFlush(entidad));
        } catch (DataIntegrityViolationException error) {
            if (violaIndiceNombreVariedad(error)) {
                throw new ExcepcionDominio(
                        "CULTIVO_DUPLICADO",
                        "Ya existe un cultivo con ese nombre y variedad.",
                        ExcepcionDominio.Tipo.CONFLICTO);
            }
            throw error;
        }
    }

    private boolean violaIndiceNombreVariedad(DataIntegrityViolationException error) {
        String causa = NestedExceptionUtils.getMostSpecificCause(error).getMessage();
        return causa != null && causa.contains(INDICE_NOMBRE_VARIEDAD);
    }

    @Override
    public Optional<Cultivo> buscarPorId(UUID id) {
        return springData.findById(id).map(MapeadorCultivo::aDominio);
    }

    @Override
    public Pagina<Cultivo> listar(String filtroNombre, int pagina, int tamanio) {
        PageRequest paginacion = PageRequest.of(pagina, tamanio, Sort.by("nombre", "variedad"));
        Page<CultivoEntidad> resultado = filtroNombre == null || filtroNombre.isBlank()
                ? springData.findAll(paginacion)
                : springData.findByNombreContainingIgnoreCase(filtroNombre.trim(), paginacion);
        return new Pagina<>(
                resultado.getContent().stream().map(MapeadorCultivo::aDominio).toList(),
                resultado.getTotalElements());
    }
}
