from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime
import logging

from app import app, db
from models import User, Wallet, Transaction, KYCDocument, CryptoPrice
from forms import RegistrationForm, LoginForm, KYCForm, TransactionForm, PaymentForm
from crypto_api import crypto_api

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Get latest crypto prices for display
    prices = crypto_api.get_crypto_prices()
    return render_template('index.html', prices=prices)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please use a different email.', 'danger')
            return render_template('register.html', form=form)
        
        # Create new user
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.phone = form.phone.data
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Create default wallets
            currencies = ['BTC', 'ETH', 'USDT', 'INR', 'USD']
            for currency in currencies:
                wallet = Wallet()
                wallet.user_id = user.id
                wallet.currency = currency
                wallet.balance = 10000.0 if currency == 'INR' else 0.0
                db.session.add(wallet)
            
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'danger')
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Check if login is username or email
        user = User.query.filter(
            (User.username == form.username.data) | 
            (User.email == form.username.data)
        ).first()
        
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username/email or password.', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's wallet balances
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    
    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc()).limit(5).all()
    
    # Get current crypto prices
    prices = crypto_api.get_crypto_prices()
    
    # Calculate portfolio value
    portfolio_value = current_user.get_portfolio_value()
    
    return render_template('dashboard.html', 
                         wallets=wallets, 
                         transactions=recent_transactions,
                         prices=prices,
                         portfolio_value=portfolio_value)

@app.route('/wallet')
@login_required
def wallet():
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    prices = crypto_api.get_crypto_prices()
    return render_template('wallet.html', wallets=wallets, prices=prices)

