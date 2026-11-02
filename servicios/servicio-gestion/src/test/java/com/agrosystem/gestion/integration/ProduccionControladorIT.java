package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.RegistroAuditoriaSpringData;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.ResultActions;

class ProduccionControladorIT extends ProduccionPruebaBase {

    @Autowired
    private RegistroAuditoriaSpringData auditoria;

    private void esperarError(ResultActions resultado, int estado, String codigo) throws Exception {
        resultado.andExpect(status().is(estado)).andExpect(jsonPath("$.codigo").value(codigo));
    }

    private long registrosDeAuditoria(String idCampania, String accion) {
        return auditoria.findAll().stream()
                .filter(registro -> registro.getIdEntidad().equals(UUID.fromString(idCampania)))
                .filter(registro -> registro.getEntidad().equals("PRODUCCION_CAMPANIA"))
                .filter(registro -> registro.getAccion().equals(accion))
                .count();
    }

    // Historia 1

    @Test
    void registraLaProduccionDeUnaCampaniaEnCurso() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");

        registrarProduccion(campania, cuerpoProduccion("76500.00", HOY), "administrador")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cantidad").value("76500.00"))
                .andExpect(jsonPath("$.unidad").value("KILOGRAMO"))
                .andExpect(jsonPath("$.fechaCosecha").value(HOY))
                .andExpect(jsonPath("$.observaciones").value("Peso de balanza"))
                .andExpect(jsonPath("$.fechaRegistro").isNotEmpty());

