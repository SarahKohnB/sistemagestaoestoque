import sqlite3
import html
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http import cookies
from datetime import date

DB_NAME = "almoxarifado_db.db"
PORTA = 8080

# =========================================================
# CONFIGURAÇÃO DO CADASTRO PRINCIPAL  (comece sempre por aqui)
# Formulários, tabelas, validação, INSERT, UPDATE e busca
# são gerados a partir desta lista.
#
#   (coluna no banco, rótulo na tela, tipo)
#   tipo: "text" ou "number"
# =========================================================
TABELA = "produtos"

CAMPOS = [
    ("nome", "Nome", "text"),
    ("categoria", "Categoria", "text"),
    ("quantidade", "Quantidade", "number"),
    ("estoque_minimo", "Estoque mínimo", "number"),
]

COLUNAS = [c[0] for c in CAMPOS]
COLUNAS_TEXTO = [c[0] for c in CAMPOS if c[2] == "text"]  # usadas na pesquisa


# =========================================================
# BANCO DE DADOS
# =========================================================
def conectar_banco():
    banco = sqlite3.connect(DB_NAME)
    banco.execute("PRAGMA foreign_keys = ON")
    return banco


def consultar(sql, params=()):
    """SELECT: devolve uma lista de tuplas."""
    banco = conectar_banco()
    resultado = banco.execute(sql, params).fetchall()
    banco.close()
    return resultado


def executar(*comandos):
    """INSERT/UPDATE/DELETE. Cada comando é uma tupla (sql, parametros).
    Todos são salvos juntos."""
    banco = conectar_banco()
    for sql, params in comandos:
        banco.execute(sql, params)
    banco.commit()
    banco.close()


