package com.agrosystem.gestion.application.port;

import java.util.UUID;

public interface RegistroAuditoria {

    /** Registra una acción de un usuario; toma el actor del contexto de seguridad. */
    void registrar(AccionAuditoria accion, String entidad, UUID idEntidad);

    /** Registra una acción de un servicio, por ejemplo un mensaje de la Saga. */
    void registrarServicio(String actor, AccionAuditoria accion, String entidad, UUID idEntidad);
}
