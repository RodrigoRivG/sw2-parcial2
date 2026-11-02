package com.agrosystem.gestion.application.campaign;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Respuesta para el coordinador. Los montos viajan como texto. */
public record RespuestaSaga(String tipo, Map<String, Object> datos) {

    public static final String REGISTRADO = "CostoCampaniaRegistrado";
    public static final String RECHAZADO = "CostoCampaniaRechazado";
    public static final String ANULADO = "CostoCampaniaAnulado";
    public static final String ANULACION_RECHAZADA = "AnulacionCostoRechazada";

    private static Map<String, Object> base(Object idSaga, Object idLabor, Object idCampania) {
        Map<String, Object> datos = new LinkedHashMap<>();
        datos.put("idSaga", idSaga);
        datos.put("idLabor", idLabor);
        datos.put("idCampania", idCampania);
        return datos;
    }

    public static RespuestaSaga registrado(UUID idSaga, UUID idLabor, UUID idCampania, UUID idCosto, BigDecimal monto) {
        Map<String, Object> datos = base(idSaga, idLabor, idCampania);
        datos.put("idCosto", idCosto);
        datos.put("monto", monto.toPlainString());
        return new RespuestaSaga(REGISTRADO, datos);
    }

    public static RespuestaSaga rechazado(Object idSaga, Object idLabor, Object idCampania, String codigo, String motivo) {
        Map<String, Object> datos = base(idSaga, idLabor, idCampania);
        datos.put("codigo", codigo);
        datos.put("motivo", motivo);
        return new RespuestaSaga(RECHAZADO, datos);
    }

    public static RespuestaSaga anulado(UUID idSaga, UUID idLabor, UUID idCampania, UUID idCosto, boolean sinEfecto) {
        Map<String, Object> datos = base(idSaga, idLabor, idCampania);
        datos.put("idCosto", idCosto);
        datos.put("sinEfecto", sinEfecto);
        return new RespuestaSaga(ANULADO, datos);
    }

    public static RespuestaSaga anulacionRechazada(
            Object idSaga, Object idLabor, Object idCampania, Object idCosto, String codigo, String motivo) {
        Map<String, Object> datos = base(idSaga, idLabor, idCampania);
        datos.put("idCosto", idCosto);
        datos.put("codigo", codigo);
        datos.put("motivo", motivo);
        return new RespuestaSaga(ANULACION_RECHAZADA, datos);
    }
}