        assertThat(registrosDeAuditoria(campania, "CREAR")).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT usuario_registro FROM produccion_campania", String.class))
                .isEqualTo("usuario-administrador");
    }

    @Test
    void enPlanificadaSeRechaza() throws Exception {
        esperarError(registrarProduccion(crearCampaniaIniciable("Soya"), cuerpoProduccion("1", HOY), "administrador"),
                422, "CAMPANIA_NO_EN_CURSO");
    }

    @Test
    void cantidadNegativaSeRechaza() throws Exception {
        esperarError(registrarProduccion(crearCampaniaEnCurso("Soya"), cuerpoProduccion("-1", HOY), "administrador"),
                422, "PRODUCCION_INVALIDA");
    }

    @Test
    void cantidadCeroSeAcepta() throws Exception {
        registrarProduccion(crearCampaniaEnCurso("Soya"), cuerpoProduccion("0", HOY), "administrador")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cantidad").value("0.00"));
    }

    @Test
    void fechaDeCosechaFueraDeRangoSeRechaza() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");

        esperarError(registrarProduccion(campania, cuerpoProduccion("1", DIA_ACTUAL.minusDays(31).toString()), "administrador"),
                422, "FECHA_COSECHA_INVALIDA");
        esperarError(registrarProduccion(campania, cuerpoProduccion("1", DIA_ACTUAL.plusDays(2).toString()), "administrador"),
                422, "FECHA_COSECHA_INVALIDA");
    }

    @Test
    void formatoInvalidoResponde400() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");

        esperarError(registrarProduccion(campania, cuerpoProduccion("1.234", HOY), "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(registrarProduccion(campania, "{\"cantidad\": 10, \"fechaCosecha\": \"" + HOY + "\"}", "administrador"),
                400, "DATOS_INVALIDOS");
        esperarError(registrarProduccion(campania, "{\"cantidad\": \"10\"}", "administrador"), 400, "DATOS_INVALIDOS");
        esperarError(registrarProduccion(campania, cuerpoProduccion("1", HOY + "T00:00:00Z"), "administrador"),
                400, "DATOS_INVALIDOS");
    }

    @Test
    void campaniaInexistenteResponde404() throws Exception {
        esperarError(registrarProduccion(UUID.randomUUID().toString(), cuerpoProduccion("1", HOY), "administrador"),
                404, "CAMPANIA_NO_ENCONTRADA");
        esperarError(mockMvc.perform(get(rutaProduccion(UUID.randomUUID().toString())).with(conRol("gerencia"))),
                404, "CAMPANIA_NO_ENCONTRADA");
    }

    @ParameterizedTest
    @ValueSource(strings = {"gerencia", "tecnico_campo", "lectura_gestion"})
    void soloElAdministradorRegistra(String rol) throws Exception {
        esperarError(registrarProduccion(crearCampaniaEnCurso("Soya"), cuerpoProduccion("1", HOY), rol), 403, "SIN_PERMISO");
    }

    // Historia 2

    @Test
    void corregirReemplazaLaAnteriorYQuedaAuditado() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        registrarProduccion(campania, cuerpoProduccion("76500", HOY), "administrador").andExpect(status().isOk());

        registrarProduccion(campania, cuerpoProduccion("77120", HOY), "administrador")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cantidad").value("77120.00"));

        assertThat(registrosDeAuditoria(campania, "MODIFICAR")).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM produccion_campania", Long.class)).isEqualTo(1);
        mockMvc.perform(get(rutaProduccion(campania)).with(conRol("gerencia")))
                .andExpect(jsonPath("$.cantidad").value("77120.00"));
    }

    // Historia 3

    @ParameterizedTest
    @ValueSource(strings = {"administrador", "gerencia", "lectura_gestion"})
    void losRolesDeLecturaConsultanLaProduccion(String rol) throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        registrarProduccion(campania, cuerpoProduccion("100", HOY), "administrador").andExpect(status().isOk());

        mockMvc.perform(get(rutaProduccion(campania)).with(conRol(rol)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cantidad").value("100.00"))
                .andExpect(jsonPath("$.unidad").value("KILOGRAMO"))
                .andExpect(jsonPath("$.fechaCosecha").value(HOY))
                .andExpect(jsonPath("$.observaciones").value("Peso de balanza"))
                .andExpect(jsonPath("$.fechaRegistro").isNotEmpty());
    }

    @Test
    void sinProduccionResponde404() throws Exception {
        esperarError(mockMvc.perform(get(rutaProduccion(crearCampaniaEnCurso("Soya"))).with(conRol("gerencia"))),
                404, "PRODUCCION_NO_REGISTRADA");
    }

    @Test
    void tecnicoDeCampoNoConsultaLaProduccion() throws Exception {
        esperarError(mockMvc.perform(get(rutaProduccion(crearCampaniaEnCurso("Soya"))).with(conRol("tecnico_campo"))),
                403, "SIN_PERMISO");
    }

    // Resumen de la campaña

    @Test
    void elDetalleDeLaCampaniaMuestraLaProduccion() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        mockMvc.perform(get(RUTA + "/" + campania).with(conRol("gerencia")))
                .andExpect(jsonPath("$.resumen.produccion").value(nullValue()));

        registrarProduccion(campania, cuerpoProduccion("76500", HOY), "administrador").andExpect(status().isOk());

        mockMvc.perform(get(RUTA + "/" + campania).with(conRol("gerencia")))
                .andExpect(jsonPath("$.resumen.produccion").value("76500.00"));
        mockMvc.perform(get(RUTA + "/" + campania).with(conRol("tecnico_campo")))
                .andExpect(jsonPath("$.resumen").doesNotExist());
    }

    // CE-PRO-03

    @Test
    void registroYConsultaRespondenEnMenosDe3Segundos() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        long inicio = System.nanoTime();

        registrarProduccion(campania, cuerpoProduccion("100", HOY), "administrador").andExpect(status().isOk());
        mockMvc.perform(get(rutaProduccion(campania)).with(conRol("gerencia"))).andExpect(status().isOk());

        assertThat((System.nanoTime() - inicio) / 1_000_000).isLessThan(3000);
    }

    // OpenAPI

    @Test
    void openApiListaLosEndpointsConSusErrores() throws Exception {
        String documento = mockMvc.perform(get("/v3/api-docs")).andReturn().getResponse().getContentAsString();
        JsonNode ruta = mapeador.readTree(documento).get("paths").get(RUTA + "/{idCampania}/produccion");

        assertThat(ruta.get("put").get("responses").get("422").get("description").asText())
                .contains("PRODUCCION_INVALIDA", "FECHA_COSECHA_INVALIDA", "CAMPANIA_NO_EN_CURSO", "CAMPANIA_FINALIZADA");
        assertThat(ruta.get("get").get("responses").get("404").get("description").asText())
                .contains("PRODUCCION_NO_REGISTRADA");
    }
}
