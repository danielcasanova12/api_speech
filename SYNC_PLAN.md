# Plano de Gerenciamento e Sincronização de Bancos de Dados

## 1. Objetivo

O objetivo é ter a capacidade de usar tanto o banco de dados local (Docker) quanto o banco de dados remoto (NeonDB), garantindo que os dados possam ser movidos ou replicados entre eles de forma controlada.

---

## 2. Análise da Arquitetura

A ideia de "salvar em ambos ao mesmo tempo" (escrita dupla em tempo real) para cada ação na API é uma abordagem **não recomendada** pelos seguintes motivos:

-   **Complexidade Elevada:** O código da aplicação precisaria gerenciar duas conexões de banco de dados, duas transações e lidar com falhas em qualquer uma delas, o que é muito complexo.
-   **Risco de Inconsistência de Dados:** Se a escrita no NeonDB falhar por um problema de rede, mas a escrita no banco de dados local do Docker for bem-sucedida, os seus dados ficarão dessincronizados e em um estado inconsistente. Corrigir isso é extremamente difícil.
-   **Baixa Performance:** Cada requisição na sua API que salva dados (como um registro de usuário ou um novo áudio) teria que esperar a confirmação de ambos os bancos de dados. A latência da rede para se conectar ao NeonDB deixaria sua aplicação muito mais lenta para o usuário.

---

## 3. Abordagem Recomendada: Ambientes Separados

A solução padrão e robusta é tratar os dois bancos de dados como servindo a propósitos diferentes:

1.  **Banco de Dados do Docker (Ambiente de Desenvolvimento):**
    -   **Propósito:** Para ser usado no dia a dia do desenvolvimento. É rápido, isolado e pode ser resetado a qualquer momento sem medo de perder dados importantes.
    -   **Como Funciona:** O `docker-compose.yml` está configurado para que a aplicação (`app`) se conecte ao serviço `db`. Esta é a configuração ideal para o desenvolvimento.

2.  **Banco de Dados da NeonDB (Ambiente de Produção):**
    -   **Propósito:** Para a aplicação "ao vivo", quando ela for acessada por usuários reais. Contém os dados verdadeiros e persistentes.
    -   **Como Funciona:** Quando você for implantar sua aplicação em um servidor de produção (fora do Docker Compose de desenvolvimento), ela lerá a `NEONDB_CONNECTION_STRING` do arquivo `.env` e se conectará ao banco de dados remoto da Neon.

---

## 4. Plano de Implementação para Sincronização

Para mover dados entre esses dois ambientes, não faremos isso em tempo real. Em vez disso, criaremos um **script de sincronização (ou "ETL" - Extract, Transform, Load)**.

**Objetivo do Script:** Ler dados de uma **origem** (source) e escrevê-los em um **destino** (destination).

### Passo 1: Modificar o `.env`

Vamos renomear a variável de conexão no `.env` para ser mais clara e adicionar uma segunda para o banco de dados do Docker.

**Arquivo `.env` (exemplo):**
```env
# Conexão para o banco de dados de PRODUÇÃO (remoto)
DATABASE_URL_PROD="postgresql://neondb_owner:PASSWORD@ep-cold-cell-ah1zi3g4-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Conexão para o banco de dados de DESENVOLVIMENTO (Docker)
DATABASE_URL_DEV="postgresql://testuser:testpassword@localhost:5432/testdb"

# ... outras variáveis ...
```
*(Nota: `@localhost:5432` funciona porque a porta do contêiner db está mapeada para a sua máquina local)*

### Passo 2: Modificar `config.py` e `database.py`

-   O `config.py` será ajustado para ler a variável de conexão de acordo com um "modo" de operação (desenvolvimento ou produção), que pode ser definido por outra variável de ambiente.
-   O `database.py` usará a conexão que o `config.py` fornecer.

### Passo 3: Criar o Script de Sincronização (`sync_db.py`)

Este novo script fará o seguinte:

1.  **Conectar-se a ambos os bancos de dados:** Ele criará dois "engines" do SQLAlchemy, um para a origem (`DATABASE_URL_DEV`) e um para o destino (`DATABASE_URL_PROD`), ou vice-versa.
2.  **Ler os Dados da Origem:** Ele irá selecionar todos os dados de uma tabela (ex: `users`) no banco de dados de origem.
3.  **Escrever os Dados no Destino:** Ele irá percorrer os dados lidos e inseri-los no banco de dados de destino, tomando cuidado para não duplicar registros que já existam.
4.  **Será Configurável:** O script aceitará argumentos para definir a direção da sincronização (ex: `python sync_db.py --from dev --to prod`).

### Resumo do Plano

1.  **Manter a arquitetura atual:** Usar o Docker para desenvolvimento e o NeonDB para produção.
2.  **Não implementar escrita dupla em tempo real.**
3.  **Criar um script `sync_db.py` dedicado:** Este script será a ferramenta para mover dados entre os ambientes de forma manual e controlada, para tarefas como backup, migração ou popular um ambiente de teste.
