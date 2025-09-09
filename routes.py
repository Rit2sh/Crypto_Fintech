from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import logging

from app import app, db
from models import User, Wallet, Transaction, KYCDocument
from forms import RegistrationForm, LoginForm, KYCForm, TransactionForm, PaymentForm
from crypto_api import crypto_api

# ----------------------
# Public Routes
# ----------------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    # Get latest crypto prices (cached)
    try:
        prices = crypto_api.get_crypto_prices()
    except Exception as e:
        logging.error(f"Error loading index prices: {e}")
        prices = {}
    
    return render_template('index.html', prices=prices)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Check duplicates
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already exists. Please choose a different one.', 'danger')
                return render_template('register.html', form=form)

            if User.query.filter_by(email=form.email.data).first():
                flash('Email already registered. Please use a different email.', 'danger')
                return render_template('register.html', form=form)

            # Create user
            user = User(
                username=form.username.data,
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                phone=form.phone.data,
            )
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.commit()

            # Create default wallets
            for currency in ['BTC', 'ETH', 'USDT', 'INR', 'USD']:
                balance = 10000.0 if currency == 'INR' else 0.0
                db.session.add(Wallet(user_id=user.id, currency=currency, balance=balance))

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
        # Allow username OR email login
        user = User.query.filter(
            (User.username == form.username.data) |
            (User.email == form.username.data)
        ).first()

        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(request.args.get('next') or url_for('dashboard'))
        else:
            flash('Invalid username/email or password.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ----------------------
# Dashboard & Wallet
# ----------------------
@app.route('/dashboard')
@login_required
def dashboard():
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc()).limit(5).all()

    try:
        prices = crypto_api.get_crypto_prices()
    except Exception as e:
        logging.error(f"Dashboard price error: {e}")
        prices = {}

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
    try:
        prices = crypto_api.get_crypto_prices()
    except Exception as e:
        logging.error(f"Wallet price error: {e}")
        prices = {}
    return render_template('wallet.html', wallets=wallets, prices=prices)


# ----------------------
# Trading
# ----------------------
@app.route('/trading', methods=['GET', 'POST'])
@login_required
def trading():
    form = TransactionForm()

    if form.validate_on_submit():
        try:
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

            converted_amount = crypto_api.convert_currency(
                form.amount.data,
                form.from_currency.data,
                form.to_currency.data
            )

            if converted_amount <= 0:
                flash('Unable to process conversion. Please try again.', 'danger')
                return render_template('trading.html', form=form)

            fee = (form.amount.data or 0.0) * 0.001  # 0.1% fee
            from_wallet.balance -= form.amount.data

            if not to_wallet:
                to_wallet = Wallet(user_id=current_user.id,
                                   currency=form.to_currency.data,
                                   balance=0.0)
                db.session.add(to_wallet)

            to_wallet.balance += converted_amount

            transaction = Transaction(
                user_id=current_user.id,
                transaction_type=form.transaction_type.data,
                from_currency=form.from_currency.data,
                to_currency=form.to_currency.data,
                amount=form.amount.data,
                rate=converted_amount / (form.amount.data or 1.0),
                fee=fee,
                status='completed',
                completed_at=datetime.utcnow()
            )

            db.session.add(transaction)
            db.session.commit()

            flash(f'Successfully converted {form.amount.data} {form.from_currency.data} '
                  f'to {converted_amount:.6f} {form.to_currency.data}', 'success')
            return redirect(url_for('wallet'))

        except Exception as e:
            db.session.rollback()
            logging.error(f"Trading error: {e}")
            flash('Transaction failed. Please try again.', 'danger')

    try:
        prices = crypto_api.get_crypto_prices()
    except Exception:
        prices = {}
    return render_template('trading.html', form=form, prices=prices)


