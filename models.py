from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    is_kyc_verified = db.Column(db.Boolean, default=False)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    wallets = db.relationship('Wallet', backref='user', lazy=True)
    kyc_documents = db.relationship('KYCDocument', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_portfolio_value(self):
        total_value = 0.0
        if hasattr(self, 'wallets') and self.wallets:
            for wallet in self.wallets:
                if wallet.balance:
                    total_value += wallet.balance * wallet.get_current_price()
        return total_value

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    currency = db.Column(db.String(10), nullable=False)  # BTC, ETH, USDT, INR, USD
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_current_price(self):
        # Mock prices for demonstration - in production would use real API
        prices = {
            'BTC': 45000.00,
            'ETH': 3200.00,
            'USDT': 1.00,
            'INR': 1.00,
            'USD': 83.12  # USD to INR rate
        }
        return prices.get(self.currency, 1.0)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # buy, sell, send, receive, convert
    from_currency = db.Column(db.String(10))
    to_currency = db.Column(db.String(10))
    amount = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float)
    fee = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    recipient_address = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class KYCDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # passport, aadhar, pan, etc.
    document_number = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime)

class CryptoPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    current_price_usd = db.Column(db.Float)
    current_price_inr = db.Column(db.Float)
    price_change_24h = db.Column(db.Float)
    market_cap = db.Column(db.Float)
    volume_24h = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
