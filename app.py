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
TABELA = "produtos" # 1 alteraçao

CAMPOS = [
    ("nome", "Nome", "text"),
    ("categoria", "Categoria", "text"),
    # novo ex- ("tamanho", "Tamanho", "text"),
    # novo ex- ("cor", "Cor", "text"), 
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

    # ----- dados iniciais 5 ou 6 alteraçao, acrescentar as colunas no select, pesquise select no ctrlf para alterar tudo onde é necessário. Exemplo: SELECT id, nome, categoria, tamanho, cor, quantidade, estoque_minimo ...-----
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
    """Lê templates/<pagina>.html, troca {{CHAVE}} pelos dados
    e coloca tudo dentro de templates/base.html."""
    with open(f"templates/{pagina}.html", encoding="utf-8") as arquivo:
        conteudo = arquivo.read()

    for chave, valor in dados.items():
        conteudo = conteudo.replace("{{" + chave + "}}", str(valor))

    with open("templates/base.html", encoding="utf-8") as arquivo:
        base = arquivo.read()

    base = base.replace("{{TITULO}}", titulo).replace("{{REFRESH}}", refresh)
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


# ----- estoque  7 alteraçao eu acho - caso eu acrescentar mais colunas como tamanho e cor, devo mudar os numero dentro de p[3] e p[4] e deixar 5,6 (sempre contar do 0 a partir do id)-----
def pagina_estoque(req, d):
    produtos = consultar("""
        SELECT id, nome, categoria, quantidade, estoque_minimo
        FROM produtos ORDER BY nome ASC
    """)

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
        classe = " class='alerta'" if p[3] < p[4] else ""
        linhas_estoque += linha(p, classe=classe)

    linhas_historico = ""
    for m in historico:
        tipo = "Entrada" if m[1] == "ENTRADA" else "Saída"
        linhas_historico += linha((m[0], tipo, m[2], m[3], m[4]))

    req.enviar_html(render("estoque", titulo="Gestão de Estoque",
                           OPCOES=opcoes, HOJE=date.today().isoformat(),
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
# INICIAR
# =========================================================
if __name__ == "__main__":
    criar_banco()

    print(f"\nServidor iniciado em: http://localhost:{PORTA}")
    print("Pressione CTRL + C para parar.\n")

    HTTPServer(("localhost", PORTA), Servidor).serve_forever()

# =========================================================
# ANOTAÇÕES EXTRAS - SE A PROVA PEDIR PREÇO (campo decimal)
# =========================================================
# São 4 alterações: 3 no Python (CAMPOS, validar_campos, campos_form)
# e 1 no SQL (CREATE TABLE).
# SEMPRE apagar o arquivo .db antes de rodar, senão o banco não atualiza.
#
# ---------------------------------------------------------
# 1) CAMPOS (topo do arquivo): adicionar o preço NO FIM da lista
# ---------------------------------------------------------
# CAMPOS = [
#     ("nome", "Nome", "text"),
#     ("categoria", "Categoria", "text"),
#     ("quantidade", "Quantidade", "number"),
#     ("estoque_minimo", "Estoque mínimo", "number"),
#     ("preco", "Preço", "decimal"),      # novo
# ]
#
# ATENÇÃO: com o preço no FIM, o p[3] < p[4] da pagina_estoque() NÃO muda.
# Só mudar (para p[4] < p[5]) se o preço for colocado ANTES de "quantidade".
#
# ---------------------------------------------------------
# 2) SQL - criar_banco(): adicionar a coluna no CREATE TABLE
# ---------------------------------------------------------
# (cuidado com a VÍRGULA depois do DEFAULT 0 do estoque_minimo)
#             estoque_minimo INTEGER NOT NULL DEFAULT 0,
#             preco REAL NOT NULL DEFAULT 0
#
# ---------------------------------------------------------
# 3) validar_campos(): aceitar número com casa decimal
# ---------------------------------------------------------
# Trocar o bloco do "if tipo == "number":" por:
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
# 4) campos_form() (Ctrl+F "def campos_form"): o campo precisa de step
# ---------------------------------------------------------
# Dentro do for, trocar a linha "minimo = ..." e o "texto += (...)" por:
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






# =========================================================
# ANOTAÇÕES EXTRAS - SE A PROVA PEDIR CAMPOS NOVOS DE TEXTO
# (exemplo: tema roupas, com TAMANHO e COR)
# =========================================================
# São 3 alterações: 2 no Python (CAMPOS e o p[3]/p[4] da pagina_estoque)
# e 1 no SQL (CREATE TABLE).
# Campos de TEXTO não precisam mexer em validar_campos() nem em campos_form(),
# porque o tipo "text" já é tratado nas duas.
# SEMPRE apagar o arquivo .db antes de rodar, senão o banco não atualiza.
#
# ---------------------------------------------------------
# 1) CAMPOS (topo do arquivo): adicionar os campos novos
# ---------------------------------------------------------
# A ORDEM da lista é a ordem das colunas nas telas.
# Aqui coloquei depois de "categoria" e ANTES de "quantidade":
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
# 2) SQL - criar_banco(): adicionar as colunas no CREATE TABLE
# ---------------------------------------------------------
# Colocar dentro do CREATE TABLE IF NOT EXISTS produtos, depois de categoria:
#
#             categoria TEXT NOT NULL,
#             tamanho TEXT NOT NULL DEFAULT 'M',
#             cor TEXT NOT NULL DEFAULT 'Preto',
#
# IMPORTANTE: o DEFAULT é necessário! Os 3 produtos de exemplo (INSERT mais
# abaixo, em criar_banco) não informam tamanho nem cor. Sem o DEFAULT, o
# programa dá erro ao criar o banco. (Se preferir, tirar o DEFAULT e incluir
# tamanho e cor no INSERT dos produtos de exemplo.)
# Cuidado com as VÍRGULAS no fim de cada linha.
#
# ---------------------------------------------------------
# 3) pagina_estoque(): ajustar o alerta (p[3] e p[4])
# ---------------------------------------------------------
# Ctrl+F e procurar por "ALTERAR AQUI".
# Com tamanho e cor ANTES de quantidade, as posições mudam:
#     p[0]=id  p[1]=nome  p[2]=categoria  p[3]=tamanho  p[4]=cor
#     p[5]=quantidade  p[6]=estoque_minimo
# Então trocar:
#         classe = " class='alerta'" if p[3] < p[4] else ""
# por:
#         classe = " class='alerta'" if p[5] < p[6] else ""
#
# Se ESQUECER disso: erro ao abrir a tela de estoque (compara texto com
# número) ou alerta aparecendo nas linhas erradas.
#
# ATALHO SEM RISCO: se colocar tamanho e cor no FIM da lista CAMPOS (depois
# de estoque_minimo), o p[3] < p[4] NÃO muda. Só as colunas aparecem numa
# ordem menos natural nas tabelas.
#
# SE A PROVA PEDIR PREÇO JUNTO: colocar o preço SEMPRE no fim de CAMPOS.
# Assim o p[5] < p[6] continua valendo.
#
# ---------------------------------------------------------
# 4) OPCIONAL - textos dos templates
# ---------------------------------------------------------
# Trocar "Produtos", "Cadastro de Produtos" etc. pelo tema novo
# (ex.: "Roupas"): Ctrl+Shift+H no VS Code troca em todos os arquivos.
# As tabelas e os formulários já mostram Tamanho e Cor sozinhos.
