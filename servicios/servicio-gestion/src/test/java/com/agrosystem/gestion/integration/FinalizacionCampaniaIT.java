package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

class FinalizacionCampaniaIT extends ProduccionPruebaBase {

    private String crearConProduccion(String nombre) throws Exception {
        String id = crearCampaniaEnCurso(nombre);
        registrarProduccion(id, cuerpoProduccion("76500", HOY), "administrador").andExpect(status().isOk());
        return id;
    }

    @Test
    void conProduccionFinalizaYGuardaLaFecha() throws Exception {
        String id = crearConProduccion("Soya");

        finalizar(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.estado").value("FINALIZADA"))
                .andExpect(jsonPath("$.fechaFinalizacion").isNotEmpty())
                .andExpect(jsonPath("$.resumen.produccion").value("76500.00"));
    }

    @Test
    void conPerdidaTotalTambienFinaliza() throws Exception {
        String id = crearCampaniaEnCurso("Soya");
        registrarProduccion(id, cuerpoProduccion("0", HOY), "administrador").andExpect(status().isOk());

        finalizar(id).andExpect(status().isOk());
    }

    @Test
    void despuesDeFinalizarLaProduccionNoCambia() throws Exception {
        String id = crearConProduccion("Soya");
        finalizar(id).andExpect(status().isOk());

        registrarProduccion(id, cuerpoProduccion("1", HOY), "administrador")
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.codigo").value("CAMPANIA_FINALIZADA"));

        assertThat(jdbc.queryForObject("SELECT cantidad FROM produccion_campania", String.class)).isEqualTo("76500.00");
    }

    @Test
    void finalizarConservaLosCostosYLosProtege() throws Exception {
        String id = crearConProduccion("Soya");
        registrarCosto(id, "OTRO", "10.00");

        finalizar(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.resumen.costoTotal").value("10.00"));

        registrar(id, cuerpoCosto("OTRO", "1", HOY, "Tarde"), "administrador")
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.codigo").value("CAMPANIA_FINALIZADA"));
    }

    private int[] enviarALaVez(MockHttpServletRequestBuilder primera, MockHttpServletRequestBuilder segunda)
            throws Exception {
        CountDownLatch salida = new CountDownLatch(1);
        Callable<Integer> tareaA = () -> {
            salida.await();
            return mockMvc.perform(primera).andReturn().getResponse().getStatus();
        };
        Callable<Integer> tareaB = () -> {
            salida.await();
            return mockMvc.perform(segunda).andReturn().getResponse().getStatus();
        };
        try (ExecutorService hilos = Executors.newFixedThreadPool(2)) {
            Future<Integer> a = hilos.submit(tareaA);
            Future<Integer> b = hilos.submit(tareaB);
            salida.countDown();
            return new int[] {a.get(), b.get()};
        }
    }

    private MockHttpServletRequestBuilder finalizacion(String id) {
        return put(RUTA + "/" + id + "/estado").with(conRol("administrador"))
                .contentType(MediaType.APPLICATION_JSON)
                .content(cuerpoEstado("FINALIZADA", versionDe(id)));
    }

    @Test
    void costoSimultaneoConLaFinalizacionQuedaAntesOSeRechaza() throws Exception {
        for (int intento = 0; intento < 5; intento++) {
            idParcela = crearParcela("Lote " + intento, "10");
            String id = crearConProduccion("Campania " + intento);
            int[] estados = enviarALaVez(
                    finalizacion(id),
                    post(rutaCostos(id)).with(conRol("administrador")).contentType(MediaType.APPLICATION_JSON)
                            .content(cuerpoCosto("OTRO", "1.00", HOY, "Simultaneo")));

            assertThat(estados[0]).isIn(200, 409);
            assertThat(estados[1]).isIn(201, 409, 422);
            assertThat(estados[0] == 200 || estados[1] == 201).isTrue();
            if (estados[0] == 200) {
                registrar(id, cuerpoCosto("OTRO", "1", HOY, "Tarde"), "administrador")
                        .andExpect(status().isUnprocessableEntity());
            }
        }
    }

    @Test
    void produccionSimultaneaConLaFinalizacionQuedaAntesOSeRechaza() throws Exception {
        String id = crearConProduccion("Soya");

        int[] estados = enviarALaVez(
                finalizacion(id),
                put(rutaProduccion(id)).with(conRol("administrador")).contentType(MediaType.APPLICATION_JSON)
                        .content(cuerpoProduccion("100", HOY)));

        assertThat(estados[0]).isIn(200, 409);
        assertThat(estados[1]).isIn(200, 409, 422);
        assertThat(estados[0] == 200 || estados[1] == 200).isTrue();
    }
}
