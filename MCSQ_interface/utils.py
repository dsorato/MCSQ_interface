import os
import requests
import operator
import re
import hashlib
import binascii
import pandas as pd
from flask import Flask, request, render_template, make_response,redirect, flash
from datetime import datetime as dt
from flask import current_app as app
import pandas as pd
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import *
from os.path import join, dirname
from flask_login import UserMixin, login_required, current_user, login_user,logout_user
from flask import Flask, request, render_template, make_response,redirect, flash
from .searches import *
from .routes import *

class UserLoginForm(FlaskForm):
	email = StringField('Email', validators=[DataRequired()])
	password = PasswordField('Password', validators=[DataRequired()])
	submit = SubmitField('Login')


class UserRegistryForm(FlaskForm):
	name = StringField('Name', validators=[DataRequired()])
	email = StringField('Email', validators=[DataRequired(), Length(min=5, max=35), Email()])
	password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=10, message='Passwords must be between 6 and 10 characters long'), 
		EqualTo('confirm_password', message='Passwords must match.')])
	confirm_password = PasswordField('Confirm your password', validators=[DataRequired()])
	submit = SubmitField('Register')


class RequestResetPasswordForm(FlaskForm):
	email = StringField('Email', validators=[DataRequired()])
	submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
	password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=10, message='Passwords must be between 6 and 10 characters long'), 
		EqualTo('confirm_password', message='Passwords must match.')])
	confirm_password = PasswordField('Confirm your password', validators=[DataRequired()])
	submit = SubmitField('Reset Password')

def check_if_parentheses_are_balanced(str):
	"""
	From https://stackoverflow.com/questions/38833819/python-program-to-check-matching-of-simple-parentheses
	Counts the number of opening (increments) and closing parentheses (decrements), if the resulting counter
	value is 0, then return True.
	
	Args:

		param1 str (string): regular expression being checked.
	
	Returns: 

		Boolean, True is balanced or False if unballanced.

	"""
	count = 0
	for i in str:
		if i == "(":
			count += 1
		elif i == ")":
			count -= 1
		if count < 0:
			return False
	return count == 0

def check_if_brackets_are_balanced(str):
	"""
	Same as check_if_parentheses_are_balanced(), but for brackets.
	Counts the number of opening (increments) and closing brackets (decrements), if the resulting counter
	value is 0, then return True.

	Args:

		param1 str (string): regular expression being checked.
	
	Returns: 

		Boolean, True is balanced or False if unballanced.

	"""
	count = 0
	for i in str:
		if i == "[":
			count += 1
		elif i == "]":
			count -= 1
		if count < 0:
			return False
	return count == 0

def check_regex_search_restrictions(word, multiple_words, partial):
	"""
	Checks if the regular expression informed by the user is valid. 
	
	Args:

		param1 word (string): the word (or multiple words) that the user wants to search for.
		param2 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param3 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).

	Returns: 
		
		An error message to be displayed to the user, if any restriction is broken.
	"""
	error_message = ''

	if multiple_words:
		error_message = "The multiple words option is only for searches that are not regex based. Use the appropriate regular expression for AND/OR operators."
	if partial:
		error_message = "The partial search option is only for searches that are not regex based. Use the appropriate regular expression for partial results."
	if '"' in word or '`' in word:
		error_message = "Quotes are not allowed in the search."
	if word.count("'") % 2 != 0:
		error_message = "Please use double 's for escaping words that contain apostrophes (e.g., d''acord instead of d'acord)."
	if check_if_parentheses_are_balanced(word) is False:
		error_message = "Unballanced parentheses. Check your regular expression."
	if check_if_brackets_are_balanced(word) is False:
		error_message = "Unballanced brackets. Check your regular expression."

	return error_message

def check_word_search_restrictions(word, multiple_words):
	"""
	Checks if the word (or words) informed by the user is valid. Word searches cannot contain spaces nor special symbols other than apostrophe.
	
	Args:

		param1 word (string): the word (or multiple words) that the user wants to search for.
		param2 multiple_words (string): indicates if the user is searching for a single words or multiple words.

	Returns: 
		
		An error message to be displayed to the user, if any restriction is broken.
	"""
	error_message = ''

	if ';' in word and not multiple_words:
		error_message = "Semicolons are valid only for Multiple word search filter."
	if ' ' in word or '\t' in word or '\n' in word:
		error_message = "Word search cannot contain spaces (or tabs, or line breaks). If you want to search for multiple words, mark the 'Multiple word search?' option and separate words by semicolon (e.g., read;this)"
	if '"' in word or '`' in word:
		error_message = "Quotes are not allowed in the word search."
	if '^' in word or '!' in word or ':' in word or ',' in word or '.' in word or '&' in word or ']' in word or '[' in word or ')' in word or '(' in word or '/' in word or '\\' in word or '*' in word or '%' in word or '#' in word or '|' in word or '=' in word or '~' in word or 'º' in word or 'ª' in word:
		error_message = "Special characters are not allowed in the word search."
	if word.count("'") % 2 != 0:
		error_message = "Please use double 's for escaping words that contain apostrophes (e.g., d''acord instead of d'acord)."


	return error_message



