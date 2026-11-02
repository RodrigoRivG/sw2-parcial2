package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

class FinalizacionConcurrenteSagaIT extends SagaPruebaBase {

    /** CE-CAM-02: el costo queda antes de finalizar o se rechaza; nunca ambas cosas. */
    @Test
    void costoDeLaSagaSimultaneoConLaFinalizacion() throws Exception {
        for (int intento = 0; intento < 8; intento++) {
            idParcela = crearParcela("Lote " + intento, "10");
            String campania = crearCampaniaEnCurso("Campania " + intento);
            registrarProduccion(campania, cuerpoProduccion("100", HOY), "administrador").andExpect(status().isOk());
            UUID saga = UUID.randomUUID();
            long version = versionDe(campania);

            Callable<Integer> finalizacion = () -> mockMvc.perform(put(RUTA + "/" + campania + "/estado")
                            .with(conRol("administrador"))
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(cuerpoEstado("FINALIZADA", version)))
                    .andReturn().getResponse().getStatus();

            int estado;
            try (ExecutorService hilos = Executors.newSingleThreadExecutor()) {
                enviarRegistro(saga, UUID.randomUUID(), campania, "10.00");
                Future<Integer> futuro = hilos.submit(finalizacion);
                estado = futuro.get();
            }
            JsonNode respuesta = recibirRespuesta();

            assertThat(estado).isIn(200, 409);
            if (respuesta.get("tipo").asText().equals("CostoCampaniaRegistrado")) {
                assertThat(costosDe(campania)).isEqualTo(1);
            } else {
                assertThat(respuesta.get("datos").get("codigo").asText()).isEqualTo("CAMPANIA_FINALIZADA");
                assertThat(costosDe(campania)).isZero();
            }
        }
    }
}
