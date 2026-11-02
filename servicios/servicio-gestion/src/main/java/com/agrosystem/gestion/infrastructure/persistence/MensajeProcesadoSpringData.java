package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.infrastructure.persistence.entity.MensajeProcesadoEntidad;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MensajeProcesadoSpringData extends JpaRepository<MensajeProcesadoEntidad, UUID> {
}
