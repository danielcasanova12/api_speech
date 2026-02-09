# Documentação da API de Gravação de Áudio para Desenvolvedores Front-End (Versão Estendida)

## 1. Visão Geral e Conceitos Essenciais

Esta documentação fornece um guia completo para integrar um aplicativo front-end com a API de Gravação de Áudio.

### 1.1. URL Base da API

-   **Desenvolvimento:** `http://localhost:8000` (ou o endereço do seu servidor local)
-   **Produção:** `https://SEU_DOMINIO.com`

### 1.2. Autenticação

A API utiliza **JWT (JSON Web Token)** para proteger a maioria dos seus endpoints.

-   **Fluxo:** O front-end envia as credenciais do usuário para o endpoint de login. Se forem válidas, a API retorna um `access_token`.
-   **Uso do Token:** Este `access_token` deve ser incluído em todas as requisições para endpoints protegidos, dentro do cabeçalho `Authorization` no formato `Bearer <token>`.
-   **Expiração:** Tokens têm um tempo de vida limitado. O front-end deve ser capaz de lidar com respostas de erro `401 Unauthorized`, que indicam que o token é inválido ou expirou, geralmente redirecionando o usuário para a página de login.

### 1.3. Estrutura dos Endpoints da API

-   `/auth` e `/users`: Para autenticação e gerenciamento de usuários.
-   `/api/v1`: Contém os endpoints principais da aplicação (datasets, blocos, sessões, gravações).

---

## 2. Endpoints de Autenticação e Usuários

### **2.1. Registrar Novo Usuário** (`POST /auth/register`)

-   **Descrição:** Cria uma nova conta de usuário com detalhes aninhados.
-   **Autenticação:** Não requerida.
-   **Corpo (JSON):**
    ```json
    {
      "email": "user@example.com",
      "password": "uma_senha_forte_e_segura",
      "nome_completo": "Nome Completo do Usuário",
      "data_nascimento": "YYYY-MM-DD",
      "genero": "Masculino/Feminino/Outro",
      "language": "Português",
      "cidade_nascimento": { "cidade": "São Paulo", "estado": "SP" },
      "cidade_atual": { "cidade": "Rio de Janeiro", "estado": "RJ" },
      "historico_moradia": [
        { "periodo": "0-12 anos", "endereco": { "cidade": "Curitiba", "estado": "PR" } }
      ],
      "familiares": [
        { "nome": "Nome do Familiar", "grau_parentesco": "Pai/Mãe", "endereco": { "cidade": "Rio de Janeiro", "estado": "RJ" } }
      ]
    }
    ```
-   **Respostas:**
    -   `201 Created`: Sucesso.
    -   `400 Bad Request`: E-mail já existe ou dados inválidos.

### **2.2. Login de Usuário** (`POST /auth/jwt/login`)

-   **Descrição:** Autentica um usuário e retorna o `access_token`.
-   **Autenticação:** Não requerida.
-   **Corpo (`application/x-www-form-urlencoded`):**
    - `username`: O e-mail do usuário.
    - `password`: A senha do usuário.
