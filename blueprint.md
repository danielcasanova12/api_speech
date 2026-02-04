# API Endpoints - Documentação Detalhada

## Base URL
`https://api.example.com/v1`

---

## Authentication Endpoints

### 1. Criar Usuário (Register)
**POST** `/auth/register`

**Descrição:** 
Este endpoint cria um novo usuário no sistema. Deve:
- Validar se o email já existe no banco de dados
- Criptografar a senha usando hash (bcrypt, argon2, etc)
- Criar registro na tabela `users`
- Criar registros relacionados em `residence` e `parentesco`
- Retornar os dados do usuário criado (sem a senha)

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "senha123",
  "nome_completo": "João Silva",
  "idade": 25,
  "genero": "masculino",
  "language": "pt-BR",
  "residence": {
    "current_residence_state": "SP",
    "current_residence_city": "São Paulo",
    "residence_0_12": "São Paulo",
    "residence_13_18": "São Paulo",
    "residence_18_plus": "São Paulo",
    "household_origins": "São Paulo"
  },
  "parentesco": [
    {
      "cidade": "São Paulo",
      "parentesco_type": "filho"
    }
  ]

}
```

**Response (201 Created):**
```json
{
  "user_id": "uuid-here",
  "email": "user@example.com",
  "nome_completo": "João Silva",
  "idade": 25,
  "genero": "masculino",
  "language": "pt-BR",
  "is_active": true,
  "created_at": "2024-02-04T10:00:00Z"
}
```

**Validações:**
- Email deve ser único
- Password deve ter no mínimo 8 caracteres
- Idade deve ser maior que 0
- Todos os campos obrigatórios devem estar presentes

---

### 2. Autenticar (Login)
**POST** `/auth/login`

**Descrição:** 
Este endpoint autentica um usuário existente. Deve:
- Buscar usuário pelo email na tabela `users`
- Verificar se a senha fornecida corresponde ao `password_hash` armazenado
- Gerar um token JWT com tempo de expiração
- Retornar o token e os dados básicos do usuário

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "senha123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "jwt-token-here",
  "token_type": "Bearer",
  "expires_in": 36000000,
  "user": {
    "user_id": "uuid-here",
    "email": "user@example.com",
    "nome_completo": "João Silva",
    "idade": 25,
    "genero": "masculino",
    "language": "pt-BR",
    "is_active": true
  }
}
```

**Validações:**
- Email deve existir no banco
- Senha deve ser válida
- Usuário deve estar ativo (is_active = true)

---

### 3. Solicitar Reset de Senha
**POST** `/auth/forgot-password`

**Descrição:** 
Este endpoint inicia o processo de recuperação de senha. Deve:
- Verificar se o email existe na tabela `users`
- Gerar um token único e aleatório
- Criar um registro na tabela `password_resets` com:
  - `user_id` do usuário
  - `token` (hash do token gerado)
  - `expires_at` (geralmente 1 hora a partir de agora)
- Enviar email para o usuário com link contendo o token
- Retornar confirmação (sem expor dados sensíveis)

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "Email de recuperação enviado com sucesso",
  "reset_id": "reset-uuid-here"
}
```

**Validações:**
- Email deve existir no sistema
- Não deve revelar se o email existe ou não (segurança)

---

### 4. Resetar Senha
**POST** `/auth/reset-password`

**Descrição:** 
Este endpoint completa o processo de reset de senha. Deve:
- Buscar o token na tabela `password_resets`
- Verificar se o token não expirou (expires_at > agora)
- Atualizar o `password_hash` na tabela `users`
- Deletar o registro de `password_resets` usado
- Invalidar todas as sessões ativas do usuário (opcional, por segurança)

**Request Body:**
```json
{
  "token": "hashed-token-from-email",
  "new_password": "novaSenha123"
}
```

**Response (200 OK):**
```json
{
  "message": "Senha alterada com sucesso"
}
```

**Validações:**
- Token deve ser válido e não expirado
- Nova senha deve atender aos requisitos mínimos
- Token só pode ser usado uma vez

---

## Session Endpoints

### 5. Criar Sessão
**POST** `/sessions`

**Descrição:** 
Este endpoint cria uma nova sessão de gravação para o usuário. Deve:
- Validar se o usuário está autenticado (via token JWT)
- Verificar se o `user_id` corresponde ao usuário autenticado
- Criar um novo registro na tabela `sessions` com:
  - `id` (UUID gerado automaticamente)
  - `user_id` (do usuário logado)
  - `dataset_id` (ID do dataset que será usado)
  - `started_at` (timestamp de início)
  - `finished_at` (null inicialmente)
  - `notes`, `vocal_health_note`, `termos`
- Retornar os dados da sessão criada
- Não criar se já existe uma seção ativa

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "user_id": "uuid-here",
  "dataset_id": "dataset-uuid",
  "started_at": "2024-02-04T10:00:00Z",
  "notes": "Sessão de gravação matinal",
  "vocal_health_note": "Voz em boas condições",
  "termos": "Aceito os termos de uso"
}
```

