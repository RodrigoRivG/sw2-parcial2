package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.application.crop.ActualizarCultivoCasoUso;
import com.agrosystem.gestion.application.crop.ConsultarCultivoCasoUso;
import com.agrosystem.gestion.application.crop.CrearCultivoCasoUso;
import com.agrosystem.gestion.application.crop.ListarCultivosCasoUso;
import com.agrosystem.gestion.domain.crop.Cultivo;
import com.agrosystem.gestion.domain.shared.Pagina;
import com.agrosystem.gestion.interfaces.rest.dto.ActualizarCultivoSolicitud;
import com.agrosystem.gestion.interfaces.rest.dto.CrearCultivoSolicitud;
import com.agrosystem.gestion.interfaces.rest.dto.CultivoRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.PaginaRespuesta;
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
@RequestMapping(CultivoControlador.RUTA)
public class CultivoControlador {

    static final String RUTA = "/api/gestion/v1/cultivos";

    private static final String PUEDE_LEER = "hasAnyRole('administrador', 'gerencia', 'lectura_gestion')";
    private static final String PUEDE_ESCRIBIR = "hasRole('administrador')";

    private final CrearCultivoCasoUso crear;
    private final ActualizarCultivoCasoUso actualizar;
    private final ConsultarCultivoCasoUso consultar;
    private final ListarCultivosCasoUso listar;

    public CultivoControlador(
            CrearCultivoCasoUso crear,
            ActualizarCultivoCasoUso actualizar,
            ConsultarCultivoCasoUso consultar,
            ListarCultivosCasoUso listar) {
        this.crear = crear;
        this.actualizar = actualizar;
        this.consultar = consultar;
        this.listar = listar;
    }

    @PostMapping
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Registrar un cultivo", responses = {
            @ApiResponse(responseCode = "201", description = "Cultivo creado"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CULTIVO_DUPLICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ResponseEntity<CultivoRespuesta> crear(@Valid @RequestBody CrearCultivoSolicitud solicitud) {
        Cultivo cultivo = crear.ejecutar(solicitud.aDatos());
        return ResponseEntity.created(URI.create(RUTA + "/" + cultivo.getId())).body(CultivoRespuesta.de(cultivo));
    }

    @GetMapping
    @PreAuthorize(PUEDE_LEER)
    @Operation(summary = "Listar cultivos por nombre", responses = {
            @ApiResponse(responseCode = "200", description = "Página de cultivos"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public PaginaRespuesta<CultivoRespuesta> listar(
            @RequestParam(required = false) String nombre,
            @RequestParam(required = false) Integer pagina,
            @RequestParam(required = false) Integer tamanio) {
        ParametrosPagina parametros = ParametrosPagina.de(pagina, tamanio);
        Pagina<Cultivo> resultado = listar.ejecutar(nombre, parametros.pagina(), parametros.tamanio());
        return new PaginaRespuesta<>(
                resultado.items().stream().map(CultivoRespuesta::de).toList(),
                parametros.pagina(),
                parametros.tamanio(),
                resultado.total());
    }

    @GetMapping("/{id}")
    @PreAuthorize(PUEDE_LEER)
    @Operation(summary = "Consultar un cultivo", responses = {
            @ApiResponse(responseCode = "200", description = "Cultivo"),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CULTIVO_NO_ENCONTRADO", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public CultivoRespuesta consultar(@PathVariable UUID id) {
        return CultivoRespuesta.de(consultar.ejecutar(id));
    }

    @PutMapping("/{id}")
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Modificar un cultivo", responses = {
            @ApiResponse(responseCode = "200", description = "Cultivo modificado"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CULTIVO_NO_ENCONTRADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CULTIVO_DUPLICADO o CONFLICTO_CONCURRENCIA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public CultivoRespuesta actualizar(@PathVariable UUID id, @Valid @RequestBody ActualizarCultivoSolicitud solicitud) {
        return CultivoRespuesta.de(actualizar.ejecutar(id, solicitud.aDatos(), solicitud.version()));
    }
}
