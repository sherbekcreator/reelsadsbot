from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey
from datetime import datetime

# Neon.tech PostgreSQL bazasi (Render va bulutli server uchun)
DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_8psr9IgPXNAE@ep-lucky-cloud-b46lv94e-pooler.c-6.us-east-2.aws.neon.tech/neondb"

# PostgreSQL uchun asinxron ulanish sozlamasi
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    language_code = Column(String, default="uz")
    
    balance = Column(Integer, default=0)
    total_earned = Column(Integer, default=0)
    
    referred_by = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tx_type = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")