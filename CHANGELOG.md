## [Não Lançado] - 16/10/2026

### 🚀 Novas Funcionalidades
- **Persistência em Arquivos**: Dados salvos em disco, sem uso de SGBD, na pasta `dados/`: filmes em `filmes.json`, clientes em `clientes.csv`, locações em `locacoes.json` e usuários em `usuarios.json`.
- **Tela de Login**: Autenticação com dois perfis. O administrador entra com usuário e senha (hash SHA-256) e o cliente entra com o CPF cadastrado.
- **Controle de Acesso**: O administrador tem acesso total. O cliente só consulta o catálogo e aluga ou devolve filmes em seu próprio nome, vendo apenas as próprias locações.
- **Consulta de Filmes**: Campo de busca que filtra o catálogo por título, diretor ou gênero enquanto o usuário digita.
- **Exportação e Importação**: Exportação do catálogo em CSV, geração de relatório em TXT (filmes e locações ativas) e importação de filmes via CSV.
- **Troca de Usuário**: Opção para trocar de perfil sem fechar o programa.

### 🔄 Alterações
- **Carregamento Assíncrono**: O `CarregarFilmesWorker` foi substituído pelo `CarregarDadosWorker`, que agora lê os arquivos (filmes, clientes e locações) em segundo plano em vez de usar dados fixos.
- **Salvamento Automático**: Os arquivos são atualizados a cada cadastro, edição, exclusão, aluguel ou devolução, e também ao fechar a janela principal.
- **Edição In-Place**: Editar filme ou cliente agora atualiza o objeto existente, mantendo as locações vinculadas.
- **Janelas Filhas**: Ao fechar a janela principal, as janelas de clientes, locação e detalhes são fechadas junto.

### 🐛 Correções e Validações
- **Locações Perdidas**: A lista de locações passou a ser da janela principal e compartilhada, então não é mais apagada ao fechar a janela de aluguel.
- **Duplicados**: Bloqueio de filmes com título repetido e de clientes com CPF repetido.
- **Exclusão Segura**: Não é possível excluir filme ou cliente com locação ativa. Ao excluir, o histórico de locações dele também é removido.
- **Permissões**: Ações exclusivas do administrador são verificadas também na lógica dos métodos, não só escondidas na interface.

## [Não Lançado] - 08/10/2026

### 🚀 Novas Funcionalidades
- **Concorrência e Multithreading**: Adicionado suporte a processamento assíncrono utilizando `QRunnable` e `QThreadPool` do PySide6.
- **Carregamento Assíncrono**: O catálogo de filmes agora é carregado em segundo plano sem congelar a interface gráfica principal.
- **Comunicação Thread-Safe**: Implementados sinais Qt (`WorkerSignals`) para repassar resultados, erros e status de término da thread secundária para a thread da GUI.