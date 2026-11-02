package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.infrastructure.persistence.entity.ParcelaEntidad;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ParcelaSpringData extends JpaRepository<ParcelaEntidad, UUID> {

    Page<ParcelaEntidad> findByNombreContainingIgnoreCase(String nombre, Pageable paginacion);
}
