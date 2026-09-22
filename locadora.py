import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel, QLineEdit, QSpinBox, QComboBox, QDialogButtonBox, QMessageBox, QToolBar,QStatusBar
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt

# Colunas que a tabela do catalogo vai mostrar, nessa ordem.
COLUNAS = ["Titulo", "Diretor", "Ano", "Genero", "Duracao", "Estoque"]

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

class Filme:
    # Representa um filme cadastrado na locadora.

    def __init__(self, titulo, diretor, ano, genero, duracao_min, estoque):
        self.titulo = titulo
        self.diretor = diretor
        self.ano = ano
        self.genero = genero
        self.duracao_min = duracao_min
        self.estoque = estoque

    def para_linha_tabela(self):
        # Devolve os dados do filme em uma lista de strings, na ordem certa para preencher uma linha da tabela da interface.
        
        return [
            self.titulo,
            self.diretor,
            str(self.ano),
            self.genero,
            f"{self.duracao_min} min",
            str(self.estoque),
        ]


# Dialog de cadastro/edicao de filme
class FilmeDialog(QDialog):
    # Janela de dialogo (modal) para cadastrar ou editar um filme. Se um "filme" for passado no construtor, os campos ja vem preenchidos com os dados dele (modo edicao). Se nao, os campos ficam vazios (modo cadastro).
    

    def __init__(self, parent=None, filme=None):
        super().__init__(parent)  # passa o parent para centralizar no parent

        self.filme_editado = filme

        titulo_janela = "Editar filme" if filme else "Cadastrar novo filme"
        self.setWindowTitle(titulo_janela)
        self.setMinimumWidth(320)

        # Formulario 
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

        # Se estamos editando, preenche os campos com os dados atuais.
        if filme:
            self.campo_titulo.setText(filme.titulo)
            self.campo_diretor.setText(filme.diretor)
            self.campo_ano.setValue(filme.ano)
            indice_genero = self.campo_genero.findText(filme.genero)
            if indice_genero >= 0:
                self.campo_genero.setCurrentIndex(indice_genero)
            self.campo_duracao.setValue(filme.duracao_min)
            self.campo_estoque.setValue(filme.estoque)

        # --- Layout do formulario (rotulo ao lado do campo) ---
        layout_formulario = QFormLayout()
        layout_formulario.addRow("Titulo:", self.campo_titulo)
        layout_formulario.addRow("Diretor:", self.campo_diretor)
        layout_formulario.addRow("Ano:", self.campo_ano)
        layout_formulario.addRow("Genero:", self.campo_genero)
        layout_formulario.addRow("Duracao:", self.campo_duracao)
        layout_formulario.addRow("Estoque:", self.campo_estoque)

        # Botoes padrao "Salvar" (Ok) e "Cancelar".
        # Lista completa de tipos de botao:
        #   https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDialogButtonBox.html
        botoes_dialog = (
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes = QDialogButtonBox(botoes_dialog)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Salvar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")

        # Sinal/slot: o clique no Ok nao fecha direto, primeiro valida os dados. So se a validacao passar e que o dialog e aceito de fato.
        self.botoes.accepted.connect(self.validar_e_aceitar)
        self.botoes.rejected.connect(self.reject)

        layout_principal = QVBoxLayout()
        layout_principal.addLayout(layout_formulario)
        layout_principal.addWidget(self.botoes)
        self.setLayout(layout_principal)

    def validar_e_aceitar(self):
        # Confere se o formulario foi preenchido corretamente antes de fechar o dialog. Se algo estiver errado, mostra um alerta e mantem o dialog aberto para o usuario corrigir.
        
        if not self.campo_titulo.text().strip():
            QMessageBox.warning(
                self, "Campo obrigatorio", "Informe o titulo do filme."
            )
            return

        if not self.campo_diretor.text().strip():
            QMessageBox.warning(
                self, "Campo obrigatorio", "Informe o diretor do filme."
            )
            return

        self.accept()

    def obter_dados(self):
        # Le os valores atuais dos campos do formulario e devolve tudoorganizado em um dicionario, pronto para virar um objeto Filme.
        
        return {
            "titulo": self.campo_titulo.text().strip(),
            "diretor": self.campo_diretor.text().strip(),
            "ano": self.campo_ano.value(),
            "genero": self.campo_genero.currentText(),
            "duracao_min": self.campo_duracao.value(),
            "estoque": self.campo_estoque.value(),
        }


# Janela adicional com os detalhes do filme

class DetalhesJanela(QWidget):
    # Esta e a "janela adicional" do trabalho: uma janela separada (nao e um dialog modal) que mostra os detalhes completos de um filme selecionado na tabela. Ela pode ficar aberta ao mesmo tempo que a janela principal.

    def __init__(self, filme):
        # Nao passei "parent" de proposito, para que essa janela seja uma janela de verdade (independente), e nao fique presa dentro da janela principal.
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
            f"Copias em estoque: {filme.estoque}"
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

# Janela principal
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Locadora de Filmes - Catalogo")
        self.resize(720, 480)

        # Lista de filmes cadastrados, guardada na memoria do programa.
        self.filmes = self._carregar_filmes_exemplo()

        # Guarda referencias das janelas de detalhes abertas, para elas nao serem destruidas assim que o metodo termina de rodar.
        self.janelas_detalhes_abertas = []

        self._montar_tabela()
        self._montar_menu()
        self._montar_barra_ferramentas()
        self._montar_barra_status()
        self._montar_layout_central()

        self._preencher_tabela()
        self._atualizar_estado_botoes()

    # Montagem da interface

    def _carregar_filmes_exemplo(self):
        # Cria alguns filmes de exemplo so para o catalogo nao comecar vazio.
        return [
            Filme("De Volta para o Futuro", "Robert Zemeckis", 1985, "Ficcao Cientifica", 116, 3),
            Filme("O Iluminado", "Stanley Kubrick", 1980, "Terror", 146, 2),
            Filme("Coringa", "Todd Phillips", 2019, "Drama", 122, 5),
        ]

    def _montar_tabela(self):
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)

        # Tabela so pode ser lida, a edicao dos dados e feita pelo dialog.
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )

        # Sinais e slots da tabela 
        # Quando a selecao muda, os botoes de editar/excluir/detalhes sao habilitados ou desabilitados dependendo se ha um filme selecionado.
        self.tabela.itemSelectionChanged.connect(self._atualizar_estado_botoes)
        # Dar dois cliques em uma linha abre a janela de detalhes.
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

        menu_ajuda = menu.addMenu("A&juda")
        acao_sobre = QAction("Sobre", self)
        acao_sobre.triggered.connect(self.mostrar_sobre)
        menu_ajuda.addAction(acao_sobre)

    def _montar_barra_ferramentas(self):
        barra = QToolBar("Ferramentas principais")
        barra.setMovable(False)
        self.addToolBar(barra)

        # Reaproveita as mesmas acoes ja criadas para o menu, assim o atalho e o comportamento ficam identicos nos dois lugares.
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

        # Botoes que ficam abaixo da tabela, alem do menu e da barra de ferramentas, so para deixar as acoes bem visiveis tambem.
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

    # Atualizacao da tabela 

    def _preencher_tabela(self):
        # Redesenha a tabela inteira a partir da lista self.filmes.
        self.tabela.setRowCount(len(self.filmes))
        for linha, filme in enumerate(self.filmes):
            for coluna, valor in enumerate(filme.para_linha_tabela()):
                item = QTableWidgetItem(valor)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.tabela.setItem(linha, coluna, item)

    def _linha_selecionada(self):
        # Devolve o indice da linha selecionada, ou None se nao houver.
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        return linhas[0].row()

    def _atualizar_estado_botoes(self):
        # Slot chamado sempre que a selecao da tabela muda. So faz sentido editar, excluir ou ver detalhes se algum filme estiver selecionado.
      
        tem_selecao = self._linha_selecionada() is not None

        self.acao_editar.setEnabled(tem_selecao)
        self.acao_excluir.setEnabled(tem_selecao)
        self.acao_detalhes.setEnabled(tem_selecao)
        self.botao_editar.setEnabled(tem_selecao)
        self.botao_excluir.setEnabled(tem_selecao)
        self.botao_detalhes.setEnabled(tem_selecao)

    # Slots das acoes de cadastro (novo, editar, excluir, detalhes)

    def cadastrar_filme(self):
        # Abre o dialog de cadastro e, se confirmado, adiciona o filme na lista.
        dialog = FilmeDialog(self)
        if dialog.exec():
            dados = dialog.obter_dados()
            self.filmes.append(Filme(**dados))
            self._preencher_tabela()
            self.statusBar().showMessage(
                f'Filme "{dados["titulo"]}" cadastrado com sucesso.', 4000
            )

    def editar_filme(self):
        # Abre o dialog ja preenchido com os dados do filme selecionado.
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
        # Pede confirmacao antes de excluir o filme selecionado do catalogo.
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
        # Abre a janela adicional com os detalhes do filme selecionado.
        linha = self._linha_selecionada()
        if linha is None:
            return

        filme = self.filmes[linha]
        janela = DetalhesJanela(filme)
        janela.show()
        # Guarda a referencia para o Python nao "destruir" a janela por falta de uso assim que essa funcao termina.
        self.janelas_detalhes_abertas.append(janela)

    def mostrar_sobre(self):
        QMessageBox.information(
            self,
            "Sobre",
            "Sistema de catalogo de filmes\nTrabalho de POO - PySide6",
        )

    # Tratamento de eventos 
    def keyPressEvent(self, evento):
        # Evento de teclado: se o usuario apertar a tecla Delete com a tabela em foco, tenta excluir o filme selecionado.
        if evento.key() == Qt.Key_Delete:
            self.excluir_filme()
        else:
            super().keyPressEvent(evento)

    def closeEvent(self, evento):
        # Evento chamado quando o usuario tenta fechar a janela principal.
        # Pede uma confirmacao antes de realmente encerrar o programa.
        
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

# Execucao do programa

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()