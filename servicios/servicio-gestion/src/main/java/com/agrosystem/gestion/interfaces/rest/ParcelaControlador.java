package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.application.plot.ActualizarParcelaCasoUso;
import com.agrosystem.gestion.application.plot.ConsultarParcelaCasoUso;
import com.agrosystem.gestion.application.plot.CrearParcelaCasoUso;
import com.agrosystem.gestion.application.plot.ListarParcelasCasoUso;
import com.agrosystem.gestion.domain.plot.Parcela;
import com.agrosystem.gestion.domain.shared.Pagina;
import com.agrosystem.gestion.interfaces.rest.dto.ActualizarParcelaSolicitud;
import com.agrosystem.gestion.interfaces.rest.dto.CrearParcelaSolicitud;
import com.agrosystem.gestion.interfaces.rest.dto.PaginaRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.ParcelaRespuesta;
import com.agrosystem.gestion.interfaces.rest.error.RespuestaError;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(ParcelaControlador.RUTA)
public class ParcelaControlador {

    static final String RUTA = "/api/gestion/v1/parcelas";

    private static final String PUEDE_LEER =
            "hasAnyRole('administrador', 'gerencia', 'tecnico_campo', 'lectura_gestion')";
    private static final String PUEDE_ESCRIBIR = "hasRole('administrador')";

    private final CrearParcelaCasoUso crear;
    private final ActualizarParcelaCasoUso actualizar;
    private final ConsultarParcelaCasoUso consultar;
    private final ListarParcelasCasoUso listar;

    public ParcelaControlador(
            CrearParcelaCasoUso crear,
            ActualizarParcelaCasoUso actualizar,
            ConsultarParcelaCasoUso consultar,
            ListarParcelasCasoUso listar) {
        this.crear = crear;
        this.actualizar = actualizar;
        this.consultar = consultar;
        this.listar = listar;
    }

    @PostMapping
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Registrar una parcela", responses = {
            @ApiResponse(responseCode = "201", description = "Parcela creada"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "NOMBRE_PARCELA_DUPLICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "SUPERFICIE_INVALIDA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ResponseEntity<ParcelaRespuesta> crear(@Valid @RequestBody CrearParcelaSolicitud solicitud) {
        Parcela parcela = crear.ejecutar(solicitud.aDatos());
        return ResponseEntity.created(URI.create(RUTA + "/" + parcela.getId())).body(ParcelaRespuesta.de(parcela));
    }

    @GetMapping
    @PreAuthorize(PUEDE_LEER)
    @Operation(summary = "Listar parcelas por nombre", responses = {
            @ApiResponse(responseCode = "200", description = "Página de parcelas"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public PaginaRespuesta<ParcelaRespuesta> listar(
            @RequestParam(required = false) String nombre,
            @RequestParam(required = false) Integer pagina,
            @RequestParam(required = false) Integer tamanio) {
        ParametrosPagina parametros = ParametrosPagina.de(pagina, tamanio);
        Pagina<Parcela> resultado = listar.ejecutar(nombre, parametros.pagina(), parametros.tamanio());
        return new PaginaRespuesta<>(
                resultado.items().stream().map(ParcelaRespuesta::de).toList(),
                parametros.pagina(),
                parametros.tamanio(),
                resultado.total());
    }

    @GetMapping("/{id}")
    @PreAuthorize(PUEDE_LEER)
    @Operation(summary = "Consultar una parcela", responses = {
            @ApiResponse(responseCode = "200", description = "Parcela"),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "PARCELA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ParcelaRespuesta consultar(@PathVariable UUID id) {
        return ParcelaRespuesta.de(consultar.ejecutar(id));
    }

    @PutMapping("/{id}")
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Modificar una parcela", responses = {
            @ApiResponse(responseCode = "200", description = "Parcela modificada"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "PARCELA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "NOMBRE_PARCELA_DUPLICADO o CONFLICTO_CONCURRENCIA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "SUPERFICIE_INVALIDA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ParcelaRespuesta actualizar(@PathVariable UUID id, @Valid @RequestBody ActualizarParcelaSolicitud solicitud) {
        return ParcelaRespuesta.de(actualizar.ejecutar(id, solicitud.aDatos(), solicitud.version()));
    }
}
