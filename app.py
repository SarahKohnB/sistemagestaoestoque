import sqlite3
import html
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http import cookies
from datetime import date


# =========================
# CONFIGURAÇÕES
# =========================

DB_NAME = "almoxarifado_db.db"
PORTA = 8080


# =========================
# BANCO DE DADOS
# =========================

def conectar_banco():
    banco = sqlite3.connect(DB_NAME)
    banco.execute("PRAGMA foreign_keys = ON")
    return banco


def criar_banco():

    banco = conectar_banco()

    # -------------------------
    # TABELA USUÁRIOS
    # -------------------------

    banco.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        )
    """)

    # -------------------------
    # TABELA PRODUTOS
    # -------------------------

    banco.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 0
        )
    """)

    # -------------------------
    # TABELA MOVIMENTAÇÕES
    # -------------------------

    banco.execute("""
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
        )
    """)

    banco.commit()

    # =========================
    # DADOS INICIAIS
    # =========================

    quantidade_usuarios = banco.execute("""
        SELECT COUNT(*) FROM usuarios
    """).fetchone()[0]

    if quantidade_usuarios == 0:

        banco.execute("""
            INSERT INTO usuarios
            (nome, usuario, senha)
            VALUES (?, ?, ?)
        """, (
            "Administrador",
            "admin",
            "123"
        ))

        banco.execute("""
            INSERT INTO usuarios
            (nome, usuario, senha)
            VALUES (?, ?, ?)
        """, (
            "Maria",
            "maria",
            "123"
        ))

        banco.execute("""
            INSERT INTO usuarios
            (nome, usuario, senha)
            VALUES (?, ?, ?)
        """, (
            "João",
            "joao",
            "123"
        ))

        banco.commit()

    quantidade_produtos = banco.execute("""
        SELECT COUNT(*) FROM produtos
    """).fetchone()[0]

    if quantidade_produtos == 0:

        banco.execute("""
            INSERT INTO produtos
            (nome, categoria, quantidade, estoque_minimo)
            VALUES (?, ?, ?, ?)
        """, (
            "Caixa de Papelão",
            "Embalagem",
            100,
            20
        ))

        banco.execute("""
            INSERT INTO produtos
            (nome, categoria, quantidade, estoque_minimo)
            VALUES (?, ?, ?, ?)
        """, (
            "Frasco Plástico 500ml",
            "Embalagem",
            50,
            10
        ))

        banco.execute("""
            INSERT INTO produtos
            (nome, categoria, quantidade, estoque_minimo)
            VALUES (?, ?, ?, ?)
        """, (
            "Pote Plástico 1L",
            "Embalagem",
            30,
            5
        ))

        banco.commit()

    # -------------------------
    # MOVIMENTAÇÕES INICIAIS
    # -------------------------

    quantidade_movimentacoes = banco.execute("""
        SELECT COUNT(*) FROM movimentacoes
    """).fetchone()[0]

    if quantidade_movimentacoes == 0:

        produtos = banco.execute("""
            SELECT id
            FROM produtos
            ORDER BY id
            LIMIT 3
        """).fetchall()

        usuario = banco.execute("""
            SELECT id
            FROM usuarios
            ORDER BY id
            LIMIT 1
        """).fetchone()

        if usuario and len(produtos) >= 3:

            hoje = "2026-09-15"

            banco.execute("""
                INSERT INTO movimentacoes
                (produto_id, usuario_id, tipo, quantidade, data_movimento)
                VALUES (?, ?, ?, ?, ?)
            """, (
                produtos[0][0],
                usuario[0],
                "ENTRADA",
                100,
                hoje
            ))

            banco.execute("""
                INSERT INTO movimentacoes
                (produto_id, usuario_id, tipo, quantidade, data_movimento)
                VALUES (?, ?, ?, ?, ?)
            """, (
                produtos[1][0],
                usuario[0],
                "ENTRADA",
                50,
                hoje
            ))

            banco.execute("""
                INSERT INTO movimentacoes
                (produto_id, usuario_id, tipo, quantidade, data_movimento)
                VALUES (?, ?, ?, ?, ?)
            """, (
                produtos[2][0],
                usuario[0],
                "ENTRADA",
                30,
                hoje
            ))

            banco.commit()

    banco.close()


# =========================
# SERVIDOR
# =========================

