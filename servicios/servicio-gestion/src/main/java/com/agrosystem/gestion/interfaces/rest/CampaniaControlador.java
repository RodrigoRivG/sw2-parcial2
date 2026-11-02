package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.application.campaign.ActualizarCampaniaCasoUso;
import com.agrosystem.gestion.application.campaign.CambiarEstadoCampaniaCasoUso;
import com.agrosystem.gestion.application.campaign.ConsultarCampaniaCasoUso;
import com.agrosystem.gestion.application.campaign.CrearCampaniaCasoUso;
import com.agrosystem.gestion.application.campaign.ListarCampaniasCasoUso;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.FiltrosCampania;
import com.agrosystem.gestion.domain.shared.Pagina;
import com.agrosystem.gestion.interfaces.rest.dto.ActualizarCampaniaSolicitud;
import com.agrosystem.gestion.interfaces.rest.dto.CambiarEstadoCampaniaSolicitud;
import com.agrosystem.gestion.interfaces.rest.dto.CampaniaRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.CampaniaSinResumenRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.CrearCampaniaSolicitud;
import com.agrosystem.gestion.interfaces.rest.dto.PaginaRespuesta;
import com.agrosystem.gestion.interfaces.rest.error.RespuestaError;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import jakarta.validation.Valid;
import java.net.URI;
import java.time.LocalDate;
import java.util.Set;
import java.util.UUID;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(CampaniaControlador.RUTA)
public class CampaniaControlador {

    static final String RUTA = "/api/gestion/v1/campanias";

    private static final String PUEDE_LEER =
            "hasAnyRole('administrador', 'gerencia', 'lectura_gestion', 'tecnico_campo')";
    private static final String PUEDE_ESCRIBIR = "hasRole('administrador')";
    private static final Set<String> ROLES_VISTA_COMPLETA =
            Set.of("ROLE_administrador", "ROLE_gerencia", "ROLE_lectura_gestion");

    private final CrearCampaniaCasoUso crear;
    private final ActualizarCampaniaCasoUso actualizar;
    private final CambiarEstadoCampaniaCasoUso cambiarEstado;
    private final ConsultarCampaniaCasoUso consultar;
    private final ListarCampaniasCasoUso listar;

    public CampaniaControlador(
            CrearCampaniaCasoUso crear,
            ActualizarCampaniaCasoUso actualizar,
            CambiarEstadoCampaniaCasoUso cambiarEstado,
            ConsultarCampaniaCasoUso consultar,
            ListarCampaniasCasoUso listar) {
        this.crear = crear;
        this.actualizar = actualizar;
        this.cambiarEstado = cambiarEstado;
        this.consultar = consultar;
        this.listar = listar;
    }

    @PostMapping
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Crear una campaña", responses = {
            @ApiResponse(responseCode = "201", description = "Campaña creada"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "PARCELA_NO_ENCONTRADA o CULTIVO_NO_ENCONTRADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "FECHAS_INVALIDAS", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ResponseEntity<CampaniaRespuesta> crear(@Valid @RequestBody CrearCampaniaSolicitud solicitud) {
        Campania campania = crear.ejecutar(solicitud.aDatos());
        return ResponseEntity.created(URI.create(RUTA + "/" + campania.getId())).body(CampaniaRespuesta.de(campania));
    }

    @GetMapping
    @PreAuthorize(PUEDE_LEER)
    @Operation(summary = "Listar campañas con filtros", responses = {
            @ApiResponse(responseCode = "200", description = "Página de campañas, sin resumen"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public PaginaRespuesta<CampaniaSinResumenRespuesta> listar(
            @RequestParam(required = false) EstadoCampania estado,
            @RequestParam(required = false) UUID idParcela,
            @RequestParam(required = false) UUID idCultivo,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fechaInicioDesde,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fechaInicioHasta,
            @RequestParam(required = false) Integer pagina,
            @RequestParam(required = false) Integer tamanio,
            @Parameter(hidden = true) Authentication autenticacion) {
        ParametrosPagina parametros = ParametrosPagina.de(pagina, tamanio);
        FiltrosCampania filtros =
                new FiltrosCampania(estado, idParcela, idCultivo, fechaInicioDesde, fechaInicioHasta, false);
        Pagina<Campania> resultado = listar.ejecutar(
                filtros, esSoloTecnico(autenticacion), parametros.pagina(), parametros.tamanio());
        return new PaginaRespuesta<>(
                resultado.items().stream().map(CampaniaSinResumenRespuesta::de).toList(),
                parametros.pagina(),
                parametros.tamanio(),
                resultado.total());
    }

    @GetMapping("/{id}")
    @PreAuthorize(PUEDE_LEER)
    @Operation(summary = "Consultar una campaña", responses = {
            @ApiResponse(responseCode = "200", description = "Campaña; sin resumen para tecnico_campo", content = @Content(schema = @Schema(oneOf = {CampaniaRespuesta.class, CampaniaSinResumenRespuesta.class}))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public Object consultar(@PathVariable UUID id, @Parameter(hidden = true) Authentication autenticacion) {
        boolean soloTecnico = esSoloTecnico(autenticacion);
        Campania campania = consultar.ejecutar(id, soloTecnico);
        return soloTecnico ? CampaniaSinResumenRespuesta.de(campania) : CampaniaRespuesta.de(campania);
    }

    @PutMapping("/{id}")
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Modificar los datos de una campaña", responses = {
            @ApiResponse(responseCode = "200", description = "Campaña modificada"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA, PARCELA_NO_ENCONTRADA o CULTIVO_NO_ENCONTRADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CONFLICTO_CONCURRENCIA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "FECHAS_INVALIDAS, CAMPO_NO_MODIFICABLE o CAMPANIA_FINALIZADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public CampaniaRespuesta actualizar(@PathVariable UUID id, @Valid @RequestBody ActualizarCampaniaSolicitud solicitud) {
        return CampaniaRespuesta.de(actualizar.ejecutar(id, solicitud.aDatos(), solicitud.version()));
    }

    @PutMapping("/{id}/estado")
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Cambiar el estado de una campaña", responses = {
            @ApiResponse(responseCode = "200", description = "Campaña con su nuevo estado"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CONFLICTO_CONCURRENCIA o PARCELA_CON_CAMPANIA_EN_CURSO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "TRANSICION_ESTADO_INVALIDA o FINALIZACION_SIN_PRODUCCION", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public CampaniaRespuesta cambiarEstado(
            @PathVariable UUID id, @Valid @RequestBody CambiarEstadoCampaniaSolicitud solicitud) {
        return CampaniaRespuesta.de(cambiarEstado.ejecutar(id, solicitud.estadoDestino(), solicitud.version()));
    }

    private boolean esSoloTecnico(Authentication autenticacion) {
        return autenticacion.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .noneMatch(ROLES_VISTA_COMPLETA::contains);
    }
}
