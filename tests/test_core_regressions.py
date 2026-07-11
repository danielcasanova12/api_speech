import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import create_engine, select as sync_select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SyncSession

import admin_router
import user_manager as user_manager_module
from auth_router import custom_register
from datasets_router import create_dataset, update_dataset
from frases_router import current_superuser as frase_current_superuser
from frases_router import router as frases_router
from models import (
    Base,
    Bloco,
    Dataset,
    Endereco,
    Frase,
    Recording,
    Session,
    User,
)
from schemas import DatasetCreate, DatasetUpdate, SessionUpdate, UserCreate
from sessions_router import _prepare_session_update
from user_manager import CustomSQLAlchemyUserDatabase, UserManager


class ScalarResult:
    def __init__(self, values):
        self.values = list(values)

    def first(self):
        return self.values[0] if self.values else None

    def all(self):
        return self.values

    def one(self):
        if len(self.values) != 1:
            raise AssertionError(f"Expected one value, got {len(self.values)}")
        return self.values[0]


class Result:
    def __init__(self, values=()):
        self._values = values

    def scalars(self):
        return ScalarResult(self._values)


class RegistrationSession:
    def __init__(self, commit_error=None):
        self.objects = []
        self.commit_error = commit_error
        self.rolled_back = False

    def add(self, value):
        self.objects.append(value)

    async def commit(self):
        if self.commit_error:
            raise self.commit_error

    async def rollback(self):
        self.rolled_back = True

    async def execute(self, _statement):
        users = [value for value in self.objects if isinstance(value, User)]
        return Result(users)


class RegistrationUserDB:
    def __init__(self, session):
        self.session = session
        self.looked_up_email = None

    async def get_by_email(self, email):
        self.looked_up_email = email
        return None


class FakePasswordHelper:
    def hash(self, password):
        return f"hashed:{password}"


def make_user_create(**overrides):
    data = {
        "email": "Potential.Admin@Example.COM",
        "password": "a-password",
        "is_active": False,
        "is_superuser": True,
        "is_verified": True,
        "nome_completo": "Test User",
        "data_nascimento": date(2000, 1, 1),
        "genero": None,
        "language": "pt-BR",
        "cidade_nascimento": {"cidade": "Curitiba", "estado": "PR"},
        "cidade_atual": {"cidade": "São Paulo", "estado": "SP"},
        "historico_moradia": [],
        "familiares": [],
    }
    data.update(overrides)
    return UserCreate.model_validate(data)


@pytest.mark.asyncio
async def test_custom_register_forces_safe_flags_and_normalizes_email():
    session = RegistrationSession()
    user_db = RegistrationUserDB(session)
    manager = SimpleNamespace(
        user_db=user_db,
        password_helper=FakePasswordHelper(),
        validate_password=AsyncMock(),
        on_after_register=AsyncMock(),
    )

    created = await custom_register(make_user_create(), manager)

    assert user_db.looked_up_email == "potential.admin@example.com"
    assert created.email == "potential.admin@example.com"
    assert created.is_active is True
    assert created.is_superuser is False
    assert created.is_verified is False


@pytest.mark.asyncio
async def test_custom_register_turns_integrity_race_into_conflict():
    error = IntegrityError("INSERT", {}, Exception("duplicate"))
    session = RegistrationSession(commit_error=error)
    manager = SimpleNamespace(
        user_db=RegistrationUserDB(session),
        password_helper=FakePasswordHelper(),
        validate_password=AsyncMock(),
        on_after_register=AsyncMock(),
    )

    with pytest.raises(HTTPException) as raised:
        await custom_register(make_user_create(), manager)

    assert raised.value.status_code == 409
    assert session.rolled_back is True


class FakeUserSession:
    def __init__(self):
        self.committed = False
        self.refreshed = None

    def add(self, _value):
        pass

    async def commit(self):
        self.committed = True

    async def refresh(self, value):
        self.refreshed = value


@pytest.mark.asyncio
async def test_nested_current_address_is_updated_as_an_orm_object():
    session = FakeUserSession()
    database = CustomSQLAlchemyUserDatabase(session, User)
    user = SimpleNamespace(
        email="old@example.com",
        cidade_atual=SimpleNamespace(cidade="Old", estado="PR"),
    )

    updated = await database.update(
        user,
        {
            "email": "NEW@EXAMPLE.COM",
            "cidade_atual": {"cidade": "New City", "estado": "SP"},
        },
    )

    assert updated is user
    assert user.email == "new@example.com"
    assert user.cidade_atual.cidade == "New City"
    assert user.cidade_atual.estado == "SP"
    assert session.committed is True


