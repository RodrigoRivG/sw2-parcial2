package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.any;
import static com.github.tomakehurst.wiremock.client.WireMock.anyRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.client.WireMock.urlMatching;

import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

/** Historia 2: rechazar solicitudes sin un token válido antes de llegar al servicio. */
class SeguridadIT extends PruebaIntegracionBase {

    private static final String RUTA = "/api/gestion/v1/parcelas";

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
    }

    @Test
    void sinTokenResponde401() {
        esperarNoAutenticado(cliente.get().uri(RUTA).exchange());
    }

    @Test
    void tokenFirmadoConOtraClaveResponde401() {
        String ajeno = token(CLAVE_AJENA, EMISOR, Instant.now().plusSeconds(300), "u", List.of("servicio-gestion"), List.of());
        esperarNoAutenticado(conToken(ajeno));
    }

    @Test
    void tokenDeOtroEmisorResponde401() {
        String otroEmisor = token(CLAVE, "http://otro/realms/agro", Instant.now().plusSeconds(300), "u",
                List.of("servicio-gestion"), List.of());
        esperarNoAutenticado(conToken(otroEmisor));
    }

    @Test
    void tokenVencidoResponde401() {
        String vencido = token(CLAVE, EMISOR, Instant.now().minusSeconds(600), "u", List.of("servicio-gestion"), List.of());
        esperarNoAutenticado(conToken(vencido));
    }

    @ParameterizedTest
    @ValueSource(strings = {"Basic dXN1YXJpbzpjbGF2ZQ==", "Bearer no-es-un-jwt", "Bearer "})
    void esquemaDistintoOTokenMalFormadoResponde401(String autorizacion) {
        esperarNoAutenticado(cliente.get().uri(RUTA).header("Authorization", autorizacion).exchange());
    }

    @Test
    void audienciaAjenaYSinRolesSeReenvian() {
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200)));
        String sinAudienciaNiRoles = token(CLAVE, EMISOR, Instant.now().plusSeconds(300), "u", List.of("otro-servicio"),
                List.of());

        conToken(sinAudienciaNiRoles).expectStatus().isOk();
    }

    @ParameterizedTest
    @ValueSource(strings = {"/salud", "/salud/liveness", "/salud/readiness"})
    void saludSinToken(String ruta) {
        cliente.get().uri(ruta).exchange()
                .expectStatus().isOk()
                .expectBody().jsonPath("$.status").isEqualTo("UP");
    }

    private WebTestClient.ResponseSpec conToken(String token) {
        return cliente.get().uri(RUTA).header("Authorization", "Bearer " + token).exchange();
    }

    private static void esperarNoAutenticado(WebTestClient.ResponseSpec respuesta) {
        respuesta.expectStatus().isUnauthorized()
                .expectHeader().exists("X-Correlation-Id")
                .expectBody()
                .jsonPath("$.codigo").isEqualTo("NO_AUTENTICADO")
                .jsonPath("$.mensaje").isEqualTo("Debe iniciar sesión para continuar.")
                .jsonPath("$.idCorrelacion").isNotEmpty();
        SERVICIOS.verify(0, anyRequestedFor(urlMatching("/api/.*")));
    }
}
