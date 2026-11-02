package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;

import com.agrosystem.gestion.application.campaign.AnularCostoSagaCasoUso;
import com.agrosystem.gestion.application.campaign.ComandoAnularCosto;
import com.agrosystem.gestion.application.campaign.ComandoRegistrarCosto;
import com.agrosystem.gestion.application.campaign.RegistrarCostoSagaCasoUso;
import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

class AnularCostoSagaIT extends SagaPruebaBase {

    @Autowired
    private RegistrarCostoSagaCasoUso registrar;

    @Autowired
    private AnularCostoSagaCasoUso anular;

    private final UUID saga = UUID.randomUUID();
    private final UUID labor = UUID.randomUUID();

    private JsonNode registrarYEsperar(String campania) throws Exception {
        enviarRegistro(saga, labor, campania, "820.50");
        return recibirRespuesta();
    }

    @Test
    void anulaElCostoRegistradoQueDejaDeSumarPeroSeConserva() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        String idCosto = registrarYEsperar(campania).get("datos").get("idCosto").asText();

        enviarAnulacion(saga, labor, campania);
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("CostoCampaniaAnulado");
        assertThat(respuesta.get("idCorrelacion").asText()).isEqualTo(saga.toString());
        assertThat(respuesta.get("datos").get("idCosto").asText()).isEqualTo(idCosto);
        assertThat(respuesta.get("datos").get("sinEfecto").asBoolean()).isFalse();
        assertThat(costoTotalDe(campania)).isEqualByComparingTo("0");
        assertThat(costosDe(campania)).isEqualTo(1);
        assertThat(resultadoDe(saga)).isEqualTo("ANULADO");
        assertThat(jdbc.queryForObject("SELECT count(*) FROM registro_auditoria WHERE accion = 'ANULAR_COSTO_SAGA' "
                + "AND id_entidad = ?", Long.class, UUID.fromString(idCosto))).isEqualTo(1);
    }

    @Test
    void sinRegistroPrevioRespondeSinEfectoYBloqueaElRegistroTardio() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");

        enviarAnulacion(saga, labor, campania);
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("CostoCampaniaAnulado");
        assertThat(respuesta.get("datos").get("sinEfecto").asBoolean()).isTrue();
        assertThat(respuesta.get("datos").get("idCosto").isNull()).isTrue();
        assertThat(resultadoDe(saga)).isEqualTo("ANULADO");

        enviarRegistro(saga, labor, campania, "10");
        JsonNode tardio = recibirRespuesta();
        assertThat(tardio.get("datos").get("codigo").asText()).isEqualTo("SAGA_ANULADA");
        assertThat(costosDe(campania)).isZero();
    }

    @Test
    void enCampaniaFinalizadaSeRechazaYElCostoSeConserva() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        String idCosto = registrarYEsperar(campania).get("datos").get("idCosto").asText();
        registrarProduccion(campania, cuerpoProduccion("100", HOY), "administrador");
        finalizar(campania);

        enviarAnulacion(saga, labor, campania);
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("AnulacionCostoRechazada");
        assertThat(respuesta.get("datos").get("codigo").asText()).isEqualTo("CAMPANIA_FINALIZADA");
        assertThat(respuesta.get("datos").get("idCosto").asText()).isEqualTo(idCosto);
        assertThat(costoTotalDe(campania)).isEqualByComparingTo("820.50");
        assertThat(resultadoDe(saga)).isEqualTo("REGISTRADO");
    }

    @Test
    void sobreUnaSagaRechazadaRespondeSinEfectoYConservaElResultado() throws Exception {
        enviarRegistro(saga, labor, UUID.randomUUID().toString(), "10");
        recibirRespuesta();

        enviarAnulacion(saga, labor, UUID.randomUUID().toString());
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("tipo").asText()).isEqualTo("CostoCampaniaAnulado");
        assertThat(respuesta.get("datos").get("sinEfecto").asBoolean()).isTrue();
        assertThat(resultadoDe(saga)).isEqualTo("RECHAZADO");
    }

    @Test
    void anulacionDuplicadaRepiteLaRespuestaSinEfectosNuevos() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        registrarYEsperar(campania);
        enviarAnulacion(saga, labor, campania);
        JsonNode primera = recibirRespuesta();

        enviarAnulacion(saga, labor, campania);
        JsonNode segunda = recibirRespuesta();

        assertThat(segunda.get("datos")).isEqualTo(primera.get("datos"));
        assertThat(jdbc.queryForObject("SELECT count(*) FROM registro_auditoria WHERE accion = 'ANULAR_COSTO_SAGA'"
                + " AND id_entidad = ?", Long.class,
                UUID.fromString(primera.get("datos").get("idCosto").asText()))).isEqualTo(1);
    }

    @Test
    void conOtraCampaniaMandaElIdSaga() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        registrarYEsperar(campania);

        enviarAnulacion(saga, labor, UUID.randomUUID().toString());
        JsonNode respuesta = recibirRespuesta();

        assertThat(respuesta.get("datos").get("idCampania").asText()).isEqualTo(campania);
        assertThat(costoTotalDe(campania)).isEqualByComparingTo("0");
    }

    @Test
    void registroYAnulacionEnParaleloTerminanSiempreAnulados() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        UUID idCampania = UUID.fromString(campania);
        for (int intento = 0; intento < 10; intento++) {
            UUID idSaga = UUID.randomUUID();
            CountDownLatch salida = new CountDownLatch(1);
            Callable<Object> registro = () -> {
                salida.await();
                return registrar.ejecutar(new ComandoRegistrarCosto(
                        UUID.randomUUID(), idSaga, labor, idCampania, new BigDecimal("1.00"),
                        LocalDate.parse(HOY), "servicio-operaciones"));
            };
            Callable<Object> anulacion = () -> {
                salida.await();
                return anular.ejecutar(new ComandoAnularCosto(
                        UUID.randomUUID(), idSaga, labor, idCampania, "servicio-operaciones"));
            };
            try (ExecutorService hilos = Executors.newFixedThreadPool(2)) {
                Future<Object> a = hilos.submit(registro);
                Future<Object> b = hilos.submit(anulacion);
                salida.countDown();
                a.get();
                b.get();
            }

            assertThat(resultadoDe(idSaga)).isEqualTo("ANULADO");
            assertThat(costoTotalDe(campania)).isEqualByComparingTo("0");
        }
    }
}