def criar_banco():
    banco = conectar_banco()

    banco.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            data_movimento TEXT NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES produtos(id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );
    """)

    # ----- dados iniciais -----
    if banco.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        banco.executemany(
            "INSERT INTO usuarios (nome, usuario, senha) VALUES (?, ?, ?)",
            [("Administrador", "admin", "123"),
             ("Maria", "maria", "123"),
             ("João", "joao", "123")])

    if banco.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 0:
        banco.executemany(
            "INSERT INTO produtos (nome, categoria, quantidade, estoque_minimo) "
            "VALUES (?, ?, ?, ?)",
            [("Caixa de Papelão", "Embalagem", 100, 20),
             ("Frasco Plástico 500ml", "Embalagem", 50, 10),
             ("Pote Plástico 1L", "Embalagem", 30, 5)])

    if banco.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0] == 0:
        produtos = banco.execute(
            "SELECT id FROM produtos ORDER BY id LIMIT 3").fetchall()
        usuario = banco.execute(
            "SELECT id FROM usuarios ORDER BY id LIMIT 1").fetchone()

        if usuario and len(produtos) >= 3:
            banco.executemany(
                "INSERT INTO movimentacoes "
                "(produto_id, usuario_id, tipo, quantidade, data_movimento) "
                "VALUES (?, ?, ?, ?, ?)",
                [(p[0], usuario[0], "ENTRADA", qtd, "2026-09-15")
                 for p, qtd in zip(produtos, (100, 50, 30))])

    banco.commit()
    banco.close()


# =========================================================
# FUNÇÕES AUXILIARES DE HTML
# =========================================================
def esc(valor):
    return html.escape(str(valor))


def render(pagina, titulo="Controle de Estoque", refresh="", **dados):
    """Pega o HTML em PAGINAS (no final do arquivo), troca {{CHAVE}}
    pelos dados e coloca tudo dentro da página "base"."""
    conteudo = PAGINAS[pagina]

    for chave, valor in dados.items():
        conteudo = conteudo.replace("{{" + chave + "}}", str(valor))

    base = PAGINAS["base"].replace("{{TITULO}}", titulo).replace("{{REFRESH}}", refresh)
    return base.replace("{{CONTEUDO}}", conteudo)


def linha(celulas, acoes="", classe=""):
    """Monta um <tr>. 'celulas' é escapado; 'acoes' é HTML pronto."""
    tds = "".join(f"<td>{esc(c)}</td>" for c in celulas)
    if acoes:
        tds += f"<td>{acoes}</td>"
    return f"<tr{classe}>{tds}</tr>"


def campos_form(valores=None):
    """Gera os <input> do formulário a partir de CAMPOS."""
    texto = ""
    for i, (coluna, rotulo, tipo) in enumerate(CAMPOS):
        valor = esc(valores[i]) if valores else ""
        minimo = ' min="0"' if tipo == "number" else ""
        texto += (f'<label>{rotulo}:</label><br>'
                  f'<input type="{tipo}" name="{coluna}"{minimo} value="{valor}">'
                  f'<br><br>')
    return texto


def validar_campos(dados):
    """Devolve (lista_de_valores, None) ou (None, mensagem_de_erro)."""
    valores = []
    for coluna, rotulo, tipo in CAMPOS:
        valor = dados.get(coluna, "")

        if valor == "":
            return None, f"O campo {rotulo} é obrigatório."

        if tipo == "number":
            try:
                valor = int(valor)
            except ValueError:
                return None, f"O campo {rotulo} deve ser um número."
            if valor < 0:
                return None, f"O campo {rotulo} não pode ser negativo."

        valores.append(valor)
    return valores, None


# =========================================================
# TELAS (cada rota é uma função)
# =========================================================
def servir_css(req, d):
    try:
        with open("estilo.css", "rb") as arquivo:
            req.enviar(arquivo.read(), "text/css; charset=utf-8")
    except FileNotFoundError:
        req.enviar(b"", "text/css", 404)


# ----- login / menu -----
def pagina_login(req, d):
    req.enviar_html(render("login", titulo="Login"))


def fazer_login(req, d):
    pessoa = consultar(
        "SELECT id FROM usuarios WHERE usuario = ? AND senha = ?",
        (d.get("usuario", ""), d.get("senha", "")))

    if pessoa:
        req.redirecionar("/principal", f"usuario_id={pessoa[0][0]}; Path=/")
    else:
        req.mensagem("Não foi possível entrar",
                     ["Usuário ou senha incorretos."], "/login")


def sair(req, d):
    req.redirecionar("/login", "usuario_id=; Max-Age=0; Path=/")


def pagina_principal(req, d):
    nome = consultar("SELECT nome FROM usuarios WHERE id = ?",
                     (req.usuario_logado(),))
    nome = nome[0][0] if nome else "Usuário"
    req.enviar_html(render("principal", titulo="Menu Principal",
                           NOME_USUARIO=esc(nome)))


# ----- produtos (CRUD) -----
def pagina_produtos(req, d):
    busca = d.get("busca", "")

    sql = f"SELECT id, {', '.join(COLUNAS)} FROM {TABELA}"
    params = ()
    if busca:
        sql += " WHERE " + " OR ".join(f"{c} LIKE ?" for c in COLUNAS_TEXTO)
        params = ("%" + busca + "%",) * len(COLUNAS_TEXTO)
    sql += f" ORDER BY {COLUNAS[0]} ASC"

    linhas = ""
    for p in consultar(sql, params):
        acoes = (
            f'<a href="/editarProduto?id={p[0]}">Editar</a> &nbsp; | &nbsp; '
            f'<a href="/excluirProduto?id={p[0]}" '
            f'onclick="return confirm(\'Deseja realmente excluir este produto?\');">'
            f'Excluir</a>')
        linhas += linha(p, acoes)

    cabecalhos = "".join(
        f"<th>{r}</th>" for r in ["ID"] + [c[1] for c in CAMPOS] + ["Ações"])

    req.enviar_html(render("produtos", titulo="Cadastro de Produtos",
                           BUSCA=esc(busca), CAMPOS_FORM=campos_form(),
                           CABECALHOS=cabecalhos, LINHAS=linhas))


def cadastrar_produto(req, d):
    valores, erro = validar_campos(d)
    if erro:
        return req.mensagem("Erro", [erro], "/produtos")

    marcas = ", ".join("?" * len(COLUNAS))
    executar((f"INSERT INTO {TABELA} ({', '.join(COLUNAS)}) VALUES ({marcas})",
              valores))
    req.redirecionar("/produtos")


def pagina_editar(req, d):
    produto = consultar(
        f"SELECT id, {', '.join(COLUNAS)} FROM {TABELA} WHERE id = ?",
        (d.get("id", ""),))

    if not produto:
        return req.mensagem("Produto não encontrado", [], "/produtos")

    produto = produto[0]
    req.enviar_html(render("editar", titulo="Editar Produto",
                           ID=produto[0], CAMPOS_FORM=campos_form(produto[1:])))


def atualizar_produto(req, d):
    valores, erro = validar_campos(d)
    if erro:
        return req.mensagem("Erro", [erro], "/produtos")

    alteracoes = ", ".join(f"{c} = ?" for c in COLUNAS)
    executar((f"UPDATE {TABELA} SET {alteracoes} WHERE id = ?",
              valores + [d.get("id", "")]))
    req.redirecionar("/produtos")


def excluir_produto(req, d):
    id_produto = d.get("id", "")

    usos = consultar(
        "SELECT COUNT(*) FROM movimentacoes WHERE produto_id = ?",
        (id_produto,))[0][0]

    if usos > 0:
        return req.mensagem(
            "Não foi possível excluir",
            ["Este produto possui movimentações registradas no histórico.",
             "Para preservar o histórico, ele não pode ser excluído."],
            "/produtos")

    executar((f"DELETE FROM {TABELA} WHERE id = ?", (id_produto,)))
    req.redirecionar("/produtos")


# ----- estoque -----
def pagina_estoque(req, d):
    # As colunas vêm de CAMPOS, na mesma ordem. Posições (começa em 0):
    # p[0] = id, p[1] = 1º campo de CAMPOS, p[2] = 2º campo, e assim por diante.
    produtos = consultar(
        f"SELECT id, {', '.join(COLUNAS)} FROM {TABELA} ORDER BY {COLUNAS[0]} ASC")

    historico = consultar("""
        SELECT produtos.nome, movimentacoes.tipo, movimentacoes.quantidade,
               usuarios.nome, movimentacoes.data_movimento
        FROM movimentacoes
        INNER JOIN produtos ON produtos.id = movimentacoes.produto_id
        INNER JOIN usuarios ON usuarios.id = movimentacoes.usuario_id
        ORDER BY movimentacoes.id DESC
    """)

    opcoes = "".join(f'<option value="{p[0]}">{esc(p[1])}</option>'
                     for p in produtos)

    linhas_estoque = ""
    for p in produtos:
        # ALTERAR AQUI se mudar CAMPOS: p[3] = quantidade, p[4] = estoque_minimo
        # (ex.: com "tamanho" e "cor" a mais, vira p[5] < p[6])
        classe = " class='alerta'" if p[3] < p[4] else ""
        linhas_estoque += linha(p, classe=classe)

    linhas_historico = ""
    for m in historico:
        tipo = "Entrada" if m[1] == "ENTRADA" else "Saída"
        linhas_historico += linha((m[0], tipo, m[2], m[3], m[4]))

    cabecalhos = "".join(f"<th>{r}</th>" for r in ["ID"] + [c[1] for c in CAMPOS])

    req.enviar_html(render("estoque", titulo="Gestão de Estoque",
                           OPCOES=opcoes, HOJE=date.today().isoformat(),
                           CABECALHOS_ESTOQUE=cabecalhos,
                           LINHAS_ESTOQUE=linhas_estoque,
                           LINHAS_HISTORICO=linhas_historico))


def movimentar_estoque(req, d):
    produto_id = d.get("produto_id", "")
    tipo = d.get("tipo", "")
    quantidade = d.get("quantidade", "")
    data_movimento = d.get("data_movimento", "")

    # ----- validações -----
    erro = ""
    if produto_id == "":
        erro = "É necessário selecionar um produto."
    elif tipo not in ("ENTRADA", "SAIDA"):
        erro = "Tipo de movimentação inválido."
    elif quantidade == "":
        erro = "A quantidade é obrigatória."
    elif data_movimento == "":
        erro = "A data da movimentação é obrigatória."
    else:
        try:
            quantidade = int(quantidade)
            if quantidade <= 0:
                erro = "A quantidade deve ser maior que zero."
        except ValueError:
            erro = "A quantidade deve ser um número."

    if erro:
        return req.mensagem("Erro", [erro], "/estoque")

    produto = consultar(
        "SELECT nome, quantidade, estoque_minimo FROM produtos WHERE id = ?",
        (produto_id,))
    if not produto:
        return req.mensagem("Produto não encontrado.", [], "/estoque")

    nome, atual, minimo = produto[0]

    # ----- calcula o novo estoque -----
    if tipo == "SAIDA":
        if quantidade > atual:
            return req.mensagem(
                "Saída não permitida",
                ["A quantidade informada é maior que o estoque atual.",
                 "A movimentação não foi registrada."],
                "/estoque", 4)
        novo = atual - quantidade
    else:
        novo = atual + quantidade

    # ----- salva estoque + histórico juntos -----
    executar(
        ("UPDATE produtos SET quantidade = ? WHERE id = ?",
         (novo, produto_id)),
        ("INSERT INTO movimentacoes "
         "(produto_id, usuario_id, tipo, quantidade, data_movimento) "
         "VALUES (?, ?, ?, ?, ?)",
         (produto_id, req.usuario_logado(), tipo, quantidade, data_movimento)))

    # ----- alerta de estoque mínimo -----
    if tipo == "SAIDA" and novo < minimo:
        return req.mensagem(
            "⚠️ Atenção: estoque baixo",
            [f"O produto <strong>{esc(nome)}</strong> ficou abaixo do estoque mínimo.",
             f"Estoque atual: <strong>{novo}</strong>",
             f"Estoque mínimo: <strong>{minimo}</strong>"],
            "/estoque", 5, "alerta")

    req.redirecionar("/estoque")


# =========================================================
# ROTAS: endereço -> função
# =========================================================
ROTAS_GET = {
    "/": lambda req, d: req.redirecionar("/login"),
    "/estilo.css": servir_css,
    "/login": pagina_login,
    "/logout": sair,
    "/principal": pagina_principal,
    "/produtos": pagina_produtos,
    "/editarProduto": pagina_editar,
    "/excluirProduto": excluir_produto,
    "/estoque": pagina_estoque,
}

ROTAS_POST = {
    "/login": fazer_login,
    "/cadastrarProduto": cadastrar_produto,
    "/atualizarProduto": atualizar_produto,
    "/movimentarEstoque": movimentar_estoque,
}

# rotas que não exigem login
PUBLICAS = ("/", "/estilo.css", "/login", "/logout")


# =========================================================
# SERVIDOR
# =========================================================
class Servidor(BaseHTTPRequestHandler):

    def log_message(self, formato, *args):
        print(formato % args)

    # ----- respostas -----
    def enviar(self, conteudo, tipo, status=200):
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(conteudo)))
        self.end_headers()
        self.wfile.write(conteudo)

    def enviar_html(self, conteudo, status=200):
        self.enviar(conteudo.encode("utf-8"), "text/html; charset=utf-8", status)

    def redirecionar(self, caminho, cookie=None):
        self.send_response(302)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Location", caminho)
        self.end_headers()

    def mensagem(self, titulo, textos, destino, segundos=3, classe="erro"):
        """Página de aviso que volta sozinha para 'destino'."""
        refresh = f'<meta http-equiv="refresh" content="{segundos};url={destino}">'
        paragrafos = "".join(f"<p>{t}</p>" for t in textos)
        self.enviar_html(render("mensagem", titulo=titulo, refresh=refresh,
                                CLASSE=classe, TITULO_MSG=titulo,
                                TEXTOS=paragrafos))

    # ----- login -----
    def usuario_logado(self):
        try:
            recebidos = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            return None

        if "usuario_id" in recebidos and recebidos["usuario_id"].value.isdigit():
            return int(recebidos["usuario_id"].value)
        return None

    # ----- despacho -----
    def tratar(self, rotas, caminho, dados):
        funcao = rotas.get(caminho)

        if funcao is None:
            return self.enviar_html(
                '<h1>Página não encontrada</h1>'
                '<p><a href="/principal">Voltar ao início</a></p>', 404)

        if caminho not in PUBLICAS and self.usuario_logado() is None:
            return self.redirecionar("/login")

        funcao(self, dados)

    def do_GET(self):
        url = urlparse(self.path)
        dados = {k: v[0].strip() for k, v in parse_qs(url.query).items()}
        self.tratar(ROTAS_GET, url.path, dados)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho).decode("utf-8")
        dados = {k: v[0].strip() for k, v in parse_qs(corpo).items()}
        self.tratar(ROTAS_POST, urlparse(self.path).path, dados)


# =========================================================
# PÁGINAS (HTML de cada tela)
# {{ALGO}} é um espaço que o Python preenche em render().
# =========================================================
PAGINAS = {}

PAGINAS["base"] = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{{TITULO}}</title>
    {{REFRESH}}
    <link rel="stylesheet" href="/estilo.css">
</head>
<body>
{{CONTEUDO}}
</body>
</html>
"""

