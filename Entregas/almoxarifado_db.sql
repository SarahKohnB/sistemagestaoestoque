-- ==========================================
-- BANCO DE DADOS: almoxarifado_db
-- SISTEMA DE GESTÃO DE ESTOQUE
-- INDÚSTRIA DE EMBALAGENS
-- ==========================================

-- ==========================================
-- TABELA: USUARIOS
-- ==========================================

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    usuario TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL
);


-- ==========================================
-- TABELA: PRODUTOS
-- ==========================================

CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 0,
    estoque_minimo INTEGER NOT NULL DEFAULT 0
);


-- ==========================================
-- TABELA: MOVIMENTACOES
-- ==========================================

CREATE TABLE IF NOT EXISTS movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    data_movimento TEXT NOT NULL,

    FOREIGN KEY (produto_id)
        REFERENCES produtos(id),

    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
);


-- ==========================================
-- INSERÇÃO DE USUÁRIOS
-- ==========================================

INSERT INTO usuarios
(nome, usuario, senha)
VALUES
('Administrador', 'admin', '123');

INSERT INTO usuarios
(nome, usuario, senha)
VALUES
('Maria', 'maria', '123');

INSERT INTO usuarios
(nome, usuario, senha)
VALUES
('João', 'joao', '123');


-- ==========================================
-- INSERÇÃO DE PRODUTOS
-- ==========================================

INSERT INTO produtos
(nome, categoria, quantidade, estoque_minimo)
VALUES
('Caixa de Papelão', 'Embalagem', 100, 20);

INSERT INTO produtos
(nome, categoria, quantidade, estoque_minimo)
VALUES
('Frasco Plástico 500ml', 'Embalagem', 50, 10);

INSERT INTO produtos
(nome, categoria, quantidade, estoque_minimo)
VALUES
('Pote Plástico 1L', 'Embalagem', 30, 5);


-- ==========================================
-- INSERÇÃO DE MOVIMENTAÇÕES
-- ==========================================

INSERT INTO movimentacoes
(produto_id, usuario_id, tipo, quantidade, data_movimento)
VALUES
(1, 1, 'ENTRADA', 100, '2026-09-15');

INSERT INTO movimentacoes
(produto_id, usuario_id, tipo, quantidade, data_movimento)
VALUES
(2, 1, 'ENTRADA', 50, '2026-09-15');

INSERT INTO movimentacoes
(produto_id, usuario_id, tipo, quantidade, data_movimento)
VALUES
(3, 1, 'ENTRADA', 30, '2026-09-15');