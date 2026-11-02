package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.application.campaign.ConsultarProduccionCasoUso;
import com.agrosystem.gestion.application.campaign.RegistrarProduccionCasoUso;
import com.agrosystem.gestion.interfaces.rest.dto.ProduccionRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.SolicitudProduccion;
import com.agrosystem.gestion.interfaces.rest.error.RespuestaError;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/gestion/v1/campanias/{idCampania}/produccion")
public class ProduccionControlador {

    private final RegistrarProduccionCasoUso registrar;
    private final ConsultarProduccionCasoUso consultar;

    public ProduccionControlador(RegistrarProduccionCasoUso registrar, ConsultarProduccionCasoUso consultar) {
        this.registrar = registrar;
        this.consultar = consultar;
    }

    @PutMapping
    @PreAuthorize("hasRole('administrador')")
    @Operation(summary = "Registrar o corregir la producción de una campaña", responses = {
            @ApiResponse(responseCode = "200", description = "Producción registrada"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CONFLICTO_CONCURRENCIA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "PRODUCCION_INVALIDA, FECHA_COSECHA_INVALIDA, CAMPANIA_NO_EN_CURSO o CAMPANIA_FINALIZADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ProduccionRespuesta registrar(
            @PathVariable UUID idCampania,
            @Valid @RequestBody SolicitudProduccion solicitud,
            @Parameter(hidden = true) Authentication autenticacion) {
        return ProduccionRespuesta.de(registrar.ejecutar(idCampania, solicitud.aDatos(), autenticacion.getName()));
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('administrador', 'gerencia', 'lectura_gestion')")
    @Operation(summary = "Consultar la producción de una campaña", responses = {
            @ApiResponse(responseCode = "200", description = "Producción"),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA o PRODUCCION_NO_REGISTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ProduccionRespuesta consultar(@PathVariable UUID idCampania) {
        return ProduccionRespuesta.de(consultar.ejecutar(idCampania));
    }
}
