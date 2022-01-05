import os
from os.path import join, dirname
from dotenv import load_dotenv

# Create .env file path.
dotenv_path = join(dirname(__file__), '.env')

# Load file from the path.
load_dotenv(dotenv_path)

class Config:
    """Set Flask configuration vars from .env file."""
    # General
    FLASK_ENV = 'production'
    DEBUG = False
    TESTING = False
    SECRET_KEY =os.getenv('SECRET_KEY')
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_RECORD_QUERIES = False
