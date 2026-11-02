CREATE TABLE campania (
    id                      UUID PRIMARY KEY,
    nombre                  VARCHAR(150)  NOT NULL,
    id_parcela              UUID          NOT NULL REFERENCES parcela (id),
    id_cultivo              UUID          NOT NULL REFERENCES cultivo (id),
    fecha_inicio            DATE          NOT NULL,
    fecha_fin               DATE          NOT NULL,
    superficie_hectareas    NUMERIC(12,4) NOT NULL,
    estado                  VARCHAR(20)   NOT NULL CHECK (estado IN ('PLANIFICADA','EN_CURSO','FINALIZADA')),
    fecha_inicio_ejecucion  TIMESTAMPTZ,
    fecha_finalizacion      TIMESTAMPTZ,
    version                 BIGINT        NOT NULL,
    fecha_creacion          TIMESTAMPTZ   NOT NULL,
    fecha_actualizacion     TIMESTAMPTZ   NOT NULL,
    CHECK (fecha_fin > fecha_inicio)
);
CREATE UNIQUE INDEX ux_campania_parcela_en_curso ON campania (id_parcela) WHERE estado = 'EN_CURSO';
CREATE INDEX ix_campania_filtros ON campania (estado, id_parcela, id_cultivo);
