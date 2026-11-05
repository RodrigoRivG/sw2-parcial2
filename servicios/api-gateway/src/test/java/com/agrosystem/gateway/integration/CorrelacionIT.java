package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.any;
import static com.github.tomakehurst.wiremock.client.WireMock.anyRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.equalTo;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo;
import static org.assertj.core.api.Assertions.assertThat;

import com.github.tomakehurst.wiremock.verification.LoggedRequest;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** Historia 4: seguir una solicitud de punta a punta (RNF-22). */
@ExtendWith(OutputCaptureExtension.class)
class CorrelacionIT extends PruebaIntegracionBase {

    private static final String RUTA = "/api/inventario/v1/insumos";
    private static final String FORMATO_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
    }

    @Test
    void idRecibidoLlegaAlServicioYVuelveEnLaRespuesta() {
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200)));

        cliente.get().uri(RUTA).header("Authorization", "Bearer " + token()).header("X-Correlation-Id", "abc-123")
                .exchange()
                .expectStatus().isOk()
                .expectHeader().valueEquals("X-Correlation-Id", "abc-123");

        SERVICIOS.verify(anyRequestedFor(urlEqualTo(RUTA)).withHeader("X-Correlation-Id", equalTo("abc-123")));
    }

    @Test
    void idDevueltoTambienPorElServicioLlegaUnaSolaVez() {
        // Los tres servicios devuelven el X-Correlation-Id que reciben; el gateway no debe duplicarlo
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200)
                .withHeader("X-Correlation-Id", "abc-123")));

        List<String> valores = cliente.get().uri(RUTA).header("Authorization", "Bearer " + token())
                .header("X-Correlation-Id", "abc-123")
                .exchange()
                .expectStatus().isOk()
                .returnResult(Void.class).getResponseHeaders().get("X-Correlation-Id");

        assertThat(valores).containsExactly("abc-123");
    }

    @Test
    void siElServicioDevuelveOtroIdSeConservaElDelGateway() {
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200)
                .withHeader("X-Correlation-Id", "otro-id")));

        List<String> valores = cliente.get().uri(RUTA).header("Authorization", "Bearer " + token())
                .header("X-Correlation-Id", "abc-123")
                .exchange()
                .expectStatus().isOk()
                .returnResult(Void.class).getResponseHeaders().get("X-Correlation-Id");

        assertThat(valores).containsExactly("abc-123");
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "con espacios", "a_b", "12345678901234567890123456789012345678901234567890123456789012345"})
    void idAusenteOInvalidoSeReemplazaPorUnUuid(String recibido) {
        SERVICIOS.stubFor(any(urlEqualTo(RUTA)).willReturn(aResponse().withStatus(200)));

        String devuelto = cliente.get().uri(RUTA).header("Authorization", "Bearer " + token())
                .headers(h -> {
                    if (!recibido.isEmpty()) {
                        h.set("X-Correlation-Id", recibido);
                    }
                })
                .exchange()
                .expectStatus().isOk()
                .returnResult(Void.class).getResponseHeaders().getFirst("X-Correlation-Id");

        assertThat(devuelto).matches(FORMATO_UUID);
        LoggedRequest recibida = SERVICIOS.findAll(anyRequestedFor(urlEqualTo(RUTA))).get(0);
        assertThat(recibida.getHeader("X-Correlation-Id")).isEqualTo(devuelto);
    }

    @Test
    void errorDelGatewayLlevaElMismoIdEnHeaderYCuerpo() {
        cliente.get().uri("/api/desconocido").header("Authorization", "Bearer " + token())
                .header("X-Correlation-Id", "id-de-error")
                .exchange()
                .expectStatus().isNotFound()
                .expectHeader().valueEquals("X-Correlation-Id", "id-de-error")
                .expectBody().jsonPath("$.idCorrelacion").isEqualTo("id-de-error");

        cliente.get().uri(RUTA).header("X-Correlation-Id", "id-sin-token")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectHeader().valueEquals("X-Correlation-Id", "id-sin-token")
                .expectBody().jsonPath("$.idCorrelacion").isEqualTo("id-sin-token");
    }

    @Test
    void unLogPorSolicitudConSusCamposYSinElToken(CapturedOutput salida) {
        SERVICIOS.stubFor(any(urlPathEqualTo(RUTA)).willReturn(aResponse().withStatus(200)));
        String token = token();

        cliente.get().uri(RUTA + "?secreto=no-va-al-log").header("Authorization", "Bearer " + token)
                .header("X-Correlation-Id", "id-del-log")
                .exchange()
                .expectStatus().isOk();
        cliente.get().uri(RUTA).header("X-Correlation-Id", "id-del-log-401")
                .exchange()
                .expectStatus().isUnauthorized();

        String linea = lineaCon(salida, "id-del-log\"");
        assertThat(linea)
                .contains("\"metodo\":\"GET\"")
                .contains("\"ruta\":\"" + RUTA + "\"")
                .contains("\"servicioDestino\":\"servicio-inventario\"")
                .contains("\"estado\":200")
                .contains("\"duracionMs\":")
                .contains("\"sub\":\"usuario-123\"")
                .doesNotContain("no-va-al-log");
        assertThat(lineaCon(salida, "id-del-log-401\""))
                .contains("\"estado\":401")
                .contains("\"servicioDestino\":\"ninguno\"");
        assertThat(salida.getAll()).doesNotContain(token);
    }

    private static String lineaCon(CapturedOutput salida, String texto) {
        return salida.getAll().lines()
                .filter(l -> l.contains("Solicitud atendida") && l.contains(texto))
                .findFirst()
                .orElseThrow(() -> new AssertionError("No hay log de acceso con " + texto));
    }
}