class Servidor(BaseHTTPRequestHandler):

    # =========================
    # DESABILITAR LOG MUITO GRANDE
    # =========================

    def log_message(self, formato, *args):
        print(formato % args)

    # =========================
    # ENVIAR HTML
    # =========================

    def enviar_html(self, conteudo):

        conteudo = conteudo.encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(conteudo))
        )

        self.end_headers()

        self.wfile.write(conteudo)

    # =========================
    # REDIRECIONAR
    # =========================

    def redirecionar(self, caminho):

        self.send_response(302)

        self.send_header(
            "Location",
            caminho
        )

        self.end_headers()

    # =========================
    # USUÁRIO LOGADO
    # =========================

    def obter_usuario_logado(self):

        cabecalho = self.headers.get("Cookie")

        if not cabecalho:
            return None

        cookies_recebidos = cookies.SimpleCookie()

        try:
            cookies_recebidos.load(cabecalho)
        except:
            return None

        if "usuario_id" not in cookies_recebidos:
            return None

        try:
            return int(
                cookies_recebidos["usuario_id"].value
            )
        except:
            return None

    # =========================
    # NOME DO USUÁRIO
    # =========================

    def obter_nome_usuario(self, usuario_id):

        banco = conectar_banco()

        usuario = banco.execute("""
            SELECT nome
            FROM usuarios
            WHERE id = ?
        """, (usuario_id,)).fetchone()

        banco.close()

        if usuario:
            return usuario[0]

        return "Usuário"

    # =========================
    # GET
    # =========================

    def do_GET(self):

        # =========================
        # ARQUIVO CSS
        # =========================

        if urlparse(self.path).path == "/estilo.css":

            try:

                with open(
                    "estilo.css",
                    "rb"
                ) as arquivo:

                    conteudo = arquivo.read()

                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "text/css; charset=utf-8"
                )

                self.send_header(
                    "Content-Length",
                    str(len(conteudo))
                )

                self.end_headers()

                self.wfile.write(conteudo)

            except FileNotFoundError:

                self.send_response(404)
                self.end_headers()

            return

        # =========================
        # CAMINHO
        # =========================

        caminho = urlparse(self.path).path

        parametros = parse_qs(
            urlparse(self.path).query
        )

        # =========================
        # INÍCIO
        # =========================

        if caminho == "/":

            self.redirecionar("/login")
            return

        # =========================
        # LOGIN
        # =========================

        if caminho == "/login":

            self.enviar_html("""
            <!DOCTYPE html>

            <html lang="pt-BR">

            <head>

                <meta charset="UTF-8">

                <title>Login</title>

                <link
                    rel="stylesheet"
                    href="/estilo.css"
                >

            </head>

            <body>

                <div class="login-container">

                    <h1>Controle de Estoque</h1>

                    <p>
                        Entre no sistema
                    </p>

                    <form
                        action="/login"
                        method="POST"
                    >

                        <label>
                            Usuário:
                        </label>

                        <br>

                        <input
                            type="text"
                            name="usuario"
                        >

                        <br><br>

                        <label>
                            Senha:
                        </label>

                        <br>

                        <input
                            type="password"
                            name="senha"
                        >

                        <br><br>

                        <button type="submit">
                            Entrar
                        </button>

                    </form>

                    <p>
                        Usuário de teste:
                        admin
                    </p>

                    <p>
                        Senha:
                        123
                    </p>

                </div>

            </body>

            </html>
            """)

            return

        # =========================
        # PRINCIPAL
        # =========================

        if caminho == "/principal":

            usuario_id = self.obter_usuario_logado()

            if usuario_id is None:

                self.redirecionar("/login")
                return

            nome = self.obter_nome_usuario(
                usuario_id
            )

            self.enviar_html(f"""
            <!DOCTYPE html>

            <html lang="pt-BR">

            <head>

                <meta charset="UTF-8">

                <title>
                    Menu Principal
                </title>

                <link
                    rel="stylesheet"
                    href="/estilo.css"
                >

            </head>

            <body>

                <div class="menu">

                    <h1>
                        Sistema de Controle de Estoque
                    </h1>

                    <p class="boas-vindas">

                        Bem-vindo,
                        <strong>
                            {html.escape(nome)}
                        </strong>!

                    </p>

                    <div class="menu-opcoes">

                        <div class="menu-card">

                            <h2>
                                📦 Produtos
                            </h2>

                            <p>
                                Cadastre, pesquise,
                                edite e exclua produtos.
                            </p>

                            <a href="/produtos">
                                Acessar produtos
                            </a>

                        </div>

                        <div class="menu-card">

                            <h2>
                                📊 Estoque
                            </h2>

                            <p>
                                Registre entradas,
                                saídas e consulte
                                o histórico.
                            </p>

                            <a href="/estoque">
                                Acessar estoque
                            </a>

                        </div>

                    </div>

                    <div class="sair">

                        <a href="/logout">
                            Sair do sistema
                        </a>

                    </div>

                </div>

            </body>

            </html>
            """)

            return

        # =========================
        # LOGOUT
        # =========================

        if caminho == "/logout":

            self.send_response(302)

            self.send_header(
                "Set-Cookie",
                "usuario_id=; Max-Age=0; Path=/"
            )

            self.send_header(
                "Location",
                "/login"
            )

            self.end_headers()

            return

        # =========================
        # PRODUTOS
        # =========================

        if caminho == "/produtos":

            usuario_id = self.obter_usuario_logado()

            if usuario_id is None:

                self.redirecionar("/login")
                return

            busca = parametros.get(
                "busca",
                [""]
            )[0].strip()

            banco = conectar_banco()

            if busca:

                produtos = banco.execute("""
                    SELECT
                        id,
                        nome,
                        categoria,
                        quantidade,
                        estoque_minimo
                    FROM produtos
                    WHERE nome LIKE ?
                       OR categoria LIKE ?
                    ORDER BY nome ASC
                """, (
                    "%" + busca + "%",
                    "%" + busca + "%"
                )).fetchall()

            else:

                produtos = banco.execute("""
                    SELECT
                        id,
                        nome,
                        categoria,
                        quantidade,
                        estoque_minimo
                    FROM produtos
                    ORDER BY nome ASC
                """).fetchall()

            banco.close()

            linhas = ""

            for produto in produtos:

                linhas += f"""
                <tr>

                    <td>
                        {produto[0]}
                    </td>

                    <td>
                        {html.escape(produto[1])}
                    </td>

                    <td>
                        {html.escape(produto[2])}
                    </td>

                    <td>
                        {produto[3]}
                    </td>

                    <td>
                        {produto[4]}
                    </td>

                    <td>

                        <a href="/editarProduto?id={produto[0]}">
                            Editar
                        </a>

                        &nbsp; | &nbsp;

                        <a
                            href="/excluirProduto?id={produto[0]}"
                            onclick="return confirm('Deseja realmente excluir este produto?');"
                        >
                            Excluir
                        </a>

                    </td>

                </tr>
                """

            self.enviar_html(f"""
            <!DOCTYPE html>

            <html lang="pt-BR">

            <head>

                <meta charset="UTF-8">

                <title>
                    Cadastro de Produtos
                </title>

                <link
                    rel="stylesheet"
                    href="/estilo.css"
                >

            </head>

            <body>

                <h1>
                    Cadastro de Produtos
                </h1>

                <p>

                    <a href="/principal">
                        Voltar para o menu principal
                    </a>

                </p>

                <hr>

                <h2>
                    Pesquisar produto
                </h2>

                <form
                    action="/produtos"
                    method="GET"
                >

                    <input
                        type="text"
                        name="busca"
                        placeholder="Digite o nome ou categoria"
                        value="{html.escape(busca)}"
                    >

                    <button type="submit">
                        Pesquisar
                    </button>

                </form>

                <hr>

                <h2>
                    Cadastrar novo produto
                </h2>

                <form
                    action="/cadastrarProduto"
                    method="POST"
                >

                    <label>
                        Nome do produto:
                    </label>

                    <br>

                    <input
                        type="text"
                        name="nome"
                    >

                    <br><br>

                    <label>
                        Categoria:
                    </label>

                    <br>

                    <input
                        type="text"
                        name="categoria"
                    >

                    <br><br>

                    <label>
                        Quantidade:
                    </label>

                    <br>

                    <input
                        type="number"
                        name="quantidade"
                        min="0"
                    >

                    <br><br>

                    <label>
                        Estoque mínimo:
                    </label>

                    <br>

                    <input
                        type="number"
                        name="estoque_minimo"
                        min="0"
                    >

                    <br><br>

                    <button type="submit">
                        Cadastrar produto
                    </button>

                </form>

                <hr>

                <h2>
                    Produtos cadastrados
                </h2>

                <table>

                    <tr>

                        <th>ID</th>

                        <th>Nome</th>

                        <th>Categoria</th>

                        <th>Quantidade</th>

                        <th>Estoque mínimo</th>

                        <th>Ações</th>

                    </tr>

                    {linhas}

                </table>

            </body>

            </html>
            """)

            return

        # =========================
        # EDITAR PRODUTO
        # =========================

        if caminho == "/editarProduto":

            usuario_id = self.obter_usuario_logado()

            if usuario_id is None:

                self.redirecionar("/login")
                return

            id_produto = parametros.get(
                "id",
                [""]
            )[0]

            banco = conectar_banco()

            produto = banco.execute("""
                SELECT
                    id,
                    nome,
                    categoria,
                    quantidade,
                    estoque_minimo
                FROM produtos
                WHERE id = ?
            """, (
                id_produto,
            )).fetchone()

            banco.close()

            if not produto:

                self.enviar_html("""
                <h1>
                    Produto não encontrado
                </h1>

                <p>
                    <a href="/produtos">
                        Voltar
                    </a>
                </p>
                """)

                return

            self.enviar_html(f"""
            <!DOCTYPE html>

            <html lang="pt-BR">

            <head>

                <meta charset="UTF-8">

                <title>
                    Editar Produto
                </title>

                <link
                    rel="stylesheet"
                    href="/estilo.css"
                >

            </head>

            <body>

                <h1>
                    Editar Produto
                </h1>

                <form
                    action="/atualizarProduto"
                    method="POST"
                >

                    <input
                        type="hidden"
                        name="id"
                        value="{produto[0]}"
                    >

                    <label>
                        Nome:
                    </label>

                    <br>

                    <input
                        type="text"
                        name="nome"
                        value="{html.escape(produto[1])}"
                    >

                    <br><br>

                    <label>
                        Categoria:
                    </label>

                    <br>

                    <input
                        type="text"
                        name="categoria"
                        value="{html.escape(produto[2])}"
                    >

                    <br><br>

                    <label>
                        Quantidade:
                    </label>

                    <br>

                    <input
                        type="number"
                        name="quantidade"
                        min="0"
                        value="{produto[3]}"
                    >

                    <br><br>

                    <label>
                        Estoque mínimo:
                    </label>

                    <br>

                    <input
                        type="number"
                        name="estoque_minimo"
                        min="0"
                        value="{produto[4]}"
                    >

                    <br><br>

                    <button type="submit">
                        Salvar alterações
                    </button>

                </form>

                <p>

                    <a href="/produtos">
                        Voltar para produtos
                    </a>

                </p>

            </body>

            </html>
            """)

            return

        # =========================
        # EXCLUIR PRODUTO
        # =========================

        if caminho == "/excluirProduto":

            usuario_id = self.obter_usuario_logado()

            if usuario_id is None:

                self.redirecionar("/login")
                return

            id_produto = parametros.get(
                "id",
                [""]
            )[0]

            banco = conectar_banco()

            movimentacoes = banco.execute("""
                SELECT COUNT(*)
                FROM movimentacoes
                WHERE produto_id = ?
            """, (
                id_produto,
            )).fetchone()[0]

            if movimentacoes > 0:

                banco.close()

                self.enviar_html("""
                <!DOCTYPE html>

                <html lang="pt-BR">

                <head>

                    <meta charset="UTF-8">

                    <meta
                        http-equiv="refresh"
                        content="3;url=/produtos"
                    >

                    <link
                        rel="stylesheet"
                        href="/estilo.css"
                    >

                </head>

                <body>

                    <h1>
                        Não foi possível excluir
                    </h1>

                    <p>
                        Este produto possui movimentações
                        registradas no histórico.
                    </p>

                    <p>
                        Para preservar o histórico,
                        ele não pode ser excluído.
                    </p>

                    <p>
                        Você será redirecionado
                        para os produtos.
                    </p>

                </body>

                </html>
                """)

                return

            banco.execute("""
                DELETE FROM produtos
                WHERE id = ?
            """, (
                id_produto,
            ))

            banco.commit()
            banco.close()

            self.redirecionar("/produtos")
            return

        # =========================
        # ESTOQUE
        # =========================

        if caminho == "/estoque":

            usuario_id = self.obter_usuario_logado()

            if usuario_id is None:

                self.redirecionar("/login")
                return

            banco = conectar_banco()

            produtos = banco.execute("""
                SELECT
                    id,
                    nome,
                    categoria,
                    quantidade,
                    estoque_minimo
                FROM produtos
                ORDER BY nome ASC
            """).fetchall()

            historico = banco.execute("""
                SELECT
                    produtos.nome,
                    movimentacoes.tipo,
                    movimentacoes.quantidade,
                    usuarios.nome,
                    movimentacoes.data_movimento
                FROM movimentacoes

                INNER JOIN produtos
                    ON produtos.id =
                       movimentacoes.produto_id

                INNER JOIN usuarios
                    ON usuarios.id =
                       movimentacoes.usuario_id

                ORDER BY
                    movimentacoes.id DESC
            """).fetchall()

            banco.close()

            opcoes = ""

            for produto in produtos:

                opcoes += f"""
                <option value="{produto[0]}">
                    {html.escape(produto[1])}
                </option>
                """

            linhas_estoque = ""

            for produto in produtos:

                classe = ""

                if produto[3] < produto[4]:

                    classe = " class='alerta'"

                linhas_estoque += f"""
                <tr{classe}>

                    <td>
                        {produto[0]}
                    </td>

                    <td>
                        {html.escape(produto[1])}
                    </td>

                    <td>
                        {html.escape(produto[2])}
                    </td>

                    <td>
                        {produto[3]}
                    </td>

                    <td>
                        {produto[4]}
                    </td>

                </tr>
                """

            linhas_historico = ""

            for movimento in historico:

                tipo = movimento[1]

                if tipo == "ENTRADA":

                    tipo_exibido = "Entrada"

                else:

                    tipo_exibido = "Saída"

                linhas_historico += f"""
                <tr>

                    <td>
                        {html.escape(movimento[0])}
                    </td>

                    <td>
                        {tipo_exibido}
                    </td>

                    <td>
                        {movimento[2]}
                    </td>

                    <td>
                        {html.escape(movimento[3])}
                    </td>

                    <td>
                        {html.escape(movimento[4])}
                    </td>

                </tr>
                """

            hoje = date.today().isoformat()

            self.enviar_html(f"""
            <!DOCTYPE html>

            <html lang="pt-BR">

            <head>

                <meta charset="UTF-8">

                <title>
                    Gestão de Estoque
                </title>

                <link
                    rel="stylesheet"
                    href="/estilo.css"
                >

            </head>

            <body>

                <h1>
                    Gestão de Estoque
                </h1>

                <p>

                    <a href="/principal">
                        Voltar para o menu principal
                    </a>

                </p>

                <hr>

                <h2>
                    Movimentação de Estoque
                </h2>

                <form
                    action="/movimentarEstoque"
                    method="POST"
                >

                    <label>
                        Produto:
                    </label>

                    <br>

                    <select name="produto_id">

                        {opcoes}

                    </select>

                    <br><br>

                    <label>
                        Tipo de movimentação:
                    </label>

                    <br>

                    <input
                        type="radio"
                        name="tipo"
                        value="ENTRADA"
                        checked
                    >

                    Entrada

                    <br>

                    <input
                        type="radio"
                        name="tipo"
                        value="SAIDA"
                    >

                    Saída

                    <br><br>

                    <label>
                        Quantidade:
                    </label>

                    <br>

                    <input
                        type="number"
                        name="quantidade"
                        min="1"
                    >

                    <br><br>

                    <label>
                        Data da movimentação:
                    </label>

                    <br>

                    <input
                        type="date"
                        name="data_movimento"
                        value="{hoje}"
                    >

                    <br><br>

                    <button type="submit">
                        Registrar movimentação
                    </button>

                </form>

                <hr>

                <h2>
                    Estoque atual
                </h2>

                <table>

                    <tr>

                        <th>ID</th>

                        <th>Produto</th>

                        <th>Categoria</th>

                        <th>Quantidade</th>

                        <th>Estoque mínimo</th>

                    </tr>

                    {linhas_estoque}

                </table>

                <hr>

                <h2>
                    Histórico de movimentações
                </h2>

                <table>

                    <tr>

                        <th>
                            Produto
                        </th>

                        <th>
                            Tipo
                        </th>

                        <th>
                            Quantidade
                        </th>

                        <th>
                            Responsável
                        </th>

                        <th>
                            Data
                        </th>

                    </tr>

                    {linhas_historico}

                </table>

            </body>

            </html>
            """)

            return

        # =========================
        # PÁGINA NÃO ENCONTRADA
        # =========================

        self.send_response(404)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write("""
        <h1>
            Página não encontrada
        </h1>

        <p>
            <a href="/principal">
                Voltar ao início
            </a>
        </p>
        """.encode("utf-8"))

    # =========================
    # POST
    # =========================

    def do_POST(self):

        caminho = urlparse(self.path).path

        tamanho = int(
            self.headers.get(
                "Content-Length",
                0
            )
        )

        corpo = self.rfile.read(
            tamanho
        ).decode("utf-8")

        formulario = parse_qs(
            corpo
        )

        # =========================
        # LOGIN
        # =========================

        if caminho == "/login":

            usuario = formulario.get(
                "usuario",
                [""]
            )[0].strip()

            senha = formulario.get(
                "senha",
                [""]
            )[0].strip()

            banco = conectar_banco()

            pessoa = banco.execute("""
                SELECT
                    id,
                    nome
                FROM usuarios
                WHERE usuario = ?
                  AND senha = ?
            """, (
                usuario,
                senha
            )).fetchone()

            banco.close()

            if pessoa:

                self.send_response(302)

                self.send_header(
                    "Set-Cookie",
                    f"usuario_id={pessoa[0]}; Path=/"
                )

                self.send_header(
                    "Location",
                    "/principal"
                )

                self.end_headers()

                return

            self.enviar_html("""
            <!DOCTYPE html>

            <html lang="pt-BR">

            <head>

                <meta charset="UTF-8">

                <meta
                    http-equiv="refresh"
                    content="3;url=/login"
                >

                <link
                    rel="stylesheet"
                    href="/estilo.css"
                >

            </head>

            <body>

                <div class="erro">

                    <h1>
                        Não foi possível entrar
                    </h1>

                    <p>
                        Usuário ou senha incorretos.
                    </p>

                    <p>
                        Você será redirecionado
                        para o login.
                    </p>

                </div>

            </body>

            </html>
            """)

            return

        # =========================
        # VERIFICAR LOGIN
        # =========================

        usuario_id = self.obter_usuario_logado()

        if usuario_id is None:

            self.redirecionar("/login")
            return

        # =========================
        # CADASTRAR PRODUTO
        # =========================

        if caminho == "/cadastrarProduto":

            nome = formulario.get(
                "nome",
                [""]
            )[0].strip()

            categoria = formulario.get(
                "categoria",
                [""]
            )[0].strip()

            quantidade = formulario.get(
                "quantidade",
                [""]
            )[0].strip()

            estoque_minimo = formulario.get(
                "estoque_minimo",
                [""]
            )[0].strip()

            erro = ""

            if nome == "":

                erro = (
                    "O nome do produto é obrigatório."
                )

            elif categoria == "":

                erro = (
                    "A categoria é obrigatória."
                )

            elif quantidade == "":

                erro = (
                    "A quantidade é obrigatória."
                )

            elif estoque_minimo == "":

                erro = (
                    "O estoque mínimo é obrigatório."
                )

            else:

                try:

                    quantidade = int(
                        quantidade
                    )

                    estoque_minimo = int(
                        estoque_minimo
                    )

                    if quantidade < 0:

                        erro = (
                            "A quantidade não pode "
                            "ser negativa."
                        )

                    elif estoque_minimo < 0:

                        erro = (
                            "O estoque mínimo não pode "
                            "ser negativo."
                        )

                except ValueError:

                    erro = (
                        "Quantidade e estoque mínimo "
                        "devem ser números."
                    )

            if erro:

                self.enviar_html(f"""
                <!DOCTYPE html>

                <html lang="pt-BR">

                <head>

                    <meta charset="UTF-8">

                    <meta
                        http-equiv="refresh"
                        content="3;url=/produtos"
                    >

                    <link
                        rel="stylesheet"
                        href="/estilo.css"
                    >

                </head>

                <body>

                    <div class="erro">

                        <h1>
                            Erro
                        </h1>

                        <p>
                            {html.escape(erro)}
                        </p>

                    </div>

                </body>

                </html>
                """)

                return

            banco = conectar_banco()

            banco.execute("""
                INSERT INTO produtos
                (
                    nome,
                    categoria,
                    quantidade,
                    estoque_minimo
                )
                VALUES (?, ?, ?, ?)
            """, (
                nome,
                categoria,
                quantidade,
                estoque_minimo
            ))

            banco.commit()
            banco.close()

            self.redirecionar("/produtos")
            return

        # =========================
        # ATUALIZAR PRODUTO
        # =========================

        if caminho == "/atualizarProduto":

            id_produto = formulario.get(
                "id",
                [""]
            )[0].strip()

            nome = formulario.get(
                "nome",
                [""]
            )[0].strip()

            categoria = formulario.get(
                "categoria",
                [""]
            )[0].strip()

            quantidade = formulario.get(
                "quantidade",
                [""]
            )[0].strip()

            estoque_minimo = formulario.get(
                "estoque_minimo",
                [""]
            )[0].strip()

            erro = ""

            if nome == "":

                erro = (
                    "O nome do produto é obrigatório."
                )

            elif categoria == "":

                erro = (
                    "A categoria é obrigatória."
                )

            else:

                try:

                    quantidade = int(
                        quantidade
                    )

                    estoque_minimo = int(
                        estoque_minimo
                    )

                    if quantidade < 0:

                        erro = (
                            "A quantidade não pode "
                            "ser negativa."
                        )

                    elif estoque_minimo < 0:

                        erro = (
                            "O estoque mínimo não pode "
                            "ser negativo."
                        )

                except ValueError:

                    erro = (
                        "Quantidade e estoque mínimo "
                        "devem ser números."
                    )

            if erro:

                self.enviar_html(f"""
                <!DOCTYPE html>

                <html lang="pt-BR">

                <head>

                    <meta charset="UTF-8">

                    <meta
                        http-equiv="refresh"
                        content="3;url=/produtos"
                    >

                    <link
                        rel="stylesheet"
                        href="/estilo.css"
                    >

                </head>

                <body>

                    <div class="erro">

                        <h1>
                            Erro
                        </h1>

                        <p>
                            {html.escape(erro)}
                        </p>

                    </div>

                </body>

                </html>
                """)

                return

            banco = conectar_banco()

            banco.execute("""
                UPDATE produtos

                SET
                    nome = ?,
                    categoria = ?,
                    quantidade = ?,
                    estoque_minimo = ?

                WHERE id = ?
            """, (
                nome,
                categoria,
                quantidade,
                estoque_minimo,
                id_produto
            ))

            banco.commit()
            banco.close()

            self.redirecionar("/produtos")
            return

        # =========================
        # MOVIMENTAR ESTOQUE
        # =========================

        if caminho == "/movimentarEstoque":

            produto_id = formulario.get(
                "produto_id",
                [""]
            )[0].strip()

            tipo = formulario.get(
                "tipo",
                [""]
            )[0].strip()

            quantidade = formulario.get(
                "quantidade",
                [""]
            )[0].strip()

            data_movimento = formulario.get(
                "data_movimento",
                [""]
            )[0].strip()

            erro = ""

            # -------------------------
            # VALIDAÇÕES
            # -------------------------

            if produto_id == "":

                erro = (
                    "É necessário selecionar um produto."
                )

            elif tipo not in [
                "ENTRADA",
                "SAIDA"
            ]:

                erro = (
                    "Tipo de movimentação inválido."
                )

            elif quantidade == "":

                erro = (
                    "A quantidade é obrigatória."
                )

            elif data_movimento == "":

                erro = (
                    "A data da movimentação "
                    "é obrigatória."
                )

            else:

                try:

                    quantidade = int(
                        quantidade
                    )

                    if quantidade <= 0:

                        erro = (
                            "A quantidade deve ser "
                            "maior que zero."
                        )

                except ValueError:

                    erro = (
                        "A quantidade deve ser "
                        "um número."
                    )

            if erro:

                self.enviar_html(f"""
                <!DOCTYPE html>

                <html lang="pt-BR">

                <head>

                    <meta charset="UTF-8">

                    <meta
                        http-equiv="refresh"
                        content="3;url=/estoque"
                    >

                    <link
                        rel="stylesheet"
                        href="/estilo.css"
                    >

                </head>

                <body>

                    <div class="erro">

                        <h1>
                            Erro
                        </h1>

                        <p>
                            {html.escape(erro)}
                        </p>

                    </div>

                </body>

                </html>
                """)

                return

            banco = conectar_banco()

            produto = banco.execute("""
                SELECT
                    id,
                    nome,
                    quantidade,
                    estoque_minimo
                FROM produtos
                WHERE id = ?
            """, (
                produto_id,
            )).fetchone()

            if not produto:

                banco.close()

                self.enviar_html("""
                <h1>
                    Produto não encontrado.
                </h1>

                <p>
                    <a href="/estoque">
                        Voltar
                    </a>
                </p>
                """)

                return

            quantidade_atual = produto[2]

            # -------------------------
            # SAÍDA MAIOR QUE ESTOQUE
            # -------------------------

            if tipo == "SAIDA":

                if quantidade > quantidade_atual:

                    banco.close()

                    self.enviar_html("""
                    <!DOCTYPE html>

                    <html lang="pt-BR">

                    <head>

                        <meta charset="UTF-8">

                        <meta
                            http-equiv="refresh"
                            content="4;url=/estoque"
                        >

                        <link
                            rel="stylesheet"
                            href="/estilo.css"
                        >

                    </head>

                    <body>

                        <div class="erro">

                            <h1>
                                Saída não permitida
                            </h1>

                            <p>
                                A quantidade informada
                                é maior que o estoque atual.
                            </p>

                            <p>
                                A movimentação não foi registrada.
                            </p>

                        </div>

                    </body>

                    </html>
                    """)

                    return

                nova_quantidade = (
                    quantidade_atual - quantidade
                )

            else:

                nova_quantidade = (
                    quantidade_atual + quantidade
                )

            # -------------------------
            # ATUALIZAR ESTOQUE
            # -------------------------

            banco.execute("""
                UPDATE produtos

                SET quantidade = ?

                WHERE id = ?
            """, (
                nova_quantidade,
                produto_id
            ))

            # -------------------------
            # REGISTRAR HISTÓRICO
            # -------------------------

            banco.execute("""
                INSERT INTO movimentacoes
                (
                    produto_id,
                    usuario_id,
                    tipo,
                    quantidade,
                    data_movimento
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                produto_id,
                usuario_id,
                tipo,
                quantidade,
                data_movimento
            ))

            banco.commit()

            estoque_minimo = produto[3]
            nome_produto = produto[1]

            banco.close()

            # -------------------------
            # ALERTA DE ESTOQUE MÍNIMO
            # -------------------------

            if (
                tipo == "SAIDA"
                and nova_quantidade < estoque_minimo
            ):

                self.enviar_html(f"""
                <!DOCTYPE html>

                <html lang="pt-BR">

                <head>

                    <meta charset="UTF-8">

                    <meta
                        http-equiv="refresh"
                        content="5;url=/estoque"
                    >

                    <link
                        rel="stylesheet"
                        href="/estilo.css"
                    >

                </head>

                <body>

                    <div class="alerta">

                        <h1>
                            ⚠️ Atenção: estoque baixo
                        </h1>

                        <p>

                            O produto
                            <strong>
                                {html.escape(nome_produto)}
                            </strong>

                            ficou abaixo do
                            estoque mínimo.

                        </p>

                        <p>

                            Estoque atual:
                            <strong>
                                {nova_quantidade}
                            </strong>

                        </p>

                        <p>

                            Estoque mínimo:
                            <strong>
                                {estoque_minimo}
                            </strong>

                        </p>

                        <p>
                            Você será redirecionado
                            para o estoque.
                        </p>

                    </div>

                </body>

                </html>
                """)

                return

            self.redirecionar("/estoque")
            return

        # =========================
        # POST NÃO ENCONTRADO
        # =========================

        self.send_response(404)
        self.end_headers()


# =========================
# INICIAR SISTEMA
# =========================

if __name__ == "__main__":

    criar_banco()

    servidor = HTTPServer(
        ("localhost", PORTA),
        Servidor
    )

    print("")
    print("==============================")
    print(" SISTEMA DE CONTROLE ESTOQUE")
    print("==============================")
    print("")
    print(
        "Servidor iniciado em:"
    )
    print(
        "http://localhost:8080"
    )
    print("")
    print(
        "Pressione CTRL + C para parar."
    )
    print("")

    servidor.serve_forever()