@app.route('/trading', methods=['GET', 'POST'])
@login_required
def trading():
    form = TransactionForm()
    
    if form.validate_on_submit():
        try:
            # Get user's wallets
            from_wallet = Wallet.query.filter_by(
                user_id=current_user.id, 
                currency=form.from_currency.data
            ).first()
            
            to_wallet = Wallet.query.filter_by(
                user_id=current_user.id,
                currency=form.to_currency.data
            ).first()
            
            if not from_wallet or from_wallet.balance < form.amount.data:
                flash('Insufficient balance in source wallet.', 'danger')
                return render_template('trading.html', form=form)
            
            # Calculate conversion rate
            converted_amount = crypto_api.convert_currency(
                form.amount.data,
                form.from_currency.data,
                form.to_currency.data
            )
            
            if converted_amount <= 0:
                flash('Unable to process conversion. Please try again.', 'danger')
                return render_template('trading.html', form=form)
            
            # Calculate fee (0.1% of transaction)
            fee = (form.amount.data or 0.0) * 0.001
            
            # Update wallet balances
            from_wallet.balance -= form.amount.data
            
            if not to_wallet:
                to_wallet = Wallet()
                to_wallet.user_id = current_user.id
                to_wallet.currency = form.to_currency.data
                to_wallet.balance = 0.0
                db.session.add(to_wallet)
            
            to_wallet.balance += converted_amount
            
            # Create transaction record
            transaction = Transaction()
            transaction.user_id = current_user.id
            transaction.transaction_type = form.transaction_type.data
            transaction.from_currency = form.from_currency.data
            transaction.to_currency = form.to_currency.data
            transaction.amount = form.amount.data
            transaction.rate = converted_amount / (form.amount.data or 1.0)
            transaction.fee = fee
            transaction.status = 'completed'
            transaction.completed_at = datetime.utcnow()
            
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Successfully converted {form.amount.data} {form.from_currency.data} to {converted_amount:.6f} {form.to_currency.data}', 'success')
            return redirect(url_for('wallet'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Trading error: {e}")
            flash('Transaction failed. Please try again.', 'danger')
    
    prices = crypto_api.get_crypto_prices()
    return render_template('trading.html', form=form, prices=prices)

@app.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    form = PaymentForm()
    
    if form.validate_on_submit():
        try:
            # Check if user has sufficient balance
            wallet = Wallet.query.filter_by(
                user_id=current_user.id,
                currency=form.currency.data
            ).first()
            
            if not wallet or wallet.balance < form.amount.data:
                flash('Insufficient balance for this payment.', 'danger')
                return render_template('payments.html', form=form)
            
            # Find recipient user
            recipient = User.query.filter_by(email=form.recipient_email.data).first()
            if not recipient:
                flash('Recipient email not found in our system.', 'danger')
                return render_template('payments.html', form=form)
            
            if recipient.id == current_user.id:
                flash('Cannot send payment to yourself.', 'danger')
                return render_template('payments.html', form=form)
            
            # Calculate fee (0.5% for P2P payments)
            fee = (form.amount.data or 0.0) * 0.005
            total_deduction = form.amount.data + fee
            
            if wallet.balance < total_deduction:
                flash(f'Insufficient balance. Total amount including fee: {total_deduction:.2f}', 'danger')
                return render_template('payments.html', form=form)
            
            # Get or create recipient wallet
            recipient_wallet = Wallet.query.filter_by(
                user_id=recipient.id,
                currency=form.currency.data
            ).first()
            
            if not recipient_wallet:
                recipient_wallet = Wallet()
                recipient_wallet.user_id = recipient.id
                recipient_wallet.currency = form.currency.data
                recipient_wallet.balance = 0.0
                db.session.add(recipient_wallet)
            
            # Update balances
            wallet.balance -= total_deduction
            recipient_wallet.balance += form.amount.data
            
            # Create transaction records
            send_transaction = Transaction()
            send_transaction.user_id = current_user.id
            send_transaction.transaction_type = 'send'
            send_transaction.from_currency = form.currency.data
            send_transaction.to_currency = form.currency.data
            send_transaction.amount = form.amount.data
            send_transaction.fee = fee
            send_transaction.status = 'completed'
            send_transaction.recipient_address = form.recipient_email.data
            send_transaction.completed_at = datetime.utcnow()
            
            receive_transaction = Transaction()
            receive_transaction.user_id = recipient.id
            receive_transaction.transaction_type = 'receive'
            receive_transaction.from_currency = form.currency.data
            receive_transaction.to_currency = form.currency.data
            receive_transaction.amount = form.amount.data
            receive_transaction.fee = 0.0
            receive_transaction.status = 'completed'
            receive_transaction.completed_at = datetime.utcnow()
            
            db.session.add(send_transaction)
            db.session.add(receive_transaction)
            db.session.commit()
            
            flash(f'Successfully sent {form.amount.data} {form.currency.data} to {form.recipient_email.data}', 'success')
            return redirect(url_for('wallet'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Payment error: {e}")
            flash('Payment failed. Please try again.', 'danger')
    
    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .filter(Transaction.transaction_type.in_(['send', 'receive']))\
        .order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('payments.html', form=form, transactions=recent_transactions)

@app.route('/kyc', methods=['GET', 'POST'])
@login_required
def kyc():
    form = KYCForm()
    
    if form.validate_on_submit():
        try:
            # Check if user already has a pending/approved KYC
            existing_kyc = KYCDocument.query.filter_by(
                user_id=current_user.id,
                status='approved'
            ).first()
            
            if existing_kyc:
                flash('Your KYC is already approved.', 'info')
                return redirect(url_for('profile'))
            
            # Create new KYC document record
            kyc_doc = KYCDocument()
            kyc_doc.user_id = current_user.id
            kyc_doc.document_type = form.document_type.data
            kyc_doc.document_number = form.document_number.data
            kyc_doc.status = 'pending'
            
            db.session.add(kyc_doc)
            db.session.commit()
            
            flash('KYC document submitted successfully. Verification may take 24-48 hours.', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"KYC submission error: {e}")
            flash('KYC submission failed. Please try again.', 'danger')
    
    # Get user's KYC documents
    kyc_documents = KYCDocument.query.filter_by(user_id=current_user.id)\
        .order_by(KYCDocument.uploaded_at.desc()).all()
    
    return render_template('kyc.html', form=form, documents=kyc_documents)

@app.route('/profile')
@login_required
def profile():
    # Get user's KYC status
    kyc_status = 'Not Submitted'
    latest_kyc = KYCDocument.query.filter_by(user_id=current_user.id)\
        .order_by(KYCDocument.uploaded_at.desc()).first()
    
    if latest_kyc:
        kyc_status = latest_kyc.status.title()
    
    # Get transaction history
    transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc()).limit(20).all()
    
    return render_template('profile.html', 
                         kyc_status=kyc_status,
                         transactions=transactions)

@app.route('/api/crypto-prices')
def api_crypto_prices():
    """API endpoint for real-time crypto prices"""
    try:
        prices = crypto_api.get_crypto_prices()
        return jsonify(prices)
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({'error': 'Failed to fetch prices'}), 500

@app.route('/api/historical-data/<coin_id>')
@login_required
def api_historical_data(coin_id):
    """API endpoint for historical price data"""
    try:
        days = request.args.get('days', 7, type=int)
        data = crypto_api.get_historical_data(coin_id, days)
        return jsonify(data)
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({'error': 'Failed to fetch historical data'}), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
