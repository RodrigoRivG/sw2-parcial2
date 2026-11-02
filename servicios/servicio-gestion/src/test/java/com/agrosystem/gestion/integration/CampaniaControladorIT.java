package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.RegistroAuditoriaSpringData;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;

class CampaniaControladorIT extends CampaniaPruebaBase {

    @Autowired
    private RegistroAuditoriaSpringData auditoria;

    private ResultActions crear(String cuerpo, String rol) throws Exception {
        return mockMvc.perform(post(RUTA).with(conRol(rol))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    private ResultActions modificar(String id, String cuerpo) throws Exception {
        return mockMvc.perform(put(RUTA + "/" + id).with(conRol("administrador"))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpo));
    }

    private ResultActions cambiarEstado(String id, String destino, long version) throws Exception {
        return mockMvc.perform(put(RUTA + "/" + id + "/estado").with(conRol("administrador"))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpoEstado(destino, version)));
    }

    private void verificarAuditoria(String id, String accion) {
        assertThat(auditoria.findAll())
                .filteredOn(registro -> registro.getIdEntidad().equals(UUID.fromString(id)))
                .filteredOn(registro -> registro.getAccion().equals(accion))
                .hasSize(1)
                .first()
                .satisfies(registro -> {
                    assertThat(registro.getActor()).isEqualTo("usuario-administrador");
                    assertThat(registro.getEntidad()).isEqualTo("CAMPANIA");
                });
    }

    private void esperarError(ResultActions resultado, int estado, String codigo) throws Exception {
        resultado.andExpect(status().is(estado)).andExpect(jsonPath("$.codigo").value(codigo));
    }

    // Historia 1

    @Test
    void administradorCreaUnaCampaniaPlanificadaConLaSuperficieDeLaParcela() throws Exception {
        String respuesta = crear(cuerpo("Soya verano 2026-2027", idParcela, idCultivo, INICIO, FIN), "administrador")
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", containsString("/api/gestion/v1/campanias/")))
                .andExpect(jsonPath("$.estado").value("PLANIFICADA"))
                .andExpect(jsonPath("$.superficieHectareas").value("25.5000"))
                .andExpect(jsonPath("$.fechaInicio").value(INICIO))
                .andExpect(jsonPath("$.fechaFin").value(FIN))
                .andExpect(jsonPath("$.fechaInicioEjecucion").value(nullValue()))
                .andExpect(jsonPath("$.resumen.costoTotal").value("0.00"))
                .andExpect(jsonPath("$.resumen.cantidadCostos").value(0))
                .andExpect(jsonPath("$.resumen.produccion").value(nullValue()))
                .andExpect(jsonPath("$.version").value(0))
                .andReturn().getResponse().getContentAsString();

        verificarAuditoria(mapeador.readTree(respuesta).get("id").asText(), "CREAR");
    }

    @ParameterizedTest
    @ValueSource(strings = {"2026-11-15", "2026-11-14"})
    void fechaDeFinIgualOAnteriorSeRechaza(String fin) throws Exception {
        esperarError(crear(cuerpo("Soya", idParcela, idCultivo, INICIO, fin), "administrador"), 422, "FECHAS_INVALIDAS");
    }

    @Test
    void parcelaOCultivoInexistenteResponde404() throws Exception {
        String inexistente = UUID.randomUUID().toString();

        esperarError(crear(cuerpo("Soya", inexistente, idCultivo, INICIO, FIN), "administrador"),
                404, "PARCELA_NO_ENCONTRADA");
        esperarError(crear(cuerpo("Soya", idParcela, inexistente, INICIO, FIN), "administrador"),
                404, "CULTIVO_NO_ENCONTRADO");
    }

    @ParameterizedTest
    @ValueSource(strings = {"gerencia", "tecnico_campo", "lectura_gestion"})
    void soloElAdministradorPuedeCrear(String rol) throws Exception {
        esperarError(crear(cuerpo("Soya", idParcela, idCultivo, INICIO, FIN), rol), 403, "SIN_PERMISO");
    }

