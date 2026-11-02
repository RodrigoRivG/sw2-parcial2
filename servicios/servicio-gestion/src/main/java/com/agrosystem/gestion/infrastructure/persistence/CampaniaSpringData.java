package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.infrastructure.persistence.entity.CampaniaEntidad;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface CampaniaSpringData
        extends JpaRepository<CampaniaEntidad, UUID>, JpaSpecificationExecutor<CampaniaEntidad> {

    boolean existsByIdParcelaAndEstado(UUID idParcela, String estado);
}
