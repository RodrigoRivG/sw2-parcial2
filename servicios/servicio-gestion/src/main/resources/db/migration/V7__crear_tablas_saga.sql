CREATE TABLE saga_procesada (
    id_saga               UUID PRIMARY KEY,
    resultado             VARCHAR(20)  NOT NULL CHECK (resultado IN ('REGISTRADO','RECHAZADO','ANULADO')),
    id_campania           UUID,
    id_labor              UUID,
    id_costo              UUID,
    monto                 NUMERIC(14,2),
    codigo                VARCHAR(50),
    motivo                VARCHAR(300),
    anulacion_resultado   VARCHAR(20)  CHECK (anulacion_resultado IN ('ANULADO','RECHAZADA')),
    anulacion_sin_efecto  BOOLEAN,
    anulacion_codigo      VARCHAR(50),
    fecha_procesamiento   TIMESTAMPTZ  NOT NULL,
    fecha_actualizacion   TIMESTAMPTZ  NOT NULL
);

CREATE TABLE mensaje_procesado (
    id_mensaje           UUID PRIMARY KEY,
    id_saga              UUID        NOT NULL,
    fecha_procesamiento  TIMESTAMPTZ NOT NULL
);