@pytest.mark.asyncio
async def test_password_and_verification_tokens_are_not_logged(monkeypatch, caplog):
    reset_sender = AsyncMock()
    verify_sender = AsyncMock()
    monkeypatch.setattr(user_manager_module, "send_reset_password_email", reset_sender)
    monkeypatch.setattr(user_manager_module, "send_verification_email", verify_sender)
    manager = UserManager(SimpleNamespace())
    user = SimpleNamespace(id=uuid.uuid4(), email="user@example.com")

    with caplog.at_level(logging.INFO):
        await manager.on_after_forgot_password(user, "private-reset-token")
        await manager.on_after_request_verify(user, "private-verify-token")

    assert "private-reset-token" not in caplog.text
    assert "private-verify-token" not in caplog.text
    reset_sender.assert_awaited_once_with(user.email, "private-reset-token")
    verify_sender.assert_awaited_once_with(user.email, "private-verify-token")


def active_session(started_at=None):
    return SimpleNamespace(
        status="active",
        started_at=started_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=None,
    )


def test_cancelling_a_session_sets_a_terminal_timestamp():
    session = active_session()
    now = session.started_at + timedelta(minutes=5)

    values, new_status, send_email = _prepare_session_update(
        session,
        SessionUpdate(status="cancelled"),
        now=now,
    )

    assert values["status"] == "cancelled"
    assert values["finished_at"] == now
    assert new_status == "cancelled"
    assert send_email is True


def test_finished_at_only_preserves_put_compatibility_and_finishes_session():
    session = active_session()
    finished_at = session.started_at + timedelta(minutes=3)

    values, new_status, _ = _prepare_session_update(
        session,
        SessionUpdate(finished_at=finished_at),
    )

    assert values["status"] == "finished"
    assert values["finished_at"] == finished_at
    assert new_status == "finished"


