package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.any;
import static com.github.tomakehurst.wiremock.client.WireMock.anyRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.client.WireMock.urlMatching;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** Historia 5: llamar al backend desde los microfrontends publicados en otro origen. */
class CorsIT extends PruebaIntegracionBase {

    private static final String RUTA = "/api/gestion/v1/parcelas";
    private static final String PERMITIDO = "https://agro.example.com";

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
    }

    @Test
    void verificacionPreviaDeOrigenPermitidoSinToken() {
        cliente.options().uri(RUTA)
                .header(HttpHeaders.ORIGIN, PERMITIDO)
                .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST")
                .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "Authorization, Content-Type, X-Correlation-Id")
                .exchange()
                .expectStatus().isOk()
                .expectHeader().valueEquals(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, PERMITIDO)
                .expectHeader().value(HttpHeaders.ACCESS_CONTROL_ALLOW_METHODS, metodos -> assertThat(metodos).contains("POST"))
                .expectHeader().value(HttpHeaders.ACCESS_CONTROL_ALLOW_HEADERS,
                        headers -> assertThat(headers.toLowerCase()).contains("authorization").contains("x-correlation-id"))
                .expectHeader().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_CREDENTIALS);

        SERVICIOS.verify(0, anyRequestedFor(urlMatching("/api/.*")));
    }

    @Test
    void verificacionPreviaDeOrigenNoPermitidoSeRechaza() {
        cliente.options().uri(RUTA)
                .header(HttpHeaders.ORIGIN, "https://malicioso.example.com")
                .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                .exchange()
                .expectStatus().isForbidden()
                .expectHeader().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN);
    }

    @Test
    void solicitudRealExponeElIdDeCorrelacion() {
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200)));

        cliente.get().uri(RUTA).header(HttpHeaders.ORIGIN, "http://localhost:9000")
                .header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isOk()
                .expectHeader().valueEquals(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:9000")
                .expectHeader().value(HttpHeaders.ACCESS_CONTROL_EXPOSE_HEADERS,
                        expuestos -> assertThat(expuestos).contains("X-Correlation-Id"));
    }

    @Test
    void sinHeaderDuplicadoSiElServicioDevuelveElSuyo() {
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200)
                .withHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, PERMITIDO)));

        List<String> valores = cliente.get().uri(RUTA).header(HttpHeaders.ORIGIN, PERMITIDO)
                .header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isOk()
                .returnResult(Void.class).getResponseHeaders().get(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN);

        assertThat(valores).containsExactly(PERMITIDO);
    }
}
