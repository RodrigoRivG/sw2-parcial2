package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

@ExtendWith(OutputCaptureExtension.class)
class SeguridadIT extends PruebaIntegracionBase {

    private static final String RUTA = "/api/gestion/v1/prueba/";

    @Test
    void sinTokenResponde401ConFormatoComun() throws Exception {
        mockMvc.perform(get(RUTA + "autenticado").header("X-Correlation-Id", "abc-123"))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string("X-Correlation-Id", "abc-123"))
                .andExpect(jsonPath("$.codigo").value("NO_AUTENTICADO"))
                .andExpect(jsonPath("$.mensaje").isNotEmpty())
                .andExpect(jsonPath("$.detalles").isArray())
                .andExpect(jsonPath("$.idCorrelacion").value("abc-123"));
    }

    @Test
    void rolSinPermisoResponde403ConFormatoComun() throws Exception {
        mockMvc.perform(get(RUTA + "administrador")
                        .header("X-Correlation-Id", "abc-456")
                        .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_gerencia"))))
                .andExpect(status().isForbidden())
                .andExpect(header().string("X-Correlation-Id", "abc-456"))
                .andExpect(jsonPath("$.codigo").value("SIN_PERMISO"))
                .andExpect(jsonPath("$.idCorrelacion").value("abc-456"));
    }

    @Test
    void rolConPermisoPuedeEntrar() throws Exception {
        mockMvc.perform(get(RUTA + "administrador")
                        .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_administrador"))))
                .andExpect(status().isOk());
    }

    @Test
    void saludYDocumentacionNoExigenToken() throws Exception {
        mockMvc.perform(get("/salud")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
        mockMvc.perform(get("/salud/liveness")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
        mockMvc.perform(get("/salud/readiness")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
        mockMvc.perform(get("/v3/api-docs")).andExpect(status().isOk());
    }

    @Test
    void generaElIdSiNoLlegaOTieneFormatoInvalido(CapturedOutput salida) throws Exception {
        String generado = mockMvc.perform(get(RUTA + "autenticado").with(jwt()))
                .andExpect(status().isOk())
                .andReturn().getResponse().getHeader("X-Correlation-Id");
        assertThat(generado).isNotBlank();
        assertThat(salida.getOut()).contains(generado);

        String reemplazado = mockMvc.perform(get(RUTA + "autenticado")
                        .header("X-Correlation-Id", "invalido con espacios")
                        .with(jwt()))
                .andReturn().getResponse().getHeader("X-Correlation-Id");
        assertThat(reemplazado).isNotEqualTo("invalido con espacios").isNotBlank();
    }

    @Test
    void propagaElIdRecibidoALosLogs(CapturedOutput salida) throws Exception {
        mockMvc.perform(get(RUTA + "autenticado").header("X-Correlation-Id", "id-para-logs").with(jwt()))
                .andExpect(status().isOk())
                .andExpect(header().string("X-Correlation-Id", "id-para-logs"));
        assertThat(salida.getOut()).contains("id-para-logs");
    }
}