**Response (201 Created):**
```json
{
  "id": "session-uuid",
  "user_id": "uuid-here",
  "dataset_id": "dataset-uuid",
  "started_at": "2024-02-04T10:00:00Z",
  "finished_at": null,
  "notes": "Sessão de gravação matinal",
  "vocal_health_note": "Voz em boas condições",
  "termos": "Aceito os termos de uso",
  "created_at": "2024-02-04T10:00:00Z"
}
```

**Validações:**
- Usuário deve estar autenticado
- Dataset_id deve existir
- Termos devem ser aceitos

---

### 6. Finalizar Sessão
**PATCH** `/sessions/{session_id}/finish`

**Descrição:** 
Este endpoint finaliza uma sessão de gravação em andamento. Deve:
- Validar se o usuário está autenticado
- Verificar se a sessão existe e pertence ao usuário autenticado
- Verificar se a sessão ainda não foi finalizada (`finished_at` é null)
- Atualizar o registro na tabela `sessions`:
  - `finished_at` (timestamp de finalização)
  - `notes` (atualizar se fornecido)
- Calcular a duração total da sessão
- Retornar os dados atualizados da sessão

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "finished_at": "2024-02-04T11:30:00Z",
  "notes": "Sessão finalizada com sucesso"
}
```

**Response (200 OK):**
```json
{
  "id": "session-uuid",
  "user_id": "uuid-here",
  "dataset_id": "dataset-uuid",
  "started_at": "2024-02-04T10:00:00Z",
  "finished_at": "2024-02-04T11:30:00Z",
  "notes": "Sessão finalizada com sucesso",
  "vocal_health_note": "Voz em boas condições",
  "termos": "Aceito os termos de uso",
  "duration_minutes": 90
}
```

**Validações:**
- Sessão deve existir e pertencer ao usuário
- Sessão não pode já estar finalizada
- finished_at deve ser posterior a started_at

---

### 7. Buscar Sessões do Usuário
**GET** `/sessions/active-{user_id}`

**Descrição:** 
Este endpoint busca TODAS as sessões (ativas e finalizadas) de um usuário específico. Deve:
- Validar se o usuário está autenticado
- Verificar se o `user_id` da URL corresponde ao usuário autenticado (ou se é admin)
- Buscar todos os registros da tabela `sessions` onde `user_id = {user_id}`
- Para cada sessão, incluir:
  - Todos os campos da sessão
  - Contagem de recordings associados
  - Status da sessão (ativa se `finished_at` é null, finalizada caso contrário)
- Ordenar por `started_at` descendente (mais recentes primeiro)
- Retornar a seção

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "total": 2,
  "sessions": [
    {
      "id": "session-uuid-1",
      "user_id": "uuid-here",
      "dataset_id": "dataset-uuid",
      "started_at": "2024-02-04T10:00:00Z",
      "finished_at": "2024-02-04T11:30:00Z",
      "notes": "Sessão finalizada com sucesso",
      "vocal_health_note": "Voz em boas condições",
      "termos": "Aceito os termos de uso",
      "recordings_count": 15,
      "status": "finished",
      "created_at": "2024-02-04T10:00:00Z",
      "updated_at": "2024-02-04T11:30:00Z"
    },
    {
      "id": "session-uuid-2",
      "user_id": "uuid-here",
      "dataset_id": "dataset-uuid",
      "started_at": "2024-02-03T14:00:00Z",
      "finished_at": null,
      "notes": "Sessão em andamento",
      "vocal_health_note": "Voz normal",
      "termos": "Aceito os termos de uso",
      "recordings_count": 5,
      "status": "active",
      "created_at": "2024-02-03T14:00:00Z",
      "updated_at": "2024-02-03T14:00:00Z"
    }
  ]
}
```

**Validações:**
- Usuário deve estar autenticado
- Apenas o próprio usuário pode ver suas sessões (ou admin)

**Notas:**
- Este endpoint retorna TODAS as sessões do usuário
- Para filtrar apenas sessões ativas, o frontend pode usar `status: "active"`
- Pode adicionar parâmetros de query para paginação: `?page=1&limit=10`

---

## Recording Endpoints

### 8. Criar Recording
**POST** `/recordings`

**Descrição:** 
Este endpoint cria um novo registro de gravação de áudio. Deve:
- Validar se o usuário está autenticado
- Verificar se a `session_id` existe e pertence ao usuário autenticado
- Verificar se a sessão ainda está ativa (`finished_at` é null)
- Receber o arquivo de áudio via multipart/form-data
- Processar o arquivo:
  - Validar formato (wav, webm, mp3, etc)
  - Extrair metadados (duração, sample_rate se não fornecidos)
  - Salvar localmente em um diretório estruturado (ex: `/recordings/YYYY/MM/DD/`)
  - Fazer upload para S3/Storage externo
  - Opcionalmente fazer upload para Google Drive