-   **Resposta de Sucesso (200 OK):**
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer"
    }
    ```

### **2.3. Obter Dados do Usuário Logado** (`GET /users/me`)

-   **Descrição:** Retorna as informações do usuário autenticado.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Resposta de Sucesso (200 OK):** Retorna o objeto completo `UserRead`.

---

## 3. Endpoints da API (v1)

Todos os endpoints abaixo estão sob o prefixo `/api/v1`.

### **3.1. Datasets (`/api/v1/datasets`)**

#### `POST /` - Criar Dataset
-   **Descrição:** Cria um novo dataset.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Corpo (JSON):**
    ```json
    { "name": "Nome do Novo Dataset" }
    ```
-   **Respostas:**
    -   `200 OK`: Sucesso. Retorna o objeto do dataset criado.
    -   `400 Bad Request`: Dataset com este nome já existe.
    -   `401 Unauthorized`: Token inválido ou não fornecido.

#### `GET /` - Listar Datasets
-   **Descrição:** Retorna uma lista de todos os datasets.
-   **Autenticação:** Não requerida.
-   **Resposta de Sucesso (200 OK):**
    ```json
    [
      { "id": 1, "name": "Dataset A" },
      { "id": 2, "name": "Dataset B" }
    ]
    ```

#### `PUT /{dataset_id}` - Atualizar Dataset
-   **Descrição:** Atualiza o nome de um dataset.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Corpo (JSON):**
    ```json
    { "name": "Novo Nome do Dataset" }
    ```
-   **Respostas:**
    -   `200 OK`: Sucesso.
    -   `404 Not Found`: Dataset não encontrado.

### **3.2. Blocos (`/api/v1/blocos`)**

#### `POST /` - Criar Bloco
-   **Descrição:** Cria um novo bloco de gravação.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Corpo (JSON):**
    ```json
    {
      "nome_bloco": "Leitura de Frases - Emoção Neutra",
      "descricao": "Bloco para leitura de frases com emoção neutra.",
      "tipo": "Leitura",
      "emocao_numerico": 0,
      "descricao_emocao": "Neutra",
      "espontaniedade": 0
    }
    ```
-   **Respostas:**
    -   `201 Created`: Sucesso. Retorna o objeto do bloco criado.
    -   `400 Bad Request`: Bloco com este nome já existe.
    -   `401 Unauthorized`: Token inválido ou não fornecido.

#### `GET /` - Listar Blocos
-   **Descrição:** Retorna uma lista de todos os blocos.
-   **Autenticação:** Não requerida.

#### `PUT /{bloco_id}` - Atualizar Bloco
-   **Descrição:** Atualiza os dados de um bloco.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Corpo (JSON):** Corpo parcial com os campos a serem atualizados.
-   **Respostas:**
    -   `200 OK`: Sucesso.
    -   `404 Not Found`: Bloco não encontrado.

#### `DELETE /{bloco_id}` - Deletar Bloco
-   **Descrição:** Deleta um bloco.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Respostas:**
    -   `204 No Content`: Sucesso.
    -   `404 Not Found`: Bloco não encontrado.

### **3.3. Sessões (`/api/v1/sessions`)**

#### `POST /` - Criar Sessão
-   **Descrição:** Inicia uma nova sessão de gravação para o usuário logado.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Corpo (JSON):**
    ```json
    {
      "dataset_id": 1,
      "notes": "Iniciando gravação de teste.",
      "vocal_health_note": "Nenhuma queixa.",
      "termos": true
    }
    ```
-   **Respostas:**
    -   `201 Created`: Sucesso.
    -   `404 Not Found`: O `dataset_id` fornecido não existe.
    -   `409 Conflict`: O usuário já possui uma sessão ativa.

### **3.4. Gravações (`/api/v1/recordings`)**

#### `POST /` - Fazer Upload de Gravação
-   **Descrição:** Envia um arquivo de áudio e seus metadados, associando-o a uma sessão e a um bloco.
-   **Autenticação:** **Requerida (Bearer Token).**
-   **Corpo (`multipart/form-data`):**
    -   `audio_file`: O arquivo de áudio (ex: `.wav`, `.webm`).
    -   `session_id` (int): ID da sessão ativa.
    -   `dataset_id` (int): ID do dataset.
    -   `bloco_id` (int): **(Novo)** ID do bloco que define o contexto da gravação.
    -   `duration` (float): Duração do áudio em segundos.
    -   `format` (str): Formato do áudio (ex: "webm").
    -   `sample_rate` (int): Taxa de amostragem (ex: 48000).
    -   `frase_content` (str, opcional): **(Novo)** A transcrição da frase, se houver.
-   **Exemplo de Implementação (Front-End com `fetch`):**
    ```javascript
    async function uploadRecording(audioBlob, metadata) {
      const accessToken = localStorage.getItem('accessToken');
      const formData = new FormData();
      
      formData.append('audio_file', audioBlob, 'recording.webm');
      formData.append('session_id', metadata.sessionId);
      formData.append('dataset_id', metadata.datasetId);
      formData.append('bloco_id', metadata.blocoId); // Novo campo
      formData.append('duration', metadata.duration);
      formData.append('format', 'webm');
      formData.append('sample_rate', 48000);
      formData.append('frase_content', metadata.fraseContent); // Novo nome

      try {
        const response = await fetch('http://localhost:8000/api/v1/recordings/', {
          method: 'POST',
          headers: {
            // Não defina 'Content-Type', o navegador faz isso.
            'Authorization': `Bearer ${accessToken}`
          },
          body: formData
        });

        if (response.status === 201) {
          const result = await response.json();
          console.log('Upload bem-sucedido:', result);
        } else {
          const error = await response.json();
          console.error('Falha no upload:', error.detail);
        }
      } catch (error) {
        console.error('Erro de rede:', error);
      }
    }
    ```
-   **Respostas:**
    -   `201 Created`: Sucesso. Retorna o objeto da gravação.
    -   `404 Not Found`: A `session_id` ou `bloco_id` não foi encontrada.
    -   `400 Bad Request`: A sessão já está finalizada.