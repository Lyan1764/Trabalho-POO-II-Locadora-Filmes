# Locadora de Filmes — Sistema Desktop (PySide6)

Aplicação desktop para gerenciamento de uma locadora de filmes, desenvolvida em Python com o framework **PySide6** (Qt para Python). O sistema permite cadastrar filmes e clientes, e controlar o ciclo de aluguel e devolução, incluindo cálculo automático de multa por atraso.

## Funcionalidades

- **Catálogo de filmes**: cadastro, edição, exclusão e visualização de detalhes (título, diretor, ano, gênero, duração e estoque).
- **Cadastro de clientes**: cadastro, edição e exclusão de clientes (nome, CPF, telefone e e-mail).
- **Aluguel e devolução**:
  - Registro de aluguel vinculando um filme disponível a um cliente, com data de devolução prevista.
  - Registro de devolução com cálculo automático de dias de atraso e multa (R$ 2,50 por dia).
  - O estoque do filme é atualizado automaticamente ao alugar e ao devolver.
- **Janelas integradas**: a janela de clientes e a janela de locação compartilham as mesmas listas de dados da janela principal, então qualquer alteração é refletida em todas as telas sem necessidade de sincronização manual.

## Estrutura do código

O arquivo está organizado em três grandes blocos:

### 1. Modelos (regras de negócio, sem Qt)
- `Filme`: representa um filme, com propriedade calculada `status_disponibilidade` baseada no estoque.
- `Cliente`: representa um cliente cadastrado.
- `Locacao`: representa um aluguel, com propriedades calculadas `esta_ativa`, `dias_atraso` e `multa`.

### 2. Diálogos (janelas modais)
- `FilmeDialog`: cadastro/edição de filme, com validação de campos obrigatórios.
- `ClienteDialog`: cadastro/edição de cliente, com validação de campos obrigatórios.
- `DevolucaoDialog`: exibe dias de atraso e valor da multa antes de confirmar a devolução.

### 3. Janelas (interface principal e auxiliares)
- `DetalhesJanela`: janela não modal com os detalhes completos de um filme.
- `ClientesWindow`: janela de gerenciamento de clientes (`QMainWindow` com menu, toolbar e barra de status).
- `LocacaoWindow`: janela de registro de aluguéis e devoluções.
- `MainWindow`: janela principal com o catálogo de filmes; abre as demais janelas via menu **Locação**.

## Requisitos

- Python 3.9+
- [PySide6](https://pypi.org/project/PySide6/)

Instalação da dependência:

```bash
pip install PySide6
```

## Como executar

```bash
python nome_do_arquivo.py
```

*(substitua `nome_do_arquivo.py` pelo nome real do arquivo do script)*

Ao iniciar, o sistema já carrega três filmes de exemplo no catálogo:

- De Volta para o Futuro (1985)
- O Iluminado (1980)
- Coringa (2019)

## Fluxo de uso básico

1. Cadastre um cliente em **Locação → Cadastro de clientes...**
2. Abra **Locação → Aluguel / Devolução...**
3. Selecione um filme disponível e um cliente, defina a data prevista de devolução e clique em **Registrar aluguel**.
4. Para devolver, selecione a locação ativa na tabela e clique em **Registrar devolução** — o sistema mostra dias de atraso e multa antes de confirmar.

## Observações técnicas

- A interface usa `QTableWidget` com seleção por linha e edição desabilitada (os dados só mudam pelos diálogos).
- Atalhos de teclado: `Ctrl+N` (novo), `Delete` (excluir).
- Ao fechar as janelas, há confirmações (`QMessageBox`) para evitar exclusões ou fechamentos acidentais, inclusive um aviso especial se houver locações ainda ativas.
- Dados são mantidos apenas em memória (não há persistência em banco de dados ou arquivo).
