package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;

class IndicadoresControladorIT extends ProduccionPruebaBase {

    private ResultActions consultar(String campania, String rol) throws Exception {
        return mockMvc.perform(get(RUTA + "/" + campania + "/indicadores").with(conRol(rol)));
    }

    private void conProduccion(String campania, String cantidad) throws Exception {
        registrarProduccion(campania, cuerpoProduccion(cantidad, HOY), "administrador").andExpect(status().isOk());
    }

    // Historia 1

    @Test
    void calculaRendimientoYCostoPorHectarea() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        conProduccion(campania, "76500");
        registrarCosto(campania, "MANO_DE_OBRA", "38250.00");

        consultar(campania, "gerencia")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.idCampania").value(campania))
                .andExpect(jsonPath("$.estadoCampania").value("EN_CURSO"))
                .andExpect(jsonPath("$.superficieHectareas").value("25.5000"))
                .andExpect(jsonPath("$.produccion").value("76500.00"))
                .andExpect(jsonPath("$.costoTotal").value("38250.00"))
                .andExpect(jsonPath("$.rendimientoPorHectarea").value("3000.00"))
                .andExpect(jsonPath("$.costoPorHectarea").value("1500.00"))
                .andExpect(jsonPath("$.motivosNoDisponible", empty()));
    }

    @Test
    void conCostosSinProduccionSonNulosConSuMotivo() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        registrarCosto(campania, "OTRO", "38250.00");

        consultar(campania, "gerencia")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.produccion").value(nullValue()))
                .andExpect(jsonPath("$.costoTotal").value("38250.00"))
                .andExpect(jsonPath("$.rendimientoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.costoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.motivosNoDisponible", contains("SIN_PRODUCCION")));
    }

    @Test
    void conProduccionSinCostosSonNulosConSuMotivo() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        conProduccion(campania, "76500");

        consultar(campania, "gerencia")
                .andExpect(jsonPath("$.costoTotal").value("0.00"))
                .andExpect(jsonPath("$.rendimientoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.costoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.motivosNoDisponible", contains("SIN_COSTOS")));
    }

    @Test
    void sinProduccionNiCostosIncluyeAmbosMotivos() throws Exception {
        consultar(crearCampaniaEnCurso("Soya"), "gerencia")
                .andExpect(jsonPath("$.rendimientoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.costoPorHectarea").value(nullValue()))
                .andExpect(jsonPath("$.motivosNoDisponible", contains("SIN_PRODUCCION", "SIN_COSTOS")));
    }

    @Test
    void perdidaTotalDaRendimientoCero() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        conProduccion(campania, "0");
        registrarCosto(campania, "OTRO", "38250.00");

        consultar(campania, "gerencia")
                .andExpect(jsonPath("$.rendimientoPorHectarea").value("0.00"))
                .andExpect(jsonPath("$.costoPorHectarea").value("1500.00"))
                .andExpect(jsonPath("$.motivosNoDisponible", empty()));
    }

    @ParameterizedTest
    @ValueSource(strings = {"administrador", "gerencia", "lectura_gestion"})
    void losRolesAutorizadosConsultan(String rol) throws Exception {
        consultar(crearCampaniaEnCurso("Soya"), rol).andExpect(status().isOk());
    }

    @ParameterizedTest
    @ValueSource(strings = {"tecnico_campo", "estado_campania"})
    void losDemasRolesReciben403(String rol) throws Exception {
        consultar(crearCampaniaEnCurso("Soya"), rol)
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"));
    }

    @Test
    void campaniaInexistenteResponde404() throws Exception {
        consultar(UUID.randomUUID().toString(), "gerencia")
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.codigo").value("CAMPANIA_NO_ENCONTRADA"));
    }

    // Historia 2

    @Test
    void enCursoSonProvisionalesYFinalizadaDefinitivos() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        conProduccion(campania, "76500");
        registrarCosto(campania, "OTRO", "38250.00");
        consultar(campania, "gerencia").andExpect(jsonPath("$.definitivo").value(false));

        finalizar(campania).andExpect(status().isOk());

        consultar(campania, "gerencia")
                .andExpect(jsonPath("$.estadoCampania").value("FINALIZADA"))
                .andExpect(jsonPath("$.definitivo").value(true))
                .andExpect(jsonPath("$.rendimientoPorHectarea").value("3000.00"));
    }

    // Casos borde

    @Test
    void cadaConsultaReflejaLosCostosVigentesSinCache() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        conProduccion(campania, "76500");
        registrarCosto(campania, "OTRO", "25.50");
        consultar(campania, "gerencia").andExpect(jsonPath("$.costoPorHectarea").value("1.00"));

        insertarCostoSaga(campania, "25.50", false);
        insertarCostoSaga(campania, "9999.00", true);

        consultar(campania, "gerencia")
                .andExpect(jsonPath("$.costoTotal").value("51.00"))
                .andExpect(jsonPath("$.costoPorHectarea").value("2.00"));
    }

    @Test
    void divisionPeriodicaSeRedondeaAlFinal() throws Exception {
        idParcela = crearParcela("Lote Treinta", "30");
        String campania = crearCampaniaEnCurso("Soya");
        conProduccion(campania, "100000");
        registrarCosto(campania, "OTRO", "100.00");

        consultar(campania, "gerencia")
                .andExpect(jsonPath("$.rendimientoPorHectarea").value("3333.33"))
                .andExpect(jsonPath("$.costoPorHectarea").value("3.33"));
    }

    @Test
    void cambiarLaSuperficieDeLaParcelaNoCambiaLosIndicadores() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        conProduccion(campania, "76500");
        registrarCosto(campania, "OTRO", "38250.00");

        mockMvc.perform(put("/api/gestion/v1/parcelas/" + idParcela).with(conRol("administrador"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"nombre\": \"Lote Norte\", \"superficieHectareas\": \"100\", \"version\": 0}"))
                .andExpect(status().isOk());

        consultar(campania, "gerencia")
                .andExpect(jsonPath("$.superficieHectareas").value("25.5000"))
                .andExpect(jsonPath("$.rendimientoPorHectarea").value("3000.00"));
    }

    // OpenAPI

    @Test
    void openApiDocumentaElEndpoint() throws Exception {
        String documento = mockMvc.perform(get("/v3/api-docs")).andReturn().getResponse().getContentAsString();
        JsonNode respuestas = mapeador.readTree(documento)
                .get("paths").get(RUTA + "/{idCampania}/indicadores").get("get").get("responses");

        assertThat(respuestas.get("404").get("description").asText()).isEqualTo("CAMPANIA_NO_ENCONTRADA");
        assertThat(respuestas.has("401")).isTrue();
        assertThat(respuestas.has("403")).isTrue();
    }
}
