import sys
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLabel, QLineEdit, QSpinBox, QComboBox, QDateEdit, QDialogButtonBox,
    QMessageBox, QToolBar, QStatusBar
)
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QDate, Signal

# CONSTANTES

# Colunas que a tabela do catalogo vai mostrar, nessa ordem.
COLUNAS = ["Titulo", "Diretor", "Ano", "Genero", "Duracao", "Estoque", "Status"]

# Lista fixa de generos disponiveis no combo box do formulario.
GENEROS = [
    "Acao",
    "Comedia",
    "Drama",
    "Terror",
    "Ficcao Cientifica",
    "Animacao",
    "Documentario",
    "Romance",
]

COLUNAS_CLIENTE = ["Nome", "CPF", "Telefone", "Email"]
COLUNAS_LOCACAO = ["Filme", "Cliente", "Retirada", "Prevista", "Status"]

# MODELOS (regras de negocio, sem nada de Qt)

class Filme:
    # Representa um filme cadastrado na locadora.

    def __init__(self, titulo, diretor, ano, genero, duracao_min, estoque):
        self.titulo = titulo
        self.diretor = diretor
        self.ano = ano
        self.genero = genero
        self.duracao_min = duracao_min
        self.estoque = estoque

    @property
    def status_disponibilidade(self):
        # Status simples calculado a partir do estoque atual.
        return "Disponivel" if self.estoque > 0 else "Indisponivel"

    def para_linha_tabela(self):
        # Devolve os dados do filme em uma lista de strings, na ordem certa para preencher uma linha da tabela da interface.
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
    # Representa um cliente cadastrado na locadora.

    def __init__(self, nome, cpf, telefone, email=""):
        self.nome = nome
        self.cpf = cpf
        self.telefone = telefone
        self.email = email

    def para_linha_tabela(self):
        return [self.nome, self.cpf, self.telefone, self.email]


class Locacao:
    # Representa o aluguel de um filme para um cliente.

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

    def para_linha_tabela(self):
        status = "Ativa" if self.esta_ativa else "Devolvida"
        return [
            self.filme.titulo,
            self.cliente.nome,
            self.data_retirada.strftime("%d/%m/%Y"),
            self.data_prevista_devolucao.strftime("%d/%m/%Y"),
            status,
        ]

# DIALOG DE CADASTRO/EDICAO DE FILME

class FilmeDialog(QDialog):
    # Janela de dialogo (modal) para cadastrar ou editar um filme. Se um "filme" for passado no construtor, os campos ja vem preenchidos com os dados dele (modo edicao). Se nao, os campos ficam vazios (modo cadastro).

    def __init__(self, parent=None, filme=None):
        super().__init__(parent)

        self.filme_editado = filme

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
        if not self.campo_titulo.text().strip():
            QMessageBox.warning(self, "Campo obrigatorio", "Informe o titulo do filme.")
            return
        if not self.campo_diretor.text().strip():
            QMessageBox.warning(self, "Campo obrigatorio", "Informe o diretor do filme.")
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

# DIALOG DE CADASTRO/EDICAO DE CLIENTE

class ClienteDialog(QDialog):
    # Janela de dialogo (modal) para cadastrar ou editar um cliente. Segue o mesmo padrao do FilmeDialog.

    def __init__(self, parent=None, cliente=None):
        super().__init__(parent)

        self.cliente_editado = cliente

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
        if not self.campo_cpf.text().strip():
            QMessageBox.warning(self, "Campo obrigatorio", "Informe o CPF do cliente.")
            return
        self.accept()

    def obter_dados(self):
        return {
            "nome": self.campo_nome.text().strip(),
            "cpf": self.campo_cpf.text().strip(),
            "telefone": self.campo_telefone.text().strip(),
            "email": self.campo_email.text().strip(),
        }

# DIALOG DE DEVOLUCAO

class DevolucaoDialog(QDialog):
    # Dialog que mostra os dias de atraso e a multa antes de confirmar a devolucao.

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

# JANELA ADICIONAL - DETALHES DO FILME

class DetalhesJanela(QWidget):
    # Janela adicional: uma janela separada (nao e um dialog modal) que mostra os detalhes completos de um filme selecionado na tabela. Pode ficar aberta ao mesmo tempo que a janela principal.

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

# JANELA ADICIONAL - CADASTRO DE CLIENTES