PAGINAS["login"] = """
<div class="login-container">
    <h1>Controle de Estoque</h1>
    <p>Entre no sistema</p>

    <form action="/login" method="POST">
        <label>Usuário:</label><br>
        <input type="text" name="usuario"><br><br>

        <label>Senha:</label><br>
        <input type="password" name="senha"><br><br>

        <button type="submit">Entrar</button>
    </form>

    <p>Usuário de teste: admin</p>
    <p>Senha: 123</p>
</div>
"""

PAGINAS["principal"] = """
<div class="menu">
    <h1>Sistema de Controle de Estoque</h1>
    <p class="boas-vindas">Bem-vindo, <strong>{{NOME_USUARIO}}</strong>!</p>

    <div class="menu-opcoes">
        <div class="menu-card">
            <h2>📦 Produtos</h2>
            <p>Cadastre, pesquise, edite e exclua produtos.</p>
            <a href="/produtos">Acessar produtos</a>
        </div>

        <div class="menu-card">
            <h2>📊 Estoque</h2>
            <p>Registre entradas, saídas e consulte o histórico.</p>
            <a href="/estoque">Acessar estoque</a>
        </div>
    </div>

    <div class="sair">
        <a href="/logout">Sair do sistema</a>
    </div>
</div>
"""

PAGINAS["produtos"] = """
<h1>Cadastro de Produtos</h1>
<p><a href="/principal">Voltar para o menu principal</a></p>
<hr>

<h2>Pesquisar produto</h2>
<form action="/produtos" method="GET">
    <input type="text" name="busca" placeholder="Digite o nome ou categoria" value="{{BUSCA}}">
    <button type="submit">Pesquisar</button>
</form>
<hr>

<h2>Cadastrar novo produto</h2>
<form action="/cadastrarProduto" method="POST">
    {{CAMPOS_FORM}}
    <button type="submit">Cadastrar produto</button>
</form>
<hr>

<h2>Produtos cadastrados</h2>
<table>
    <tr>{{CABECALHOS}}</tr>
    {{LINHAS}}
</table>
"""

