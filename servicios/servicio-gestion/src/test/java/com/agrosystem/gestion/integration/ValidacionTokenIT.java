package com.agrosystem.gestion.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * Valida tokens reales, firmados con una clave propia: jwt() se salta esta validación.
 * El emisor configurado no existe en la red, así que el test también comprueba que no se contacta.
 */
class ValidacionTokenIT extends PruebaIntegracionBase {

    private static final String EMISOR = "http://keycloak-ficticio/realms/agro";
    private static final String RUTA = "/api/gestion/v1/prueba/administrador";

    private static final RSAKey CLAVE = generarClave();
    private static final RSAKey OTRA_CLAVE = generarClave();
    private static final HttpServer SERVIDOR_JWKS = iniciarServidorJwks();

    private static RSAKey generarClave() {
        try {
            return new RSAKeyGenerator(2048).keyID("clave-prueba").generate();
        } catch (JOSEException error) {
            throw new IllegalStateException(error);
        }
    }

    private static HttpServer iniciarServidorJwks() {
        try {
            HttpServer servidor = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
            byte[] jwks = new JWKSet(CLAVE.toPublicJWK()).toString().getBytes(StandardCharsets.UTF_8);
            servidor.createContext("/certs", intercambio -> {
                intercambio.getResponseHeaders().add("Content-Type", "application/json");
                intercambio.sendResponseHeaders(200, jwks.length);
                intercambio.getResponseBody().write(jwks);
                intercambio.close();
            });
            servidor.start();
            return servidor;
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    @DynamicPropertySource
    static void configurarJwks(DynamicPropertyRegistry registro) {
        registro.add("KEYCLOAK_JWKS_URI",
                () -> "http://localhost:" + SERVIDOR_JWKS.getAddress().getPort() + "/certs");
        registro.add("spring.rabbitmq.listener.simple.auto-startup", () -> "false");
    }

    @AfterAll
    static void detenerServidor() {
        SERVIDOR_JWKS.stop(0);
    }

    private String token(RSAKey clave, String emisor, String audiencia, Instant vencimiento) throws Exception {
        JWTClaimsSet datos = new JWTClaimsSet.Builder()
                .subject("usuario-1")
                .issuer(emisor)
                .audience(audiencia)
                .expirationTime(Date.from(vencimiento))
                .claim("realm_access", Map.of("roles", List.of("administrador")))
                .build();
        SignedJWT firmado = new SignedJWT(
                new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(clave.getKeyID()).build(), datos);
        firmado.sign(new RSASSASigner(clave));
        return firmado.serialize();
    }

    private void esperarRechazo(String token) throws Exception {
        mockMvc.perform(get(RUTA).header("Authorization", "Bearer " + token))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.codigo").value("NO_AUTENTICADO"));
    }

    private Instant enUnMinuto() {
        return Instant.now().plusSeconds(60);
    }

    @Test
    void aceptaUnTokenValidoYLeeLosRolesDeRealm() throws Exception {
        String valido = token(CLAVE, EMISOR, "servicio-gestion", enUnMinuto());
        mockMvc.perform(get(RUTA).header("Authorization", "Bearer " + valido)).andExpect(status().isOk());
    }

    @Test
    void rechazaEmisorIncorrecto() throws Exception {
        esperarRechazo(token(CLAVE, "http://otro/realms/agro", "servicio-gestion", enUnMinuto()));
    }

    @Test
    void rechazaAudienciaIncorrecta() throws Exception {
        esperarRechazo(token(CLAVE, EMISOR, "servicio-inventario", enUnMinuto()));
    }

    @Test
    void rechazaTokenVencido() throws Exception {
        esperarRechazo(token(CLAVE, EMISOR, "servicio-gestion", Instant.now().minusSeconds(3600)));
    }

    @Test
    void rechazaFirmaDeOtraClave() throws Exception {
        esperarRechazo(token(OTRA_CLAVE, EMISOR, "servicio-gestion", enUnMinuto()));
    }
}
