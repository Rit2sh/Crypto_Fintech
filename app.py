import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Define the base for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

# --- Create the Flask App ---
# Vercel will look for this 'app' object
app = Flask(__name__)

# --- Configuration ---
# Use environment variables for sensitive data
app.secret_key = os.environ.get("SESSION_SECRET", "crypto-fintech-secret-key-2024")
# Use Vercel's proxy fix to ensure correct request information
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///crypto_platform.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- Initialize Extensions with the App ---
db.init_app(app)
login_manager.init_app(app)

# --- Flask-Login Configuration ---
login_manager.login_view = 'login'  # The route for the login page
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    # Import here to avoid circular dependencies
    from models import User
    return User.query.get(int(user_id))

# --- Import Routes ---
# Import your routes after the app object is fully configured
# This assumes you have a routes.py file
import routes
