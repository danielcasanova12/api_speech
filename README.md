# API Speech

API FastAPI para cadastro de participantes, gerenciamento de sessões e coleta de
áudios de fala/música. Os metadados são persistidos em PostgreSQL; os arquivos
ficam em `STORAGE_PATH` e podem ser espelhados no Amazon S3 e Google Drive.

## Requisitos

- Python 3.12
- PostgreSQL acessível por uma URL compatível com `asyncpg`
- FFmpeg para as rotinas opcionais de inspeção de áudio

## Instalação local

No PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` com valores próprios. Nunca reutilize credenciais de produção em
desenvolvimento ou testes. Para gerar um segredo JWT, por exemplo:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Em um banco novo, crie somente as tabelas ausentes:

```powershell
python init_db.py
```

Esse helper não substitui migrations. Em bancos existentes, revise o schema e os
scripts de migração antes de implantar uma nova versão.

Inicie a API:

```powershell
uvicorn main:app --reload
```

A documentação fica em `http://127.0.0.1:8000/docs`.

## Testes

A suíte padrão é isolada e não deve acessar banco ou serviços externos:

```powershell
python -m pytest -q
```

Os módulos antigos de integração são opt-in. Execute-os apenas contra banco e
storage descartáveis, com a API local preparada:

```powershell
$env:RUN_INTEGRATION_TESTS = "1"
python -m pytest -m integration
```

## Áudios e painel administrativo

Os arquivos enviados ao S3 são recuperados pelo backend por URL assinada
temporária. O banco deve armazenar a referência permanente do objeto; registros
legados que ainda contenham URL completa do bucket continuam sendo aceitos pelo
parser de storage.

### Gravações

- `GET /api/v1/recordings`
  - Autenticação: usuário ativo.
  - Permissão: usuário comum consulta apenas suas próprias gravações; admin pode
    consultar todos os usuários.
  - Filtros opcionais: `recording_id`, `session_id`, `user_id`,
    `latest_session`, `created_from`, `created_to`, `limit`, `offset`, `page`,
    `page_size`, `order`, `has_audio`, `status`.
  - Paginação: `page=1`, `page_size=20`, máximo `100`.
  - `latest_session=true` sem `user_id` usa o usuário autenticado; com `user_id`
    exige que seja o próprio usuário ou admin.
  - Resposta: `total`, `page`, `page_size` e `items` com metadados e
    `audio_url` assinada quando disponível.

- `GET /api/v1/sessions/{session_id}/recordings`
  - Autenticação: usuário ativo.
  - Permissão: dono da sessão ou admin.
  - Parâmetros: `page`, `page_size`.
  - Retorna `404` para sessão inexistente e `403` para sessão de outro usuário.

- `GET /api/v1/recordings/{recording_id}/audio`
  - Autenticação: usuário ativo.
  - Permissão: dono da gravação ou admin.
  - Retorna URL assinada com expiração padrão de 900 segundos.
  - Retorna `404` quando a gravação ou o arquivo não existe e `503` quando o
    bucket está indisponível.

- `GET /api/v1/recordings/{recording_id}/details`
  - Autenticação: usuário ativo.
  - Permissão: dono da gravação ou admin.
  - Retorna metadados completos da gravação, incluindo `frase_content`,
    `frase_texto`, sessão, dataset e bloco relacionados.

- `GET /api/v1/recordings/sessions/{session_id}/audios`
  - Autenticação: admin.
  - Uso: rota administrativa para consultar áudios de uma sessão específica.

### Sessões

- `GET /api/v1/sessions/recent`
  - Autenticação: usuário ativo.
  - Permissão: usuário comum lista apenas as próprias sessões; admin lista todas.
  - Filtros opcionais: `dataset_id`, `created_from`, `created_to`, `page`,
    `page_size`.
  - Ordenação: sessões mais recentes primeiro por `started_at`.
  - Retorna `400` para intervalo de datas inválido e `404` para dataset
    inexistente.

### Músicas

