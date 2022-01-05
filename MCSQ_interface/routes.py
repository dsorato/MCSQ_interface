import datetime
import os
import requests
import operator
import re
from .models import db, Survey, Module, Alignment, Survey_item, Instruction, Introduction, Request, Response, User
from .searches import *
from .utils import *
from flask import Flask, request, render_template, make_response,redirect, flash
from datetime import datetime as dt
from flask import current_app as app
import pandas as pd
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired
from os.path import join, dirname
from flask_login import UserMixin, login_required, current_user, login_user,logout_user
import nltk
from nltk.collocations import *
from nltk.tokenize import TweetTokenizer
import string
from .tmx import *
from flask import Response

from flask_jwt_extended import create_access_token, decode_token
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError

# using SendGrid's Python Library
# https://github.com/sendgrid/sendgrid-python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

# Create .env file path.
dotenv_path = join(dirname(__file__), 'sendgrid.env')

# Load file from the path.
load_dotenv(dotenv_path)



@app.route('/activate/<id>', methods=['GET', 'POST'])
def activate(id):
	"""
	Activates an user account by setting the is_active to true in the users table.
	
	Args:
		param1 id (string): the user's email, being used as an ID

	Returns: 

		Redirects user to main page. If the user was successfuly activated, then logs user in.
	"""
	user = User.query.filter_by(email=id).first()
	if user:
		user.is_active=True
		db.session.commit()
		flash("The account was successfully activated, please log in using the e-mail and password used in the moment of the registration.", "info")
	else:
		flash("User not found in the database!", "danger")

	db.session.close()
	db.session.remove()
	return redirect('/')


@app.route('/requestReset', methods=['GET', 'POST'])
def request_reset():
	"""
	Manages the user's password reset request by triggering an email with an access token valid for 8 hours.
	"""
	form = RequestResetPasswordForm()
	if request.method == 'POST':
		informed_email = request.form['email']
		if informed_email == "":
			flash("Please enter a valid e-mail.", "danger")
			return redirect('/requestReset')
		else:
			exists = db.session.query(User.email).filter_by(email=informed_email).scalar() is not None
			if exists == False:
				flash('Wrong email! The informed address %s is not registered in the system' % informed_email, "danger")
				db.session.close()
				db.session.remove()
				return redirect('/requestReset')
			else:
				flash('A password recovery email has been sent to %s. Open the email and click on the link to complete the reset' % informed_email, "info")
				
				user = User.query.filter_by(email=informed_email).first()

				expires = datetime.timedelta(hours=8)
				reset_token = create_access_token(str(user.email), expires_delta=expires)
				

				localhost_url = ''
				message = Mail(
					from_email='',
					to_emails=informed_email,
					subject='Reset your MCSQ database password',
					html_content='Hello,<br> In order to complete the password reset please click  <a href="' + (localhost_url) + '/reset/' + str(reset_token) + '"> here </a>. If you did not ask for a password reset, contact the MCSQ administrators immediately.<br> Best wishes,<br> MCSQ team'
								
					)
				try:
					sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
					response = sg.send(message)
				except Exception as e:
						print(e.message)
				db.session.close()
				db.session.remove()
				return redirect('/')


	return render_template('request_reset.html', title='', form=form)

def verify_reset_token(token):
	"""
	Verifies if a given reset token really corresponds to the user supposedly asking for the reset 
	
	Args:
		param1 token (string): verification token.
	Returns: 
		The email of the user, stored in the database.
	"""
	try:
		user_id = decode_token(token)['identity']
	except Exception as e:
		return
	
	user = User.query.filter_by(email=user_id).first()

	return user

@app.route('/reset/<id>', methods=['GET', 'POST'])
def reset(id):
	"""
	Resets the user's password, if the user identity is valid.
	Also sends an email to the user informing of the password reset.
	
	Args:
		param1 id (string): verification token.
	"""
	user = verify_reset_token(id)
	if not user:
		flash('Invalid user!', "danger")
		db.session.close()
		db.session.remove()
		return redirect('/')
	else:
		form = ResetPasswordForm()
		if form.validate_on_submit():
			if request.method == 'POST':
				informed_password = hash_password(request.form['password'])
				user.password=informed_password
				db.session.commit()
				flash('Password reset successful! Log in using your new password.', "info")
				localhost_url = ''
				message = Mail(
					from_email='',
					to_emails=user.email,
					subject='Password reset successful',
					html_content='Hello,<br>Your password reset was successful. If you did not ask for a password reset, contact the MCSQ administrators.<br><br>Best wishes,<br> MCSQ team'				
					)
				try:
					sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
					response = sg.send(message)
				except Exception as e:
					print(e)

				db.session.close()
				db.session.remove()
				return redirect('/')
		else:
			return render_template('reset.html', title='', form=form)   

	return render_template('reset.html', title='', form=form)   

	



@app.route('/userRegistry', methods=['GET', 'POST'])
def user_registry():
	"""
	Inserts an user account in the database with a non activated status.
	Also sends an account activation email to the user.

	"""
	form = UserRegistryForm()
	if form.validate_on_submit():
		if request.method == 'POST':
			informed_email = request.form['email']
			password = hash_password(request.form['password'])
			name = request.form['name']
			exists = db.session.query(User.email).filter_by(email=informed_email).scalar() is not None
			if exists:
				flash('The address %s is already in use, please choose another one' % informed_email, "danger")
				db.session.close()
				db.session.remove()
				return redirect('/userRegistry')
			else:
				false_active = False
				curr_user = User(email=informed_email, name=name, password=password, is_active=false_active)
				db.session.add(curr_user)
				db.session.commit()
				localhost_url = ''
				message = Mail(
					from_email='',
					to_emails=informed_email,
					subject='Confirm your MCSQ database account',
					html_content='Hello,<br> Thank you for your interest in using the MCSQ interface.<br>'+ 
					'After activating your account, you can login in the MCSQ interface using the email and password provided at the moment of registration.<br>'+ 
					'In order to complete your registration in the MCSQ interface, please click  <a href="' + (localhost_url) + '/activate/' + str(curr_user.email) + '"> in this link </a>.<br>'+ 
					'In some cases you will need to click on the link more than once to complete activation, please be patient.<br>'+ 
					'If you have trouble activating your account, please respond to this email informing the problem.<br>'+
					'Keep in mind that the MCSQ interface is a work in progress, and sometimes it may unavailable to new features inclusion/testing.<br><br> Best wishes,<br> MCSQ team'
								
					)
				try:
					sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
					response = sg.send(message)
					flash('An activation e-mail has been sent to you, please check your inbox and activate your account.', "info")
				except Exception as e:
						print(e.message)
				db.session.close()
				db.session.remove()
				return redirect('/')
	else:
		return render_template('register.html', title='', form=form)