    @Test
    void formatoInvalidoResponde400() throws Exception {
        esperarError(crear(cuerpo("  ", idParcela, idCultivo, INICIO, FIN), "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(crear(cuerpo("Soya", "no-es-uuid", idCultivo, INICIO, FIN), "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(crear("{\"nombre\": \"Soya\"}", "administrador"), 400, "DATOS_INVALIDOS");
    }

    @Test
    void fechasConHoraResponden400() throws Exception {
        crear(cuerpo("Soya", idParcela, idCultivo, "2026-11-15T00:00:00Z", FIN), "administrador")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DATOS_INVALIDOS"))
                .andExpect(jsonPath("$.detalles[0].campo").value("fechaInicio"));
    }

    // Historia 2

    @Test
    void pasarAEnCursoRegistraFechaYUsuario() throws Exception {
        String id = crearCampania("Soya");

        cambiarEstado(id, "EN_CURSO", 0)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.estado").value("EN_CURSO"))
                .andExpect(jsonPath("$.fechaInicioEjecucion").isNotEmpty())
                .andExpect(jsonPath("$.version").value(1));

        verificarAuditoria(id, "CAMBIAR_ESTADO");
    }

    @Test
    void finalizarSinProduccionSeRechaza() throws Exception {
        String id = crearCampania("Soya");
        iniciar(id);

        esperarError(cambiarEstado(id, "FINALIZADA", 1), 422, "FINALIZACION_SIN_PRODUCCION");
    }

    @Test
    void transicionesInvalidasSeRechazan() throws Exception {
        String id = crearCampania("Soya");
        esperarError(cambiarEstado(id, "FINALIZADA", 0), 422, "TRANSICION_ESTADO_INVALIDA");
        esperarError(cambiarEstado(id, "PLANIFICADA", 0), 422, "TRANSICION_ESTADO_INVALIDA");

        iniciar(id);
        esperarError(cambiarEstado(id, "PLANIFICADA", 1), 422, "TRANSICION_ESTADO_INVALIDA");
        esperarError(cambiarEstado(id, "EN_CURSO", 1), 422, "TRANSICION_ESTADO_INVALIDA");

        String finalizada = crearFinalizada("Cerrada");
        esperarError(cambiarEstado(finalizada, "EN_CURSO", 0), 422, "TRANSICION_ESTADO_INVALIDA");
    }

    @Test
    void parcelaConCampaniaEnCursoNoAdmiteOtra() throws Exception {
        String primera = crearCampania("Primera");
        String segunda = crearCampania("Segunda");
        iniciar(primera);

        esperarError(cambiarEstado(segunda, "EN_CURSO", 0), 409, "PARCELA_CON_CAMPANIA_EN_CURSO");
    }

    @Test
    void otraParcelaSiPuedeTenerSuCampaniaEnCurso() throws Exception {
        iniciar(crearCampania("Primera"));
        String otraParcela = crearParcela("Lote Sur", "10");
        String segunda = crearEn(RUTA, cuerpo("Segunda", otraParcela, idCultivo, INICIO, FIN));

        cambiarEstado(segunda, "EN_CURSO", 0).andExpect(status().isOk());
    }

    @Test
    void cambioDeEstadoConErroresDeSolicitud() throws Exception {
        String id = crearCampania("Soya");

        esperarError(cambiarEstado(id, "INEXISTENTE", 0), 400, "DATOS_INVALIDOS");
        esperarError(cambiarEstado(id, "EN_CURSO", 7), 409, "CONFLICTO_CONCURRENCIA");
        esperarError(cambiarEstado(UUID.randomUUID().toString(), "EN_CURSO", 0), 404, "CAMPANIA_NO_ENCONTRADA");
        esperarError(mockMvc.perform(put(RUTA + "/" + id + "/estado").with(conRol("gerencia"))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpoEstado("EN_CURSO", 0))), 403, "SIN_PERMISO");
    }

    // Historia 3

    @Test
    void filtraPorEstadoParcelaCultivoYFechas() throws Exception {
        String otraParcela = crearParcela("Lote Sur", "10");
        String otroCultivo = crearCultivo("Trigo");
        String enCurso = crearCampania("En curso");
        iniciar(enCurso);
        String planificada = crearEn(RUTA, cuerpo("Planificada", otraParcela, otroCultivo, "2027-05-01", "2027-09-01"));

        mockMvc.perform(get(RUTA + "?estado=EN_CURSO").with(conRol("gerencia")))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].id").value(enCurso))
                .andExpect(jsonPath("$.total").value(1));
        mockMvc.perform(get(RUTA + "?idParcela=" + otraParcela).with(conRol("gerencia")))
                .andExpect(jsonPath("$.items[0].id").value(planificada))
                .andExpect(jsonPath("$.total").value(1));
        mockMvc.perform(get(RUTA + "?idCultivo=" + idCultivo + "&idParcela=" + idParcela).with(conRol("gerencia")))
                .andExpect(jsonPath("$.items[0].id").value(enCurso))
                .andExpect(jsonPath("$.total").value(1));
        mockMvc.perform(get(RUTA + "?fechaInicioDesde=2027-01-01").with(conRol("gerencia")))
                .andExpect(jsonPath("$.items[0].id").value(planificada))
                .andExpect(jsonPath("$.total").value(1));
        mockMvc.perform(get(RUTA + "?fechaInicioHasta=2027-01-01").with(conRol("gerencia")))
                .andExpect(jsonPath("$.items[0].id").value(enCurso))
                .andExpect(jsonPath("$.total").value(1));
    }

