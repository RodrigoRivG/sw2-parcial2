package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.infrastructure.persistence.entity.CultivoEntidad;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CultivoSpringData extends JpaRepository<CultivoEntidad, UUID> {

    Page<CultivoEntidad> findByNombreContainingIgnoreCase(String nombre, Pageable paginacion);
}