- Criar registro na tabela `recordings` com:
  - `id_recordings` (UUID gerado)
  - `session_id`, `dataset_id`, `phrase_id`
  - `path_local_audio` (caminho do arquivo no servidor)
  - `audio_url_drive` (URL do Google Drive, se aplicável)
  - `audio_url_s3` (URL do S3/Storage)
  - `duration`, `format`, `sample_rate`
  - `text_content`, `espontaniedade`, `emocao`
  - `room_tone_start`, `room_tone_end` (booleanos)
  - `created_at` (timestamp atual)
- Retornar os dados da gravação criada

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**Request Body (multipart/form-data):**
```json
{
  "session_id": "session-uuid",
  "dataset_id": "dataset-uuid",
  "phrase_id": "phrase-123",
  "audio_file": "<binary-audio-file>",
  "duration": 5.5,
  "format": "wav",
  "sample_rate": 44100,
  "text_content": "Texto a ser lido pelo usuário",
  "espontaniedade": "alta",
  "emocao": "neutro",
  "room_tone_start": true,
  "room_tone_end": false
}
```

**Response (201 Created):**
```json
{
  "id_recordings": "recording-uuid",
  "session_id": "session-uuid",
  "dataset_id": "dataset-uuid",
  "phrase_id": "phrase-123",
  "path_local_audio": "/recordings/2024/02/04/recording-uuid.wav",
  "audio_url_drive": "https://drive.google.com/file/d/xxxxx",
  "audio_url_s3": "https://s3.amazonaws.com/bucket/recording-uuid.wav",
  "duration": 5.5,
  "format": "wav",
  "sample_rate": 44100,
  "text_content": "Texto a ser lido pelo usuário",
  "espontaniedade": "alta",
  "emocao": "neutro",
  "room_tone_start": true,
  "room_tone_end": false,
  "created_at": "2024-02-04T10:15:00Z"
}
```

**Validações:**
- Arquivo de áudio é obrigatório
- Formato deve ser suportado (wav, webm, mp3, etc)
- Sessão deve estar ativa
- Tamanho do arquivo deve estar dentro do limite permitido
- Sample_rate deve ser válido (8000, 16000, 44100, 48000, etc)

**Processamento:**
1. Receber arquivo
2. Validar tipo e tamanho
3. Gerar UUID para o recording
4. Salvar arquivo localmente
5. Upload assíncrono para S3
6. Upload assíncrono para Google Drive (opcional)
7. Salvar metadados no banco
8. Retornar resposta

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Bad Request",
  "message": "Campos obrigatórios ausentes",
  "fields": ["email", "password"]
}
```
**Quando usar:** Dados inválidos ou ausentes na requisição

---

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "message": "Token inválido ou expirado"
}
```
**Quando usar:** Token JWT ausente, inválido ou expirado

---

### 403 Forbidden
```json
{
  "error": "Forbidden",
  "message": "Você não tem permissão para acessar este recurso"
}
```
**Quando usar:** Usuário tentando acessar recursos de outro usuário

---

### 404 Not Found
```json
{
  "error": "Not Found",
  "message": "Recurso não encontrado"
}
```
**Quando usar:** Sessão, recording ou usuário não encontrado

---

### 409 Conflict
```json
{
  "error": "Conflict",
  "message": "Email já cadastrado no sistema"
}
```
**Quando usar:** Tentativa de criar recurso duplicado (ex: email já existe)

---

### 413 Payload Too Large
```json
{
  "error": "Payload Too Large",
  "message": "Arquivo muito grande. Tamanho máximo: 50MB"
}
```
**Quando usar:** Upload de arquivo excede o limite permitido

---

### 500 Internal Server Error
```json
{
  "error": "Internal Server Error",
  "message": "Erro interno do servidor"
}
```
**Quando usar:** Erro não previsto no servidor

---

## Notas Importantes

### Segurança:
- Todos os endpoints (exceto login e register) requerem autenticação JWT
- Senhas devem ser sempre hasheadas (nunca armazenar em texto plano)
- Tokens de reset de senha devem expirar em tempo razoável (1 hora recomendado)
- Validar sempre se o usuário tem permissão para acessar o recurso

### Performance:
- Implementar paginação nos endpoints de listagem
- Upload de arquivos deve ser processado de forma assíncrona quando possível
- Usar cache para dados que não mudam frequentemente

### Boas Práticas:
- Sempre retornar códigos HTTP apropriados
- Mensagens de erro devem ser claras mas não expor informações sensíveis
- Documentar todos os campos obrigatórios e opcionais
- Manter consistência nos formatos de resposta