@pytest.mark.parametrize(
    "update",
    [
        SessionUpdate(finished_at=None),
        SessionUpdate(
            status="active",
            finished_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ],
)
def test_inconsistent_session_updates_are_rejected(update):
    with pytest.raises(HTTPException):
        _prepare_session_update(active_session(), update)


def test_terminal_session_cannot_be_reopened():
    session = SimpleNamespace(
        status="finished",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as raised:
        _prepare_session_update(session, SessionUpdate(status="active"))

    assert raised.value.status_code == 409


def test_session_update_rejects_naive_client_timestamp():
    with pytest.raises(ValidationError):
        SessionUpdate(finished_at=datetime(2026, 1, 2))


class DatasetDB:
    def __init__(self, dataset=None):
        self.dataset = dataset
        self.added = None

    async def execute(self, _statement):
        return Result()

    def add(self, value):
        self.added = value

    async def get(self, _model, _identifier):
        return self.dataset

    async def commit(self):
        pass

    async def refresh(self, _value):
        pass


@pytest.mark.asyncio
async def test_dataset_type_is_persisted_on_create_and_update():
    create_db = DatasetDB()
    created = await create_dataset(
        DatasetCreate(name="Music dataset", dataset_type="music"),
        create_db,
        SimpleNamespace(),
    )
    assert created.dataset_type == "music"

    update_db = DatasetDB(created)
    renamed = await update_dataset(
        1,
        DatasetUpdate(name="Renamed music dataset"),
        update_db,
        SimpleNamespace(),
    )
    assert renamed.dataset_type == "music"

    update_db = DatasetDB(renamed)
    updated = await update_dataset(
        1,
        DatasetUpdate(name="Renamed music dataset", dataset_type="singing"),
        update_db,
        SimpleNamespace(),
    )
    assert updated.dataset_type == "singing"


def test_create_phrase_route_has_an_admin_dependency():
    route = next(
        route
        for route in frases_router.routes
        if isinstance(route, APIRoute) and "POST" in route.methods
    )
    assert any(
        dependency.call is frase_current_superuser
        for dependency in route.dependant.dependencies
    )


def test_deleting_user_cascades_sessions_and_recordings():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with SyncSession(engine) as db:
        user = User(
            email="cascade@example.com",
            hashed_password="hash",
            is_active=True,
            is_superuser=False,
            is_verified=False,
            nome_completo="Cascade User",
            data_nascimento=date(2000, 1, 1),
            cidade_nascimento=Endereco(cidade="A", estado="PR"),
            cidade_atual=Endereco(cidade="B", estado="SP"),
        )
        dataset = Dataset(name="Cascade dataset", dataset_type="speech")
        bloco = Bloco(nome_bloco="Cascade bloco")
        frase = Frase(texto="Cascade phrase", bloco=bloco)
        recording_session = Session(user=user, dataset=dataset, termos=True)
        recording = Recording(
            session=recording_session,
            dataset=dataset,
            bloco=bloco,
            frase=frase,
            is_test=False,
        )
        db.add_all([user, dataset, bloco, frase, recording_session, recording])
        db.commit()

        db.delete(user)
        db.commit()

        assert db.scalar(sync_select(Session).where(Session.user_id == user.id)) is None
        assert db.scalar(sync_select(Recording)) is None


class AdminDB:
    def __init__(self, target, recording, *, fail_commit=False):
        self.results = iter(
            [
                Result([target]),
                Result([recording]),
                Result([3]),
                Result([4]),
                Result(),
            ]
        )
        self.events = []
        self.fail_commit = fail_commit

    async def execute(self, _statement):
        self.events.append("execute")
        return next(self.results)

    async def delete(self, _value):
        self.events.append("delete")

    async def flush(self):
        self.events.append("flush")

    async def commit(self):
        self.events.append("commit")
        if self.fail_commit:
            raise RuntimeError("commit failed")

    async def rollback(self):
        self.events.append("rollback")


def admin_fixtures():
    target = SimpleNamespace(
        id=uuid.uuid4(),
        email="target@example.com",
        cidade_nascimento_id=1,
        cidade_atual_id=2,
    )
    recording = SimpleNamespace(
        path_local="uploads/recording.wav",
        audio_url_s3="s3-key",
        audio_url_drive="drive-id",
    )
    return target, recording


@pytest.mark.asyncio
async def test_admin_commits_database_before_asset_cleanup(monkeypatch):
    target, recording = admin_fixtures()
    db = AdminDB(target, recording)

    async def cleanup(_assets):
        db.events.append("cleanup")

    monkeypatch.setattr(admin_router, "_cleanup_recording_assets", cleanup)
    await admin_router.delete_user_and_data_by_email(
        target.email,
        SimpleNamespace(id=uuid.uuid4()),
        db,
    )

    assert db.events.index("commit") < db.events.index("cleanup")
    assert db.events.index("delete") < db.events.index("commit")
    assert "rollback" not in db.events


@pytest.mark.asyncio
async def test_admin_does_not_cleanup_assets_when_database_commit_fails(monkeypatch):
    target, recording = admin_fixtures()
    db = AdminDB(target, recording, fail_commit=True)
    cleanup = AsyncMock()
    monkeypatch.setattr(admin_router, "_cleanup_recording_assets", cleanup)

    with pytest.raises(HTTPException) as raised:
        await admin_router.delete_user_and_data_by_email(
            target.email,
            SimpleNamespace(id=uuid.uuid4()),
            db,
        )

    assert raised.value.status_code == 500
    assert "rollback" in db.events
    cleanup.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_cleanup_deletes_local_and_cloud_assets(monkeypatch, tmp_path):
    local_file = tmp_path / "recording.wav"
    local_file.write_bytes(b"audio")
    delete_s3 = AsyncMock(return_value=True)
    delete_drive = AsyncMock(return_value=True)
    monkeypatch.setattr(admin_router.settings, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(admin_router, "delete_from_s3", delete_s3)
    monkeypatch.setattr(admin_router, "delete_from_gdrive", delete_drive)

    await admin_router._cleanup_recording_assets(
        [
            admin_router.RecordingAssets(
                path_local=str(local_file),
                audio_url_s3="bucket/key.wav",
                audio_url_drive="drive-id",
            )
        ]
    )

    assert not local_file.exists()
    delete_s3.assert_awaited_once_with("bucket/key.wav")
    delete_drive.assert_awaited_once_with("drive-id")
