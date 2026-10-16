import sys
import csv
import json
import time
import hashlib
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLabel, QLineEdit, QSpinBox, QComboBox, QDateEdit, QDialogButtonBox,
    QMessageBox, QToolBar, QStatusBar, QFileDialog
)
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QDate, Signal, QObject, QRunnable, QThreadPool

# CONSTANTES

COLUNAS = ["Titulo", "Diretor", "Ano", "Genero", "Duracao", "Estoque", "Status"]

GENEROS = [
    "Acao", "Comedia", "Drama", "Terror",
    "Ficcao Cientifica", "Animacao", "Documentario", "Romance",
]

COLUNAS_CLIENTE = ["Nome", "CPF", "Telefone", "Email"]
COLUNAS_LOCACAO = ["Filme", "Cliente", "Retirada", "Prevista", "Status"]

# Pasta onde ficam os arquivos de dados (criada automaticamente)
PASTA_DADOS = Path(__file__).parent / "dados"
ARQ_FILMES = PASTA_DADOS / "filmes.json"
ARQ_CLIENTES = PASTA_DADOS / "clientes.csv"
ARQ_LOCACOES = PASTA_DADOS / "locacoes.json"
ARQ_USUARIOS = PASTA_DADOS / "usuarios.json"

# Credenciais do admin criadas na primeira execucao
ADMIN_PADRAO_USUARIO = "admin"
ADMIN_PADRAO_SENHA = "admin123"

# MODELOS

class Filme:
    def __init__(self, titulo, diretor, ano, genero, duracao_min, estoque):
        self.titulo = titulo
        self.diretor = diretor
        self.ano = ano
        self.genero = genero
        self.duracao_min = duracao_min
        self.estoque = estoque

    @property
    def status_disponibilidade(self):
        return "Disponivel" if self.estoque > 0 else "Indisponivel"

    def atualizar(self, titulo, diretor, ano, genero, duracao_min, estoque):
        # Atualiza o proprio objeto para as locacoes continuarem apontando para ele
        self.titulo = titulo
        self.diretor = diretor
        self.ano = ano
        self.genero = genero
        self.duracao_min = duracao_min
        self.estoque = estoque

    def para_dict(self):
        return {
            "titulo": self.titulo,
            "diretor": self.diretor,
            "ano": self.ano,
            "genero": self.genero,
            "duracao_min": self.duracao_min,
            "estoque": self.estoque,
        }

    def para_linha_tabela(self):
        return [
            self.titulo,
            self.diretor,
            str(self.ano),
            self.genero,
            f"{self.duracao_min} min",
            str(self.estoque),
            self.status_disponibilidade,
        ]


class Cliente:
    def __init__(self, nome, cpf, telefone, email=""):
        self.nome = nome
        self.cpf = cpf
        self.telefone = telefone
        self.email = email or ""

    def atualizar(self, nome, cpf, telefone, email=""):
        self.nome = nome
        self.cpf = cpf
        self.telefone = telefone
        self.email = email

    def para_dict(self):
        return {
            "nome": self.nome,
            "cpf": self.cpf,
            "telefone": self.telefone,
            "email": self.email,
        }

    def para_linha_tabela(self):
        return [self.nome, self.cpf, self.telefone, self.email]


class Locacao:
    VALOR_DIARIA_MULTA = 2.50

    def __init__(self, filme, cliente, data_prevista_devolucao=None):
        self.filme = filme
        self.cliente = cliente
        self.data_retirada = date.today()
        self.data_prevista_devolucao = data_prevista_devolucao or (date.today() + timedelta(days=3))
        self.data_devolucao = None

    @property
    def esta_ativa(self):
        return self.data_devolucao is None

    @property
    def dias_atraso(self):
        referencia = self.data_devolucao or date.today()
        atraso = (referencia - self.data_prevista_devolucao).days
        return atraso if atraso > 0 else 0

    @property
    def multa(self):
        return round(self.dias_atraso * self.VALOR_DIARIA_MULTA, 2)

    def devolver(self):
        self.data_devolucao = date.today()
        self.filme.estoque += 1

    def para_dict(self):
        # Guarda so o titulo e o CPF; os objetos sao religados ao carregar
        return {
            "filme": self.filme.titulo,
            "cliente_cpf": self.cliente.cpf,
            "retirada": self.data_retirada.isoformat(),
            "prevista": self.data_prevista_devolucao.isoformat(),
            "devolucao": self.data_devolucao.isoformat() if self.data_devolucao else None,
        }

    @classmethod
    def de_dict(cls, dados, filme, cliente):
        locacao = cls(filme, cliente, date.fromisoformat(dados["prevista"]))
        locacao.data_retirada = date.fromisoformat(dados["retirada"])
        if dados["devolucao"]:
            locacao.data_devolucao = date.fromisoformat(dados["devolucao"])
        # Nao mexe no estoque aqui: ele ja foi salvo com o valor atual
        return locacao

    def para_linha_tabela(self):
        status = "Ativa" if self.esta_ativa else "Devolvida"
        return [
            self.filme.titulo,
            self.cliente.nome,
            self.data_retirada.strftime("%d/%m/%Y"),
            self.data_prevista_devolucao.strftime("%d/%m/%Y"),
            status,
        ]

# AUTENTICACAO

def gerar_hash(texto):
    # Guarda so o hash da senha, nunca a senha em texto puro
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def somente_digitos(texto):
    # Permite comparar CPF com ou sem pontuacao
    return "".join(c for c in texto if c.isdigit())


class Sessao:
    # Guarda quem esta logado e qual o perfil de acesso
    def __init__(self, perfil, nome, cpf=None):
        self.perfil = perfil
        self.nome = nome
        self.cpf = cpf

    @property
    def eh_admin(self):
        return self.perfil == "admin"

    @property
    def descricao(self):
        return "Administrador" if self.eh_admin else f"Cliente: {self.nome}"

# PERSISTENCIA EM ARQUIVOS (SEM SGBD)

