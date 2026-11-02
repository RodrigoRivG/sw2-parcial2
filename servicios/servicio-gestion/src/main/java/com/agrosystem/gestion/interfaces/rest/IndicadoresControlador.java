package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.application.campaign.ConsultarIndicadoresCasoUso;
import com.agrosystem.gestion.interfaces.rest.dto.IndicadoresRespuesta;
import com.agrosystem.gestion.interfaces.rest.error.RespuestaError;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import java.util.UUID;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class IndicadoresControlador {

    private final ConsultarIndicadoresCasoUso consultar;

    public IndicadoresControlador(ConsultarIndicadoresCasoUso consultar) {
        this.consultar = consultar;
    }

    @GetMapping("/api/gestion/v1/campanias/{idCampania}/indicadores")
    @PreAuthorize("hasAnyRole('administrador', 'gerencia', 'lectura_gestion')")
    @Operation(summary = "Consultar el rendimiento y el costo por hectárea de una campaña", responses = {
            @ApiResponse(responseCode = "200", description = "Indicadores; sin datos suficientes son null con su motivo"),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public IndicadoresRespuesta consultar(@PathVariable UUID idCampania) {
        return IndicadoresRespuesta.de(consultar.ejecutar(idCampania));
    }
}
