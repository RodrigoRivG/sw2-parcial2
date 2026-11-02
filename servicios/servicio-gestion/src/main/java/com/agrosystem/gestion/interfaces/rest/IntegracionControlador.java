package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.application.campaign.ConsultarEstadoCampaniaCasoUso;
import com.agrosystem.gestion.application.campaign.EstadoResumidoCampania;
import com.agrosystem.gestion.application.campaign.FiltrosHistoricos;
import com.agrosystem.gestion.application.campaign.ListarHistoricosCasoUso;
import com.agrosystem.gestion.application.campaign.RegistroHistorico;
import com.agrosystem.gestion.domain.shared.Pagina;
import com.agrosystem.gestion.interfaces.rest.dto.HistoricoRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.PaginaRespuesta;
import com.agrosystem.gestion.interfaces.rest.error.RespuestaError;
import com.agrosystem.gestion.interfaces.rest.error.SolicitudInvalidaExcepcion;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import java.time.LocalDate;
import java.util.UUID;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Consultas de solo lectura para otros servicios; no generan auditoría (RQ-INT-05). */
@RestController
@RequestMapping("/api/gestion/v1/campanias")
public class IntegracionControlador {

    private static final int TAMANIO_MAXIMO_HISTORICOS = 500;

    private final ConsultarEstadoCampaniaCasoUso consultarEstado;
    private final ListarHistoricosCasoUso listarHistoricos;

    public IntegracionControlador(
            ConsultarEstadoCampaniaCasoUso consultarEstado, ListarHistoricosCasoUso listarHistoricos) {
        this.consultarEstado = consultarEstado;
        this.listarHistoricos = listarHistoricos;
    }

    @GetMapping("/{id}/estado")
    @PreAuthorize("hasRole('estado_campania')")
    @Operation(summary = "Consultar el estado resumido de una campaña", responses = {
            @ApiResponse(responseCode = "200", description = "Estado resumido"),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public EstadoResumidoCampania consultarEstado(@PathVariable UUID id) {
        return consultarEstado.ejecutar(id);
    }

    @GetMapping("/historicos")
    @PreAuthorize("hasRole('lectura_gestion')")
    @Operation(summary = "Listar los datos históricos de las campañas finalizadas", responses = {
            @ApiResponse(responseCode = "200", description = "Página de históricos; máximo 500 por página"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public PaginaRespuesta<HistoricoRespuesta> listarHistoricos(
            @RequestParam(required = false) UUID idCultivo,
            @RequestParam(required = false) UUID idParcela,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fechaFinalizacionDesde,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fechaFinalizacionHasta,
            @RequestParam(required = false) Integer pagina,
            @RequestParam(required = false) Integer tamanio) {
        if (fechaFinalizacionDesde != null
                && fechaFinalizacionHasta != null
                && fechaFinalizacionDesde.isAfter(fechaFinalizacionHasta)) {
            throw new SolicitudInvalidaExcepcion(
                    "fechaFinalizacionDesde", "No puede ser posterior a fechaFinalizacionHasta.");
        }
        ParametrosPagina parametros = ParametrosPagina.de(pagina, tamanio, TAMANIO_MAXIMO_HISTORICOS);
        Pagina<RegistroHistorico> resultado = listarHistoricos.ejecutar(
                new FiltrosHistoricos(idCultivo, idParcela, fechaFinalizacionDesde, fechaFinalizacionHasta),
                parametros.pagina(),
                parametros.tamanio());
        return new PaginaRespuesta<>(
                resultado.items().stream().map(HistoricoRespuesta::de).toList(),
                parametros.pagina(),
                parametros.tamanio(),
                resultado.total());
    }
}
