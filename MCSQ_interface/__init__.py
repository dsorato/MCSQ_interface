from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import *
import time
import threading
from flask_login import LoginManager
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity
)

db = SQLAlchemy()


def create_app():
	"""Construct the core application."""
	app = Flask(__name__, instance_relative_config=False)
	app.config.from_object('config.Config')
	
	app.config['JWT_SECRET_KEY'] = ''
	jwt = JWTManager(app)

	db.init_app(app)
	login_manager = LoginManager()
	login_manager.init_app(app)
	
	from .models import User

	@login_manager.user_loader
	def load_user(email):
		return User.query.get(email)

	app.app_context().push()
	db.create_all()
	from . import routes
	return app

if __name__ == '__main__':
	app.run(debug=True)
