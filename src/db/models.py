import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from src.db.connection import Base


class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(String(50), primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False, index=True)
    account_type = Column(String(50), nullable=False, default="checking")
    risk_tier = Column(String(20), nullable=False, default="LOW")
    country = Column(String(50), nullable=False, default="USA")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    transactions = relationship("Transaction", back_populates="account")
    alerts = relationship("Alert", back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(50), primary_key=True, index=True)
    account_id = Column(String(50), ForeignKey("accounts.account_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    counterparty_name = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    location_country = Column(String(50), nullable=False, default="USA")
    transaction_type = Column(String(50), nullable=False, default="wire_transfer")
    is_flagged = Column(Boolean, default=False)

    account = relationship("Account", back_populates="transactions")


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(50), primary_key=True, index=True)
    account_id = Column(String(50), ForeignKey("accounts.account_id"), nullable=False, index=True)
    transaction_id = Column(String(50), ForeignKey("transactions.transaction_id"), nullable=True)
    trigger_reason = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")
    risk_score = Column(Integer, nullable=True)
    risk_rationale = Column(Text, nullable=True)
    sar_document = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    account = relationship("Account", back_populates="alerts")