class ClientesWindow(QMainWindow):
    # Janela adicional que gerencia o cadastro de clientes da locadora.
    # Recebe a MESMA lista de clientes usada pela janela de locacao, entao mudancas aqui aparecem la tambem sem precisar de sinal nenhum - o sinal abaixo serve so para quem quiser reagir na hora.

    clientes_atualizados = Signal()

    def __init__(self, clientes, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Locadora - Cadastro de Clientes")
        self.resize(560, 420)

        self.clientes = clientes

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
        self.clientes_atualizados.emit()

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
        dialog = ClienteDialog(self)
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
        dialog = ClienteDialog(self, cliente=cliente_atual)
        if dialog.exec():
            dados = dialog.obter_dados()
            self.clientes[linha] = Cliente(**dados)
            self._preencher_tabela()
            self.tabela.selectRow(linha)
            self.statusBar().showMessage("Cliente atualizado com sucesso.", 4000)

    def excluir_cliente(self):
        linha = self._linha_selecionada()
        if linha is None:
            return
        cliente = self.clientes[linha]
        resposta = QMessageBox.question(
            self, "Confirmar exclusao",
            f'Tem certeza que deseja excluir o cliente "{cliente.nome}"?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            del self.clientes[linha]
            self._preencher_tabela()
            self._atualizar_estado_botoes()
            self.statusBar().showMessage("Cliente excluido.", 4000)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Delete:
            self.excluir_cliente()
        else:
            super().keyPressEvent(evento)

    def closeEvent(self, evento):
        resposta = QMessageBox.question(
            self, "Fechar",
            "Deseja realmente fechar o cadastro de clientes?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            evento.accept()
        else:
            evento.ignore()

# JANELA ADICIONAL - ALUGUEL E DEVOLUCAO

class LocacaoWindow(QMainWindow):
    # Janela adicional para registrar alugueis e devolucoes.
    # Recebe as MESMAS listas de filmes e clientes usadas pelo catalogo e pela janela de clientes, entao alugar um filme aqui ja desconta do estoque que aparece na tabela do catalogo.

    locacao_alterada = Signal()

    def __init__(self, filmes, clientes, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Locadora - Aluguel e Devolucao")
        self.resize(700, 460)

        self.filmes = filmes
        self.clientes = clientes
        self.locacoes = []

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
        rotulo_cabecalho = QLabel("Aluguel e devolucao de filmes")
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
            self.combo_cliente.addItem(cliente.nome, userData=cliente)

        pode_alugar = self.combo_filme.count() > 0 and self.combo_cliente.count() > 0
        self.botao_alugar.setEnabled(pode_alugar)
        self.acao_alugar.setEnabled(pode_alugar)

    def _preencher_tabela(self):
        self.tabela.setRowCount(len(self.locacoes))
        for linha, locacao in enumerate(self.locacoes):
            for coluna, valor in enumerate(locacao.para_linha_tabela()):
                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.tabela.setItem(linha, coluna, item)

    def _linha_selecionada(self):
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        return linhas[0].row()

    def _atualizar_estado_botoes(self):
        linha = self._linha_selecionada()
        pode_devolver = linha is not None and self.locacoes[linha].esta_ativa
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
        linha = self._linha_selecionada()
        if linha is None:
            return

        locacao = self.locacoes[linha]
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

    def closeEvent(self, evento):
        ativas = sum(1 for l in self.locacoes if l.esta_ativa)
        if ativas > 0:
            resposta = QMessageBox.question(
                self, "Locacoes em aberto",
                f"Existem {ativas} locacao(oes) ativa(s). Fechar mesmo assim?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resposta != QMessageBox.Yes:
                evento.ignore()
                return
        evento.accept()

# JANELA PRINCIPAL

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Locadora de Filmes - Catalogo")
        self.resize(760, 480)

        self.filmes = self._carregar_filmes_exemplo()

        self.janelas_detalhes_abertas = []

        self.clientes = []
        self.janela_clientes = None
        self.janela_locacao = None

        self._montar_tabela()
        self._montar_menu()
        self._montar_barra_ferramentas()
        self._montar_barra_status()
        self._montar_layout_central()

        self._preencher_tabela()
        self._atualizar_estado_botoes()

    def _carregar_filmes_exemplo(self):
        return [
            Filme("De Volta para o Futuro", "Robert Zemeckis", 1985, "Ficcao Cientifica", 116, 3),
            Filme("O Iluminado", "Stanley Kubrick", 1980, "Terror", 146, 2),
            Filme("Coringa", "Todd Phillips", 2019, "Drama", 122, 5),
        ]

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

        self.acao_sair = QAction("Sair", self)
        self.acao_sair.setShortcut(QKeySequence.Quit)
        self.acao_sair.triggered.connect(self.close)
        menu_arquivo.addAction(self.acao_sair)

        menu_exibir = menu.addMenu("E&xibir")
        self.acao_detalhes = QAction("Ver detalhes", self)
        self.acao_detalhes.triggered.connect(self.abrir_detalhes)
        menu_exibir.addAction(self.acao_detalhes)

        menu_locacao = menu.addMenu("&Locacao")
        acao_clientes = QAction("Cadastro de clientes...", self)
        acao_clientes.triggered.connect(self.abrir_clientes)
        menu_locacao.addAction(acao_clientes)

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

        self.botao_novo = QPushButton("Novo")
        self.botao_editar = QPushButton("Editar")
        self.botao_excluir = QPushButton("Excluir")
        self.botao_detalhes = QPushButton("Detalhes")

        self.botao_novo.clicked.connect(self.cadastrar_filme)
        self.botao_editar.clicked.connect(self.editar_filme)
        self.botao_excluir.clicked.connect(self.excluir_filme)
        self.botao_detalhes.clicked.connect(self.abrir_detalhes)

        layout_botoes = QHBoxLayout()
        layout_botoes.addWidget(self.botao_novo)
        layout_botoes.addWidget(self.botao_editar)
        layout_botoes.addWidget(self.botao_excluir)
        layout_botoes.addStretch()
        layout_botoes.addWidget(self.botao_detalhes)

        layout_principal = QVBoxLayout()
        layout_principal.addWidget(rotulo_cabecalho)
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

    def cadastrar_filme(self):
        dialog = FilmeDialog(self)
        if dialog.exec():
            dados = dialog.obter_dados()
            self.filmes.append(Filme(**dados))
            self._preencher_tabela()
            self.statusBar().showMessage(
                f'Filme "{dados["titulo"]}" cadastrado com sucesso.', 4000
            )

    def editar_filme(self):
        linha = self._linha_selecionada()
        if linha is None:
            return

        filme_atual = self.filmes[linha]
        dialog = FilmeDialog(self, filme=filme_atual)
        if dialog.exec():
            dados = dialog.obter_dados()
            self.filmes[linha] = Filme(**dados)
            self._preencher_tabela()
            self.tabela.selectRow(linha)
            self.statusBar().showMessage("Filme atualizado com sucesso.", 4000)

    def excluir_filme(self):
        linha = self._linha_selecionada()
        if linha is None:
            return

        filme = self.filmes[linha]
        resposta = QMessageBox.question(
            self,
            "Confirmar exclusao",
            f'Tem certeza que deseja excluir o filme "{filme.titulo}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            del self.filmes[linha]
            self._preencher_tabela()
            self._atualizar_estado_botoes()
            self.statusBar().showMessage("Filme excluido.", 4000)

    def abrir_detalhes(self):
        linha = self._linha_selecionada()
        if linha is None:
            return

        filme = self.filmes[linha]
        janela = DetalhesJanela(filme)
        janela.show()
        self.janelas_detalhes_abertas.append(janela)

    def abrir_clientes(self):
        if self.janela_clientes is None or not self.janela_clientes.isVisible():
            self.janela_clientes = ClientesWindow(self.clientes)
        self.janela_clientes.show()
        self.janela_clientes.raise_()
        self.janela_clientes.activateWindow()

    def abrir_locacao(self):
        if self.janela_locacao is None or not self.janela_locacao.isVisible():
            self.janela_locacao = LocacaoWindow(self.filmes, self.clientes)
            self.janela_locacao.locacao_alterada.connect(self._preencher_tabela)
        self.janela_locacao.show()
        self.janela_locacao.raise_()
        self.janela_locacao.activateWindow()

    def mostrar_sobre(self):
        QMessageBox.information(
            self,
            "Sobre",
            "Sistema de catalogo de filmes\nTrabalho de POO - PySide6",
        )

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Delete:
            self.excluir_filme()
        else:
            super().keyPressEvent(evento)

    def closeEvent(self, evento):
        resposta = QMessageBox.question(
            self,
            "Sair",
            "Tem certeza que deseja sair do sistema?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            evento.accept()
        else:
            evento.ignore()

# EXECUCAO DO PROGRAMA

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()