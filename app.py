import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
# Add WhiteNoise to serve static files
from whitenoise import WhiteNoise

# Configure logging
logging.basicConfig(level=logging.INFO)

# Define the base for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

# --- Create the Flask App ---
app = Flask(__name__)

# --- Configuration ---
app.secret_key = os.environ.get("SESSION_SECRET", "a-secure-secret-key-that-you-should-change")

# Serve static files from the 'static/' directory
app.wsgi_app = WhiteNoise(app.wsgi_app, root="static/")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# --- Database configuration ---
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///crypto_platform.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 280,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- Initialize Extensions ---
db.init_app(app)
login_manager.init_app(app)

# --- Flask-Login Configuration ---
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# --- Import Routes ---
import routes

# --- Database Creation (Run once before first deploy) ---
# Use a separate script to create the database
# with app.app_context():
#     db.create_all()

