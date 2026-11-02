package com.agrosystem.gestion.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.agrosystem.gestion.domain.saga.RepositorioSagaProcesada;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.amqp.core.Message;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

/** Usa colas propias, para que otros contextos de Spring en caché no consuman sus mensajes. */
@TestPropertySource(properties = {
        "gestion.saga.cola-comandos=prueba-fallos.comandos",
        "gestion.saga.cola-errores=prueba-fallos.comandos.dlq",
        "gestion.saga.cola-respuestas=prueba-fallos.respuestas"
})
class FallosSagaIT extends SagaPruebaBase {

    private static final long ESPERA_ERROR_MS = 20_000;

    @MockitoSpyBean
    private RepositorioSagaProcesada sagas;

    private final UUID saga = UUID.randomUUID();
    private final UUID labor = UUID.randomUUID();

    private void sinRespuesta() {
        assertThat(rabbit.receive(colaRespuestas, 500)).isNull();
    }

    @Test
    void falloTecnicoReintentaCuatroVecesYVaALaColaDeErrores() throws Exception {
        String campania = crearCampaniaEnCurso("Soya");
        doThrow(new IllegalStateException("Base de datos no disponible")).when(sagas).bloquear(any());

        enviarRegistro(saga, labor, campania, "10");

        Message error = recibirError(ESPERA_ERROR_MS);
        assertThat(error).as("mensaje en la Dead Letter Queue").isNotNull();
        verify(sagas, times(4)).bloquear(saga);
        sinRespuesta();
        assertThat(costosDe(campania)).isZero();
        assertThat(mapeador.readTree(error.getBody()).get("idCorrelacion").asText()).isEqualTo(saga.toString());
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "esto no es json",
            "[1, 2]",
            "{\"tipo\": \"RegistrarCostoCampania\"}",
            "{\"idMensaje\": \"no-uuid\", \"idCorrelacion\": \"x\", \"tipo\": \"RegistrarCostoCampania\"}",
            "{\"idMensaje\": \"6f1c7a52-0e2b-4f0e-9a51-111111111111\", \"tipo\": \"RegistrarCostoCampania\"}",
            "{\"idMensaje\": \"6f1c7a52-0e2b-4f0e-9a51-111111111111\", \"idCorrelacion\": \"x\", \"tipo\": \"Desconocido\"}"
    })
    void sobreNoInterpretableVaALaColaDeErroresSinReintentos(String cuerpo) {
        enviarCrudo(cuerpo);

        Message error = recibirError(ESPERA_ERROR_MS);
        assertThat(error).isNotNull();
        assertThat(new String(error.getBody())).isEqualTo(cuerpo);
        verify(sagas, never()).bloquear(any());
        sinRespuesta();
    }

    private void esperarDatosInvalidos(String tipoRespuesta) throws Exception {
        JsonNode respuesta = recibirRespuesta();
        assertThat(respuesta.get("tipo").asText()).isEqualTo(tipoRespuesta);
        assertThat(respuesta.get("idCorrelacion").asText()).isEqualTo(saga.toString());
        assertThat(respuesta.get("datos").get("codigo").asText()).isEqualTo("DATOS_INVALIDOS");
    }

    @ParameterizedTest
    @ValueSource(strings = {"\"0\"", "\"-5.00\"", "\"1.234\"", "\"1e5\"", "10.50", "null", "\"1234567890123\""})
    void montoInvalidoSeRechazaComoDatosInvalidos(String monto) throws Exception {
        String datos = "{\"idSaga\": \"" + saga + "\", \"idLabor\": \"" + labor + "\", \"idCampania\": \""
                + UUID.randomUUID() + "\", \"monto\": " + monto + ", \"categoria\": \"INSUMO\"}";

        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "RegistrarCostoCampania", 1, datos));

        esperarDatosInvalidos("CostoCampaniaRechazado");
        verify(sagas, never()).bloquear(any());
    }

    @Test
    void categoriaCamposAusentesYVersionSeRechazan() throws Exception {
        String conOtraCategoria = "{\"idSaga\": \"" + saga + "\", \"idLabor\": \"" + labor + "\", \"idCampania\": \""
                + UUID.randomUUID() + "\", \"monto\": \"10\", \"categoria\": \"OTRO\"}";
        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "RegistrarCostoCampania", 1, conOtraCategoria));
        esperarDatosInvalidos("CostoCampaniaRechazado");

        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "RegistrarCostoCampania", 1, "{}"));
        esperarDatosInvalidos("CostoCampaniaRechazado");

        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "RegistrarCostoCampania", 2,
                datosRegistro(saga, labor, UUID.randomUUID().toString(), "10")));
        esperarDatosInvalidos("CostoCampaniaRechazado");

        enviarCrudo(sobre(UUID.randomUUID(), UUID.randomUUID().toString().replace(saga.toString(), ""),
                "RegistrarCostoCampania", 1, datosRegistro(saga, labor, UUID.randomUUID().toString(), "10")));
        JsonNode correlacionDistinta = recibirRespuesta();
        assertThat(correlacionDistinta.get("datos").get("codigo").asText()).isEqualTo("DATOS_INVALIDOS");
    }

    @Test
    void anulacionConDatosInvalidosSeRechaza() throws Exception {
        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "AnularCostoCampania", 1, "{\"idSaga\": \"" + saga + "\"}"));
        esperarDatosInvalidos("AnulacionCostoRechazada");

        enviarCrudo(sobre(UUID.randomUUID(), saga.toString(), "AnularCostoCampania", 3,
                datosAnulacion(saga, labor, UUID.randomUUID().toString())));
        esperarDatosInvalidos("AnulacionCostoRechazada");
        verify(sagas, never()).bloquear(any());
    }
}