@app.route('/login', methods=['GET', 'POST'])
def login():
	"""
	Manages the user login. A given user must have activated his/her account through the activation
	e-mail before being able to log in.

	"""
	form = UserLoginForm()
	if request.method == 'POST':
		informed_email = request.form['email']
		password = request.form['password']
		if informed_email == "" or password == "":
			flash("Enter a valid email and password!", "danger")
			return redirect('/login')
		possible_user =  User.query.filter_by(email=informed_email).first()
		if not possible_user:
			flash('The %s email is not registered in the database!' % informed_email, "danger")
			return redirect('/login')
		verify_pass = db.session.query(User.password).filter_by(email=informed_email)
		verify_active = db.session.query(User.is_active).filter_by(email=informed_email)
		if verify_password(verify_pass[0][0], password) and verify_active[0][0] is True:
			print("Logged in")
			login_user(possible_user)
			return redirect('/')
		else:
			flash('Wrong password or account not confirmed!', "danger")
			db.session.close()
			db.session.remove()
			return redirect('/login')
	else:
		return render_template('login.html', title='', form=form)




@app.route("/logout")
@login_required
def logout():
	"""
	Manages the user logout.
	"""
	logout_user()
	db.session.close()
	db.session.remove()
	db.engine.dispose()

	return redirect('/')


@app.route('/', methods=['GET'])
def index():
	"""
	Displays the main page.
	"""
	return render_template('home.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')

@app.route('/userguide', methods=['GET'])
def user_guidelines():
	"""
	Displays the user guidelines.
	"""
	return render_template('user_guidelines.html',maintitle='MCSQ Interface', title='User guidelines for executing word search')


@app.route('/changelogs', methods=['GET'])
def changelogs():
	"""
	Displays the MCSQ changelogs.
	"""
	return render_template('changelogs.html',maintitle='MCSQ Interface', title='MCSQ version changelog')


@app.route('/surveys', methods=['GET'])
@login_required
def display_survey():
	"""
	Displays which questionnaires are available in the MCSQ.
	"""
	if current_user.is_authenticated:
		surveys = db.session.query(Survey).all()
		lst = []
		for survey in surveys:
			item = {'Survey ID': survey.surveyid, 'Study': survey.study, 'Wave or Round': survey.wave_round, 
			'Year': survey.year, 'Language/Country': survey.country_language}
			lst.append(item)

		db.session.close()
		db.session.remove()
		df = pd.DataFrame.from_dict(lst)
		return render_template('display_table.html', maintitle='Questionnaires available in MCSQ',table=df.to_html(), title ='MCSQ Survey Collection')
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/modules', methods=['GET'])
@login_required
def display_modules():
	"""
	Displays which modules are present across all questionnaires.
	"""
	if current_user.is_authenticated:
		modules = db.session.query(Module).all()
		lst = []
		for module in modules:
			item = {'Module ID': module.moduleid, 'Module Name': module.module_name}
			lst.append(item)

		db.session.close()
		db.session.remove()
		df = pd.DataFrame.from_dict(lst)
		return render_template('display_table.html', maintitle='Modules in MCSQ',table=df.to_html(), title ='MCSQ Module Collection')
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/downloadsurveys', methods=['GET'])
@login_required
def download_survey():
	"""
	Creates a pandas dataframe of the survey table and outputs it for the user as a tab separated csv.
	"""
	if current_user.is_authenticated:
		surveys = db.session.query(Survey).all()
		lst = []
		for survey in surveys:
			item = {'Survey ID': survey.surveyid, 'Study': survey.study, 'Wave or Round': survey.wave_round, 
			'Year': survey.year, 'Country/Language': survey.country_language}
			lst.append(item)

		db.session.close()
		db.session.remove()
		df = pd.DataFrame.from_dict(lst)
		resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
		resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
		resp.headers["Content-Type"] = "text/csv"

		return resp
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/downloadmodules', methods=['GET'])
@login_required
def download_modules():
	"""
	Creates a pandas dataframe of the module table and outputs it for the user as a tab separated csv.
	"""
	if current_user.is_authenticated:
		modules = db.session.query(Module).all()
		lst = []
		for module in modules:
			item = {'Module ID': module.moduleid, 'Module Name': module.module_name}
			lst.append(item)

		db.session.close()
		db.session.remove()
		df = pd.DataFrame.from_dict(lst)
		resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
		resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
		resp.headers["Content-Type"] = "text/csv"

		return resp
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')



