package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

class CultivoConcurrenciaIT extends CultivoPruebaBase {

    private int crear(CountDownLatch salida) throws Exception {
        salida.await();
        return mockMvc.perform(post(RUTA).with(conRol("administrador"))
                        .contentType(MediaType.APPLICATION_JSON).content(cuerpo("Soya", "Munasqa")))
                .andReturn().getResponse().getStatus();
    }

    @Test
    void dosCreacionesSimultaneasDejanUnaSola() throws Exception {
        for (int intento = 0; intento < 5; intento++) {
            cultivos.deleteAll();
            CountDownLatch salida = new CountDownLatch(1);
            try (ExecutorService hilos = Executors.newFixedThreadPool(2)) {
                Callable<Integer> tarea = () -> crear(salida);
                Future<Integer> a = hilos.submit(tarea);
                Future<Integer> b = hilos.submit(tarea);
                salida.countDown();

                assertThat(List.of(a.get(), b.get())).containsExactlyInAnyOrder(201, 409);
            }
            assertThat(cultivos.count()).isEqualTo(1);
        }
    }
}
