package com.agrosystem.gateway.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.options;

import com.github.tomakehurst.wiremock.WireMockServer;
import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.io.IOException;
import java.net.ServerSocket;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * Un WireMock hace de los cuatro servicios y de Keycloak (JWKS). Los tokens se firman en el test:
 * no se levanta Keycloak (D-GW-04). Cada clase IT declara su @DynamicPropertySource llamando a
 * {@link #propiedades}, y puede reemplazar valores después.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
abstract class PruebaIntegracionBase {

    static final String EMISOR = "http://keycloak-ficticio/realms/agro";
    static final String RUTA_JWKS = "/realms/agro/protocol/openid-connect/certs";

    static final WireMockServer SERVICIOS = new WireMockServer(options().dynamicPort());
    static final RSAKey CLAVE;
    static final RSAKey CLAVE_AJENA;

    static {
        SERVICIOS.start();
        try {
            CLAVE = new RSAKeyGenerator(2048).keyID("clave-agro").generate();
            CLAVE_AJENA = new RSAKeyGenerator(2048).keyID("clave-ajena").generate();
        } catch (JOSEException e) {
            throw new IllegalStateException(e);
        }
    }

    @Autowired
    WebTestClient cliente;

    static void propiedades(DynamicPropertyRegistry registro) {
        String base = SERVICIOS.baseUrl();
        registro.add("GESTION_URL", () -> base);
        registro.add("INVENTARIO_URL", () -> base);
        registro.add("OPERACIONES_URL", () -> base);
        registro.add("IA_URL", () -> base);
        registro.add("KEYCLOAK_JWKS_URI", () -> base + RUTA_JWKS);
        registro.add("KEYCLOAK_ISSUER", () -> EMISOR);
        registro.add("GATEWAY_TIEMPO_LIMITE", () -> "1s");
        registro.add("GATEWAY_TIEMPO_LIMITE_SINCRONIZACION", () -> "3000");
        registro.add("CORS_ORIGENES_PERMITIDOS", () -> "http://localhost:9000, https://agro.example.com");
    }

    @BeforeEach
    void reiniciarServicios() {
        SERVICIOS.resetAll();
        SERVICIOS.stubFor(get(urlEqualTo(RUTA_JWKS)).willReturn(aResponse()
                .withHeader("Content-Type", "application/json")
                .withBody(new JWKSet(CLAVE.toPublicJWK()).toString())));
    }

    /** Token válido de un usuario con audiencia de gestión y rol de administrador. */
    static String token() {
        return token(CLAVE, EMISOR, Instant.now().plusSeconds(300), "usuario-123", List.of("servicio-gestion"),
                List.of("administrador"));
    }

    static String token(RSAKey clave, String emisor, Instant vence, String sub, List<String> audiencia, List<String> roles) {
        JWTClaimsSet reclamos = new JWTClaimsSet.Builder()
                .issuer(emisor)
                .subject(sub)
                .audience(audiencia)
                .issueTime(Date.from(Instant.now().minusSeconds(60)))
                .expirationTime(Date.from(vence))
                .claim("realm_access", Map.of("roles", roles))
                .build();
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(clave.getKeyID()).build(), reclamos);
        try {
            jwt.sign(new RSASSASigner(clave));
        } catch (JOSEException e) {
            throw new IllegalStateException(e);
        }
        return jwt.serialize();
    }

    /** Un puerto local donde nadie escucha: la conexión se rechaza al instante. */
    static int puertoCerrado() {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }
}
