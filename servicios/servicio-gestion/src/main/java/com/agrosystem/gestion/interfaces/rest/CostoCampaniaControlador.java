package com.agrosystem.gestion.interfaces.rest;

import com.agrosystem.gestion.application.campaign.EliminarCostoManualCasoUso;
import com.agrosystem.gestion.application.campaign.ListarCostosCasoUso;
import com.agrosystem.gestion.application.campaign.ModificarCostoManualCasoUso;
import com.agrosystem.gestion.application.campaign.RegistrarCostoManualCasoUso;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.OrigenCosto;
import com.agrosystem.gestion.interfaces.rest.dto.CostoRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.CostosCampaniaRespuesta;
import com.agrosystem.gestion.interfaces.rest.dto.SolicitudCosto;
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
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/gestion/v1/campanias/{idCampania}/costos")
public class CostoCampaniaControlador {

    private static final String PUEDE_LEER = "hasAnyRole('administrador', 'gerencia', 'lectura_gestion')";
    private static final String PUEDE_ESCRIBIR = "hasRole('administrador')";

    private final RegistrarCostoManualCasoUso registrar;
    private final ModificarCostoManualCasoUso modificar;
    private final EliminarCostoManualCasoUso eliminar;
    private final ListarCostosCasoUso listar;

    public CostoCampaniaControlador(
            RegistrarCostoManualCasoUso registrar,
            ModificarCostoManualCasoUso modificar,
            EliminarCostoManualCasoUso eliminar,
            ListarCostosCasoUso listar) {
        this.registrar = registrar;
        this.modificar = modificar;
        this.eliminar = eliminar;
        this.listar = listar;
    }

    @PostMapping
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Registrar un costo manual", responses = {
            @ApiResponse(responseCode = "201", description = "Costo registrado"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CONFLICTO_CONCURRENCIA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "MONTO_INVALIDO, FECHA_COSTO_INVALIDA o CAMPANIA_FINALIZADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ResponseEntity<CostoRespuesta> registrar(
            @PathVariable UUID idCampania, @Valid @RequestBody SolicitudCosto solicitud) {
        CostoCampania costo = registrar.ejecutar(idCampania, solicitud.aDatos());
        URI ubicacion = URI.create("/api/gestion/v1/campanias/" + idCampania + "/costos/" + costo.getId());
        return ResponseEntity.created(ubicacion).body(CostoRespuesta.de(costo));
    }

    @GetMapping
    @PreAuthorize(PUEDE_LEER)
    @Operation(summary = "Listar los costos de una campaña, con totales", responses = {
            @ApiResponse(responseCode = "200", description = "Página de costos con los totales de la campaña"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public CostosCampaniaRespuesta listar(
            @PathVariable UUID idCampania,
            @RequestParam(required = false) CategoriaCosto categoria,
            @RequestParam(required = false) OrigenCosto origen,
            @RequestParam(required = false) Integer pagina,
            @RequestParam(required = false) Integer tamanio) {
        ParametrosPagina parametros = ParametrosPagina.de(pagina, tamanio);
        return CostosCampaniaRespuesta.de(
                listar.ejecutar(idCampania, categoria, origen, parametros.pagina(), parametros.tamanio()),
                parametros.pagina(),
                parametros.tamanio());
    }

    @PutMapping("/{idCosto}")
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Modificar un costo manual", responses = {
            @ApiResponse(responseCode = "200", description = "Costo modificado"),
            @ApiResponse(responseCode = "400", description = "DATOS_INVALIDOS", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA o COSTO_NO_ENCONTRADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CONFLICTO_CONCURRENCIA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "MONTO_INVALIDO, FECHA_COSTO_INVALIDA, CAMPANIA_FINALIZADA o COSTO_NO_EDITABLE", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public CostoRespuesta modificar(
            @PathVariable UUID idCampania, @PathVariable UUID idCosto, @Valid @RequestBody SolicitudCosto solicitud) {
        return CostoRespuesta.de(modificar.ejecutar(idCampania, idCosto, solicitud.aDatos()));
    }

    @DeleteMapping("/{idCosto}")
    @PreAuthorize(PUEDE_ESCRIBIR)
    @Operation(summary = "Eliminar un costo manual", responses = {
            @ApiResponse(responseCode = "204", description = "Costo eliminado"),
            @ApiResponse(responseCode = "401", description = "NO_AUTENTICADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "403", description = "SIN_PERMISO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "404", description = "CAMPANIA_NO_ENCONTRADA o COSTO_NO_ENCONTRADO", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "409", description = "CONFLICTO_CONCURRENCIA", content = @Content(schema = @Schema(implementation = RespuestaError.class))),
            @ApiResponse(responseCode = "422", description = "CAMPANIA_FINALIZADA o COSTO_NO_EDITABLE", content = @Content(schema = @Schema(implementation = RespuestaError.class)))
    })
    public ResponseEntity<Void> eliminar(@PathVariable UUID idCampania, @PathVariable UUID idCosto) {
        eliminar.ejecutar(idCampania, idCosto);
        return ResponseEntity.noContent().build();
    }
}
