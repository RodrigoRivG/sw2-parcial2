package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class RegistrarCostoSagaIT extends SagaPruebaBase {

    private final UUID saga = UUID.randomUUID();
    private final UUID labor = UUID.randomUUID();

    @Test
    void enCursoRegistraElCostoYResponde() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");

        enviarRegistro(saga, labor, campania, "820.50");
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("CostoCampaniaRegistrado");
        assertThat(respuesta.get("idCorrelacion").asText()).isEqualTo(saga.toString());
        assertThat(respuesta.get("origen").asText()).isEqualTo("servicio-gestion");
        assertThat(respuesta.get("version").asInt()).isEqualTo(1);
        assertThat(respuesta.get("idMensaje").asText()).isNotBlank();
        assertThat(respuesta.get("fechaOcurrencia").asText()).isNotBlank();
        JsonNode datos = respuesta.get("datos");
        assertThat(datos.get("idSaga").asText()).isEqualTo(saga.toString());
        assertThat(datos.get("idLabor").asText()).isEqualTo(labor.toString());
        assertThat(datos.get("idCampania").asText()).isEqualTo(campania);
        assertThat(datos.get("idCosto").asText()).isNotBlank();
        assertThat(datos.get("monto").isTextual()).isTrue();
        assertThat(datos.get("monto").asText()).isEqualTo("820.50");

        assertThat(resultadoDe(saga)).isEqualTo("REGISTRADO");
        mockMvc.perform(get(rutaCostos(campania)).with(conRol("gerencia")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.costoTotal").value("820.50"))
                .andExpect(jsonPath("$.items[0].origen").value("SAGA"))
                .andExpect(jsonPath("$.items[0].categoria").value("INSUMO"))
                .andExpect(jsonPath("$.items[0].idLabor").value(labor.toString()))
                .andExpect(jsonPath("$.items[0].descripcion").value("Insumos de la labor " + labor));
        assertThat(jdbc.queryForObject(
                "SELECT count(*) FROM registro_auditoria WHERE actor = 'servicio-operaciones' "
                        + "AND accion = 'REGISTRAR_COSTO_SAGA' AND id_entidad = ?",
                Long.class,
                UUID.fromString(datos.get("idCosto").asText()))).isEqualTo(1);
    }

    @Test
    void enPlanificadaTambienSeRegistra() throws Exception {
        String campania = crearCampania("Soya");

        enviarRegistro(saga, labor, campania, "10");

        assertThat(recibirRespuesta().get("tipo").asText()).isEqualTo("CostoCampaniaRegistrado");
        assertThat(costoTotalDe(campania)).isEqualByComparingTo("10");
    }

    @Test
    void enFinalizadaSeRechazaSinRegistrar() throws Exception {
        String campania = crearFinalizada("Cerrada");

        enviarRegistro(saga, labor, campania, "10");
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("CostoCampaniaRechazado");
        assertThat(respuesta.get("datos").get("codigo").asText()).isEqualTo("CAMPANIA_FINALIZADA");
        assertThat(respuesta.get("datos").get("motivo").asText()).isNotBlank();
        assertThat(costosDe(campania)).isZero();
        assertThat(resultadoDe(saga)).isEqualTo("RECHAZADO");
    }

    @Test
    void campaniaInexistenteSeRechaza() throws Exception {
        enviarRegistro(saga, labor, UUID.randomUUID().toString(), "10");

        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("CostoCampaniaRechazado");
        assertThat(respuesta.get("datos").get("codigo").asText()).isEqualTo("CAMPANIA_NO_ENCONTRADA");
    }

    @Test
    void sagaYaAnuladaSeRechazaConSagaAnulada() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        enviarAnulacion(saga, labor, campania);
        recibirRespuesta();

        enviarRegistro(saga, labor, campania, "10");
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("CostoCampaniaRechazado");
        assertThat(respuesta.get("datos").get("codigo").asText()).isEqualTo("SAGA_ANULADA");
        assertThat(costosDe(campania)).isZero();
    }
}
