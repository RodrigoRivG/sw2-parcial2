package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.any;
import static com.github.tomakehurst.wiremock.client.WireMock.anyRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.equalTo;
import static com.github.tomakehurst.wiremock.client.WireMock.equalToJson;
import static com.github.tomakehurst.wiremock.client.WireMock.getRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.postRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.client.WireMock.urlMatching;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathMatching;
import static org.assertj.core.api.Assertions.assertThat;

import com.github.tomakehurst.wiremock.verification.LoggedRequest;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Random;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** Historia 1: llegar al microservicio correcto, con todo intacto. */
class EnrutamientoIT extends PruebaIntegracionBase {

    @DynamicPropertySource
    static void configurar(DynamicPropertyRegistry registro) {
        propiedades(registro);
    }

    @Test
    void reenviaRutaQueryHeadersYRespuestaSinCambios() {
        String token = token();
        SERVICIOS.stubFor(any(urlPathMatching("/api/gestion/.*")).willReturn(aResponse()
                .withStatus(200)
                .withHeader("Content-Type", "application/json")
                .withHeader("X-Propio-Del-Servicio", "si")
                .withBody("{\"estado\":\"EN_CURSO\"}")));

        cliente.get().uri("/api/gestion/v1/campanias/c1/estado?x=1&y=dos")
                .header("Authorization", "Bearer " + token)
                .header("X-Otro", "valor")
                .exchange()
                .expectStatus().isOk()
                .expectHeader().valueEquals("X-Propio-Del-Servicio", "si")
                .expectBody().json("{\"estado\":\"EN_CURSO\"}", true);

        SERVICIOS.verify(getRequestedFor(urlEqualTo("/api/gestion/v1/campanias/c1/estado?x=1&y=dos"))
                .withHeader("Authorization", equalTo("Bearer " + token))
                .withHeader("X-Otro", equalTo("valor")));
    }

    @ParameterizedTest
    @ValueSource(strings = {"/api/gestion/v1/parcelas", "/api/inventario/v1/insumos", "/api/operaciones/v1/labores",
        "/api/ia/v1/predicciones"})
    void cadaPrefijoLlegaASuServicio(String ruta) {
        SERVICIOS.stubFor(any(urlEqualTo(ruta)).willReturn(aResponse().withStatus(200).withBody("ok")));

        cliente.get().uri(ruta).header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isOk()
                .expectBody(String.class).isEqualTo("ok");

        SERVICIOS.verify(getRequestedFor(urlEqualTo(ruta)));
    }

    @Test
    void multipartLlegaByteAByte() {
        SERVICIOS.stubFor(any(urlEqualTo("/api/operaciones/v1/incidencias")).willReturn(aResponse().withStatus(201)));
        byte[] foto = new byte[3 * 1024 * 1024];
        new Random(7).nextBytes(foto);
        byte[] cuerpo = multipart("limite123", "{\"tipo\":\"PLAGA\"}", foto);

        cliente.post().uri("/api/operaciones/v1/incidencias")
                .header("Authorization", "Bearer " + token())
                // Como texto: MediaType normalizaría el header y no se probaría que llega sin cambios
                .header("Content-Type", "multipart/form-data; boundary=limite123")
                .bodyValue(cuerpo)
                .exchange()
                .expectStatus().isCreated();

        LoggedRequest recibida = SERVICIOS.findAll(anyRequestedFor(urlEqualTo("/api/operaciones/v1/incidencias"))).get(0);
        assertThat(recibida.getBody()).isEqualTo(cuerpo);
        assertThat(recibida.getHeader("Content-Type")).isEqualTo("multipart/form-data; boundary=limite123");
    }

    @Test
    void errorDelServicioSeDevuelveTalCual() {
        String error = "{\"codigo\":\"CAMPANIA_FINALIZADA\",\"mensaje\":\"m\",\"detalles\":[],\"idCorrelacion\":\"x\"}";
        SERVICIOS.stubFor(any(urlEqualTo("/api/operaciones/v1/labores")).willReturn(aResponse()
                .withStatus(422).withHeader("Content-Type", "application/json").withBody(error)));

        cliente.post().uri("/api/operaciones/v1/labores")
                .header("Authorization", "Bearer " + token())
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{}")
                .exchange()
                .expectStatus().isEqualTo(422)
                .expectBody().json(error, true);
    }

