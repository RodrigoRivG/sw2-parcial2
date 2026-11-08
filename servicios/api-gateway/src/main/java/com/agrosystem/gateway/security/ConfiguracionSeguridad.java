package com.agrosystem.gateway.security;

import com.agrosystem.gateway.web.CodigoError;
import com.agrosystem.gateway.web.EscritorRespuestaError;
import com.agrosystem.gateway.web.FiltroIdCorrelacion;
import io.netty.channel.ChannelOption;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusReactiveJwtDecoder;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.security.web.server.ServerAuthenticationEntryPoint;
import org.springframework.security.web.server.context.NoOpServerSecurityContextRepository;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsConfigurationSource;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

/**
 * Valida firma, emisor y vigencia del JWT en /api/** (constitución §5). Ni audiencia ni roles: los valida
 * cada microservicio. CORS va en esta cadena para que la verificación previa, que no lleva token, no reciba 401.
 */
@Configuration
@EnableWebFluxSecurity
public class ConfiguracionSeguridad {

    private static final List<String> METODOS = List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS");
    private static final List<String> HEADERS_PERMITIDOS = List.of("Authorization", "Content-Type", FiltroIdCorrelacion.HEADER);
    private static final Duration VIGENCIA_VERIFICACION_PREVIA = Duration.ofHours(1);

    @Bean
    SecurityWebFilterChain cadenaSeguridad(
            ServerHttpSecurity http, CorsConfigurationSource cors, ServerAuthenticationEntryPoint noAutenticado) {
        return http
                .csrf(ServerHttpSecurity.CsrfSpec::disable)
                .httpBasic(ServerHttpSecurity.HttpBasicSpec::disable)
                .formLogin(ServerHttpSecurity.FormLoginSpec::disable)
                .logout(ServerHttpSecurity.LogoutSpec::disable)
                .securityContextRepository(NoOpServerSecurityContextRepository.getInstance())
                .cors(configuracion -> configuracion.configurationSource(cors))
                .authorizeExchange(reglas -> reglas
                        .pathMatchers(HttpMethod.OPTIONS, "/api/**").permitAll()
                        .pathMatchers("/salud", "/salud/**").permitAll()
                        .pathMatchers("/api/**").authenticated()
                        // Cualquier otra ruta llega al gateway y responde 404 RUTA_NO_ENCONTRADA (D-GW-03)
                        .anyExchange().permitAll())
                .oauth2ResourceServer(recurso -> recurso
                        .jwt(Customizer.withDefaults())
                        .authenticationEntryPoint(noAutenticado))
                .exceptionHandling(excepciones -> excepciones.authenticationEntryPoint(noAutenticado))
                .build();
    }

    /**
     * El mismo decodificador que armaría Spring Boot (claves de {@code jwk-set-uri}, solo se compara {@code iss}),
     * pero si las claves no se pueden obtener el fallo sale como {@link JwtException}: Spring Security lo convierte
     * en {@code AuthenticationServiceException} y el gateway responde 503 AUTENTICACION_NO_DISPONIBLE, no 500.
     *
     * <p>La descarga del JWKS usa un cliente propio con tiempo de conexión y de espera de respuesta (el cliente de
     * enrutamiento no lo rige) y además un plazo total: {@code responseTimeout} limita cada espera de lectura, no la
     * descarga completa. El plazo total también cubre la validación con claves en caché, que tarda milisegundos
     * (spec-enrutamiento.md, casos borde).
     */
    @Bean
    ReactiveJwtDecoder decodificadorJwt(
            @Value("${spring.security.oauth2.resourceserver.jwt.jwk-set-uri}") String jwks,
            @Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri}") String emisor,
            @Value("${gateway.jwks.tiempo-conexion}") Duration tiempoConexion,
            @Value("${gateway.jwks.tiempo-respuesta}") Duration tiempoRespuesta,
            @Value("${gateway.jwks.plazo-total}") Duration plazoTotal) {
        HttpClient clienteJwks = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, (int) tiempoConexion.toMillis())
                .responseTimeout(tiempoRespuesta);
        NimbusReactiveJwtDecoder nimbus = NimbusReactiveJwtDecoder.withJwkSetUri(jwks)
                .webClient(WebClient.builder().clientConnector(new ReactorClientHttpConnector(clienteJwks)).build())
                .build();
        nimbus.setJwtValidator(JwtValidators.createDefaultWithIssuer(emisor));
        return token -> nimbus.decode(token)
                .timeout(plazoTotal)
                .onErrorMap(
                        error -> !(error instanceof JwtException),
                        error -> new JwtException("No se pudieron obtener las claves de Keycloak", error));
    }

    @Bean
    ServerAuthenticationEntryPoint noAutenticado(EscritorRespuestaError escritor) {
        return (exchange, error) -> escritor.escribir(exchange, HttpStatus.UNAUTHORIZED, CodigoError.NO_AUTENTICADO);
    }

    @Bean
    CorsConfigurationSource fuenteCors(@Value("${gateway.cors.origenes-permitidos:}") String origenes) {
        CorsConfiguration configuracion = new CorsConfiguration();
        configuracion.setAllowedOrigins(Arrays.stream(origenes.split(","))
                .map(String::trim)
                .filter(origen -> !origen.isEmpty())
                .toList());
        configuracion.setAllowedMethods(METODOS);
        configuracion.setAllowedHeaders(HEADERS_PERMITIDOS);
        configuracion.setExposedHeaders(List.of(FiltroIdCorrelacion.HEADER));
        configuracion.setAllowCredentials(false);
        configuracion.setMaxAge(VIGENCIA_VERIFICACION_PREVIA);
        UrlBasedCorsConfigurationSource fuente = new UrlBasedCorsConfigurationSource();
        fuente.registerCorsConfiguration("/api/**", configuracion);
        return fuente;
    }
}