PAGINAS["editar"] = """
<h1>Editar Produto</h1>

<form action="/atualizarProduto" method="POST">
    <input type="hidden" name="id" value="{{ID}}">
    {{CAMPOS_FORM}}
    <button type="submit">Salvar alterações</button>
</form>

<p><a href="/produtos">Voltar para produtos</a></p>
"""

PAGINAS["estoque"] = """
<h1>Gestão de Estoque</h1>
<p><a href="/principal">Voltar para o menu principal</a></p>
<hr>

<h2>Movimentação de Estoque</h2>
<form action="/movimentarEstoque" method="POST">
    <label>Produto:</label><br>
    <select name="produto_id">
        {{OPCOES}}
    </select>
    <br><br>

    <label>Tipo de movimentação:</label><br>
    <input type="radio" name="tipo" value="ENTRADA" checked> Entrada<br>
    <input type="radio" name="tipo" value="SAIDA"> Saída
    <br><br>

    <label>Quantidade:</label><br>
    <input type="number" name="quantidade" min="1">
    <br><br>

    <label>Data da movimentação:</label><br>
    <input type="date" name="data_movimento" value="{{HOJE}}">
    <br><br>

    <button type="submit">Registrar movimentação</button>
</form>
<hr>

<h2>Estoque atual</h2>
<table>
    <tr>{{CABECALHOS_ESTOQUE}}</tr>
    {{LINHAS_ESTOQUE}}
</table>
<hr>

<h2>Histórico de movimentações</h2>
<table>
    <tr>
        <th>Produto</th><th>Tipo</th><th>Quantidade</th><th>Responsável</th><th>Data</th>
    </tr>
    {{LINHAS_HISTORICO}}
</table>
"""

