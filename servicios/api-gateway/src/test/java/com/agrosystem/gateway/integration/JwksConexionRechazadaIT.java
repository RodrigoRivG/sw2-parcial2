package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.anyRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlMatching;

import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * Regresión: si la conexión con Keycloak se rechaza (puerto sin nadie escuchando), el gateway responde 503 AUTENTICACION_NO_DISPONIBLE y no SERVICIO_NO_DISPONIBLE, aunque
 * la causa sea un error de conexión. Contexto propio para que la caché de claves esté vacía.
 */
class JwksConexionRechazadaIT extends PruebaIntegracionBase {

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
        registro.add("KEYCLOAK_JWKS_URI", () -> "http://localhost:" + puertoCerrado() + "/certs");
    }

    @Test
    void sinAlcanzarKeycloakResponde503DeAutenticacion() {
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
