package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.any;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * Historia 3: la caída o la lentitud de un servicio no afecta a los demás (RNF-08).
 * Aquí servicio-inventario apunta a un puerto sin servicio; el tiempo límite general es de 1 s.
 */
class ResilienciaIT extends PruebaIntegracionBase {

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
        int cerrado = puertoCerrado();
        registro.add("INVENTARIO_URL", () -> "http://localhost:" + cerrado);
    }

    @Test
    void servicioCaidoResponde503YLosDemasSiguen() {
        SERVICIOS.stubFor(any(urlEqualTo("/api/gestion/v1/parcelas")).willReturn(aResponse().withStatus(200)));

        cliente.get().uri("/api/inventario/v1/insumos").header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectHeader().contentType(MediaType.APPLICATION_JSON)
                .expectBody()
                .jsonPath("$.codigo").isEqualTo("SERVICIO_NO_DISPONIBLE")
                .jsonPath("$.idCorrelacion").isNotEmpty();

        cliente.get().uri("/api/gestion/v1/parcelas").header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isOk();
    }

    @Test
    void servicioLentoResponde504AlCumplirseElTiempoLimite() {
        SERVICIOS.stubFor(any(urlEqualTo("/api/gestion/v1/parcelas"))
                .willReturn(aResponse().withStatus(200).withFixedDelay(2000)));

        long inicio = System.nanoTime();
        cliente.mutate().responseTimeout(Duration.ofSeconds(5)).build()
                .get().uri("/api/gestion/v1/parcelas").header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isEqualTo(504)
                .expectBody()
                .jsonPath("$.codigo").isEqualTo("TIEMPO_AGOTADO");
        long transcurridoMs = (System.nanoTime() - inicio) / 1_000_000;

        assertThat(transcurridoMs).isLessThan(1900);
    }

    @Test
    void sincronizacionTieneSuPropioTiempoLimite() {
        SERVICIOS.stubFor(any(urlEqualTo("/api/operaciones/v1/sincronizacion"))
                .willReturn(aResponse().withStatus(200).withBody("lote").withFixedDelay(2000)));

        cliente.mutate().responseTimeout(Duration.ofSeconds(5)).build()
                .post().uri("/api/operaciones/v1/sincronizacion").header("Authorization", "Bearer " + token())
                // Lo que se prueba es el tiempo límite de la ruta, no el formato del lote
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{}")
                .exchange()
                .expectStatus().isOk()
                .expectBody(String.class).isEqualTo("lote");
    }

    @Test
    void readinessSigueUpConUnServicioCaido() {
        cliente.get().uri("/salud/readiness").exchange()
                .expectStatus().isOk()
                .expectBody().jsonPath("$.status").isEqualTo("UP");
    }
}
