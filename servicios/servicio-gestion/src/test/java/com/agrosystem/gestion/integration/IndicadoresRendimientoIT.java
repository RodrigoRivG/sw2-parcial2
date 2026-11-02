package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.sql.Date;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class IndicadoresRendimientoIT extends ProduccionPruebaBase {

    @Test
    void con1000CostosRespondeEnMenosDe3Segundos() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        registrarProduccion(campania, cuerpoProduccion("76500", HOY), "administrador").andExpect(status().isOk());
        Timestamp ahora = Timestamp.from(Instant.now());
        List<Object[]> filas = new ArrayList<>();
        for (int i = 0; i < 1000; i++) {
            filas.add(new Object[] {UUID.randomUUID(), UUID.fromString(campania), Date.valueOf(HOY), ahora});
        }
        jdbc.batchUpdate("INSERT INTO costo_campania (id, id_campania, categoria, monto, fecha, descripcion, origen, fecha_registro) "
                + "VALUES (?, ?, 'OTRO', 38.25, ?, 'Costo', 'MANUAL', ?)", filas);

        long inicio = System.nanoTime();
        mockMvc.perform(get(RUTA + "/" + campania + "/indicadores").with(conRol("gerencia")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.costoTotal").value("38250.00"))
                .andExpect(jsonPath("$.costoPorHectarea").value("1500.00"));

        assertThat(Duration.ofNanos(System.nanoTime() - inicio)).isLessThan(Duration.ofSeconds(3));
    }
}