    @Test
    void notFoundDelServicioConSuCodigoNoSeReescribe() {
        // servicio-operaciones solo da por inexistente la campaña con este código (spec-enrutamiento.md 1.6)
        String error = "{\"codigo\":\"CAMPANIA_NO_ENCONTRADA\",\"mensaje\":\"m\",\"detalles\":[],\"idCorrelacion\":\"x\"}";
        SERVICIOS.stubFor(any(urlEqualTo("/api/gestion/v1/campanias/c9/estado")).willReturn(aResponse()
                .withStatus(404).withHeader("Content-Type", "application/json").withBody(error)));

        cliente.get().uri("/api/gestion/v1/campanias/c9/estado")
                .header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isNotFound()
                .expectBody().json(error, true);
    }

    @Test
    void locationRelativoDelServicioLlegaIgual() {
        SERVICIOS.stubFor(any(urlEqualTo("/api/gestion/v1/parcelas")).willReturn(aResponse()
                .withStatus(201).withHeader("Location", "/api/gestion/v1/parcelas/p1")));

        cliente.post().uri("/api/gestion/v1/parcelas")
                .header("Authorization", "Bearer " + token())
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{}")
                .exchange()
                .expectStatus().isCreated()
                .expectHeader().valueEquals("Location", "/api/gestion/v1/parcelas/p1");
    }

    @Test
    void graphqlLlegaASuServidorYSuRespuestaVuelveTalCual() {
        // Un error de campo de GraphQL viaja con 200 y la lista "errors": el gateway no lo toca (spec-ruta-graphql.md)
        String consulta = "{\"query\":\"{ campanias { total } }\"}";
        String respuesta = "{\"data\":{\"campanias\":null},\"errors\":[{\"message\":\"m\","
                + "\"extensions\":{\"codigo\":\"DEPENDENCIA_NO_DISPONIBLE\"}}]}";
        String token = token();
        SERVICIOS.stubFor(any(urlEqualTo("/api/graphql")).willReturn(aResponse()
                .withStatus(200).withHeader("Content-Type", "application/json").withBody(respuesta)));

        cliente.post().uri("/api/graphql")
                .header("Authorization", "Bearer " + token)
                .header("X-Correlation-Id", "abc-123")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(consulta)
                .exchange()
                .expectStatus().isOk()
                .expectHeader().valueEquals("X-Correlation-Id", "abc-123")
                .expectBody().json(respuesta, true);

        SERVICIOS.verify(postRequestedFor(urlEqualTo("/api/graphql"))
                .withHeader("Authorization", equalTo("Bearer " + token))
                .withHeader("X-Correlation-Id", equalTo("abc-123"))
                .withRequestBody(equalToJson(consulta)));
    }

    @Test
    void graphqlSinTokenResponde401SinLlamarAlServidor() {
        cliente.post().uri("/api/graphql")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"query\":\"{ campanias { total } }\"}")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectBody().jsonPath("$.codigo").isEqualTo("NO_AUTENTICADO");

        SERVICIOS.verify(0, anyRequestedFor(urlMatching("/api/.*")));
    }

    @ParameterizedTest
    @ValueSource(strings = {"/api/desconocido/v1/x", "/otra-ruta", "/api/gestionx/v1/parcelas", "/",
        "/api/graphqlx", "/api/graphql/otra"})
    void rutaSinDestinoResponde404SinLlamarANadie(String ruta) {
        cliente.get().uri(ruta).header("Authorization", "Bearer " + token())
                .exchange()
                .expectStatus().isNotFound()
                .expectHeader().contentType(MediaType.APPLICATION_JSON)
                .expectBody()
                .jsonPath("$.codigo").isEqualTo("RUTA_NO_ENCONTRADA")
                .jsonPath("$.mensaje").isEqualTo("La ruta solicitada no existe.")
                .jsonPath("$.detalles").isEmpty()
                .jsonPath("$.idCorrelacion").isNotEmpty();

        SERVICIOS.verify(0, anyRequestedFor(urlMatching("/api/.*")));
    }

    private static byte[] multipart(String limite, String datos, byte[] foto) {
        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        String inicio = "--" + limite + "\r\nContent-Disposition: form-data; name=\"datos\"\r\n\r\n" + datos + "\r\n"
                + "--" + limite + "\r\nContent-Disposition: form-data; name=\"foto\"; filename=\"f.jpg\"\r\n"
                + "Content-Type: image/jpeg\r\n\r\n";
        salida.writeBytes(inicio.getBytes(StandardCharsets.UTF_8));
        salida.writeBytes(foto);
        salida.writeBytes(("\r\n--" + limite + "--\r\n").getBytes(StandardCharsets.UTF_8));
        return salida.toByteArray();
    }
}
