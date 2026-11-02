package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.infrastructure.persistence.entity.RegistroAuditoriaEntidad;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RegistroAuditoriaSpringData extends JpaRepository<RegistroAuditoriaEntidad, UUID> {
}