- `GET /api/v1/musics`
  - Autenticação: usuário ativo.
  - Por padrão retorna apenas metadados e flags `has_vocal_audio` e
    `has_instrumental_audio`.
  - Use `include_audio_urls=true` para incluir URLs assinadas dos áudios na
    listagem.

- `GET /api/v1/musics/{music_id}/audio?kind=vocal`
- `GET /api/v1/musics/{music_id}/audio?kind=instrumental`
  - Autenticação: usuário ativo.
  - Retorna URL assinada de um arquivo específico da música.
  - Retorna `404` quando a música ou o arquivo não existe e `503` quando o
    bucket está indisponível.

- `POST /api/v1/musics`, `PATCH /api/v1/musics/{music_id}` e
  `DELETE /api/v1/musics/{music_id}`
  - Autenticação: admin.
  - Uso: criação, edição e remoção de conteúdo sensível e objetos no bucket.

## Erros da API

Todas as exceções tratadas pelo backend são normalizadas no mesmo formato para o
frontend:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Verifique os campos informados.",
    "details": null,
    "field_errors": {
      "email": ["Informe um e-mail válido."]
    },
    "request_id": "..."
  }
}
```

O frontend deve tomar decisões usando `error.code`, não o texto de `message`.
Mensagens técnicas de banco, bucket, bibliotecas, stack trace, tokens e URLs
assinadas não são retornadas ao cliente; detalhes técnicos ficam nos logs do
backend com o `request_id`.

Códigos principais:

- `VALIDATION_ERROR`: campos ou parâmetros inválidos.
- `AUTHENTICATION_REQUIRED`: login ausente, inválido ou expirado.
- `PERMISSION_DENIED`: usuário autenticado sem permissão.
- `ADMIN_REQUIRED`: operação exclusiva de administrador.
- `RESOURCE_NOT_FOUND`, `SESSION_NOT_FOUND`, `RECORDING_NOT_FOUND`,
  `MUSIC_NOT_FOUND`, `AUDIO_NOT_FOUND`: recurso inexistente.
- `RESOURCE_ALREADY_EXISTS`, `RESOURCE_CONFLICT`: duplicidade ou conflito de
  estado.
- `FILE_TOO_LARGE`, `UNSUPPORTED_AUDIO_FORMAT`: problemas no upload.
- `STORAGE_UNAVAILABLE`, `DATABASE_ERROR`, `INTERNAL_ERROR`: falhas de serviço
  externo, banco ou erro inesperado.

## Autorização

O backend não confia em `user_id` enviado pelo frontend para recursos privados.
Sessões, gravações e áudios de gravações são sempre associados ao usuário
autenticado pelo token. Usuários comuns acessam apenas os próprios recursos;
administradores (`is_superuser=true`) podem consultar recursos privados quando a
rota tiver finalidade administrativa.

Respostas públicas de gravações não expõem `path_local`, chave interna do bucket
ou URL permanente de storage. Para reproduzir áudio, use os endpoints que geram
URL assinada temporária após validar a permissão.

## Docker

O build exclui `.env`, tokens OAuth, certificados, ambientes virtuais e uploads.
O processo da aplicação roda sem privilégios de root e os uploads usam um volume
persistente. Para subir apenas aplicação e banco, sem o proxy TLS:

```powershell
docker compose up --build db app
```

A aplicação fica vinculada a `127.0.0.1:8000`. A URL efetivamente usada pela API
continua sendo `NEONDB_CONNECTION_STRING` do `.env`; ajuste-a para o banco
desejado. O Nginx exige certificados válidos nos caminhos descritos em
`nginx/nginx.conf` antes de subir a composição completa.

## Monitor W&B

O monitor é opcional e tem dependências separadas:

```powershell
python -m pip install -r requirements-monitor.txt
$env:WANDB_API_KEY = "..."
$env:WANDB_ENTITY = "..."
$env:DISCORD_WEBHOOK_URL = "..."
python wandb_monitor.py
```

As chaves são obrigatoriamente fornecidas em runtime e não devem ser versionadas.
