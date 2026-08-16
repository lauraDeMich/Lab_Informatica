CREATE TABLE IF NOT EXISTS web_resources (
    url        VARCHAR(768)  NOT NULL,
    domain     VARCHAR(255)  NOT NULL,
    title      VARCHAR(2048) NOT NULL,
    html_text  LONGTEXT      NOT NULL,
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IF NOT EXISTS idx_web_resources_domain ON web_resources (domain);

CREATE TABLE IF NOT EXISTS gold_standard (
    url        VARCHAR(768) NOT NULL,
    gold_text  LONGTEXT     NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (url),
    CONSTRAINT fk_gold_standard_url
        FOREIGN KEY (url) REFERENCES web_resources (url)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS evaluations (
    url                 VARCHAR(768) NOT NULL,
    domain              VARCHAR(255) NOT NULL,
    precision_value     DOUBLE       NOT NULL,
    recall_value        DOUBLE       NOT NULL,
    f1_value            DOUBLE       NOT NULL,
    extra_metric_name   VARCHAR(255) NULL,
    extra_metric_score  DOUBLE       NULL,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (url),
    CONSTRAINT fk_evaluations_url
        FOREIGN KEY (url) REFERENCES web_resources (url)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IF NOT EXISTS idx_evaluations_domain ON evaluations (domain);

CREATE TABLE IF NOT EXISTS llm_judgments (
    url            VARCHAR(768) NOT NULL,
    domain         VARCHAR(255) NOT NULL,
    model_name     VARCHAR(255) NOT NULL,
    judge_score    TINYINT      NOT NULL,
    judge_feedback TEXT         NOT NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (url),
    CONSTRAINT fk_llm_judgments_url
        FOREIGN KEY (url) REFERENCES web_resources (url)
        ON DELETE CASCADE,
    CONSTRAINT chk_llm_judgments_score
        CHECK (judge_score BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IF NOT EXISTS idx_llm_judgments_domain ON llm_judgments (domain);
