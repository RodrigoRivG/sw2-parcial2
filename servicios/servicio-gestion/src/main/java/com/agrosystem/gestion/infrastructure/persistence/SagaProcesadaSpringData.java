package com.agrosystem.gestion.infrastructure.persistence;

import com.agrosystem.gestion.infrastructure.persistence.entity.SagaProcesadaEntidad;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface SagaProcesadaSpringData extends JpaRepository<SagaProcesadaEntidad, UUID> {

    /** La subconsulta evita devolver el tipo void de PostgreSQL, que Hibernate no sabe leer. */
    @Query(value = "SELECT 1 FROM (SELECT pg_advisory_xact_lock(hashtext(CAST(:clave AS text)))) AS bloqueo",
            nativeQuery = true)
    Integer bloquear(@Param("clave") String clave);
}
