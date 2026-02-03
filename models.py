import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Mall(Base):
    __tablename__ = "malls"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    ois = relationship("OI", back_populates="mall")

class OI(Base):
    __tablename__ = "ois"
    id = Column(Integer, primary_key=True, index=True)
    mall_id = Column(Integer, ForeignKey("malls.id"))
    oi_code = Column(String, unique=True, nullable=False)
    oi_name = Column(String, nullable=False)
    annual_budget_usd = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    mall = relationship("Mall", back_populates="ois")

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    oi_id = Column(Integer, ForeignKey("ois.id"))
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    budget_usd = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    oi = relationship("OI")

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    id = Column(Integer, primary_key=True)
    effective_date = Column(Date, default=datetime.date.today)
    gtq_per_usd = Column(Float, nullable=False)
    is_active = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class ActivityType(Base):
    __tablename__ = "activity_types"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class Insumo(Base):
    __tablename__ = "insumos"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    unit_type = Column(String) 
    cost_gtq = Column(Float, default=0.0)
    billing_mode = Column(String) 
    is_active = Column(Boolean, default=True)

class Quote(Base):
    __tablename__ = "quotes"
    id = Column(Integer, primary_key=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    mall_id = Column(Integer, ForeignKey("malls.id"), nullable=True)
    oi_id = Column(Integer, ForeignKey("ois.id"), nullable=True)
    activity_name = Column(String, nullable=False)
    activity_type_id = Column(Integer, ForeignKey("activity_types.id"))
    status = Column(String, default="BORRADOR") 
    total_cost_gtq = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    suggested_price_usd_m70 = Column(Float, default=0.0)
    suggested_price_usd_m60 = Column(Float, default=0.0)
    suggested_price_usd_m50 = Column(Float, default=0.0)
    final_sale_price_usd = Column(Float, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    creator = relationship("User")
    activity_type = relationship("ActivityType")
    lines = relationship("QuoteLine", back_populates="quote")
    oi = relationship("OI")

class QuoteLine(Base):
    __tablename__ = "quote_lines"
    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"))
    insumo_id = Column(Integer, ForeignKey("insumos.id"))
    qty_personas = Column(Float, default=1.0)
    units_value = Column(Float, default=1.0)
    line_cost_gtq = Column(Float, default=0.0)
    line_cost_usd = Column(Float, default=0.0)
    quote = relationship("Quote", back_populates="lines")
    insumo = relationship("Insumo")

class ExpenseType(Base):
    __tablename__ = "expense_types"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    is_active = Column(Boolean, default=True)

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True) 
    provider_type = Column(String, nullable=True) 
    bank_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    legal_name = Column(String, nullable=True) 
    nit = Column(String, nullable=True)
    cui = Column(String, nullable=True) # <--- NUEVO CAMPO CUI
    is_active = Column(Boolean, default=True)

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    year = Column(Integer)
    month = Column(Integer)
    mall_id = Column(Integer, ForeignKey("malls.id"))
    oi_id = Column(Integer, ForeignKey("ois.id"))
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    category = Column(String) 
    description = Column(String)
    amount_gtq = Column(Float)
    amount_usd = Column(Float)
    doc_number = Column(String, nullable=True) 
    odc_number = Column(String, nullable=True) 
    text_additional = Column(String, nullable=True) 
    host_details = Column(JSON, nullable=True) 
    company_id = Column(Integer, ForeignKey("companies.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    mall = relationship("Mall")
    oi = relationship("OI")
    company = relationship("Company")
    quote = relationship("Quote")