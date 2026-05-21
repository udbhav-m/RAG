from app.db import Base
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Text, JSON

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    password_hash: Mapped[str]

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Conversation(Base):
    __tablename__="conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),index=True)
    title: Mapped[str | None]

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="conversations")

    messages: Mapped[list['Message']] = relationship(
        back_populates='conversation',
        cascade="all, delete-orphan"
    )

class Message(Base):
    __tablename__="messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"),index=True)
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    message_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    conversation: Mapped['Conversation'] = relationship(back_populates="messages")