    @Test
    void listadoOrdenaPorFechaDeInicioDescendenteSinResumen() throws Exception {
        crearEn(RUTA, cuerpo("Antigua", idParcela, idCultivo, "2025-01-01", "2025-06-01"));
        crearEn(RUTA, cuerpo("Nueva", idParcela, idCultivo, "2027-01-01", "2027-06-01"));

        mockMvc.perform(get(RUTA).with(conRol("administrador")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(2)))
                .andExpect(jsonPath("$.items[0].nombre").value("Nueva"))
                .andExpect(jsonPath("$.items[1].nombre").value("Antigua"))
                .andExpect(jsonPath("$.items[0].resumen").doesNotExist())
                .andExpect(jsonPath("$.items[0].superficieHectareas").value("25.5000"));
    }

    @Test
    void filtrosInvalidosResponden400() throws Exception {
        for (String consulta : new String[] {"estado=OTRO", "idParcela=x", "fechaInicioDesde=2026-11-15T00:00:00Z", "tamanio=101"}) {
            esperarError(mockMvc.perform(get(RUTA + "?" + consulta).with(conRol("gerencia"))), 400, "DATOS_INVALIDOS");
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"administrador", "gerencia", "lectura_gestion"})
    void detalleIncluyeElResumenParaLaVistaCompleta(String rol) throws Exception {
        String id = crearCampania("Soya");

        mockMvc.perform(get(RUTA + "/" + id).with(conRol(rol)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.estado").value("PLANIFICADA"))
                .andExpect(jsonPath("$.resumen.costoTotal").value("0.00"))
                .andExpect(jsonPath("$.resumen.cantidadCostos").value(0))
                .andExpect(jsonPath("$.resumen.produccion").value(nullValue()));
    }

    @Test
    void idInexistenteResponde404() throws Exception {
        esperarError(mockMvc.perform(get(RUTA + "/" + UUID.randomUUID()).with(conRol("gerencia"))),
                404, "CAMPANIA_NO_ENCONTRADA");
    }

    // Historia 4

    @Test
    void enPlanificadaCambiarLaParcelaActualizaLaSuperficie() throws Exception {
        String id = crearCampania("Soya");
        String otraParcela = crearParcela("Lote Sur", "10");

        modificar(id, cuerpoConVersion("Soya", otraParcela, idCultivo, INICIO, FIN, 0))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.idParcela").value(otraParcela))
                .andExpect(jsonPath("$.superficieHectareas").value("10.0000"))
                .andExpect(jsonPath("$.version").value(1));
        verificarAuditoria(id, "MODIFICAR");
    }

    @Test
    void enPlanificadaParcelaOCultivoNuevoInexistenteResponde404() throws Exception {
        String id = crearCampania("Soya");
        String inexistente = UUID.randomUUID().toString();

        esperarError(modificar(id, cuerpoConVersion("Soya", inexistente, idCultivo, INICIO, FIN, 0)),
                404, "PARCELA_NO_ENCONTRADA");
        esperarError(modificar(id, cuerpoConVersion("Soya", idParcela, inexistente, INICIO, FIN, 0)),
                404, "CULTIVO_NO_ENCONTRADO");
    }

    @Test
    void enCursoSeModificanNombreYFechaDeFin() throws Exception {
        String id = crearCampania("Soya");
        iniciar(id);

        modificar(id, cuerpoConVersion("Soya tardia", idParcela, idCultivo, INICIO, "2027-04-15", 1))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nombre").value("Soya tardia"))
                .andExpect(jsonPath("$.fechaFin").value("2027-04-15"));
    }

    @Test
    void enCursoNoSeModificanParcelaCultivoNiFechaDeInicio() throws Exception {
        String id = crearCampania("Soya");
        iniciar(id);
        String otra = UUID.randomUUID().toString();

        esperarError(modificar(id, cuerpoConVersion("Soya", otra, idCultivo, INICIO, FIN, 1)),
                422, "CAMPO_NO_MODIFICABLE");
        esperarError(modificar(id, cuerpoConVersion("Soya", idParcela, otra, INICIO, FIN, 1)),
                422, "CAMPO_NO_MODIFICABLE");
        esperarError(modificar(id, cuerpoConVersion("Soya", idParcela, idCultivo, "2026-11-16", FIN, 1)),
                422, "CAMPO_NO_MODIFICABLE");
    }

    @Test
    void finalizadaNoAdmiteModificaciones() throws Exception {
        String id = crearFinalizada("Cerrada");

        esperarError(modificar(id, cuerpoConVersion("Otro", idParcela, idCultivo, INICIO, FIN, 0)),
                422, "CAMPANIA_FINALIZADA");
    }

    @Test
    void modificarConFechasInvalidasOVersionVieja() throws Exception {
        String id = crearCampania("Soya");

        esperarError(modificar(id, cuerpoConVersion("Soya", idParcela, idCultivo, FIN, INICIO, 0)),
                422, "FECHAS_INVALIDAS");
        esperarError(modificar(id, cuerpoConVersion("Soya", idParcela, idCultivo, INICIO, FIN, 9)),
                409, "CONFLICTO_CONCURRENCIA");
        esperarError(modificar(UUID.randomUUID().toString(), cuerpoConVersion("Soya", idParcela, idCultivo, INICIO, FIN, 0)),
                404, "CAMPANIA_NO_ENCONTRADA");
        esperarError(modificar(id, cuerpo("Soya", idParcela, idCultivo, INICIO, FIN)), 400, "DATOS_INVALIDOS");
    }

    // CE-CAM-04

    @Test
    void laCampaniaConservaSuSuperficieCuandoCambiaLaParcela() throws Exception {
        String id = crearCampania("Soya");

        mockMvc.perform(put("/api/gestion/v1/parcelas/" + idParcela).with(conRol("administrador"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"nombre\": \"Lote Norte\", \"superficieHectareas\": \"27\", \"version\": 0}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.superficieHectareas").value("27.0000"));

        mockMvc.perform(get(RUTA + "/" + id).with(conRol("gerencia")))
                .andExpect(jsonPath("$.superficieHectareas").value("25.5000"));
    }

    // OpenAPI

    @Test
    void openApiListaLosEndpointsConSusErrores() throws Exception {
        String documento = mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        JsonNode rutas = mapeador.readTree(documento).get("paths");

        assertThat(rutas.get(RUTA).get("post").get("responses").get("422").get("description").asText())
                .isEqualTo("FECHAS_INVALIDAS");
        assertThat(rutas.get(RUTA).get("get").get("responses").has("400")).isTrue();
        assertThat(rutas.get(RUTA + "/{id}").get("get").get("responses").get("404").get("description").asText())
                .isEqualTo("CAMPANIA_NO_ENCONTRADA");
        assertThat(rutas.get(RUTA + "/{id}").get("get").get("responses").get("200").toString())
                .contains("CampaniaRespuesta", "CampaniaSinResumenRespuesta");
        assertThat(rutas.get(RUTA + "/{id}").get("put").get("responses").get("422").get("description").asText())
                .contains("CAMPO_NO_MODIFICABLE");
        assertThat(rutas.get(RUTA + "/{id}/estado").get("put").get("responses").get("409").get("description").asText())
                .contains("PARCELA_CON_CAMPANIA_EN_CURSO");
    }
}
