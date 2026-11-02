package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.agrosystem.gestion.infrastructure.persistence.entity.CultivoEntidad;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

class CultivoRendimientoIT extends CultivoPruebaBase {

    private static final Duration LIMITE = Duration.ofSeconds(3);

    @Test
    void listadoYDetalleRespondenEnMenosDe3Segundos() throws Exception {
        Instant ahora = Instant.now();
        List<CultivoEntidad> entidades = new ArrayList<>();
        for (int i = 0; i < 1000; i++) {
            CultivoEntidad entidad = new CultivoEntidad(UUID.randomUUID(), "KILOGRAMO", ahora);
            entidad.actualizar("Cultivo %04d".formatted(i), null, null, ahora);
            entidades.add(entidad);
        }
        cultivos.saveAll(entidades);

        medir(get(RUTA + "?tamanio=100&nombre=cultivo"));
        medir(get(RUTA + "/" + entidades.get(500).getId()));

        cultivos.deleteAll();
    }

    private void medir(MockHttpServletRequestBuilder solicitud) throws Exception {
        long inicio = System.nanoTime();
        mockMvc.perform(solicitud.with(conRol("gerencia"))).andExpect(status().isOk());
        assertThat(Duration.ofNanos(System.nanoTime() - inicio)).isLessThan(LIMITE);
    }
}
