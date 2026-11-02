package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

class ParcelaConcurrenciaIT extends ParcelaPruebaBase {

    @Autowired
    private ObjectMapper mapeador;

    private List<Integer> enviarALaVez(MockHttpServletRequestBuilder primera, MockHttpServletRequestBuilder segunda)
            throws Exception {
        CountDownLatch salida = new CountDownLatch(1);
        try (ExecutorService hilos = Executors.newFixedThreadPool(2)) {
            Callable<Integer> tareaA = () -> {
                salida.await();
                return mockMvc.perform(primera).andReturn().getResponse().getStatus();
            };
            Callable<Integer> tareaB = () -> {
                salida.await();
                return mockMvc.perform(segunda).andReturn().getResponse().getStatus();
            };
            Future<Integer> a = hilos.submit(tareaA);
            Future<Integer> b = hilos.submit(tareaB);
            salida.countDown();
            return List.of(a.get(), b.get());
        }
    }

    @Test
    void dosCreacionesSimultaneasConElMismoNombreDejanUnaSola() throws Exception {
        for (int intento = 0; intento < 5; intento++) {
            parcelas.deleteAll();
            String cuerpo = cuerpo("Lote Norte", "1");

            List<Integer> estados = enviarALaVez(
                    post(RUTA).with(conRol("administrador")).contentType(MediaType.APPLICATION_JSON).content(cuerpo),
                    post(RUTA).with(conRol("administrador")).contentType(MediaType.APPLICATION_JSON).content(cuerpo));

            assertThat(estados).containsExactlyInAnyOrder(201, 409);
            assertThat(parcelas.count()).isEqualTo(1);
        }
    }

    @Test
    void dosModificacionesConLaMismaVersionDejanPasarUnaSola() throws Exception {
        for (int intento = 0; intento < 5; intento++) {
            parcelas.deleteAll();
            String respuesta = mockMvc.perform(post(RUTA).with(conRol("administrador"))
                            .contentType(MediaType.APPLICATION_JSON).content(cuerpo("Lote Norte", "1")))
                    .andReturn().getResponse().getContentAsString();
            String id = mapeador.readTree(respuesta).get("id").asText();

            List<Integer> estados = enviarALaVez(
                    put(RUTA + "/" + id).with(conRol("administrador")).contentType(MediaType.APPLICATION_JSON)
                            .content(cuerpoConVersion("Lote Norte", "2", 0)),
                    put(RUTA + "/" + id).with(conRol("administrador")).contentType(MediaType.APPLICATION_JSON)
                            .content(cuerpoConVersion("Lote Norte", "3", 0)));

            assertThat(estados).containsExactlyInAnyOrder(200, 409);
            assertThat(parcelas.findById(UUID.fromString(id)).orElseThrow().getVersion()).isEqualTo(1);
        }
    }
}
