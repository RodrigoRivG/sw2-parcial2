package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

class CampaniaConcurrenciaIT extends CampaniaPruebaBase {

    private List<Integer> iniciarALaVez(String primera, String segunda) throws Exception {
        CountDownLatch salida = new CountDownLatch(1);
        try (ExecutorService hilos = Executors.newFixedThreadPool(2)) {
            Future<Integer> a = hilos.submit(iniciarDespuesDe(salida, primera));
            Future<Integer> b = hilos.submit(iniciarDespuesDe(salida, segunda));
            salida.countDown();
            return List.of(a.get(), b.get());
        }
    }

    private Callable<Integer> iniciarDespuesDe(CountDownLatch salida, String id) {
        return () -> {
            salida.await();
            return mockMvc.perform(put(RUTA + "/" + id + "/estado").with(conRol("administrador"))
                            .contentType(MediaType.APPLICATION_JSON).content(cuerpoEstado("EN_CURSO", 0)))
                    .andReturn().getResponse().getStatus();
        };
    }

    @Test
    void dosCambiosDeEstadoConLaMismaVersionDejanPasarUno() throws Exception {
        for (int intento = 0; intento < 5; intento++) {
            campanias.deleteAllInBatch();
            String id = crearCampania("Soya");

            assertThat(iniciarALaVez(id, id)).containsExactlyInAnyOrder(200, 409);
        }
    }

    @Test
    void dosCampaniasDeLaMismaParcelaNuncaQuedanEnCursoALaVez() throws Exception {
        for (int intento = 0; intento < 5; intento++) {
            campanias.deleteAllInBatch();
            String primera = crearCampania("Primera");
            String segunda = crearCampania("Segunda");

            assertThat(iniciarALaVez(primera, segunda)).containsExactlyInAnyOrder(200, 409);
            assertThat(campanias.findAll())
                    .filteredOn(campania -> campania.getEstado().equals("EN_CURSO"))
                    .hasSize(1);
        }
    }
}