def call_appropriated_word_search_method(tableid, word, case_sensitive, partial, language_country, year,  study, multiple_words, displaytagged, regex):
	"""
	Calls the appropriated word search type, depending if the search is item type dependent and if user wants a case sensitive search or not.
	
	Args:
		param1 tableid (string): indicates from which table the results should be retrieved.
		param2 word (string): the word (or multiple words) that the user wants to search for.
		param3 case_sensitive (string): indicates if the word search is case sensitive.
		param4 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).
		param5 language_country (string): country and language questionnaire metadata.
		param6 year (string): year metadata. Indicates in which year a given study was released.
		param7 study (string): study questionnaire metadata.
		param8 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param9 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations or not.
		param10 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		A pandas dataframe containing the results of the search query, to be displayed to or downloaded by the user.
	"""
	if tableid == '':
		if case_sensitive:
			df = case_sensitive_search_item_type_independent(word, language_country, year,  study, multiple_words, displaytagged, regex)
		else:
			df = case_insensitive_search_item_type_independent(word, language_country, year, study, multiple_words, partial, displaytagged, regex)
	elif tableid == 'alignment':
		source_word = word[0]
		target_word = word[1]
		df = alignment_search(source_word, target_word, language_country, year, study, multiple_words, partial, case_sensitive, displaytagged, regex)
	else:
		if case_sensitive:
			df = generic_case_sensitive_search(tableid, word, language_country, year,  study, multiple_words, displaytagged, regex)
		else:
			df = generic_case_insensitive_search(tableid, word, language_country, year, study, multiple_words, partial, displaytagged, regex)
	
	return df

def results_to_csv(df):
	"""
	Outputs the results derived from the search query as CSV file with tab separators.
	
	Args:
		param1 df (dataframe): a pandas dataframe containing the results of the search query, to be displayed to or downloaded by the user.

	Returns: 
		
		An attachment response (text/csv type).
		
	"""
	resp = make_response(df.to_csv(sep='\t', encoding='utf-8-sig', index=False))
	resp.headers["Content-Disposition"] = "attachment; filename=results.tsv"
	resp.headers["Content-Type"] = "text/csv"

	return resp

def hash_password(password): 
	"""
	Hashes the password informed by the user, so it is not visible in the users table.
	Args:
		param1 password (string): password informed by new user.
	
	Returns: 
		hashed password.
	"""
	salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii') 
	pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'),salt, 100000)
	pwdhash = binascii.hexlify(pwdhash)

	return (salt + pwdhash).decode('ascii')


def verify_password(stored_password, provided_password):
	"""
	Verifies if the password informed by the user is equal to the password stored in the users table.

	Args:
		param1 stored_password: password stored in users table (hashed)
		param2 provided_password: password informed by new user.
	
	Returns: 
		boolean value indicating if the passwords are equal or not.
	"""
	salt = stored_password[:64]
	stored_password = stored_password[64:]
	pwdhash = hashlib.pbkdf2_hmac('sha512', provided_password.encode('utf-8'), salt.encode('ascii'),100000)
	pwdhash = binascii.hexlify(pwdhash).decode('ascii')
	
	return pwdhash == stored_password


def get_item_name_intersection(dataframes):
	unique_item_names = []
	for df in dataframes:
		item_names = df.item_name.unique()
		item_names = [x.lower() for x in item_names]
		unique_item_names.append(set(item_names))

	intersection_item_names = set.intersection(*unique_item_names)
	return sorted(intersection_item_names)

def label_item_order(row):
	return int(row['survey_itemid'].split('_')[-1])

def manipulate_results_dataframe(dataframes):
	updated_dfs = []

	unique_item_names = []
	for df in dataframes:
		item_names = df.item_name.unique()
		item_names = [x.lower() for x in item_names]
		unique_item_names.append(set(item_names))

	intersection_item_names = set.intersection(*unique_item_names)
	intersection_item_names = sorted(intersection_item_names)

	dfs = []
	for item_name in intersection_item_names:

		for i, df in enumerate(dataframes):
			df_by_item_name= df[df['item_name'].str.lower()==item_name.lower()]
			fn = lambda row: label_item_order(row)
			col = df_by_item_name.apply(fn, axis=1)
			df_by_item_name = df_by_item_name.assign(item_order=col.values)
			df_by_item_name = df_by_item_name.sort_values(by='item_order')
			del df_by_item_name['item_order']

			if i==0:
				df_partial = df_by_item_name
			else:
				df_partial =  pd.concat([df_partial.reset_index(drop=True), df_by_item_name.reset_index(drop=True)], axis = 1)


		
		dfs.append(df_partial)

	result = pd.concat(dfs)


	return result

def define_export_name(language_country, language, study, year):
	"""
	Defines the name of the export, based on the filters that the user applied.
	Args:
		param1 language_country (string): language and country metadata. Language codes follow the ISO 639- 2/B three-digit standard and country codes follow the ISO 3166 Alpha-2 two digit standard.
		param2 language (string): language metadata. Language codes follow the ISO 639- 2/B three-digit standard.
		param3 study (string): study metadata. Can be ESS, EVS, SHARE or WIS.
		param4 year (string): year metadata. All possible years are shown, but dataset availability depends on the study.

	Returns: 
		export name (string).
	"""
	if language != 'No filter':
		name = language
		if study != 'No filter':
			name = name +'_'+study
		if year != 'No filter':
			name = name +'_'+year

	elif language_country != 'No filter':
		name = language_country
		if study != 'No filter':
			name = name +'_'+study
		if year != 'No filter':
			name = name +'_'+year

	return name