# ----------------------
# Payments
# ----------------------
@app.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    form = PaymentForm()

    if form.validate_on_submit():
        try:
            wallet = Wallet.query.filter_by(
                user_id=current_user.id,
                currency=form.currency.data
            ).first()

            if not wallet or wallet.balance < form.amount.data:
                flash('Insufficient balance for this payment.', 'danger')
                return render_template('payments.html', form=form)

            recipient = User.query.filter_by(email=form.recipient_email.data).first()
            if not recipient:
                flash('Recipient email not found in our system.', 'danger')
                return render_template('payments.html', form=form)

            if recipient.id == current_user.id:
                flash('Cannot send payment to yourself.', 'danger')
                return render_template('payments.html', form=form)

            fee = (form.amount.data or 0.0) * 0.005  # 0.5% fee
            total_deduction = form.amount.data + fee

            if wallet.balance < total_deduction:
                flash(f'Insufficient balance. Need {total_deduction:.2f} including fees.', 'danger')
                return render_template('payments.html', form=form)

            recipient_wallet = Wallet.query.filter_by(
                user_id=recipient.id,
                currency=form.currency.data
            ).first()

            if not recipient_wallet:
                recipient_wallet = Wallet(user_id=recipient.id,
                                          currency=form.currency.data,
                                          balance=0.0)
                db.session.add(recipient_wallet)

            wallet.balance -= total_deduction
            recipient_wallet.balance += form.amount.data

            send_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='send',
                from_currency=form.currency.data,
                to_currency=form.currency.data,
                amount=form.amount.data,
                fee=fee,
                status='completed',
                recipient_address=form.recipient_email.data,
                completed_at=datetime.utcnow()
            )

            receive_transaction = Transaction(
                user_id=recipient.id,
                transaction_type='receive',
                from_currency=form.currency.data,
                to_currency=form.currency.data,
                amount=form.amount.data,
                fee=0.0,
                status='completed',
                completed_at=datetime.utcnow()
            )

            db.session.add(send_transaction)
            db.session.add(receive_transaction)
            db.session.commit()

            flash(f'Successfully sent {form.amount.data} {form.currency.data} to {form.recipient_email.data}', 'success')
            return redirect(url_for('wallet'))

        except Exception as e:
            db.session.rollback()
            logging.error(f"Payment error: {e}")
            flash('Payment failed. Please try again.', 'danger')

    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .filter(Transaction.transaction_type.in_(['send', 'receive']))\
        .order_by(Transaction.created_at.desc()).limit(10).all()

    return render_template('payments.html', form=form, transactions=recent_transactions)


# ----------------------
# KYC & Profile
# ----------------------
@app.route('/kyc', methods=['GET', 'POST'])
@login_required
def kyc():
    form = KYCForm()

    if form.validate_on_submit():
        try:
            if KYCDocument.query.filter_by(user_id=current_user.id, status='approved').first():
                flash('Your KYC is already approved.', 'info')
                return redirect(url_for('profile'))

            kyc_doc = KYCDocument(
                user_id=current_user.id,
                document_type=form.document_type.data,
                document_number=form.document_number.data,
                status='pending'
            )

            db.session.add(kyc_doc)
            db.session.commit()

            flash('KYC submitted. Verification may take 24-48 hours.', 'success')
            return redirect(url_for('profile'))

        except Exception as e:
            db.session.rollback()
            logging.error(f"KYC error: {e}")
            flash('KYC submission failed. Please try again.', 'danger')

    kyc_documents = KYCDocument.query.filter_by(user_id=current_user.id)\
        .order_by(KYCDocument.uploaded_at.desc()).all()

    return render_template('kyc.html', form=form, documents=kyc_documents)


@app.route('/profile')
@login_required
def profile():
    latest_kyc = KYCDocument.query.filter_by(user_id=current_user.id)\
        .order_by(KYCDocument.uploaded_at.desc()).first()
    kyc_status = latest_kyc.status.title() if latest_kyc else 'Not Submitted'

    transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc()).limit(20).all()

    return render_template('profile.html',
                           kyc_status=kyc_status,
                           transactions=transactions)


# ----------------------
# API Endpoints
# ----------------------
@app.route('/api/crypto-prices')
def api_crypto_prices():
    try:
        prices = crypto_api.get_crypto_prices()
        return jsonify(prices)
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({'error': 'Failed to fetch prices'}), 500


@app.route('/api/historical-data/<coin_id>')
@login_required
def api_historical_data(coin_id):
    try:
        days = request.args.get('days', 7, type=int)
        data = crypto_api.get_historical_data(coin_id, days)
        return jsonify(data)
    except Exception as e:
        logging.error(f"API historical error: {e}")
        return jsonify({'error': 'Failed to fetch historical data'}), 500


# ----------------------
# Error Handlers
# ----------------------
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