class Repositorio:
    # Filmes em JSON, clientes em CSV, locacoes em JSON, usuarios em JSON

    @staticmethod
    def salvar_filmes(filmes):
        PASTA_DADOS.mkdir(exist_ok=True)
        with open(ARQ_FILMES, "w", encoding="utf-8") as arquivo:
            json.dump([f.para_dict() for f in filmes], arquivo, ensure_ascii=False, indent=2)

    @staticmethod
    def carregar_filmes():
        if not ARQ_FILMES.exists():
            return []
        with open(ARQ_FILMES, encoding="utf-8") as arquivo:
            return [Filme(**dados) for dados in json.load(arquivo)]

    @staticmethod
    def salvar_clientes(clientes):
        PASTA_DADOS.mkdir(exist_ok=True)
        with open(ARQ_CLIENTES, "w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=["nome", "cpf", "telefone", "email"])
            escritor.writeheader()
            for cliente in clientes:
                escritor.writerow(cliente.para_dict())

    @staticmethod
    def carregar_clientes():
        if not ARQ_CLIENTES.exists():
            return []
        with open(ARQ_CLIENTES, encoding="utf-8", newline="") as arquivo:
            return [Cliente(**linha) for linha in csv.DictReader(arquivo)]

    @staticmethod
    def salvar_locacoes(locacoes):
        PASTA_DADOS.mkdir(exist_ok=True)
        with open(ARQ_LOCACOES, "w", encoding="utf-8") as arquivo:
            json.dump([l.para_dict() for l in locacoes], arquivo, ensure_ascii=False, indent=2)

    @staticmethod
    def carregar_locacoes(filmes, clientes):
        if not ARQ_LOCACOES.exists():
            return []
        filmes_por_titulo = {f.titulo: f for f in filmes}
        clientes_por_cpf = {c.cpf: c for c in clientes}
        locacoes = []
        with open(ARQ_LOCACOES, encoding="utf-8") as arquivo:
            for dados in json.load(arquivo):
                filme = filmes_por_titulo.get(dados["filme"])
                cliente = clientes_por_cpf.get(dados["cliente_cpf"])
                # Ignora locacao orfa (filme ou cliente que nao existe mais)
                if filme and cliente:
                    locacoes.append(Locacao.de_dict(dados, filme, cliente))
        return locacoes

    @staticmethod
    def carregar_usuarios():
        # Na primeira execucao cria o arquivo com o admin padrao
        if not ARQ_USUARIOS.exists():
            PASTA_DADOS.mkdir(exist_ok=True)
            with open(ARQ_USUARIOS, "w", encoding="utf-8") as arquivo:
                json.dump({ADMIN_PADRAO_USUARIO: gerar_hash(ADMIN_PADRAO_SENHA)}, arquivo, indent=2)
        with open(ARQ_USUARIOS, encoding="utf-8") as arquivo:
            return json.load(arquivo)

# ESTRUTURA PARA THREADING (QRunnable + QThreadPool)

class WorkerSignals(QObject):
    # Sinais Qt para comunicacao segura da thread secundaria com a thread principal
    finished = Signal()
    result = Signal(object)
    error = Signal(str)


class CarregarDadosWorker(QRunnable):
    # Tarefa em segundo plano que le os arquivos sem travar a interface
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()

    def run(self):
        try:
            # Simula uma tarefa demorada em paralelo (ex: busca na rede/banco)
            time.sleep(2)

            filmes = Repositorio.carregar_filmes()
            if not filmes:
                # Primeira execucao: cria um catalogo inicial
                filmes = [
                    Filme("De Volta para o Futuro", "Robert Zemeckis", 1985, "Ficcao Cientifica", 116, 3),
                    Filme("O Iluminado", "Stanley Kubrick", 1980, "Terror", 146, 2),
                    Filme("Coringa", "Todd Phillips", 2019, "Drama", 122, 5),
                    Filme("Matrix", "Lana Wachowski, Lilly Wachowski", 1999, "Ficcao Cientifica", 136, 4),
                ]
            clientes = Repositorio.carregar_clientes()
            locacoes = Repositorio.carregar_locacoes(filmes, clientes)

            self.signals.result.emit({"filmes": filmes, "clientes": clientes, "locacoes": locacoes})
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

# DIALOGS

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sessao = None
        self.setWindowTitle("Locadora - Login")
        self.setMinimumWidth(340)

        self.combo_perfil = QComboBox()
        self.combo_perfil.addItems(["Administrador", "Cliente"])

        self.rotulo_usuario = QLabel("Usuario:")
        self.campo_usuario = QLineEdit()
        self.rotulo_senha = QLabel("Senha:")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)

        self.rotulo_dica = QLabel()
        self.rotulo_dica.setWordWrap(True)
        self.rotulo_dica.setStyleSheet("color: gray;")

        layout_formulario = QFormLayout()
        layout_formulario.addRow("Entrar como:", self.combo_perfil)
        layout_formulario.addRow(self.rotulo_usuario, self.campo_usuario)
        layout_formulario.addRow(self.rotulo_senha, self.campo_senha)

        botoes_dialog = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.botoes = QDialogButtonBox(botoes_dialog)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")

        self.botoes.accepted.connect(self.tentar_login)
        self.botoes.rejected.connect(self.reject)
        self.combo_perfil.currentIndexChanged.connect(self._ao_mudar_perfil)
        self.campo_usuario.returnPressed.connect(self.tentar_login)
        self.campo_senha.returnPressed.connect(self.tentar_login)

        layout_principal = QVBoxLayout()
        layout_principal.addLayout(layout_formulario)
        layout_principal.addWidget(self.rotulo_dica)
        layout_principal.addWidget(self.botoes)
        self.setLayout(layout_principal)

        self._ao_mudar_perfil()

    def _ao_mudar_perfil(self):
        # Admin entra com usuario e senha; cliente entra so com o CPF cadastrado
        eh_admin = self.combo_perfil.currentIndex() == 0
        self.rotulo_usuario.setText("Usuario:" if eh_admin else "CPF:")
        self.rotulo_senha.setVisible(eh_admin)
        self.campo_senha.setVisible(eh_admin)
        self.campo_usuario.clear()
        self.campo_senha.clear()
        if eh_admin:
            self.rotulo_dica.setText("Acesso total ao sistema.")
        else:
            self.rotulo_dica.setText("Use o CPF informado no seu cadastro. Acesso limitado a consulta e aluguel.")
        self.campo_usuario.setFocus()

    def tentar_login(self):
        if self.combo_perfil.currentIndex() == 0:
            self._login_admin()
        else:
            self._login_cliente()

    def _login_admin(self):
        usuarios = Repositorio.carregar_usuarios()
        usuario = self.campo_usuario.text().strip()
        senha_hash = gerar_hash(self.campo_senha.text())
        if usuarios.get(usuario) == senha_hash:
            self.sessao = Sessao("admin", usuario)
            self.accept()
        else:
            QMessageBox.warning(self, "Login invalido", "Usuario ou senha incorretos.")
            self.campo_senha.clear()

    def _login_cliente(self):
        cpf_digitado = somente_digitos(self.campo_usuario.text())
        if cpf_digitado:
            for cliente in Repositorio.carregar_clientes():
                if somente_digitos(cliente.cpf) == cpf_digitado:
                    self.sessao = Sessao("cliente", cliente.nome, cliente.cpf)
                    self.accept()
                    return
        QMessageBox.warning(
            self, "Login invalido",
            "CPF nao encontrado. Peca ao administrador para cadastrar voce.",
        )


