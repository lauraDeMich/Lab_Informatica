CREATE DATABASE IF NOT EXISTS minerva_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE minerva_db;

CREATE TABLE IF NOT EXISTS web_resources (
    url         VARCHAR(2048) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    domain      VARCHAR(255)    NOT NULL,
    title       TEXT            NOT NULL DEFAULT '',
    html_text   LONGTEXT        NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (url),
    INDEX idx_wr_domain (domain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS gold_standard (
    url         VARCHAR(2048) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    gold_text   LONGTEXT        NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (url),
    CONSTRAINT fk_gs_web_resources
        FOREIGN KEY (url) REFERENCES web_resources (url)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS parsed_documents (
    id          INT             NOT NULL AUTO_INCREMENT,
    url         VARCHAR(2048) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    domain      VARCHAR(255)    NOT NULL,
    title       TEXT            NOT NULL DEFAULT '',
    parsed_text LONGTEXT        NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_pd_url (url),
    INDEX idx_pd_domain (domain),
    CONSTRAINT fk_pd_web_resources
        FOREIGN KEY (url) REFERENCES web_resources (url)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS evaluations (
    id              INT             NOT NULL AUTO_INCREMENT,
    url             VARCHAR(2048) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    domain          VARCHAR(255)    NOT NULL,
    tl_precision    FLOAT           NOT NULL DEFAULT 0.0,
    tl_recall       FLOAT           NOT NULL DEFAULT 0.0,
    tl_f1           FLOAT           NOT NULL DEFAULT 0.0,
    extra_metric_name  VARCHAR(128) NOT NULL DEFAULT '',
    extra_metric_score FLOAT        NOT NULL DEFAULT 0.0,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_ev_url (url),
    INDEX idx_ev_domain (domain),
    CONSTRAINT fk_ev_web_resources
        FOREIGN KEY (url) REFERENCES web_resources (url)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS llm_judgments (
    id              INT             NOT NULL AUTO_INCREMENT,
    url             VARCHAR(2048) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    domain          VARCHAR(255)    NOT NULL,
    model_name      VARCHAR(128)    NOT NULL,
    judge_score     TINYINT         NOT NULL CHECK (judge_score BETWEEN 1 AND 5),
    judge_feedback  TEXT            NOT NULL DEFAULT '',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_lj_url (url),
    INDEX idx_lj_domain (domain),
    CONSTRAINT fk_lj_web_resources
        FOREIGN KEY (url) REFERENCES web_resources (url)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;