Database Schema
users

user_id (UUID, PK)
email (Unique)
password_hash
nome_completo
Idade
genero
language
is_active (Boolean)


password_resets

id
user_id (FK)
token (Hashed)
expires_at (Timestamp)


residence

current_residence_state
current_residence_city
residence_0_12
residence_13_18
residence_18_plus
household_origins


Parentesco

cidade
Parentesco_type


sessions

id (PK)
user_id (FK)
dataset_id (FK)
started_at
finished_at
notes
vocal_health_note
Termos


recordings

id_recordings (PK)
session_id (FK)
Dataset_id
phrase_id
path local do audio
audio_url (Drive)
audio_url (Caminho no S3/Storage)
duration (Float)
format (Ex: "wav", "webm")
sample_rate (Ex: 44100)
text_content (O texto a ser lido, se houver)
Espontaniedade
Emoção
room_tone_start
room_tone_end
created_at


Relationships

password_resets.user_id → users.user_id
residence → users (relationship indicated by arrow)
Parentesco → users (relationship indicated by arrow)
sessions.user_id → users.user_id
recordings.session_id → sessions.id