class FilmeDialog(QDialog):
    def __init__(self, parent=None, filme=None, titulos_usados=()):
        super().__init__(parent)
        self.filme_editado = filme
        # Titulos em minusculo que ja existem (para impedir duplicados)
        self.titulos_usados = set(titulos_usados)

        titulo_janela = "Editar filme" if filme else "Cadastrar novo filme"
        self.setWindowTitle(titulo_janela)
        self.setMinimumWidth(320)

        self.campo_titulo = QLineEdit()
        self.campo_diretor = QLineEdit()

        self.campo_ano = QSpinBox()
        self.campo_ano.setRange(1900, 2100)
        self.campo_ano.setValue(2026)

        self.campo_genero = QComboBox()
        self.campo_genero.addItems(GENEROS)

        self.campo_duracao = QSpinBox()
        self.campo_duracao.setRange(1, 500)
        self.campo_duracao.setSuffix(" min")
        self.campo_duracao.setValue(90)

        self.campo_estoque = QSpinBox()
        self.campo_estoque.setRange(0, 999)
        self.campo_estoque.setValue(1)

        if filme:
            self.campo_titulo.setText(filme.titulo)
            self.campo_diretor.setText(filme.diretor)
            self.campo_ano.setValue(filme.ano)
            indice_genero = self.campo_genero.findText(filme.genero)
            if indice_genero >= 0:
                self.campo_genero.setCurrentIndex(indice_genero)
            self.campo_duracao.setValue(filme.duracao_min)
            self.campo_estoque.setValue(filme.estoque)

        layout_formulario = QFormLayout()
        layout_formulario.addRow("Titulo:", self.campo_titulo)
        layout_formulario.addRow("Diretor:", self.campo_diretor)
        layout_formulario.addRow("Ano:", self.campo_ano)
        layout_formulario.addRow("Genero:", self.campo_genero)
        layout_formulario.addRow("Duracao:", self.campo_duracao)
        layout_formulario.addRow("Estoque:", self.campo_estoque)

        botoes_dialog = (
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes = QDialogButtonBox(botoes_dialog)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Salvar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")

        self.botoes.accepted.connect(self.validar_e_aceitar)
        self.botoes.rejected.connect(self.reject)

        layout_principal = QVBoxLayout()
        layout_principal.addLayout(layout_formulario)
        layout_principal.addWidget(self.botoes)
        self.setLayout(layout_principal)

    def validar_e_aceitar(self):
        titulo = self.campo_titulo.text().strip()
        if not titulo:
            QMessageBox.warning(self, "Campo obrigatorio", "Informe o titulo do filme.")
            return
        if not self.campo_diretor.text().strip():
            QMessageBox.warning(self, "Campo obrigatorio", "Informe o diretor do filme.")
            return
        if titulo.lower() in self.titulos_usados:
            QMessageBox.warning(self, "Titulo duplicado", "Ja existe um filme com esse titulo.")
            return
        self.accept()

    def obter_dados(self):
        return {
            "titulo": self.campo_titulo.text().strip(),
            "diretor": self.campo_diretor.text().strip(),
            "ano": self.campo_ano.value(),
            "genero": self.campo_genero.currentText(),
            "duracao_min": self.campo_duracao.value(),
            "estoque": self.campo_estoque.value(),
        }


class ClienteDialog(QDialog):
    def __init__(self, parent=None, cliente=None, cpfs_usados=()):
        super().__init__(parent)
        self.cliente_editado = cliente
        # CPFs (so digitos) que ja existem (para impedir duplicados)
        self.cpfs_usados = set(cpfs_usados)

        titulo_janela = "Editar cliente" if cliente else "Cadastrar novo cliente"
        self.setWindowTitle(titulo_janela)
        self.setMinimumWidth(320)

        self.campo_nome = QLineEdit()
        self.campo_cpf = QLineEdit()
        self.campo_telefone = QLineEdit()
        self.campo_email = QLineEdit()

        if cliente:
            self.campo_nome.setText(cliente.nome)
            self.campo_cpf.setText(cliente.cpf)
            self.campo_telefone.setText(cliente.telefone)
            self.campo_email.setText(cliente.email)

        layout_formulario = QFormLayout()
        layout_formulario.addRow("Nome:", self.campo_nome)
        layout_formulario.addRow("CPF:", self.campo_cpf)
        layout_formulario.addRow("Telefone:", self.campo_telefone)
        layout_formulario.addRow("Email:", self.campo_email)

        botoes_dialog = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.botoes = QDialogButtonBox(botoes_dialog)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Salvar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")

        self.botoes.accepted.connect(self.validar_e_aceitar)
        self.botoes.rejected.connect(self.reject)

        layout_principal = QVBoxLayout()
        layout_principal.addLayout(layout_formulario)
        layout_principal.addWidget(self.botoes)
        self.setLayout(layout_principal)

    def validar_e_aceitar(self):
        if not self.campo_nome.text().strip():
            QMessageBox.warning(self, "Campo obrigatorio", "Informe o nome do cliente.")
            return
        cpf = self.campo_cpf.text().strip()
        if not cpf:
            QMessageBox.warning(self, "Campo obrigatorio", "Informe o CPF do cliente.")
            return
        if somente_digitos(cpf) in self.cpfs_usados:
            QMessageBox.warning(self, "CPF duplicado", "Ja existe um cliente com esse CPF.")
            return
        self.accept()

    def obter_dados(self):
        return {
            "nome": self.campo_nome.text().strip(),
            "cpf": self.campo_cpf.text().strip(),
            "telefone": self.campo_telefone.text().strip(),
            "email": self.campo_email.text().strip(),
        }


class DevolucaoDialog(QDialog):
    def __init__(self, locacao, parent=None):
        super().__init__(parent)
        self.locacao = locacao
        self.setWindowTitle("Confirmar devolucao")
        self.setMinimumWidth(300)

        layout_info = QFormLayout()
        layout_info.addRow("Filme:", QLabel(locacao.filme.titulo))
        layout_info.addRow("Cliente:", QLabel(locacao.cliente.nome))
        layout_info.addRow("Prevista para:", QLabel(locacao.data_prevista_devolucao.strftime("%d/%m/%Y")))

        self.rotulo_atraso = QLabel(str(locacao.dias_atraso))
        self.rotulo_multa = QLabel(f"R$ {locacao.multa:.2f}")
        if locacao.dias_atraso > 0:
            self.rotulo_multa.setStyleSheet("color: red; font-weight: bold;")
        layout_info.addRow("Dias de atraso:", self.rotulo_atraso)
        layout_info.addRow("Multa:", self.rotulo_multa)

        botoes_dialog = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.botoes = QDialogButtonBox(botoes_dialog)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar devolucao")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)

        layout_principal = QVBoxLayout()
        layout_principal.addLayout(layout_info)
        layout_principal.addWidget(self.botoes)
        self.setLayout(layout_principal)

# JANELAS AUXILIARES

class DetalhesJanela(QWidget):
    def __init__(self, filme):
        super().__init__()
        self.setWindowTitle(f"Detalhes - {filme.titulo}")
        self.setMinimumWidth(300)

        rotulo_titulo = QLabel(filme.titulo)
        fonte = rotulo_titulo.font()
        fonte.setPointSize(14)
        fonte.setBold(True)
        rotulo_titulo.setFont(fonte)
        rotulo_titulo.setAlignment(Qt.AlignCenter)

        texto_info = (
            f"Diretor: {filme.diretor}\n"
            f"Ano de lancamento: {filme.ano}\n"
            f"Genero: {filme.genero}\n"
            f"Duracao: {filme.duracao_min} minutos\n"
            f"Copias em estoque: {filme.estoque}\n"
            f"Status: {filme.status_disponibilidade}"
        )
        rotulo_info = QLabel(texto_info)
        rotulo_info.setWordWrap(True)

        botao_fechar = QPushButton("Fechar")
        botao_fechar.clicked.connect(self.close)

        layout = QVBoxLayout()
        layout.addWidget(rotulo_titulo)
        layout.addWidget(rotulo_info)
        layout.addStretch()
        layout.addWidget(botao_fechar)
        self.setLayout(layout)


class ClientesWindow(QMainWindow):
    clientes_atualizados = Signal()

    def __init__(self, clientes, locacoes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Locadora - Cadastro de Clientes")
        self.resize(560, 420)
        self.clientes = clientes
        self.locacoes = locacoes

        self._montar_tabela()
        self._montar_menu()
        self._montar_barra_ferramentas()
        self._montar_barra_status()
        self._montar_layout_central()

        self._preencher_tabela()
        self._atualizar_estado_botoes()

    def _montar_tabela(self):
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(len(COLUNAS_CLIENTE))
        self.tabela.setHorizontalHeaderLabels(COLUNAS_CLIENTE)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.itemSelectionChanged.connect(self._atualizar_estado_botoes)

    def _montar_menu(self):
        menu = self.menuBar()
        menu_clientes = menu.addMenu("&Clientes")
        self.acao_novo = QAction("Novo cliente...", self)
        self.acao_novo.setShortcut(QKeySequence.New)
        self.acao_novo.triggered.connect(self.cadastrar_cliente)
        menu_clientes.addAction(self.acao_novo)

        self.acao_editar = QAction("Editar cliente...", self)
        self.acao_editar.triggered.connect(self.editar_cliente)
        menu_clientes.addAction(self.acao_editar)

        self.acao_excluir = QAction("Excluir cliente", self)
        self.acao_excluir.setShortcut(QKeySequence.Delete)
        self.acao_excluir.triggered.connect(self.excluir_cliente)
        menu_clientes.addAction(self.acao_excluir)

        menu_clientes.addSeparator()
        acao_fechar = QAction("Fechar janela", self)
        acao_fechar.triggered.connect(self.close)
        menu_clientes.addAction(acao_fechar)

    def _montar_barra_ferramentas(self):
        barra = QToolBar("Ferramentas de clientes")
        barra.setMovable(False)
        self.addToolBar(barra)
        barra.addAction(self.acao_novo)
        barra.addAction(self.acao_editar)
        barra.addAction(self.acao_excluir)

    def _montar_barra_status(self):
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto.")

    def _montar_layout_central(self):
        rotulo_cabecalho = QLabel("Clientes cadastrados")
        fonte = rotulo_cabecalho.font()
        fonte.setPointSize(13)
        fonte.setBold(True)
        rotulo_cabecalho.setFont(fonte)

        self.botao_novo = QPushButton("Novo")
        self.botao_editar = QPushButton("Editar")
        self.botao_excluir = QPushButton("Excluir")

        self.botao_novo.clicked.connect(self.cadastrar_cliente)
        self.botao_editar.clicked.connect(self.editar_cliente)
        self.botao_excluir.clicked.connect(self.excluir_cliente)

        layout_botoes = QHBoxLayout()
        layout_botoes.addWidget(self.botao_novo)
        layout_botoes.addWidget(self.botao_editar)
        layout_botoes.addWidget(self.botao_excluir)
        layout_botoes.addStretch()

        layout_principal = QVBoxLayout()
        layout_principal.addWidget(rotulo_cabecalho)
        layout_principal.addWidget(self.tabela)
        layout_principal.addLayout(layout_botoes)

        widget_central = QWidget()
        widget_central.setLayout(layout_principal)
        self.setCentralWidget(widget_central)

    def _preencher_tabela(self):
        self.tabela.setRowCount(len(self.clientes))
        for linha, cliente in enumerate(self.clientes):
            for coluna, valor in enumerate(cliente.para_linha_tabela()):
                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.tabela.setItem(linha, coluna, item)
        # Avisa a janela principal para salvar o arquivo
        self.clientes_atualizados.emit()

    def _cpfs_usados(self, ignorar=None):
        return {somente_digitos(c.cpf) for c in self.clientes if c is not ignorar}

    def _linha_selecionada(self):
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        return linhas[0].row()

    def _atualizar_estado_botoes(self):
        tem_selecao = self._linha_selecionada() is not None
        self.acao_editar.setEnabled(tem_selecao)
        self.acao_excluir.setEnabled(tem_selecao)
        self.botao_editar.setEnabled(tem_selecao)
        self.botao_excluir.setEnabled(tem_selecao)

    def cadastrar_cliente(self):
        dialog = ClienteDialog(self, cpfs_usados=self._cpfs_usados())
        if dialog.exec():
            dados = dialog.obter_dados()
            self.clientes.append(Cliente(**dados))
            self._preencher_tabela()
            self.statusBar().showMessage(f'Cliente "{dados["nome"]}" cadastrado com sucesso.', 4000)

    def editar_cliente(self):
        linha = self._linha_selecionada()
        if linha is None:
            return
        cliente_atual = self.clientes[linha]
        dialog = ClienteDialog(self, cliente=cliente_atual, cpfs_usados=self._cpfs_usados(ignorar=cliente_atual))
        if dialog.exec():
            dados = dialog.obter_dados()
            cliente_atual.atualizar(**dados)
            self._preencher_tabela()
            self.tabela.selectRow(linha)
            self.statusBar().showMessage("Cliente atualizado com sucesso.", 4000)

    def excluir_cliente(self):
        linha = self._linha_selecionada()
        if linha is None:
            return
        cliente = self.clientes[linha]

        # Nao deixa excluir cliente com filme alugado
        if any(l.cliente is cliente and l.esta_ativa for l in self.locacoes):
            QMessageBox.warning(self, "Impossivel excluir", "Este cliente possui locacao ativa.")
            return

        resposta = QMessageBox.question(
            self, "Confirmar exclusao",
            f'Tem certeza que deseja excluir o cliente "{cliente.nome}"?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            del self.clientes[linha]
            # Remove tambem o historico de locacoes desse cliente
            self.locacoes[:] = [l for l in self.locacoes if l.cliente is not cliente]
            self._preencher_tabela()
            self._atualizar_estado_botoes()
            self.statusBar().showMessage("Cliente excluido.", 4000)


class LocacaoWindow(QMainWindow):
    locacao_alterada = Signal()

    def __init__(self, filmes, clientes, locacoes, sessao, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Locadora - Aluguel e Devolucao")
        self.resize(700, 460)

        self.filmes = filmes
        self.clientes = clientes
        # Lista compartilhada com a janela principal (nao perde ao fechar)
        self.locacoes = locacoes
        self.sessao = sessao
        # Locacoes que aparecem na tabela (cliente so ve as proprias)
        self.locacoes_exibidas = []

        self._montar_formulario_aluguel()
        self._montar_tabela()
        self._montar_menu()
        self._montar_barra_ferramentas()
        self._montar_barra_status()
        self._montar_layout_central()

        self._atualizar_combos()
        self._preencher_tabela()
        self._atualizar_estado_botoes()

    def _montar_formulario_aluguel(self):
        self.combo_filme = QComboBox()
        self.combo_cliente = QComboBox()
        self.campo_prevista = QDateEdit(QDate.currentDate().addDays(3))
        self.campo_prevista.setCalendarPopup(True)

    def _montar_tabela(self):
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(len(COLUNAS_LOCACAO))
        self.tabela.setHorizontalHeaderLabels(COLUNAS_LOCACAO)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.itemSelectionChanged.connect(self._atualizar_estado_botoes)

    def _montar_menu(self):
        menu = self.menuBar()
        menu_locacao = menu.addMenu("&Locacao")
        self.acao_alugar = QAction("Registrar aluguel", self)
        self.acao_alugar.triggered.connect(self.registrar_locacao)
        menu_locacao.addAction(self.acao_alugar)

        self.acao_devolver = QAction("Registrar devolucao", self)
        self.acao_devolver.triggered.connect(self.abrir_dialog_devolucao)
        menu_locacao.addAction(self.acao_devolver)

        menu_locacao.addSeparator()
        acao_atualizar = QAction("Atualizar listas", self)
        acao_atualizar.triggered.connect(self._atualizar_combos)
        menu_locacao.addAction(acao_atualizar)

        menu_locacao.addSeparator()
        acao_fechar = QAction("Fechar janela", self)
        acao_fechar.triggered.connect(self.close)
        menu_locacao.addAction(acao_fechar)

    def _montar_barra_ferramentas(self):
        barra = QToolBar("Ferramentas de locacao")
        barra.setMovable(False)
        self.addToolBar(barra)
        barra.addAction(self.acao_alugar)
        barra.addAction(self.acao_devolver)

    def _montar_barra_status(self):
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto.")

    def _montar_layout_central(self):
        titulo = "Aluguel e devolucao de filmes" if self.sessao.eh_admin else "Meus alugueis"
        rotulo_cabecalho = QLabel(titulo)
        fonte = rotulo_cabecalho.font()
        fonte.setPointSize(13)
        fonte.setBold(True)
        rotulo_cabecalho.setFont(fonte)

        layout_formulario = QFormLayout()
        layout_formulario.addRow("Filme disponivel:", self.combo_filme)
        layout_formulario.addRow("Cliente:", self.combo_cliente)
        layout_formulario.addRow("Devolucao prevista:", self.campo_prevista)

        self.botao_alugar = QPushButton("Registrar aluguel")
        self.botao_alugar.clicked.connect(self.registrar_locacao)

        self.botao_devolver = QPushButton("Registrar devolucao")
        self.botao_devolver.clicked.connect(self.abrir_dialog_devolucao)

        layout_botoes = QHBoxLayout()
        layout_botoes.addWidget(self.botao_alugar)
        layout_botoes.addStretch()
        layout_botoes.addWidget(self.botao_devolver)

        layout_principal = QVBoxLayout()
        layout_principal.addWidget(rotulo_cabecalho)
        layout_principal.addLayout(layout_formulario)
        layout_principal.addWidget(self.tabela)
        layout_principal.addLayout(layout_botoes)

        widget_central = QWidget()
        widget_central.setLayout(layout_principal)
        self.setCentralWidget(widget_central)

    def _atualizar_combos(self):
        self.combo_filme.clear()
        for filme in self.filmes:
            if filme.estoque > 0:
                self.combo_filme.addItem(f"{filme.titulo} ({filme.estoque} em estoque)", userData=filme)

        self.combo_cliente.clear()
        for cliente in self.clientes:
            # Cliente logado so pode alugar em nome dele mesmo
            if self.sessao.eh_admin or cliente.cpf == self.sessao.cpf:
                self.combo_cliente.addItem(cliente.nome, userData=cliente)

        pode_alugar = self.combo_filme.count() > 0 and self.combo_cliente.count() > 0
        self.botao_alugar.setEnabled(pode_alugar)
        self.acao_alugar.setEnabled(pode_alugar)

    def _preencher_tabela(self):
        self.locacoes_exibidas = [
            l for l in self.locacoes
            if self.sessao.eh_admin or l.cliente.cpf == self.sessao.cpf
        ]
        self.tabela.setRowCount(len(self.locacoes_exibidas))
        for linha, locacao in enumerate(self.locacoes_exibidas):
            for coluna, valor in enumerate(locacao.para_linha_tabela()):
                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.tabela.setItem(linha, coluna, item)

    def _locacao_selecionada(self):
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        return self.locacoes_exibidas[linhas[0].row()]

    def _atualizar_estado_botoes(self):
        locacao = self._locacao_selecionada()
        pode_devolver = locacao is not None and locacao.esta_ativa
        self.botao_devolver.setEnabled(pode_devolver)
        self.acao_devolver.setEnabled(pode_devolver)

    def registrar_locacao(self):
        if self.combo_filme.count() == 0 or self.combo_cliente.count() == 0:
            QMessageBox.warning(
                self, "Impossivel registrar",
                "E preciso ter pelo menos um filme em estoque e um cliente cadastrado.",
            )
            return

        filme = self.combo_filme.currentData()
        cliente = self.combo_cliente.currentData()
        prevista = self.campo_prevista.date().toPython()

        locacao = Locacao(filme=filme, cliente=cliente, data_prevista_devolucao=prevista)
        filme.estoque -= 1
        self.locacoes.append(locacao)

        self._atualizar_combos()
        self._preencher_tabela()
        self.locacao_alterada.emit()
        self.statusBar().showMessage(f'Aluguel de "{filme.titulo}" registrado.', 4000)

    def abrir_dialog_devolucao(self):
        locacao = self._locacao_selecionada()
        if locacao is None:
            return

        if not locacao.esta_ativa:
            QMessageBox.information(self, "Ja devolvido", "Esta locacao ja foi encerrada.")
            return

        dialog = DevolucaoDialog(locacao, self)
        if dialog.exec():
            locacao.devolver()
            self._atualizar_combos()
            self._preencher_tabela()
            self.locacao_alterada.emit()
            self.statusBar().showMessage("Devolucao registrada.", 4000)


# JANELA PRINCIPAL

class MainWindow(QMainWindow):
    def __init__(self, sessao):
        super().__init__()

        self.sessao = sessao
        self.resize(760, 480)

        # Configuracao do pool de threads do Qt
        self.threadpool = QThreadPool.globalInstance()

        self.filmes = []
        self.clientes = []
        self.locacoes = []
        self.janelas_detalhes_abertas = []
        self.janela_clientes = None
        self.janela_locacao = None

        self._montar_tabela()
        self._montar_menu()
        self._montar_barra_ferramentas()
        self._montar_barra_status()
        self._montar_layout_central()

        self._aplicar_permissoes()
        self._atualizar_estado_botoes()

        # Carrega os dados dos arquivos em paralelo via threading
        self.carregar_filmes_em_paralelo()

    # CONTROLE DE ACESSO

    def _aplicar_permissoes(self):
        # Admin ve tudo; cliente so consulta filmes e mexe nos proprios alugueis
        eh_admin = self.sessao.eh_admin
        for acao in (self.acao_novo, self.acao_editar, self.acao_excluir,
                     self.acao_exportar_csv, self.acao_exportar_txt,
                     self.acao_importar, self.acao_clientes):
            acao.setVisible(eh_admin)
        for botao in (self.botao_novo, self.botao_editar, self.botao_excluir):
            botao.setVisible(eh_admin)

        self.setWindowTitle(f"Locadora de Filmes - Catalogo [{self.sessao.descricao}]")
        self.statusBar().showMessage(f"Logado como {self.sessao.descricao}.")

    def _exige_admin(self):
        # Segunda barreira: mesmo se alguem ativar a acao, o metodo bloqueia
        if self.sessao.eh_admin:
            return True
        QMessageBox.warning(self, "Acesso negado", "Apenas o administrador pode realizar esta acao.")
        return False

    def trocar_usuario(self):
        dialog = LoginDialog(self)
        if dialog.exec():
            self.salvar_tudo()
            self._fechar_janelas_filhas()
            self.sessao = dialog.sessao
            self._aplicar_permissoes()

    def _fechar_janelas_filhas(self):
        for janela in (self.janela_clientes, self.janela_locacao):
            if janela is not None:
                janela.close()
        self.janela_clientes = None
        self.janela_locacao = None
        for janela in self.janelas_detalhes_abertas:
            janela.close()
        self.janelas_detalhes_abertas.clear()

    # THREADS E ARQUIVOS

    def carregar_filmes_em_paralelo(self):
        # Dispara a execucao paralela via QRunnable + QThreadPool
        self.statusBar().showMessage("Carregando dados em segundo plano...")
        self.botao_carregar.setEnabled(False)

        worker = CarregarDadosWorker()
        worker.signals.result.connect(self._ao_receber_dados)
        worker.signals.error.connect(self._ao_erro_carregamento)
        worker.signals.finished.connect(self._ao_finalizar_carregamento)

        self.threadpool.start(worker)

    def _ao_receber_dados(self, dados):
        # Slot que recebe o resultado retornado pela thread
        # Janelas filhas guardam referencias antigas, entao sao fechadas
        self._fechar_janelas_filhas()
        # O [:] mantem o mesmo objeto de lista em memoria
        self.filmes[:] = dados["filmes"]
        self.clientes[:] = dados["clientes"]
        self.locacoes[:] = dados["locacoes"]
        self._preencher_tabela()
        self.salvar_tudo()
        self.statusBar().showMessage("Dados carregados com sucesso!", 4000)

    def _ao_erro_carregamento(self, mensagem_erro):
        # Slot acionado em caso de excecao na thread
        QMessageBox.critical(self, "Erro", f"Erro ao carregar dados: {mensagem_erro}")

    def _ao_finalizar_carregamento(self):
        # Slot acionado quando a thread conclui a execucao
        self.botao_carregar.setEnabled(True)

    def salvar_tudo(self):
        try:
            Repositorio.salvar_filmes(self.filmes)
            Repositorio.salvar_clientes(self.clientes)
            Repositorio.salvar_locacoes(self.locacoes)
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Nao foi possivel salvar os arquivos: {e}")

    def closeEvent(self, event):
        # Garante que nada se perde ao fechar e que as janelas filhas fecham junto
        self.salvar_tudo()
        self._fechar_janelas_filhas()
        super().closeEvent(event)

    # MONTAGEM DA INTERFACE

    def _montar_tabela(self):
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        self.tabela.itemSelectionChanged.connect(self._atualizar_estado_botoes)
        self.tabela.itemDoubleClicked.connect(self.abrir_detalhes)

    def _montar_menu(self):
        menu = self.menuBar()

        menu_arquivo = menu.addMenu("&Arquivo")
        self.acao_novo = QAction("Novo filme...", self)
        self.acao_novo.setShortcut(QKeySequence.New)
        self.acao_novo.triggered.connect(self.cadastrar_filme)
        menu_arquivo.addAction(self.acao_novo)

        self.acao_editar = QAction("Editar filme...", self)
        self.acao_editar.triggered.connect(self.editar_filme)
        menu_arquivo.addAction(self.acao_editar)

        self.acao_excluir = QAction("Excluir filme", self)
        self.acao_excluir.setShortcut(QKeySequence.Delete)
        self.acao_excluir.triggered.connect(self.excluir_filme)
        menu_arquivo.addAction(self.acao_excluir)

        menu_arquivo.addSeparator()

        self.acao_exportar_csv = QAction("Exportar catalogo (CSV)...", self)
        self.acao_exportar_csv.triggered.connect(self.exportar_csv)
        menu_arquivo.addAction(self.acao_exportar_csv)

        self.acao_exportar_txt = QAction("Exportar relatorio (TXT)...", self)
        self.acao_exportar_txt.triggered.connect(self.exportar_txt)
        menu_arquivo.addAction(self.acao_exportar_txt)

        self.acao_importar = QAction("Importar filmes (CSV)...", self)
        self.acao_importar.triggered.connect(self.importar_csv)
        menu_arquivo.addAction(self.acao_importar)

        menu_arquivo.addSeparator()

        self.acao_trocar_usuario = QAction("Trocar usuario...", self)
        self.acao_trocar_usuario.triggered.connect(self.trocar_usuario)
        menu_arquivo.addAction(self.acao_trocar_usuario)

        self.acao_sair = QAction("Sair", self)
        self.acao_sair.setShortcut(QKeySequence.Quit)
        self.acao_sair.triggered.connect(self.close)
        menu_arquivo.addAction(self.acao_sair)

        menu_exibir = menu.addMenu("E&xibir")
        self.acao_detalhes = QAction("Ver detalhes", self)
        self.acao_detalhes.triggered.connect(self.abrir_detalhes)
        menu_exibir.addAction(self.acao_detalhes)

        menu_locacao = menu.addMenu("&Locacao")
        self.acao_clientes = QAction("Cadastro de clientes...", self)
        self.acao_clientes.triggered.connect(self.abrir_clientes)
        menu_locacao.addAction(self.acao_clientes)

        acao_aluguel = QAction("Aluguel / Devolucao...", self)
        acao_aluguel.triggered.connect(self.abrir_locacao)
        menu_locacao.addAction(acao_aluguel)

        menu_ajuda = menu.addMenu("A&juda")
        acao_sobre = QAction("Sobre", self)
        acao_sobre.triggered.connect(self.mostrar_sobre)
        menu_ajuda.addAction(acao_sobre)

    def _montar_barra_ferramentas(self):
        barra = QToolBar("Ferramentas principais")
        barra.setMovable(False)
        self.addToolBar(barra)

        barra.addAction(self.acao_novo)
        barra.addAction(self.acao_editar)
        barra.addAction(self.acao_excluir)
        barra.addSeparator()
        barra.addAction(self.acao_detalhes)

    def _montar_barra_status(self):
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto.")

    def _montar_layout_central(self):
        rotulo_cabecalho = QLabel("Catalogo de filmes da locadora")
        fonte = rotulo_cabecalho.font()
        fonte.setPointSize(13)
        fonte.setBold(True)
        rotulo_cabecalho.setFont(fonte)

        # Campo de consulta: filtra a tabela enquanto digita
        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("Buscar por titulo, diretor ou genero...")
        self.campo_busca.setClearButtonEnabled(True)
        self.campo_busca.textChanged.connect(self._filtrar_tabela)

        self.botao_novo = QPushButton("Novo")
        self.botao_editar = QPushButton("Editar")
        self.botao_excluir = QPushButton("Excluir")
        self.botao_detalhes = QPushButton("Detalhes")
        self.botao_carregar = QPushButton("Recarregar em Segundo Plano (Thread)")

        self.botao_novo.clicked.connect(self.cadastrar_filme)
        self.botao_editar.clicked.connect(self.editar_filme)
        self.botao_excluir.clicked.connect(self.excluir_filme)
        self.botao_detalhes.clicked.connect(self.abrir_detalhes)
        self.botao_carregar.clicked.connect(self.carregar_filmes_em_paralelo)

        layout_botoes = QHBoxLayout()
        layout_botoes.addWidget(self.botao_novo)
        layout_botoes.addWidget(self.botao_editar)
        layout_botoes.addWidget(self.botao_excluir)
        layout_botoes.addWidget(self.botao_carregar)
        layout_botoes.addStretch()
        layout_botoes.addWidget(self.botao_detalhes)

        layout_principal = QVBoxLayout()
        layout_principal.addWidget(rotulo_cabecalho)
        layout_principal.addWidget(self.campo_busca)
        layout_principal.addWidget(self.tabela)
        layout_principal.addLayout(layout_botoes)

        widget_central = QWidget()
        widget_central.setLayout(layout_principal)
        self.setCentralWidget(widget_central)

    def _preencher_tabela(self):
        self.tabela.setRowCount(len(self.filmes))
        for linha, filme in enumerate(self.filmes):
            for coluna, valor in enumerate(filme.para_linha_tabela()):
                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.tabela.setItem(linha, coluna, item)
        # Reaplica o filtro de busca depois de recarregar a tabela
        self._filtrar_tabela(self.campo_busca.text())

    def _filtrar_tabela(self, texto):
        # Esconde as linhas em vez de refazer a tabela, assim os indices continuam batendo
        texto = texto.lower().strip()
        for linha, filme in enumerate(self.filmes):
            bate = (
                texto in filme.titulo.lower()
                or texto in filme.diretor.lower()
                or texto in filme.genero.lower()
            )
            self.tabela.setRowHidden(linha, not bate)

    def _linha_selecionada(self):
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        return linhas[0].row()

    def _atualizar_estado_botoes(self):
        tem_selecao = self._linha_selecionada() is not None

        self.acao_editar.setEnabled(tem_selecao)
        self.acao_excluir.setEnabled(tem_selecao)
        self.acao_detalhes.setEnabled(tem_selecao)
        self.botao_editar.setEnabled(tem_selecao)
        self.botao_excluir.setEnabled(tem_selecao)
        self.botao_detalhes.setEnabled(tem_selecao)

    def _titulos_usados(self, ignorar=None):
        return {f.titulo.lower() for f in self.filmes if f is not ignorar}

    # ACOES DE FILMES (SOMENTE ADMIN)

    def cadastrar_filme(self):
        if not self._exige_admin():
            return
        dialog = FilmeDialog(self, titulos_usados=self._titulos_usados())
        if dialog.exec():
            dados = dialog.obter_dados()
            self.filmes.append(Filme(**dados))
            self._preencher_tabela()
            self.salvar_tudo()
            self.statusBar().showMessage(
                f'Filme "{dados["titulo"]}" cadastrado com sucesso.', 4000
            )

    def editar_filme(self):
        if not self._exige_admin():
            return
        linha = self._linha_selecionada()
        if linha is None:
            return

        filme_atual = self.filmes[linha]
        dialog = FilmeDialog(self, filme=filme_atual, titulos_usados=self._titulos_usados(ignorar=filme_atual))
        if dialog.exec():
            dados = dialog.obter_dados()
            filme_atual.atualizar(**dados)
            self._preencher_tabela()
            self.tabela.selectRow(linha)
            self.salvar_tudo()
            self.statusBar().showMessage("Filme atualizado com sucesso.", 4000)

    def excluir_filme(self):
        if not self._exige_admin():
            return
        linha = self._linha_selecionada()
        if linha is None:
            return

        filme = self.filmes[linha]

        # Nao deixa excluir filme que esta alugado no momento
        if any(l.filme is filme and l.esta_ativa for l in self.locacoes):
            QMessageBox.warning(self, "Impossivel excluir", "Este filme possui locacao ativa.")
            return

        resposta = QMessageBox.question(
            self,
            "Confirmar exclusao",
            f'Tem certeza que deseja excluir o filme "{filme.titulo}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            del self.filmes[linha]
            # Remove tambem o historico de locacoes desse filme
            self.locacoes[:] = [l for l in self.locacoes if l.filme is not filme]
            self._preencher_tabela()
            self._atualizar_estado_botoes()
            self.salvar_tudo()
            self.statusBar().showMessage("Filme excluido.", 4000)

    # EXPORTAR E IMPORTAR (SOMENTE ADMIN)

    def exportar_csv(self):
        if not self._exige_admin():
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar catalogo", "catalogo.csv", "CSV (*.csv)")
        if not caminho:
            return
        try:
            with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
                escritor = csv.DictWriter(
                    arquivo,
                    fieldnames=["titulo", "diretor", "ano", "genero", "duracao_min", "estoque"],
                )
                escritor.writeheader()
                for filme in self.filmes:
                    escritor.writerow(filme.para_dict())
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Nao foi possivel exportar: {e}")
            return
        self.statusBar().showMessage("Catalogo exportado.", 4000)

    def exportar_txt(self):
        if not self._exige_admin():
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar relatorio", "relatorio.txt", "Texto (*.txt)")
        if not caminho:
            return
        try:
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write("RELATORIO DA LOCADORA\n")
                arquivo.write("=" * 40 + "\n\n")
                arquivo.write("FILMES\n")
                for filme in self.filmes:
                    arquivo.write(
                        f"- {filme.titulo} ({filme.ano}) | {filme.genero} | estoque: {filme.estoque}\n"
                    )
                arquivo.write("\nLOCACOES ATIVAS\n")
                for locacao in self.locacoes:
                    if locacao.esta_ativa:
                        prevista = locacao.data_prevista_devolucao.strftime("%d/%m/%Y")
                        arquivo.write(
                            f"- {locacao.filme.titulo} -> {locacao.cliente.nome} (prevista {prevista})\n"
                        )
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Nao foi possivel exportar: {e}")
            return
        self.statusBar().showMessage("Relatorio exportado.", 4000)

    def importar_csv(self):
        if not self._exige_admin():
            return
        caminho, _ = QFileDialog.getOpenFileName(self, "Importar filmes", "", "CSV (*.csv)")
        if not caminho:
            return

        titulos = self._titulos_usados()
        importados = 0
        try:
            with open(caminho, encoding="utf-8", newline="") as arquivo:
                for dados in csv.DictReader(arquivo):
                    titulo = dados["titulo"].strip()
                    # Pula linhas vazias e titulos que ja existem
                    if not titulo or titulo.lower() in titulos:
                        continue
                    self.filmes.append(Filme(
                        titulo, dados["diretor"], int(dados["ano"]), dados["genero"],
                        int(dados["duracao_min"]), int(dados["estoque"]),
                    ))
                    titulos.add(titulo.lower())
                    importados += 1
        except (KeyError, ValueError, OSError) as e:
            QMessageBox.warning(self, "Erro na importacao", f"Arquivo invalido: {e}")

        self._preencher_tabela()
        self.salvar_tudo()
        self.statusBar().showMessage(f"{importados} filme(s) importado(s).", 4000)

    # JANELAS AUXILIARES

    def abrir_detalhes(self):
        linha = self._linha_selecionada()
        if linha is None:
            return

        filme = self.filmes[linha]
        janela = DetalhesJanela(filme)
        janela.show()
        self.janelas_detalhes_abertas.append(janela)

    def abrir_clientes(self):
        if not self._exige_admin():
            return
        if self.janela_clientes is None or not self.janela_clientes.isVisible():
            self.janela_clientes = ClientesWindow(self.clientes, self.locacoes)
            # Salva o arquivo sempre que a lista de clientes mudar
            self.janela_clientes.clientes_atualizados.connect(self.salvar_tudo)
        self.janela_clientes.show()
        self.janela_clientes.raise_()
        self.janela_clientes.activateWindow()

    def abrir_locacao(self):
        if self.janela_locacao is None or not self.janela_locacao.isVisible():
            self.janela_locacao = LocacaoWindow(self.filmes, self.clientes, self.locacoes, self.sessao)
            self.janela_locacao.locacao_alterada.connect(self._preencher_tabela)
            self.janela_locacao.locacao_alterada.connect(self.salvar_tudo)
        self.janela_locacao.show()
        self.janela_locacao.raise_()
        self.janela_locacao.activateWindow()

    def mostrar_sobre(self):
        QMessageBox.information(
            self,
            "Sobre",
            "Sistema de catalogo de filmes\nTrabalho de POO - PySide6 com Threads e Arquivos",
        )

# EXECUCAO DO PROGRAMA

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # A tela de login aparece antes da janela principal
    login = LoginDialog()
    if login.exec():
        window = MainWindow(login.sessao)
        window.show()
        app.exec()