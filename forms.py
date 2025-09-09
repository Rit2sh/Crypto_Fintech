from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SelectField, FloatField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from wtforms.widgets import FileInput
from flask_wtf.file import FileField, FileAllowed

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=20)
    ])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])

class LoginForm(FlaskForm):
    username = StringField('Username or Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class KYCForm(FlaskForm):
    document_type = SelectField('Document Type', choices=[
        ('passport', 'Passport'),
        ('aadhar', 'Aadhar Card'),
        ('pan', 'PAN Card'),
        ('driving_license', 'Driving License')
    ], validators=[DataRequired()])
    document_number = StringField('Document Number', validators=[DataRequired()])
    document_file = FileField('Upload Document', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Only images and PDFs allowed')
    ])

class TransactionForm(FlaskForm):
    transaction_type = SelectField('Transaction Type', choices=[
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('convert', 'Convert'),
        ('send', 'Send')
    ], validators=[DataRequired()])
    from_currency = SelectField('From Currency', choices=[
        ('INR', 'Indian Rupee'),
        ('USD', 'US Dollar'),
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('USDT', 'Tether')
    ], validators=[DataRequired()])
    to_currency = SelectField('To Currency', choices=[
        ('INR', 'Indian Rupee'),
        ('USD', 'US Dollar'),
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('USDT', 'Tether')
    ], validators=[DataRequired()])
    amount = FloatField('Amount', validators=[
        DataRequired(),
        NumberRange(min=0.00001, message='Amount must be greater than 0')
    ])
    recipient_address = StringField('Recipient Address (for send transactions)')

class PaymentForm(FlaskForm):
    recipient_email = EmailField('Recipient Email', validators=[DataRequired(), Email()])
    amount = FloatField('Amount', validators=[
        DataRequired(),
        NumberRange(min=1, message='Amount must be at least 1')
    ])
    currency = SelectField('Currency', choices=[
        ('INR', 'Indian Rupee'),
        ('USD', 'US Dollar')
    ], validators=[DataRequired()])
    note = TextAreaField('Note (Optional)', validators=[Length(max=200)])
