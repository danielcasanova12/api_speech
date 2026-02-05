# Documentação da API de Gravação de Áudio para Desenvolvedores Front-End (Versão Estendida)

## 1. Visão Geral e Conceitos Essenciais

Esta documentação fornece um guia completo para integrar um aplicativo front-end com a API de Gravação de Áudio.

### 1.1. URL Base da API

-   **Desenvolvimento:** `http://127.0.0.1:8000`
-   **Produção:** Substitua pelo endereço do seu servidor.

### 1.2. Autenticação

A API utiliza **JWT (JSON Web Token)** para proteger seus endpoints.

-   **Fluxo:** O front-end envia as credenciais do usuário (e-mail e senha) para o endpoint de login. Se forem válidas, a API retorna um `access_token`.
-   **Uso do Token:** Este `access_token` deve ser incluído em todas as requisições para endpoints protegidos, dentro do cabeçalho `Authorization` no formato `Bearer <token>`.
-   **Armazenamento:** O front-end é responsável por armazenar este token de forma segura (por exemplo, em `localStorage`, `sessionStorage` ou em memória) e gerenciá-lo durante a sessão do usuário.
-   **Expiração:** Tokens JWT têm um tempo de vida limitado. O front-end deve ser capaz de lidar com respostas de erro `401 Unauthorized`, que indicam que o token é inválido ou expirou, geralmente redirecionando o usuário para a página de login.

### 1.3. Headers Padrão

-   `Content-Type: application/json`: Necessário para o corpo de requisições `POST` e `PATCH` que enviam dados JSON.
-   `Authorization: Bearer <seu_access_token>`: Necessário para todos os endpoints que exigem autenticação.
-   `Accept: application/json`: Boa prática para indicar que o cliente espera uma resposta em JSON.

---

## 2. Endpoints de Autenticação e Usuários

### **2.1. Registrar Novo Usuário**

-   **Endpoint:** `POST /auth/register`
-   **Descrição:** Cria uma nova conta de usuário.
-   **Autenticação:** Não requerida.

#### Requisição
-   **Corpo (JSON):**
    ```json
    {
      "email": "user@example.com",
      "password": "uma_senha_forte_e_segura"
    }
    ```

#### Respostas
-   **Sucesso (201 Created):** Indica que o usuário foi criado.
    ```json
    {
      "id": "uuid-do-usuario",
      "email": "user@example.com",
      "is_active": true,
      "is_superuser": false,
      "is_verified": false
    }
    ```
-   **Erro (400 Bad Request):** E-mail ou senha inválidos.
    ```json
    { "detail": "REGISTER_INVALID_PASSWORD" }
    ```
-   **Erro (400 Bad Request):** E-mail já registrado.
    ```json
    { "detail": "REGISTER_USER_ALREADY_EXISTS" }
    ```

#### Exemplo de Implementação (Front-End)
```javascript
async function registerUser(email, password) {
  const response = await fetch('http://127.0.0.1:8000/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  if (response.status === 201) {
    alert('Registro bem-sucedido! Por favor, faça o login.');
    // Redirecionar para a página de login
  } else {
    alert(`Erro no registro: ${data.detail}`);
  }
}
```

### **2.2. Login de Usuário**

-   **Endpoint:** `POST /auth/jwt/login`
-   **Descrição:** Autentica um usuário e retorna o `access_token`.
-   **Autenticação:** Não requerida.

#### Requisição
-   **Corpo (`application/x-www-form-urlencoded`):**
    - `username`: O e-mail do usuário.
    - `password`: A senha do usuário.

