package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.any;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** CE-GW-02: el gateway agrega poca latencia (p95 < 50 ms contra un destino que responde al instante). */
class LatenciaIT extends PruebaIntegracionBase {

    private static final String RUTA = "/api/gestion/v1/campanias/c1/estado";

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
    }

    @Test
    void p95MenorA50Ms() {
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200).withBody("{}")));
        String token = token();
        for (int i = 0; i < 20; i++) {
            solicitar(token);
        }

        List<Long> duraciones = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            long inicio = System.nanoTime();
            solicitar(token);
            duraciones.add((System.nanoTime() - inicio) / 1_000_000);
        }
        Collections.sort(duraciones);

        assertThat(duraciones.get(94)).isLessThan(50);
    }

    private void solicitar(String token) {
        cliente.get().uri(RUTA).header("Authorization", "Bearer " + token).exchange().expectStatus().isOk();
    }
}