@app.route('/searchrequest', methods=['GET', 'POST'])
@login_required
def search_request():
	"""
	Word search in the Request table.
	"""
	if current_user.is_authenticated:
		if request.method == 'POST':
			word = request.form['word']
			if not word:
				flash('Type at least one word to search for!', "danger")
			else:
				language_country = request.form.get('langcountry')
				study = request.form.get('study')
				year = request.form.get('year')
				displaytagged = request.form.get('displaytagged')
				csv = request.form.get('csv') 
				multiple_words = request.form.get('multiplew')
				partial = request.form.get('partial')
				case_sensitive = request.form.get('casesensitive')
				regex_search = request.form.get('regex')

				if not regex_search:
					error_message = check_word_search_restrictions(word, multiple_words)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if case_sensitive and not partial:
						flash("Full word search is only case insensitive!", "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					error_message = check_regex_search_restrictions(word, multiple_words, partial)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())

				df = call_appropriated_word_search_method('requestid', word, case_sensitive, partial, language_country, year,  study, multiple_words, displaytagged, regex_search)
				
				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = results_to_csv(df)
						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results for the word "'+str(word)+'" in MCSQ Request Collection')
	
		return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/searchinstruction', methods=['GET', 'POST'])
@login_required
def search_instruction():
	"""
	Word search in the Instruction table.
	"""
	if current_user.is_authenticated:
		if request.method == 'POST':
			word = request.form['word']
			if not word:
				flash('Type at least one word to search for!', "warning")
			else:
				language_country = request.form.get('langcountry')
				study = request.form.get('study')
				year = request.form.get('year')
				displaytagged = request.form.get('displaytagged')
				csv = request.form.get('csv')
				multiple_words = request.form.get('multiplew')
				partial = request.form.get('partial')
				case_sensitive = request.form.get('casesensitive')
				regex_search = request.form.get('regex')

				if not regex_search:
					error_message = check_word_search_restrictions(word, multiple_words)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if case_sensitive and not partial:
						flash("Full word search is only case insensitive!", "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					error_message = check_regex_search_restrictions(word, multiple_words, partial)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())

				df = call_appropriated_word_search_method('instructionid', word, case_sensitive, partial, language_country, year,  study, multiple_words, displaytagged, regex_search)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = results_to_csv(df)
						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results for the word(s) "'+str(word)+'" in MCSQ Instruction Collection')
		return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/searchintroduction', methods=['GET', 'POST'])
@login_required
def search_introduction():
	"""
	Word search in the Introduction table.
	"""
	if current_user.is_authenticated:
		if request.method == 'POST':
			word = request.form['word']
			if not word:
				flash('Type at least one word to search for!', "warning")
			else:
				language_country = request.form.get('langcountry')
				study = request.form.get('study')
				year = request.form.get('year')
				displaytagged = request.form.get('displaytagged')
				csv = request.form.get('csv')
				multiple_words = request.form.get('multiplew')
				partial = request.form.get('partial')
				case_sensitive = request.form.get('casesensitive')
				regex_search = request.form.get('regex')

				if not regex_search:
					error_message = check_word_search_restrictions(word, multiple_words)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if case_sensitive and not partial:
						flash("Full word search is only case insensitive!", "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					error_message = check_regex_search_restrictions(word, multiple_words, partial)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())

				df = call_appropriated_word_search_method('introductionid', word, case_sensitive, partial, language_country, year,  study, multiple_words, displaytagged, regex_search)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = results_to_csv(df)
						return resp
					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results for the word '+str(word)+' in MCSQ Introduction Collection')
		return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')

@app.route('/searchresponse', methods=['GET', 'POST'])
@login_required
def search_response():
	"""
	Word search in the Response table.
	"""
	if current_user.is_authenticated:
		if request.method == 'POST':
			word = request.form['word']
			if not word:
				flash('Type at least one word to search for!', "warning")
			else:
				language_country = request.form.get('langcountry')
				study = request.form.get('study')
				year = request.form.get('year')
				displaytagged = request.form.get('displaytagged')
				csv = request.form.get('csv')
				multiple_words = request.form.get('multiplew')
				partial = request.form.get('partial')
				case_sensitive = request.form.get('casesensitive')
				regex_search = request.form.get('regex')

				if not regex_search:
					error_message = check_word_search_restrictions(word, multiple_words)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if case_sensitive and not partial:
						flash("Full word search is only case insensitive!", "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					error_message = check_regex_search_restrictions(word, multiple_words, partial)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())


				df = call_appropriated_word_search_method('responseid', word, case_sensitive, partial, language_country, year,  study, multiple_words, displaytagged, regex_search)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = results_to_csv(df)
						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results for the word '+str(word)+' in MCSQ Response Collection')
		return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/searchsurveyitem', methods=['GET', 'POST'])
@login_required
def search_survey_item():
	"""
	Word search in the Survey_item table (type independent).
	"""
	if current_user.is_authenticated:
		if request.method == 'POST':
			word = request.form['word']
			if not word:
				flash('Type at least one word to search for!', "warning")
			else:
				language_country = request.form.get('langcountry')
				study = request.form.get('study')
				year = request.form.get('year')
				displaytagged = request.form.get('displaytagged')
				csv = request.form.get('csv')
				multiple_words = request.form.get('multiplew')
				partial = request.form.get('partial')
				case_sensitive = request.form.get('casesensitive')
				regex_search = request.form.get('regex')

				if not regex_search:
					error_message = check_word_search_restrictions(word, multiple_words)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if case_sensitive and not partial:
						flash("Full word search is only case insensitive!", "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					error_message = check_regex_search_restrictions(word, multiple_words, partial)
					if error_message != '':
						flash(error_message, "danger")
						return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())

				df = call_appropriated_word_search_method('', word, case_sensitive, partial, language_country, year,  study, multiple_words, displaytagged, regex_search)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = results_to_csv(df)
						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results for the word '+str(word)+' in MCSQ')
		return render_template('word_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/searchalignment', methods=['GET', 'POST'])
@login_required
def search_alignment():
	"""
	Word search in the Alignemnt table.
	"""
	if current_user.is_authenticated:
		if request.method == 'POST':
			source_word = request.form['source_word']
			target_word = request.form['target_word']
			if not source_word and not target_word:
				flash('Type at least a word in source or target text to search for.', "warning")
				return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				study = request.form.get('study')
				year = request.form.get('year')
				langcountrytarget = request.form.get('langcountrytarget')
				displaytagged = request.form.get('displaytagged')
				csv = request.form.get('csv')
				multiple_words = request.form.get('multiplew')
				partial = request.form.get('partial')
				case_sensitive = request.form.get('casesensitive')
				regex_search = request.form.get('regex')

				if not regex_search:
					if source_word:
						error_message = check_word_search_restrictions(source_word, multiple_words)
						if error_message != '':
							flash(error_message, "danger")
							return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if target_word:
						error_message = check_word_search_restrictions(target_word, multiple_words)
						if error_message != '':
							flash(error_message, "danger")
							return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if case_sensitive and not partial:
						flash("Full word search is only case insensitive!", "danger")
						return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if source_word:
						error_message = check_regex_search_restrictions(source_word, multiple_words, partial)
						if error_message != '':
							flash(error_message, "danger")
							return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if target_word:
						error_message = check_regex_search_restrictions(target_word, multiple_words, partial)
						if error_message != '':
							flash(error_message, "danger")
							return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())

				df = call_appropriated_word_search_method('alignment', [source_word, target_word], case_sensitive, partial, langcountrytarget, year,  study, multiple_words, displaytagged, regex_search)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = results_to_csv(df)
						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results retrieved from MCSQ Alignment Collection')
				
		return render_template('alignment_search.html', langcountriestarget=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/comparebyword', methods=['GET', 'POST'])
@login_required
def compare_by_word():
	if current_user.is_authenticated:
		if request.method == 'POST':
			study = request.form.get('study')
			year = request.form.get('year')
			word = request.form['word']
			multiple_words = request.form.get('multiplew')
			partial = request.form.get('partial')
			csv = request.form.get('csv')


			if study == 'No filter' or year == 'No filter':
				flash('Study and year filters are obligatory for this type of search', "warning")
				return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if not word:
				flash('Type at least one word to search for!', "warning")
				return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				df_study_exists = verify_is_study_exists(year,study)

				if df_study_exists.empty:
					flash('There are no results in MCSQ for '+study+' studies in the year '+year, "warning")
					return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					langcountry1 = request.form.get('langcountry1')
					langcountry2 = request.form.get('langcountry2')
					langcountry3 = request.form.get('langcountry3')
					langcountry4 = request.form.get('langcountry4')
					langcountry5 = request.form.get('langcountry5')
					langcountry6 = request.form.get('langcountry6')
					langcountry7 = request.form.get('langcountry7')
					langcountry8 = request.form.get('langcountry8')

					list_all_country_lang = [langcountry1, langcountry2, langcountry3, langcountry4, langcountry5, langcountry6,
					langcountry7, langcountry8]
					country_lang_filters = [x for x in list_all_country_lang if x != 'No filter']

					if ';' in word and not multiple_words:
						flash("Semicolons are valid only for Multiple word search filter", "warning")
						return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if '!' in word or ':' in word or ',' in word or '.' in word or '&' in word or ')' in word or '(' in word or '/' in word or '\\' in word or '*' in word or '%' in word or '#' in word or '|' in word or '=' in word or '~' in word or 'º' in word or 'ª' in word:
						flash("Special characters are not allowed in the word search.", "warning")
						return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if ' ' in word or '\t' in word or '\n' in word:
						flash("Word search cannot contain spaces (or tabs, or line breaks). If you want to search for multiple words, mark the 'Multiple word search?' option and separate words by semicolon (e.g., read;this)", "warning")
						return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if '"' in word or '`' in word:
						flash("Quotes are not allowed in the word search.", "warning")
						return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					if word.count("'") % 2 != 0:
						flash("Please use double 's for escaping words that contain apostrophes (e.g., d''acord instead of d'acord).", "warning")
						return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())

					if len(country_lang_filters) < 2:
						flash('Select at least two country/language pairs to compare', "warning")
						return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					else:
						if request.form.get('casesensitive'):
							if not partial:
								flash("Full word search is only case insensitive!", "warning")
								return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
							else:
								results = []
								for country_lang in list_all_country_lang:
									df = compare_by_word_case_insensitive(word, country_lang, year, study, multiple_words, partial)
									if df.empty == False:
										results.append(df)
						else:
							results = []
							for country_lang in list_all_country_lang:
								df = compare_by_word_case_insensitive(word, country_lang, year, study, multiple_words, partial)
								if df.empty == False:
									results.append(df)
				
						if len(results)<2:
							flash('There are no valid results for this filter combination', "warning")
							return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
						else:
							results = manipulate_results_dataframe(results)
							if csv:
								resp = make_response(results.to_csv(sep='\t', encoding='utf-8-sig', index=False))
								resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
								resp.headers["Content-Type"] = "text/csv"

								return resp

							return render_template('display_table.html', maintitle='Search results',table=results.to_html(),title ='Comparing by word')					
		else:
			return render_template('compare_by_word.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/comparebyitemtype', methods=['GET', 'POST'])
@login_required
def compare_by_item_type():
	item_type_options = ['INTRODUCTION', 'INSTRUCTION', 'REQUEST', 'RESPONSE']
	if current_user.is_authenticated:
		if request.method == 'POST':
			study = request.form.get('study')
			year = request.form.get('year')
			csv = request.form.get('csv')

			if study == 'No filter' or year == 'No filter':
				flash('Study and year filters are obligatory for this type of search', "warning")
				return render_template('compare_by_type.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
			else:
				df_study_exists = verify_is_study_exists(year,study)

				if df_study_exists.empty:
					flash('There are no results in MCSQ for '+study+' studies in the year '+year, "warning")
					return render_template('compare_by_type.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
				else:
					langcountry1 = request.form.get('langcountry1')
					langcountry2 = request.form.get('langcountry2')
					langcountry3 = request.form.get('langcountry3')
					langcountry4 = request.form.get('langcountry4')
					langcountry5 = request.form.get('langcountry5')
					langcountry6 = request.form.get('langcountry6')
					langcountry7 = request.form.get('langcountry7')
					langcountry8 = request.form.get('langcountry8')

					item_type = request.form.get('item_type')

					list_all_country_lang = [langcountry1, langcountry2, langcountry3, langcountry4, langcountry5, langcountry6,
					langcountry7, langcountry8]

					country_lang_filters = [x for x in list_all_country_lang if x != 'No filter']

					if len(country_lang_filters) < 2:
						flash('Select at least two country/language pairs to compare', "warning")
						return render_template('compare_by_type.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
					else:
						results = []
						for country_lang in list_all_country_lang:		
							df = search_to_compare_by_item_type(country_lang,year,study,item_type)
							if df.empty == False:
								results.append(df)
						
						if len(results)<2:
							flash('There are no valid studies for one or more country/language pairs indicated in the filters', "warning")
							return render_template('compare_by_type.html', langcountries=get_unique_language_country(), item_types=item_type_options)
						else:
							results = manipulate_results_dataframe(results)
							if csv:
								resp = make_response(results.to_csv(sep='\t', encoding='utf-8-sig', index=False))
								resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
								resp.headers["Content-Type"] = "text/csv"

								return resp
		
							return render_template('display_table.html', maintitle='Search results',table=results.to_html(),title ='Comparing by item type')					
		else:
			return render_template('compare_by_type.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/comparewholequestionnaire', methods=['GET', 'POST'])
@login_required
def compare_whole():
	if current_user.is_authenticated:				
		if request.method == 'POST':
			study = request.form.get('study')
			year = request.form.get('year')
			csv = request.form.get('csv')

			if study == 'No filter' or year == 'No filter':
				flash('Study and year filters are obligatory for this type of search', "warning")
				return render_template('compare_whole.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				df_study_exists = verify_is_study_exists(year,study)

				if df_study_exists.empty:
					flash('There are no results in MCSQ for '+study+' studies in the year '+year, "warning")
					return render_template('compare_whole.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					langcountry1 = request.form.get('langcountry1')
					langcountry2 = request.form.get('langcountry2')
					langcountry3 = request.form.get('langcountry3')
					langcountry4 = request.form.get('langcountry4')
					langcountry5 = request.form.get('langcountry5')
					langcountry6 = request.form.get('langcountry6')
					langcountry7 = request.form.get('langcountry7')
					langcountry8 = request.form.get('langcountry8')

					list_all_country_lang = [langcountry1, langcountry2, langcountry3, langcountry4, langcountry5, langcountry6,
					langcountry7, langcountry8]
					country_lang_filters = [x for x in list_all_country_lang if x != 'No filter']

					if len(country_lang_filters) < 2:
						flash('Select at least two country/language pairs to compare', "warning")
						return render_template('compare_whole.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
					else:
						results = []
						for country_lang in list_all_country_lang:		
							df = search_to_compare_item_type_independent(country_lang,year,study)
							if df.empty == False:
								results.append(df)
						
						if len(results)<2:
							flash('There are no valid studies for one or more country/language pairs indicated in the filters', "warning")
							return render_template('compare_whole.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
						else:
							results = manipulate_results_dataframe(results)
							if csv:
								resp = make_response(results.to_csv(sep='\t', encoding='utf-8-sig', index=False))
								resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
								resp.headers["Content-Type"] = "text/csv"

								return resp
							return render_template('display_table.html', maintitle='Search results',table=results.to_html(),title ='Comparing whole questionnaires')	
		else:
			return render_template('compare_whole.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/wordfrequency', methods=['GET', 'POST'])
@login_required
def word_frequency():
	if current_user.is_authenticated:
		item_type_options = ['No filter', 'INTRODUCTION', 'INSTRUCTION', 'REQUEST', 'RESPONSE']
		if request.method == 'POST':
			word = request.form['word']
			if not word:
				flash('Type at least one word to search for!', "warning")
			else:
				language_country = request.form.get('langcountry')
				study = request.form.get('study')
				year = request.form.get('year')
				csv = request.form.get('csv')
				item_type = request.form.get('item_type')
				multiple_words = request.form.get('multiplew')
				combined_frequency = request.form.get('combined')

				if ';' in word and not combined_frequency and not multiple_words:
					flash("Semicolons are valid only for Multiple/Combined word filters.", "warning")
					return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
				if '!' in word or ':' in word or ',' in word or '.' in word or '&' in word or ')' in word or '(' in word or '/' in word or '\\' in word or '*' in word or '%' in word or '#' in word or '|' in word or '=' in word or '~' in word or 'º' in word or 'ª' in word:
					flash("Special characters are not allowed in the word search.", "warning")
					return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
				if combined_frequency and multiple_words:
					flash("Cannot use both Multiple/Combined word filters at the same time, one must be chosen.", "warning")
					return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
				if ' ' in word or '\t' in word or '\n' in word:
					flash("Word search cannot contain spaces (or tabs, or line breaks). If you want to search for multiple words, mark the 'Multiple word search?' option and separate words by semicolon (e.g., read;this)", "warning")
					return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
				if '"' in word or '`' in word:
					flash("Quotes are not allowed in the word search.", "warning")
					return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
				if word.count("'") % 2 != 0:
					flash("Please use double 's for escaping words that contain apostrophes (e.g., d''acord instead of d'acord).", "warning")
					return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)

				df = compute_word_frequency(word, language_country, year,  study, multiple_words, combined_frequency, item_type)
				
				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
				else:
					if csv:
						resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
						resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
						resp.headers["Content-Type"] = "text/csv"

						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Frequency of the word(s) "'+str(word)+'" in MCSQ')
		return render_template('word_frequency.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options)
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


def tokenize_texts(text_list):
	preprocessed_text = []
	tknzr = TweetTokenizer()
	for text in text_list:
		if isinstance(text, str):
			text = text.replace('-',' ')
			text = text.replace('\n',' ')
			text = text.replace('\t',' ')
			text = text.replace('—',' ')
			text = text.replace('…',' ')
			text = text.replace('‘',"'")
			text = text.replace('`',"'")
			text = text.replace('“',' ')
			text = text.replace('“',' ')

			text = text.rstrip()
			text = text.lstrip()
			
			tokens = tknzr.tokenize(text.lower())
			tokens_without_punct = []
			for token in tokens: 
				token = re.sub(r"[^\w\d'\s]+",'',token) 
				if token != '' and token != '«' and token != '»':
					tokens_without_punct.append(token)

			preprocessed_text.append(tokens_without_punct)


	return preprocessed_text

def tokenize_and_produce_collocations(text_list, measure, n_collocations):
	if measure == 'bigram':
		bigram_measures = nltk.collocations.BigramAssocMeasures()
		preprocessed_text = tokenize_texts(text_list)
		finder = BigramCollocationFinder.from_documents(preprocessed_text)
		collocations = finder.nbest(bigram_measures.raw_freq, int(n_collocations))
		ret = pd.DataFrame(columns=['word 1', 'word 2'])

		for item in collocations:
			data = {'word 1': item[0], 'word 2': item[1]}
			ret = ret.append(data, ignore_index=True)
	else:
		trigram_measures = nltk.collocations.TrigramAssocMeasures()
		preprocessed_text = tokenize_texts(text_list)
		finder = TrigramCollocationFinder.from_documents(preprocessed_text)
		collocations = finder.nbest(trigram_measures.raw_freq, int(n_collocations))
		ret = pd.DataFrame(columns=['word 1', 'word 2', 'word 3'])

		for item in collocations:
			data = {'word 1': item[0], 'word 2': item[1], 'word 3': item[2]}
			ret = ret.append(data, ignore_index=True)


	return ret

def tokenize_and_produce_collocations_comparison(text_list1, text_list2, measure, n_collocations):
	if measure == 'bigram':
		bigram_measures = nltk.collocations.BigramAssocMeasures()
		preprocessed_text1 = tokenize_texts(text_list1)
		finder = BigramCollocationFinder.from_documents(preprocessed_text1)
		collocations1 = finder.nbest(bigram_measures.raw_freq, int(n_collocations))

		preprocessed_text2 = tokenize_texts(text_list2)
		finder = BigramCollocationFinder.from_documents(preprocessed_text2)
		collocations2 = finder.nbest(bigram_measures.raw_freq, int(n_collocations))

		ret = pd.DataFrame(columns=['word 1 (first word)', 'word 2 (first word)', 'word 1 (second word)', 'word 2 (second word)'])

		for c1, c2 in zip(collocations1, collocations2):
			data = {'word 1 (first word)': c1[0], 'word 2 (first word)': c1[1], 'word 1 (second word)': c2[0], 'word 2 (second word)': c2[1]}
			ret = ret.append(data, ignore_index=True)
	else:
		trigram_measures = nltk.collocations.TrigramAssocMeasures()
		preprocessed_text1 = tokenize_texts(text_list1)
		finder = TrigramCollocationFinder.from_documents(preprocessed_text1)
		collocations1 = finder.nbest(trigram_measures.raw_freq, n_collocations)

		preprocessed_text2 = tokenize_texts(text_list2)
		finder = TrigramCollocationFinder.from_documents(preprocessed_text2)
		collocations2 = finder.nbest(trigram_measures.raw_freq, n_collocations)

		ret = pd.DataFrame(columns=['word 1 (first word)', 'word 2 (first word)', 'word 3 (first word)',
		 'word 1 (second word)', 'word 2 (second word)', 'word 3 (second word)'])

		for c1, c2 in zip(collocations1, collocations2):
			data = {'word 1 (first word)': c1[0], 'word 2 (first word)': c1[1],  'word 3 (first word)': c1[2],
			'word 1 (second word)': c2[0], 'word 2 (second word)': c2[1], 'word 3 (second word)': c2[2]}
			ret = ret.append(data, ignore_index=True)


	return ret

@app.route('/collocation', methods=['GET', 'POST'])
@login_required
def compute_collocation():
	if current_user.is_authenticated:
		n_collocation_options = [10, 20, 30]
		item_type_options = ['No filter', 'INTRODUCTION', 'INSTRUCTION', 'REQUEST', 'RESPONSE']
		if request.method == 'POST':
			word = request.form['word']
			n_collocations = request.form['n_collocations']
			if not word:
				flash('Type at least one word to search for!', "warning")
			if not n_collocations:
				flash('Select the number of collocations to be retrieved!', "warning")
			else:
				language_country = request.form.get('langcountry')
				study = request.form.get('study')
				year = request.form.get('year')
				item_type = request.form.get('item_type')
				csv = request.form.get('csv')
				trigram = request.form.get('trigram')

				if trigram:
					measure = 'trigram'
				else:
					measure = 'bigram'
				
				if ';' in word:
					flash("Semicolons are not valid characters in the collocation functionality", "warning")
					return render_template('word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if ' ' in word or '\t' in word or '\n' in word:
					flash("Word search cannot contain spaces (or tabs, or line breaks). If you want to search for multiple words, mark the 'Multiple word search?' option and separate words by semicolon (e.g., read;this)", "warning")
					return render_template('word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if '"' in word or '`' in word:
					flash("Quotes are not allowed in the word search.", "warning")
					return render_template('word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if '!' in word or ':' in word or ',' in word or '.' in word or '&' in word or ')' in word or '(' in word or '/' in word or '\\' in word or '*' in word or '%' in word or '#' in word or '|' in word or '=' in word or '~' in word or 'º' in word or 'ª' in word:
					flash("Special characters are not allowed in the word search.", "warning")
					return render_template('word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if word.count("'") % 2 != 0:
					flash("Please use double 's for escaping words that contain apostrophes (e.g., d''acord instead of d'acord).", "warning")
					return render_template('word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)

				
				text_list = compute_word_search_for_collocation(word, language_country, year, study, item_type)  
				
				if not text_list:
					flash("No results found for your search!", "warning")
					return render_template('word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				else:
					df = tokenize_and_produce_collocations(text_list, measure, n_collocations)
					if csv:
						resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
						resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
						resp.headers["Content-Type"] = "text/csv"

						return resp
					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Collocations for the word "'+str(word)+'" in MCSQ, ranked by frequency')
		return render_template('word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')




@app.route('/comparecollocation', methods=['GET', 'POST'])
@login_required
def compare_collocation():
	if current_user.is_authenticated:
		n_collocation_options = [10, 20, 30]
		item_type_options = ['No filter', 'INTRODUCTION', 'INSTRUCTION', 'REQUEST', 'RESPONSE']

		if request.method == 'POST':
			word1 = request.form['word1']
			word2 = request.form['word2']
			n_collocations = request.form['n_collocations']
			if not n_collocations:
				flash('Select the number of collocations to be retrieved!', "warning")
			if not word1 and not word2:
				flash('Type at least one word to search for!', "warning")
			elif not word1 or not word2:
				flash('Two words are necessary for this functionality.', "warning")
			elif word1 == word2:
				flash('The two words are equal. Use the single word collocation functionality for this end.', "warning")
			else:
				
				language_country = request.form.get('langcountry1')
				study = request.form.get('study1')
				year = request.form.get('year1')
				item_type = request.form.get('item_type1')
				language_country2 = request.form.get('langcountry2')
				study2 = request.form.get('study2')
				year2 = request.form.get('year2')
				item_type2 = request.form.get('item_type2')
				csv = request.form.get('csv')
				trigram = request.form.get('trigram')

				if trigram:
					measure = 'trigram'
				else:
					measure = 'bigram'

				
				if ';' in word1 or ';' in word2:
					flash("Semicolons are not valid characters in the collocation functionality", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if ' ' in word1 or '\t' in word1 or '\n' in word1 or ' ' in word2 or '\t' in word2 or '\n' in word2:
					flash("Word search cannot contain spaces (or tabs, or line breaks). If you want to search for multiple words, mark the 'Multiple word search?' option and separate words by semicolon (e.g., read;this)", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if '"' in word1 or '`' in word1 or '"' in word2 or '`' in word2:
					flash("Quotes are not allowed in the word search.", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if word1.count("'") % 2 != 0 or word2.count("'") % 2 != 0:
					flash("Please use double 's for escaping words that contain apostrophes (e.g., d''acord instead of d'acord).", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if '!' in word1 or ':' in word1 or ',' in word1 or '.' in word1 or '&' in word1 or ')' in word1 or '(' in word1 or '/' in word1 or '\\' in word1 or '*' in word1 or '%' in word1 or '#' in word1 or '|' in word1 or '=' in word1 or '~' in word1 or 'º' in word1 or 'ª' in word1:
					flash("Special characters are not allowed in the word search.", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				if '!' in word2 or ':' in word2 or ',' in word2 or '.' in word2 or '&' in word2 or ')' in word2 or '(' in word2 or '/' in word2 or '\\' in word2 or '*' in word2 or '%' in word2 or '#' in word2 or '|' in word2 or '=' in word2 or '~' in word2 or 'º' in word2 or 'ª' in word2:
					flash("Special characters are not allowed in the word search.", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
					
				text_list1 = compute_word_search_for_collocation(word1, language_country, year, study, item_type)  
				text_list2 = compute_word_search_for_collocation(word2, language_country2, year2, study2, item_type2) 
				
				if not text_list1 and not text_list2:
					flash("No results found for your search!", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				elif not text_list1:
					flash("No results found for the word "+word1+"!", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				elif not text_list2:
					flash("No results found for the word "+word2+"!", "warning")
					return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
				else:
					df = tokenize_and_produce_collocations_comparison(text_list1, text_list2, measure, n_collocations)
					if csv:
						resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
						resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
						resp.headers["Content-Type"] = "text/csv"

						return resp
					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Comparing collocations for the words "'+str(word1)+'" and "'+str(word2)+'" in MCSQ, ranked by frequency')
		return render_template('compare_word_collocation.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, n_collocations=n_collocation_options)
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/displayquestionnaire', methods=['GET', 'POST'])
@login_required
def display_questionnaire():
	if current_user.is_authenticated:
		if request.method == 'POST':
			language_country = request.form.get('langcountry')
			study = request.form.get('study')
			year = request.form.get('year')
			displaytagged = request.form.get('displaytagged')
			csv = request.form.get('csv')

			if language_country == 'No filter' and study == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if study == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language_country == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language_country == 'No filter' and study == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				df = get_questionnaire(language_country, year, study, displaytagged)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
						resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
						resp.headers["Content-Type"] = "text/csv"

						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results')
		return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/displayalignment', methods=['GET', 'POST'])
@login_required
def display_alignment():
	if current_user.is_authenticated:
		if request.method == 'POST':
			language_country = request.form.get('langcountry')
			study = request.form.get('study')
			year = request.form.get('year')
			displaytagged = request.form.get('displaytagged')
			csv = request.form.get('csv')

		
			if language_country == 'No filter' and study == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if study == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language_country == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language_country == 'No filter' and study == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least two filters from the following: language/country, study or year.", "warning")
				return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				df = get_alignment(language_country, year, study, displaytagged)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					if csv:
						resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
						resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
						resp.headers["Content-Type"] = "text/csv"

						return resp

					return render_template('display_table.html', maintitle='Search results',table=df.to_html(), title ='Search results')
		return render_template('display_data.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')



@app.route('/downloadquestionnaire', methods=['GET', 'POST'])
@login_required
def download_questionnaire():
	if current_user.is_authenticated:
		language_options = ['No filter', 'CAT', 'CZE', 'ENG', 'FRE', 'GER', 'NOR', 'POR', 'RUS', 'SPA']
		if request.method == 'POST':
			language_country = request.form.get('langcountry')
			language = request.form.get('lang')
			study = request.form.get('study')
			year = request.form.get('year')
			displaytagged = request.form.get('displaytagged')
			

			if language != 'No filter' and language_country != 'No filter':
				flash("Use only language filter or language/country filter, not both!", "warning")
				return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language == 'No filter' and language_country == 'No filter' and study == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least one filter from the following: language, language/country, study or year.", "warning")
				return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				if language != 'No filter':
					df = get_questionnaire(language, year, study, displaytagged)
				else:
					df = get_questionnaire(language_country, year, study, displaytagged)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
					resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
					resp.headers["Content-Type"] = "text/csv"

					return resp
		return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/downloadalignment', methods=['GET', 'POST'])
@login_required
def download_alignment():
	if current_user.is_authenticated:
		language_options = ['No filter', 'CAT', 'CZE', 'ENG', 'FRE', 'GER', 'NOR', 'POR', 'RUS', 'SPA']
		if request.method == 'POST':
			language_country = request.form.get('langcountry')
			language = request.form.get('lang')
			study = request.form.get('study')
			year = request.form.get('year')
			displaytagged = request.form.get('displaytagged')

			if language != 'No filter' and language_country != 'No filter':
				flash("Use only language filter or language/country filter, not both!", "warning")
				return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language == 'No filter' and language_country == 'No filter' and study == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least one filter from the following: language, language/country, study or year.", "warning")
				return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				if language != 'No filter':
					df = get_alignment(language, year, study, displaytagged)
				else:
					df = get_alignment(language_country, year, study, displaytagged)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
					resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
					resp.headers["Content-Type"] = "text/csv"

					return resp

		return render_template('download_data.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/createtmx', methods=['GET', 'POST'])
@login_required
def create_tmx():
	if current_user.is_authenticated:
		language_options = ['No filter', 'CAT', 'CZE', 'ENG', 'FRE', 'GER', 'NOR', 'POR', 'RUS', 'SPA']
		if request.method == 'POST':
			language_country = request.form.get('langcountry')
			language = request.form.get('lang')
			study = request.form.get('study')
			year = request.form.get('year')

			if language != 'No filter' and language_country != 'No filter':
				flash("Use only language filter or language/country filter, not both!", "warning")
				return render_template('create_tmx.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language == 'No filter' and language_country == 'No filter' and study == 'No filter' and year == 'No filter':
				flash("It is necessary to use at least one filter from the following: language, language/country, study or year.", "warning")
				return render_template('create_tmx.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			if language == 'No filter' and language_country == 'No filter':
				flash("Language or language/country filter is required to produce the TMX.", "warning")
				return render_template('create_tmx.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
			else:
				if language != 'No filter':
					df, target_lang = get_alignment_for_tmx(language, year, study)
				else:
					df, target_lang = get_alignment_for_tmx(language_country, year, study)

				if df.empty:
					flash("No results found for your search!", "warning")
					return render_template('create_tmx.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
				else:
					xml = createTMX(df, 'en', target_lang, adminlang='en', segtype='phrase', datatype='PlainText', oEncoding='UTF-8')
					# return Response(xml, mimetype='text/xml')

					resp = make_response(xml)
					resp.headers["Content-Disposition"] = "attachment; filename="+define_export_name(language_country, language, study, year)+".tmx"
					resp.headers["Content-Type"] = "text/xml"

					return resp

		return render_template('create_tmx.html', langs=language_options, langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')


@app.route('/postagsearch', methods=['GET', 'POST'])
@login_required
def search_by_pos_tags():
	item_type_options = ['No filter', 'INTRODUCTION', 'INSTRUCTION', 'REQUEST', 'RESPONSE']
	if current_user.is_authenticated:
		if request.method == 'POST':
			study = request.form.get('study')
			year = request.form.get('year')
			csv = request.form.get('csv')
			country_language = request.form.get('langcountry')
			partial = request.form.get('partial')

			if study == 'No filter' and country_language == 'No filter' and year == 'No filter':
				flash('Select at least one of the Study, Year or Language/country filters!', "warning")
				return render_template('pos_sequence_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, postags=get_pos_tag_options())
			else:
				postag1 = request.form.get('postag1')
				postag2 = request.form.get('postag2')
				postag3 = request.form.get('postag3')
				postag4 = request.form.get('postag4')
				postag5 = request.form.get('postag5')
				postag6 = request.form.get('postag6')
				postag7 = request.form.get('postag7')
				postag8 = request.form.get('postag8')
				postag9 = request.form.get('postag9')
				postag10 = request.form.get('postag10')

				item_type = request.form.get('item_type')

				list_all_tags = [postag1, postag2, postag3, postag4, postag5, postag6, postag7, postag8, postag9, postag10]

				tag_filters = [x for x in list_all_tags if x != 'No filter']

				if len(tag_filters) < 1:
					flash('Select at least one Part-of-Speech tag!', "warning")
					return render_template('pos_sequence_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, postags=get_pos_tag_options())
				else:
			
					df = search_by_pos_tag_sequence(tag_filters, country_language, year, study, item_type, partial)

					if df.empty:
						flash("No results found for your search!", "warning")
						return render_template('pos_sequence_search.html', langcountries=get_unique_language_country(),  studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, postags=get_pos_tag_options())
					else:
						if csv:
							resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
							resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
							resp.headers["Content-Type"] = "text/csv"

							return resp
						return render_template('display_table.html', maintitle='Search results',table=df.to_html(),title ='Searching for Part-of-Speech tag sequence')					
		else:
			return render_template('pos_sequence_search.html', langcountries=get_unique_language_country(), studies=get_study_options(), years=get_unique_year(), item_types=item_type_options, postags=get_pos_tag_options())
	else:
		return render_template('index.html',maintitle='MCSQ Interface', title='Welcome to the MCSQ Interface!')
