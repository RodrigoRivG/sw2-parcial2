CREATE TABLE costo_campania (
    id               UUID PRIMARY KEY,
    id_campania      UUID          NOT NULL REFERENCES campania (id),
    categoria        VARCHAR(20)   NOT NULL CHECK (categoria IN ('INSUMO','MANO_DE_OBRA','MAQUINARIA','OTRO')),
    monto            NUMERIC(14,2) NOT NULL CHECK (monto > 0),
    fecha            DATE          NOT NULL,
    descripcion      VARCHAR(300)  NOT NULL,
    origen           VARCHAR(10)   NOT NULL CHECK (origen IN ('MANUAL','SAGA')),
    id_saga          UUID          UNIQUE,
    id_labor         UUID,
    anulado          BOOLEAN       NOT NULL DEFAULT FALSE,
    fecha_anulacion  TIMESTAMPTZ,
    fecha_registro   TIMESTAMPTZ   NOT NULL
);
CREATE INDEX ix_costo_campania ON costo_campania (id_campania, fecha DESC);