PAGINAS["mensagem"] = """
<div class="{{CLASSE}}">
    <h1>{{TITULO_MSG}}</h1>
    {{TEXTOS}}
    <p>Você será redirecionado.</p>
</div>
"""

# =========================================================
# INICIAR
# =========================================================
if __name__ == "__main__":
    criar_banco()

    print(f"\nServidor iniciado em: http://localhost:{PORTA}")
    print("Pressione CTRL + C para parar.\n")

    HTTPServer(("localhost", PORTA), Servidor).serve_forever()

# =========================================================
# ANOTAÇÕES EXTRAS - COMO ADAPTAR O SISTEMA NA PROVA (apagar a pasta templates)
# =========================================================
# REGRAS GERAIS (valem para tudo abaixo):
#  - SEMPRE apagar o arquivo .db antes de rodar, senão o banco não atualiza.
#  - Rodar o sistema depois de CADA passo, para achar o erro logo.
#  - A ordem dos campos na lista CAMPOS é a ordem das colunas nas telas.
#  - Os formulários, as tabelas, o INSERT, o UPDATE e a pesquisa se
#    adaptam sozinhos a partir da lista CAMPOS (lá no topo do arquivo).
#
# =========================================================
# PARTE A - ADICIONAR PREÇO (campo decimal)
# =========================================================
# São 4 alterações: CAMPOS, CREATE TABLE, validar_campos e campos_form.
#
# ---------------------------------------------------------
# A1) CAMPOS (topo do arquivo): adicionar o preço NO FIM da lista
# ---------------------------------------------------------
# CAMPOS = [
#     ("nome", "Nome", "text"),
#     ("categoria", "Categoria", "text"),
#     ("quantidade", "Quantidade", "number"),
#     ("estoque_minimo", "Estoque mínimo", "number"),
#     ("preco", "Preço", "decimal"),      # novo
# ]
#
# ATENÇÃO: com o preço no FIM, o "p[3] < p[4]" da pagina_estoque()
# NÃO muda. Só mudar se o preço for colocado ANTES de "quantidade".
#
# ---------------------------------------------------------
# A2) SQL - criar_banco(): adicionar a coluna no CREATE TABLE
# ---------------------------------------------------------
# Ctrl+F: "CREATE TABLE IF NOT EXISTS produtos"
# Cuidado com a VÍRGULA depois do DEFAULT 0 do estoque_minimo:
#
#             estoque_minimo INTEGER NOT NULL DEFAULT 0,
#             preco REAL NOT NULL DEFAULT 0
#
# (REAL e não INTEGER, para aceitar centavos. O DEFAULT 0 faz os
#  3 produtos de exemplo continuarem funcionando sem informar preço.)
#
# ---------------------------------------------------------
# A3) validar_campos(): aceitar número com casa decimal
# ---------------------------------------------------------
# Ctrl+F: "def validar_campos"
# Trocar o bloco do "if tipo == "number":" por:
#
#         if tipo in ("number", "decimal"):
#             try:
#                 if tipo == "number":
#                     valor = int(valor)
#                 else:
#                     valor = float(valor.replace(",", "."))
#             except ValueError:
#                 return None, f"O campo {rotulo} deve ser um número."
#
# (o replace troca vírgula por ponto, porque o Python só entende o
#  ponto: "49,90" vira "49.90")
#
# ---------------------------------------------------------
# A4) campos_form(): o campo precisa do step="0.01"
# ---------------------------------------------------------
# Ctrl+F: "def campos_form"
# Dentro do for, apagar a linha "minimo = ..." e trocar o "texto += (...)" por:
#
#         if tipo == "text":
#             atributos = 'type="text"'
#         elif tipo == "number":
#             atributos = 'type="number" min="0"'
#         else:  # decimal
#             atributos = 'type="number" min="0" step="0.01"'
#
#         texto += (f'<label>{rotulo}:</label><br>'
#                   f'<input {atributos} name="{coluna}" value="{valor}">'
#                   f'<br><br>')
#
# (sem o step, o navegador só aceita número inteiro e recusa 49,90.
#  Sem esta alteração o campo vira uma caixa de texto comum)
#
# OBS: o preço aparece na tabela como 49.9 (e não 49,90). Funciona,
# só não tem formatação em reais.
#
# =========================================================
# PARTE B - ADICIONAR CAMPOS DE TEXTO (ex.: TAMANHO e COR, tema roupas)
# =========================================================
# Campos de TEXTO não mexem em validar_campos() nem em campos_form(),
# porque o tipo "text" já é tratado nas duas.
# São 3 alterações: CAMPOS, CREATE TABLE e o p[3]/p[4] da pagina_estoque.
#
# ---------------------------------------------------------
# B1) CAMPOS: adicionar os campos novos
# ---------------------------------------------------------
# Colocando depois de "categoria" e ANTES de "quantidade":
#
# CAMPOS = [
#     ("nome", "Nome", "text"),
#     ("categoria", "Categoria", "text"),
#     ("tamanho", "Tamanho", "text"),     # novo
#     ("cor", "Cor", "text"),             # novo
#     ("quantidade", "Quantidade", "number"),
#     ("estoque_minimo", "Estoque mínimo", "number"),
# ]
#
# ---------------------------------------------------------
# B2) SQL - criar_banco(): adicionar as colunas no CREATE TABLE
# ---------------------------------------------------------
# Ctrl+F: "CREATE TABLE IF NOT EXISTS produtos"
# Colocar depois de categoria:
#
#             categoria TEXT NOT NULL,
#             tamanho TEXT NOT NULL DEFAULT 'M',
#             cor TEXT NOT NULL DEFAULT 'Preto',
#
# O DEFAULT é NECESSÁRIO: os produtos de exemplo (INSERT mais abaixo,
# em criar_banco) não informam tamanho nem cor. Sem o DEFAULT dá erro
# ao criar o banco. (Alternativa: tirar o DEFAULT e incluir tamanho e
# cor no INSERT dos produtos de exemplo.)
# Cuidado com as VÍRGULAS no fim de cada linha.
#
# ---------------------------------------------------------
# B3) pagina_estoque(): ajustar o alerta (p[3] e p[4])
# ---------------------------------------------------------
# Ctrl+F: "ALTERAR AQUI"
# Com tamanho e cor ANTES de quantidade, as posições mudam
# (a contagem começa em 0, e o id é sempre p[0]):
#     p[0]=id  p[1]=nome  p[2]=categoria  p[3]=tamanho  p[4]=cor
#     p[5]=quantidade  p[6]=estoque_minimo
# Trocar:
#         classe = " class='alerta'" if p[3] < p[4] else ""
# por:
#         classe = " class='alerta'" if p[5] < p[6] else ""
#
# Se ESQUECER: erro ao abrir a tela de estoque (compara texto com
# número) ou alerta nas linhas erradas.
#
# ATALHO SEM RISCO: colocar tamanho e cor no FIM da lista CAMPOS
# (depois de estoque_minimo). Aí o p[3] < p[4] não muda.
#
# SE A PROVA PEDIR PREÇO JUNTO COM TAMANHO E COR: colocar o preço
# SEMPRE no fim de CAMPOS. Assim o p[5] < p[6] continua valendo.
#
# =========================================================
# PARTE C - TROCAR OS TEXTOS DA TELA (tema novo, ex.: "Roupas")
# =========================================================
# O HTML de todas as telas está no FINAL do arquivo, na seção
# "PÁGINAS (HTML de cada tela)". Textos como "Cadastro de Produtos",
# "Pesquisar produto", "Cadastrar produto", "Estoque" ficam lá.
# Outros textos estão nas funções (ex.: o confirm "Deseja realmente
# excluir este produto?" e os títulos nos render(...)).
#
# Usar Ctrl+Shift+H (substituir em todos os arquivos) trocando só os
# TEXTOS que aparecem na tela.
# NÃO trocar o "produtos" que é nome de tabela, de rota ("/produtos")
# ou de função, senão o sistema para de funcionar.
#
# O placeholder da pesquisa ("Digite o nome ou categoria") também
# vale ajustar: a pesquisa busca em TODOS os campos de texto do CAMPOS.


