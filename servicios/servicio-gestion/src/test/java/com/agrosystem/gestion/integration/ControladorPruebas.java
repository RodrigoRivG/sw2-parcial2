package com.agrosystem.gestion.integration;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.interfaces.rest.ParametrosPagina;
import com.agrosystem.gestion.interfaces.rest.dto.PaginaRespuesta;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Profile;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Endpoints solo para tests: la Fase 0 todavía no tiene endpoints de negocio. */
@RestController
@Profile("test")
@RequestMapping("/api/gestion/v1/prueba")
class ControladorPruebas {

    private static final Logger LOG = LoggerFactory.getLogger(ControladorPruebas.class);

    record Decimal(@NotNull BigDecimal valor) {
    }

    record Fecha(@NotNull LocalDate fecha) {
    }

    @GetMapping("/autenticado")
    String autenticado() {
        LOG.info("Solicitud autenticada");
        return "ok";
    }

    @GetMapping("/administrador")
    @PreAuthorize("hasRole('administrador')")
    String administrador() {
        return "ok";
    }

    @PostMapping("/decimales")
    Decimal decimales(@Valid @RequestBody Decimal cuerpo) {
        return cuerpo;
    }

    @PostMapping("/fechas")
    Fecha fechas(@Valid @RequestBody Fecha cuerpo) {
        return cuerpo;
    }

    @GetMapping("/pagina")
    PaginaRespuesta<String> pagina(@RequestParam(required = false) Integer pagina,
                                   @RequestParam(required = false) Integer tamanio) {
        ParametrosPagina parametros = ParametrosPagina.de(pagina, tamanio);
        return new PaginaRespuesta<>(List.of("a"), parametros.pagina(), parametros.tamanio(), 1);
    }

    @GetMapping("/dominio/{tipo}")
    String dominio(@PathVariable ExcepcionDominio.Tipo tipo) {
        throw new ExcepcionDominio("CODIGO_PRUEBA", "Mensaje de prueba.", tipo);
    }

    @GetMapping("/concurrencia")
    String concurrencia() {
        throw new ObjectOptimisticLockingFailureException("Entidad", "id");
    }

    @GetMapping("/fallo")
    String fallo() {
        throw new IllegalStateException("detalle interno secreto");
    }
}
