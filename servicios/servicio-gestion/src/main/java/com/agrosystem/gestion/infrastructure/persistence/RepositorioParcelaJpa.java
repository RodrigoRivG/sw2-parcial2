package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.plot.RepositorioParcela;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Pagina;
import com.agrosystem.gestion.infrastructure.persistence.entity.ParcelaEntidad;
import com.agrosystem.gestion.infrastructure.persistence.mapper.MapeadorParcela;
import java.util.Optional;
import java.util.UUID;
import org.springframework.core.NestedExceptionUtils;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Repository;

@Repository
public class RepositorioParcelaJpa implements RepositorioParcela {

    private static final String INDICE_NOMBRE = "ux_parcela_nombre";

    private final ParcelaSpringData springData;

    public RepositorioParcelaJpa(ParcelaSpringData springData) {
        this.springData = springData;
    }

    @Override
    public Parcela guardar(Parcela parcela) {
        ParcelaEntidad entidad = parcela.getVersion() == null
                ? new ParcelaEntidad(parcela.getId(), parcela.getFechaCreacion())
                : springData.findById(parcela.getId()).orElseThrow();
        MapeadorParcela.copiarDatos(parcela, entidad);
        try {
            return MapeadorParcela.aDominio(springData.saveAndFlush(entidad));
        } catch (DataIntegrityViolationException error) {
            if (violaIndiceNombre(error)) {
                throw new ExcepcionDominio(
                        "NOMBRE_PARCELA_DUPLICADO",
                        "Ya existe una parcela con ese nombre.",
                        ExcepcionDominio.Tipo.CONFLICTO);
            }
            throw error;
        }
    }

    private boolean violaIndiceNombre(DataIntegrityViolationException error) {
        String causa = NestedExceptionUtils.getMostSpecificCause(error).getMessage();
        return causa != null && causa.contains(INDICE_NOMBRE);
    }

    @Override
    public Optional<Parcela> buscarPorId(UUID id) {
        return springData.findById(id).map(MapeadorParcela::aDominio);
    }

    @Override
    public Pagina<Parcela> listar(String filtroNombre, int pagina, int tamanio) {
        PageRequest paginacion = PageRequest.of(pagina, tamanio, Sort.by("nombre"));
        Page<ParcelaEntidad> resultado = filtroNombre == null || filtroNombre.isBlank()
                ? springData.findAll(paginacion)
                : springData.findByNombreContainingIgnoreCase(filtroNombre.trim(), paginacion);
        return new Pagina<>(
                resultado.getContent().stream().map(MapeadorParcela::aDominio).toList(),
                resultado.getTotalElements());
    }
}