# =========================================================
# PARTE D - TAMANHO + COR + PREÇO JUNTOS (tema roupas completo)
# =========================================================
# Testado: funciona. São 5 alterações, nesta ordem.
# Rodar o sistema depois de cada passo. Lembrar de apagar o .db.
#
# ---------------------------------------------------------
# D1) CAMPOS (topo do arquivo)
# ---------------------------------------------------------
# Tamanho e cor ANTES de quantidade. Preço por ÚLTIMO.
#
# CAMPOS = [
#     ("nome", "Nome", "text"),
#     ("categoria", "Categoria", "text"),
#     ("tamanho", "Tamanho", "text"),            # novo
#     ("cor", "Cor", "text"),                    # novo
#     ("quantidade", "Quantidade", "number"),
#     ("estoque_minimo", "Estoque mínimo", "number"),
#     ("preco", "Preço", "decimal"),             # novo
# ]
#
# ---------------------------------------------------------
# D2) SQL - criar_banco(): CREATE TABLE
# ---------------------------------------------------------
# Ctrl+F: "CREATE TABLE IF NOT EXISTS produtos"
# A ORDEM das colunas aqui não precisa ser igual à do CAMPOS, mas
# o nome de cada coluna tem que ser IGUAL ao do CAMPOS.
# Cuidado com as VÍRGULAS (a última coluna não leva vírgula):
#
#             categoria TEXT NOT NULL,
#             tamanho TEXT NOT NULL DEFAULT 'M',
#             cor TEXT NOT NULL DEFAULT 'Preto',
#             quantidade INTEGER NOT NULL DEFAULT 0,
#             estoque_minimo INTEGER NOT NULL DEFAULT 0,
#             preco REAL NOT NULL DEFAULT 0
#
# (os DEFAULT são necessários: os produtos de exemplo, mais abaixo
#  em criar_banco, não informam tamanho, cor nem preço)
#
# ---------------------------------------------------------
# D3) validar_campos(): aceitar decimal
# ---------------------------------------------------------
# Ctrl+F: "def validar_campos"
# Trocar o bloco do "if tipo == "number":" por:
#
#         if tipo in ("number", "decimal"):
#             try:
#                 if tipo == "number":
#                     valor = int(valor)
#                 else:
#                     valor = float(valor.replace(",", "."))
#             except ValueError:
#                 return None, f"O campo {rotulo} deve ser um número."
#
# ---------------------------------------------------------
# D4) campos_form(): step="0.01" para o preço
# ---------------------------------------------------------
# Ctrl+F: "def campos_form"
# Dentro do for, apagar a linha "minimo = ..." e trocar o "texto += (...)" por:
#
#         if tipo == "text":
#             atributos = 'type="text"'
#         elif tipo == "number":
#             atributos = 'type="number" min="0"'
#         else:  # decimal
#             atributos = 'type="number" min="0" step="0.01"'
#
#         texto += (f'<label>{rotulo}:</label><br>'
#                   f'<input {atributos} name="{coluna}" value="{valor}">'
#                   f'<br><br>')
#
# ---------------------------------------------------------
# D5) pagina_estoque(): o alerta passa a ser p[5] e p[6]
# ---------------------------------------------------------
# Ctrl+F: "ALTERAR AQUI"
# Posições (contagem começa em 0):
#     p[0]=id  p[1]=nome  p[2]=categoria  p[3]=tamanho  p[4]=cor
#     p[5]=quantidade  p[6]=estoque_minimo  p[7]=preco
# Trocar:
#         classe = " class='alerta'" if p[3] < p[4] else ""
# por:
#         classe = " class='alerta'" if p[5] < p[6] else ""
#
# POR QUE o preço fica no fim: ele vem depois de estoque_minimo,
# então não desloca p[5] e p[6].
#
# ---------------------------------------------------------
# CONFERÊNCIA FINAL (se algo der errado)
# ---------------------------------------------------------
#  - Erro "no such column" ou "has no column": esqueceu de apagar o .db,
#    ou o nome da coluna no CREATE TABLE está diferente do CAMPOS.
#  - Erro de sintaxe SQL ao iniciar: vírgula faltando ou sobrando no
#    CREATE TABLE.
#  - Erro ao abrir a tela de estoque, ou alerta nas linhas erradas:
#    o p[5] < p[6] não foi ajustado (D5).
#  - Campo de preço aparece como caixa de texto, ou recusa 49,90:
#    esqueceu o campos_form() (D4).
#  - Preço dá "deve ser um número": esqueceu o validar_campos() (D3).
