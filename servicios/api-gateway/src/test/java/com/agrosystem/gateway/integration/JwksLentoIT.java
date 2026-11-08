package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.anyRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.client.WireMock.urlMatching;
import static org.assertj.core.api.Assertions.assertThat;

import com.nimbusds.jose.jwk.JWKSet;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * Caso borde: Keycloak acepta la conexión pero tarda en entregar las claves, y el gateway aún no las tiene.
 * Contexto propio (caché de claves vacía) con límites cortos para el JWKS; la respuesta es un JWKS válido, solo
 * que llega tarde. El cliente de prueba espera más que el plazo del gateway, para medir el del gateway.
 */
class JwksLentoIT extends PruebaIntegracionBase {

    private static final String RUTA_JWKS_LENTO = "/jwks-lento";

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
        registro.add("KEYCLOAK_JWKS_URI", () -> SERVICIOS.baseUrl() + RUTA_JWKS_LENTO);
        registro.add("GATEWAY_JWKS_TIEMPO_RESPUESTA", () -> "1s");
        registro.add("GATEWAY_JWKS_PLAZO_TOTAL", () -> "2s");
    }

    @Test
    void jwksQueNoRespondeATiempoResponde503SinLlegarAlServicio() {
        SERVICIOS.stubFor(get(urlEqualTo(RUTA_JWKS_LENTO)).willReturn(aResponse()
                .withHeader("Content-Type", "application/json")
                .withBody(new JWKSet(CLAVE.toPublicJWK()).toString())
                .withFixedDelay(4000)));

        long inicio = System.nanoTime();
        cliente.mutate().responseTimeout(Duration.ofSeconds(10)).build()
                .get().uri("/api/gestion/v1/parcelas")
                .header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectBody()
                .jsonPath("$.codigo").isEqualTo("AUTENTICACION_NO_DISPONIBLE")
                .jsonPath("$.idCorrelacion").isNotEmpty();
        Duration duracion = Duration.ofNanos(System.nanoTime() - inicio);

        assertThat(duracion).isLessThan(Duration.ofMillis(3500));
        SERVICIOS.verify(0, anyRequestedFor(urlMatching("/api/.*")));
    }
}
