import os
from sqlalchemy.orm import Session
from models import ExchangeRate, Quote, QuoteLine, User, ExpenseType
from auth import hash_password

def init_db_seeds(db: Session):
    # Crea admin inicial si no existe
    if not db.query(User).first():
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="ADMIN"
        )
        db.add(admin)
        db.add(ExpenseType(name="ODC"))
        db.add(ExpenseType(name="Caja Chica"))
        db.add(ExchangeRate(gtq_per_usd=7.8, is_active=True))
        db.commit()

def get_active_rate(db: Session):
    rate = db.query(ExchangeRate).filter(ExchangeRate.is_active == True).first()
    return rate.gtq_per_usd if rate else 7.8

def calculate_quote_totals(db: Session, quote_id: int):
    quote = db.query(Quote).get(quote_id)
    rate = get_active_rate(db)
    total_gtq = 0
    total_usd = 0
    for line in quote.lines:
        total_gtq += line.line_cost_gtq
        total_usd += line.line_cost_usd
    
    quote.total_cost_gtq = total_gtq
    quote.total_cost_usd = total_usd
    # Margenes sugeridos
    quote.suggested_price_usd_m70 = total_usd / (1 - 0.70) if total_usd else 0
    quote.suggested_price_usd_m60 = total_usd / (1 - 0.60) if total_usd else 0
    quote.suggested_price_usd_m50 = total_usd / (1 - 0.50) if total_usd else 0
    
    db.commit()
    db.refresh(quote)
    return quote