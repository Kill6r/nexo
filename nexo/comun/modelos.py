import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column("username", String(64), unique=True)
    clave_cifrada: Mapped[str] = mapped_column("password_hash", String(255))
    creado_en: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), default=ahora_utc
    )


class Evento(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_event_owner_key"),
        Index("ix_events_owner_created", "owner_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_usuario: Mapped[uuid.UUID] = mapped_column("owner_id", ForeignKey("users.id"))
    tipo: Mapped[str] = mapped_column("type", String(100))
    origen: Mapped[str] = mapped_column("source", String(100))
    datos: Mapped[dict[str, Any]] = mapped_column("payload", JSON)
    clave_idempotencia: Mapped[str] = mapped_column("idempotency_key", String(128))
    huella: Mapped[str] = mapped_column("fingerprint", String(64))
    estado: Mapped[str] = mapped_column("status", String(20), default="pending")
    intentos: Mapped[int] = mapped_column("attempts", default=0)
    resultado: Mapped[dict[str, Any] | None] = mapped_column("result", JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), default=ahora_utc
    )
    procesado_en: Mapped[datetime | None] = mapped_column(
        "processed_at", DateTime(timezone=True), nullable=True
    )


class Pendiente(Base):
    __tablename__ = "outbox"
    __table_args__ = (Index("ix_outbox_pending", "published_at", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_evento: Mapped[uuid.UUID] = mapped_column("event_id", ForeignKey("events.id"), unique=True)
    creado_en: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), default=ahora_utc
    )
    publicado_en: Mapped[datetime | None] = mapped_column(
        "published_at", DateTime(timezone=True), nullable=True
    )
