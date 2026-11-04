package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.anyRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.client.WireMock.urlMatching;

import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * Caso borde: Keycloak no entrega las claves y el gateway aún no las tiene. Contexto propio, apuntado a
 * un JWKS que falla, para que ninguna clave quede en caché de otro test.
 */
class AutenticacionNoDisponibleIT extends PruebaIntegracionBase {

    private static final String RUTA_JWKS_CAIDO = "/jwks-caido";

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
        registro.add("KEYCLOAK_JWKS_URI", () -> SERVICIOS.baseUrl() + RUTA_JWKS_CAIDO);
    }

    @Test
    void sinClavesDeKeycloakResponde503() {
        SERVICIOS.stubFor(get(urlEqualTo(RUTA_JWKS_CAIDO)).willReturn(aResponse().withStatus(500)));

        cliente.get().uri("/api/gestion/v1/parcelas")
                .header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectBody()
                .jsonPath("$.codigo").isEqualTo("AUTENTICACION_NO_DISPONIBLE")
                .jsonPath("$.idCorrelacion").isNotEmpty();

        SERVICIOS.verify(0, anyRequestedFor(urlMatching("/api/.*")));
    }
}