#### Respostas
-   **Sucesso (200 OK):** Login bem-sucedido.
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer"
    }
    ```
-   **Erro (400 Bad Request):** Credenciais inválidas.
    ```json
    { "detail": "LOGIN_BAD_CREDENTIALS" }
    ```

#### Exemplo de Implementação (Front-End)
```javascript
async function login(email, password) {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);

  const response = await fetch('http://127.0.0.1:8000/auth/jwt/login', {
    method: 'POST',
    body: formData
  });
  const data = await response.json();
  if (response.ok) {
    localStorage.setItem('accessToken', data.access_token);
    // Redirecionar para a página principal da aplicação
  } else {
    alert(`Falha no login: ${data.detail}`);
  }
}
```

### **2.3. Solicitar Redefinição de Senha**

-   **Endpoint:** `POST /auth/forgot-password`
-   **Descrição:** Envia um e-mail com um link de redefinição de senha para o usuário.
-   **Autenticação:** Não requerida.

#### Requisição
-   **Corpo (JSON):**
    ```json
    { "email": "user@example.com" }
    ```

#### Respostas
-   **Sucesso (202 Accepted):** A requisição foi aceita. O corpo da resposta é vazio. Esta resposta é sempre a mesma para evitar a enumeração de usuários.

### **2.4. Redefinir a Senha**

-   **Endpoint:** `POST /auth/reset-password`
-   **Descrição:** Define uma nova senha usando o token recebido por e-mail.
-   **Autenticação:** Não requerida.

#### Requisição
-   **Corpo (JSON):**
    ```json
    {
      "token": "token_recebido_no_email",
      "password": "minha_nova_senha"
    }
    ```
#### Respostas
-   **Sucesso (200 OK):** Senha alterada com sucesso. Corpo vazio.
-   **Erro (400 Bad Request):** O token é inválido.
    ```json
    { "detail": "RESET_PASSWORD_BAD_TOKEN" }
    ```

### **2.5. Obter Dados do Usuário Logado**

-   **Endpoint:** `GET /users/me`
-   **Descrição:** Retorna as informações do usuário autenticado.
-   **Autenticação:** **Requerida (Bearer Token).**

#### Respostas
-   **Sucesso (200 OK):**
    ```json
    {
      "id": "uuid-do-usuario",
      "email": "user@example.com",
      "is_active": true,
      "is_superuser": false,
      "is_verified": true
    }
    ```
-   **Erro (401 Unauthorized):** Token não fornecido, inválido ou expirado.

---

## 3. Endpoints de Sessões e Gravações

### **3.1. Criar Nova Sessão de Gravação**

-   **Endpoint:** `POST /api/v1/sessions/`
-   **Descrição:** Cria uma sessão para agrupar uma ou mais gravações de áudio.
-   **Autenticação:** **Requerida (Bearer Token).**

#### Requisição
-   **Corpo (JSON):**
    ```json
    { "session_name": "Minha Primeira Sessão" }
    ```
#### Respostas
-   **Sucesso (200 OK):** Retorna o objeto da sessão criada.
    ```json
    {
      "id": 1,
      "session_name": "Minha Primeira Sessão",
      "user_id": "uuid-do-usuario",
      "created_at": "2026-02-05T14:30:00Z"
    }
    ```
-   **Erro (401 Unauthorized):** Não autenticado.
-   **Erro (422 Unprocessable Entity):** O corpo da requisição é inválido.

### **3.2. Listar Sessões do Usuário**

-   **Endpoint:** `GET /api/v1/sessions/`
-   **Descrição:** Retorna uma lista de todas as sessões criadas pelo usuário.
-   **Autenticação:** **Requerida (Bearer Token).**

#### Respostas
-   **Sucesso (200 OK):** Retorna um array de objetos de sessão.
    ```json
    [
      {
        "id": 1,
        "session_name": "Minha Primeira Sessão",
        "user_id": "uuid-do-usuario",
        "created_at": "2026-02-05T14:30:00Z"
      }
    ]
    ```
-   **Erro (401 Unauthorized):** Não autenticado.

### **3.3. Upload de Arquivo de Áudio**

-   **Endpoint:** `POST /api/v1/recordings/`
-   **Descrição:** Faz o upload de um arquivo de áudio e o associa a uma sessão.
-   **Autenticação:** **Requerida (Bearer Token).**

#### Requisição
-   **Corpo (`multipart/form-data`):**
    - `file`: O arquivo de áudio (`.wav`, `.mp3`, `.webm`, etc.).
    - `session_id`: O `id` da sessão à qual este áudio pertence.

#### Respostas
-   **Sucesso (200 OK):** Retorna metadados da gravação salva.
    ```json
    {
      "id": 1,
      "filename": "nome_unico_gerado.webm",
      "gdrive_id": null,
      "session_id": 1,
      "created_at": "2026-02-05T14:35:00Z"
    }
    ```
-   **Erro (401 Unauthorized):** Não autenticado.
-   **Erro (422 Unprocessable Entity):** Faltam campos (`file` ou `session_id`) ou os tipos são inválidos.

#### Exemplo de Implementação (Front-End)
```javascript
// 'audioBlob' é um objeto Blob da gravação
// 'sessionId' é o ID da sessão ativa
async function uploadAudio(audioBlob, sessionId) {
  const accessToken = localStorage.getItem('accessToken');
  const formData = new FormData();
  formData.append('file', audioBlob, 'minha-gravacao.webm');
  formData.append('session_id', sessionId);

  const response = await fetch('http://127.0.0.1:8000/api/v1/recordings/', {
    method: 'POST',
    headers: {
      // NÃO definir 'Content-Type', o navegador faz isso
      'Authorization': `Bearer ${accessToken}`
    },
    body: formData
  });
  const data = await response.json();
  if (response.ok) {
    alert('Upload realizado com sucesso!');
  } else {
    alert(`Falha no upload: ${data.detail}`);
  }
}
```
