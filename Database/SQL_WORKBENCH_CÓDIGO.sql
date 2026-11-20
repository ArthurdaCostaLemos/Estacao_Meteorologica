USE estacao_meteorologica;
-- ------------------------------------------------------------------------------
-- Tabela 'leitura' (Persistência Cronológica da Telemetria)
-- Atende a todas as grandezas especificadas no modelo da disciplina (Seção 4.7)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leituras_sensores (
    id_leitura BIGINT AUTO_INCREMENT PRIMARY KEY,
    id_estacao INT NOT NULL,
    temperatura FLOAT NULL,              -- Em Graus Celsius (°C)
    umidade FLOAT NULL,                  -- Em Porcentagem (%)
    pressao FLOAT NULL,                  -- Em hPa
    qualidade_ar FLOAT NULL,             -- Valor em PPM (MQ-135)
    luminosidade FLOAT NULL,             -- Valor em ADC/Lux (LDR)
    pluviometria FLOAT DEFAULT 0.0,      -- Precipitação em mm (Sensor dispensado na montagem prática)
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    boot_id VARCHAR(32) NULL,
    sequencia BIGINT NULL,
    payload JSON NULL,
    qualidade JSON NULL,
    UNIQUE KEY uq_amostra (id_estacao, boot_id, sequencia),
    INDEX ix_estacao_tempo (id_estacao, data_hora),
    CONSTRAINT fk_estacao FOREIGN KEY (id_estacao) REFERENCES estacao(id_estacao),
    CONSTRAINT ck_temperatura CHECK (temperatura IS NULL OR temperatura BETWEEN -40 AND 80),
    CONSTRAINT ck_umidade CHECK (umidade IS NULL OR umidade BETWEEN 0 AND 100),
    CONSTRAINT ck_pressao CHECK (pressao IS NULL OR pressao BETWEEN 300 AND 1200),
    CONSTRAINT ck_qualidade_ar CHECK (qualidade_ar IS NULL OR qualidade_ar BETWEEN 0 AND 10000),
    CONSTRAINT ck_luminosidade CHECK (luminosidade IS NULL OR luminosidade BETWEEN 0 AND 100000)
);

USE estacao_meteorologica;

-- Mostra os últimos 100 registros salvos na tabela
SELECT *
FROM leituras_sensores
ORDER BY id DESC
LIMIT 100;

-- (Opcional) Mostra apenas a estrutura das colunas da tabela
DESCRIBE leituras_sensores;
