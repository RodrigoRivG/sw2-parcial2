package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.infrastructure.persistence.entity.CostoCampaniaEntidad;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface CostoCampaniaSpringData
        extends JpaRepository<CostoCampaniaEntidad, UUID>, JpaSpecificationExecutor<CostoCampaniaEntidad> {
}
