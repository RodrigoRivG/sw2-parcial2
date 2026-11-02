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

class CostoCampaniaConcurrenciaIT extends CostoCampaniaPruebaBase {

    @Test
    void dosCostosSimultaneosNuncaSePierdenEnSilencio() throws Exception {
        String campania = crearCampania("Soya");
        CountDownLatch salida = new CountDownLatch(1);
        Callable<Integer> tarea = () -> {
            salida.await();
            return mockMvc.perform(post(rutaCostos(campania)).with(conRol("administrador"))
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(cuerpoCosto("OTRO", "1.00", HOY, "x")))
                    .andReturn().getResponse().getStatus();
        };

        List<Integer> estados;
        try (ExecutorService hilos = Executors.newFixedThreadPool(2)) {
            Future<Integer> a = hilos.submit(tarea);
            Future<Integer> b = hilos.submit(tarea);
            salida.countDown();
            estados = List.of(a.get(), b.get());
        }

        assertThat(estados).allMatch(estado -> estado == 201 || estado == 409);
        long aceptados = estados.stream().filter(estado -> estado == 201).count();
        assertThat(aceptados).isGreaterThanOrEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM costo_campania", Long.class)).isEqualTo(aceptados);
    }
}
