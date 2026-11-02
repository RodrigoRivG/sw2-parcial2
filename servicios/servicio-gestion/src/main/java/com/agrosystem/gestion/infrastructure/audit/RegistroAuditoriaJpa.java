package com.agrosystem.gestion.infrastructure.audit;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.infrastructure.persistence.RegistroAuditoriaSpringData;
import com.agrosystem.gestion.infrastructure.persistence.entity.RegistroAuditoriaEntidad;
import java.time.Clock;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Component
public class RegistroAuditoriaJpa implements RegistroAuditoria {

    private final RegistroAuditoriaSpringData repositorio;
    private final Clock reloj;

    public RegistroAuditoriaJpa(RegistroAuditoriaSpringData repositorio, Clock reloj) {
        this.repositorio = repositorio;
        this.reloj = reloj;
    }

    @Override
    @Transactional(propagation = Propagation.MANDATORY)
    public void registrar(AccionAuditoria accion, String entidad, UUID idEntidad) {
        registrarServicio(actorActual(), accion, entidad, idEntidad);
    }

    @Override
    @Transactional(propagation = Propagation.MANDATORY)
    public void registrarServicio(String actor, AccionAuditoria accion, String entidad, UUID idEntidad) {
        repositorio.save(new RegistroAuditoriaEntidad(
                UUID.randomUUID(),
                actor,
                accion.name(),
                entidad,
                idEntidad,
                MDC.get("idCorrelacion"),
                reloj.instant()));
    }

    private String actorActual() {
        Authentication autenticacion = SecurityContextHolder.getContext().getAuthentication();
        if (autenticacion == null || autenticacion instanceof AnonymousAuthenticationToken) {
            throw new IllegalStateException("No hay un usuario autenticado para auditar la acción");
        }
        return autenticacion.getName();
    }
}
