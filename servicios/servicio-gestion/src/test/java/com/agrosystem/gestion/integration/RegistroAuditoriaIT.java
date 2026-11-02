package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.agrosystem.gestion.application.port.AccionAuditoria;
import com.agrosystem.gestion.application.port.RegistroAuditoria;
import com.agrosystem.gestion.infrastructure.persistence.RegistroAuditoriaSpringData;
import com.agrosystem.gestion.infrastructure.persistence.entity.RegistroAuditoriaEntidad;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.authentication.TestingAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.transaction.IllegalTransactionStateException;
import org.springframework.transaction.support.TransactionTemplate;

class RegistroAuditoriaIT extends PruebaIntegracionBase {

    @Autowired
    private RegistroAuditoria auditoria;

    @Autowired
    private RegistroAuditoriaSpringData repositorio;

    @Autowired
    private TransactionTemplate transaccion;

    @AfterEach
    void limpiar() {
        SecurityContextHolder.clearContext();
        MDC.clear();
    }

    private RegistroAuditoriaEntidad buscar(UUID idEntidad) {
        return repositorio.findAll().stream()
                .filter(registro -> registro.getIdEntidad().equals(idEntidad))
                .findFirst()
                .orElseThrow();
    }

    @Test
    void registraAlUsuarioDelTokenConSuIdCorrelacion() {
        UUID idEntidad = UUID.randomUUID();
        SecurityContextHolder.getContext().setAuthentication(new TestingAuthenticationToken("usuario-1", "n/a"));
        MDC.put("idCorrelacion", "correlacion-1");

        transaccion.executeWithoutResult(estado ->
                auditoria.registrar(AccionAuditoria.CREAR, "PARCELA", idEntidad));

        RegistroAuditoriaEntidad registro = buscar(idEntidad);
        assertThat(registro.getActor()).isEqualTo("usuario-1");
        assertThat(registro.getAccion()).isEqualTo("CREAR");
        assertThat(registro.getEntidad()).isEqualTo("PARCELA");
        assertThat(registro.getIdCorrelacion()).isEqualTo("correlacion-1");
        assertThat(registro.getFecha()).isNotNull();
    }

    @Test
    void registraAlServicioIndicado() {
        UUID idEntidad = UUID.randomUUID();

        transaccion.executeWithoutResult(estado -> auditoria.registrarServicio(
                "servicio-operaciones", AccionAuditoria.REGISTRAR_COSTO_SAGA, "COSTO_CAMPANIA", idEntidad));

        assertThat(buscar(idEntidad).getActor()).isEqualTo("servicio-operaciones");
    }

    @Test
    void sinUsuarioAutenticadoFalla() {
        assertThatThrownBy(() -> transaccion.executeWithoutResult(estado ->
                auditoria.registrar(AccionAuditoria.CREAR, "PARCELA", UUID.randomUUID())))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void exigeUnaTransaccionAbierta() {
        assertThatThrownBy(() -> auditoria.registrarServicio(
                "servicio-operaciones", AccionAuditoria.CREAR, "PARCELA", UUID.randomUUID()))
                .isInstanceOf(IllegalTransactionStateException.class);
    }

    @Test
    void siLaTransaccionFallaNoQuedaRegistro() {
        UUID idEntidad = UUID.randomUUID();

        assertThatThrownBy(() -> transaccion.executeWithoutResult(estado -> {
            auditoria.registrarServicio("servicio", AccionAuditoria.CREAR, "PARCELA", idEntidad);
            throw new IllegalStateException("fallo del caso de uso");
        })).isInstanceOf(IllegalStateException.class);

        assertThat(repositorio.findAll()).noneMatch(registro -> registro.getIdEntidad().equals(idEntidad));
    }
}
