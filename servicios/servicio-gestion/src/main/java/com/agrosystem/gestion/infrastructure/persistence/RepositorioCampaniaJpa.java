package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.FiltrosCampania;
import com.agrosystem.gestion.domain.campaign.OrigenCosto;
import com.agrosystem.gestion.domain.campaign.RepositorioCampania;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Pagina;
import com.agrosystem.gestion.infrastructure.persistence.entity.CampaniaEntidad;
import com.agrosystem.gestion.infrastructure.persistence.entity.CostoCampaniaEntidad;
import com.agrosystem.gestion.infrastructure.persistence.entity.ProduccionCampaniaEntidad;
import com.agrosystem.gestion.infrastructure.persistence.mapper.MapeadorCampania;
import jakarta.persistence.criteria.Predicate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.core.NestedExceptionUtils;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Repository;

@Repository
public class RepositorioCampaniaJpa implements RepositorioCampania {

    private static final String INDICE_EN_CURSO = "ux_campania_parcela_en_curso";

    private final CampaniaSpringData springData;
    private final CostoCampaniaSpringData costos;
    private final ProduccionCampaniaSpringData producciones;

    public RepositorioCampaniaJpa(
            CampaniaSpringData springData,
            CostoCampaniaSpringData costos,
            ProduccionCampaniaSpringData producciones) {
        this.springData = springData;
        this.costos = costos;
        this.producciones = producciones;
    }

    @Override
    public Campania guardar(Campania campania) {
        CampaniaEntidad entidad = campania.getVersion() == null
                ? new CampaniaEntidad(campania.getId(), campania.getFechaCreacion())
                : springData.findById(campania.getId()).orElseThrow();
        MapeadorCampania.copiarDatos(campania, entidad);
        try {
            CampaniaEntidad guardada = springData.saveAndFlush(entidad);
            return MapeadorCampania.aDominio(guardada, guardarProduccion(campania));
        } catch (DataIntegrityViolationException error) {
            if (violaIndiceEnCurso(error)) {
                throw new ExcepcionDominio(
                        "PARCELA_CON_CAMPANIA_EN_CURSO",
                        "La parcela ya tiene otra campaña en curso.",
                        ExcepcionDominio.Tipo.CONFLICTO);
            }
            throw error;
        }
    }

    /** La producción se guarda aparte: una relación 1 a 1 por clave compartida no se carga de forma diferida. */
    private ProduccionCampaniaEntidad guardarProduccion(Campania campania) {
        if (!campania.tieneProduccion()) {
            return null;
        }
        ProduccionCampaniaEntidad entidad = producciones.findById(campania.getId())
                .orElseGet(() -> new ProduccionCampaniaEntidad(campania.getId()));
        MapeadorCampania.copiarProduccion(campania.getProduccion(), entidad);
        return producciones.saveAndFlush(entidad);
    }

    private boolean violaIndiceEnCurso(DataIntegrityViolationException error) {
        String causa = NestedExceptionUtils.getMostSpecificCause(error).getMessage();
        return causa != null && causa.contains(INDICE_EN_CURSO);
    }

    @Override
    public Optional<Campania> buscarPorId(UUID id) {
        return springData.findById(id)
                .map(entidad -> MapeadorCampania.aDominio(entidad, producciones.findById(id).orElse(null)));
    }

    @Override
    public Pagina<Campania> listar(FiltrosCampania filtros, int pagina, int tamanio) {
        PageRequest paginacion = PageRequest.of(
                pagina, tamanio, Sort.by(Sort.Order.desc("fechaInicio"), Sort.Order.asc("id")));
        Page<CampaniaEntidad> resultado = springData.findAll(condiciones(filtros), paginacion);
        return new Pagina<>(
                resultado.getContent().stream().map(MapeadorCampania::aDominioResumido).toList(),
                resultado.getTotalElements());
    }

    /** Solo agrega las condiciones presentes: PostgreSQL no admite parámetros nulos sin tipo en JPQL. */
    private Specification<CampaniaEntidad> condiciones(FiltrosCampania filtros) {
        return (raiz, consulta, criterio) -> {
            List<Predicate> condiciones = new ArrayList<>();
            if (filtros.estado() != null) {
                condiciones.add(criterio.equal(raiz.get("estado"), filtros.estado().name()));
            }
            if (filtros.soloNoFinalizadas()) {
                condiciones.add(criterio.notEqual(raiz.get("estado"), EstadoCampania.FINALIZADA.name()));
            }
            if (filtros.idParcela() != null) {
                condiciones.add(criterio.equal(raiz.get("idParcela"), filtros.idParcela()));
            }
            if (filtros.idCultivo() != null) {
                condiciones.add(criterio.equal(raiz.get("idCultivo"), filtros.idCultivo()));
            }
            if (filtros.fechaInicioDesde() != null) {
                condiciones.add(criterio.greaterThanOrEqualTo(raiz.get("fechaInicio"), filtros.fechaInicioDesde()));
            }
            if (filtros.fechaInicioHasta() != null) {
                condiciones.add(criterio.lessThanOrEqualTo(raiz.get("fechaInicio"), filtros.fechaInicioHasta()));
            }
            return criterio.and(condiciones.toArray(Predicate[]::new));
        };
    }

    @Override
    public boolean existeEnCursoEnParcela(UUID idParcela) {
        return springData.existsByIdParcelaAndEstado(idParcela, EstadoCampania.EN_CURSO.name());
    }

    @Override
    public Pagina<CostoCampania> listarCostos(
            UUID idCampania, CategoriaCosto categoria, OrigenCosto origen, int pagina, int tamanio) {
        Specification<CostoCampaniaEntidad> condiciones = (raiz, consulta, criterio) -> {
            List<Predicate> lista = new ArrayList<>();
            lista.add(criterio.equal(raiz.get("idCampania"), idCampania));
            lista.add(criterio.isFalse(raiz.get("anulado")));
            if (categoria != null) {
                lista.add(criterio.equal(raiz.get("categoria"), categoria.name()));
            }
            if (origen != null) {
                lista.add(criterio.equal(raiz.get("origen"), origen.name()));
            }
            return criterio.and(lista.toArray(Predicate[]::new));
        };
        PageRequest paginacion = PageRequest.of(pagina, tamanio, Sort.by(
                Sort.Order.desc("fecha"), Sort.Order.desc("fechaRegistro"), Sort.Order.asc("id")));
        Page<CostoCampaniaEntidad> resultado = costos.findAll(condiciones, paginacion);
        return new Pagina<>(
                resultado.getContent().stream().map(MapeadorCampania::costoADominio).toList(),
                resultado.getTotalElements());
    }
}
