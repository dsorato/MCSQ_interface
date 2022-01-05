from . import db
from sqlalchemy import *
from flask_login import UserMixin

class User(db.Model,UserMixin):
	__tablename__ = 'users'
	__table_args__ = (PrimaryKeyConstraint('id'),)
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String)
	name = db.Column(db.String)
	password = db.Column(db.String)
	is_active = db.Column(db.Boolean)
	def __init__(self, email, name, password, is_active):
		self.email = email
		self.name = name
		self.password = password
		self.is_active

class Module(db.Model):
	__tablename__ = 'module'
	__table_args__ = (PrimaryKeyConstraint('moduleid'),)
	moduleid = db.Column(db.Integer, primary_key=True)
	module_name = db.Column(db.String)

	def __init__(self, moduleid, module_name):
		self.moduleid = moduleid
		self.module_name = module_name

class Survey(db.Model):
	__tablename__ = 'survey'
	__table_args__ = (PrimaryKeyConstraint('surveyid'), )
	surveyid = db.Column(db.String, primary_key=True)
	study = db.Column(db.String)
	wave_round = db.Column(db.Integer)
	year = db.Column(db.Integer)
	country_language = Column(db.String)

	def __init__(self, surveyid, study, wave_round, year,country_language):
		self.surveyid = surveyid
		self.study = study
		self.wave_round = wave_round
		self.year = year
		self.country_language = country_language

class Alignment(db.Model):
	__tablename__ = 'alignment'
	alignmentid = db.Column(db.Integer, primary_key=True)
	source_text = Column(db.String)
	target_text = Column(db.String)
	source_survey_itemid = Column(db.String)
	target_survey_itemid = Column(db.String)
	source_pos_tagged_text = db.Column(db.String)
	target_pos_tagged_text = db.Column(db.String)
	source_ner_tagged_text = db.Column(db.String)
	target_ner_tagged_text = db.Column(db.String)


	def __init__(self,source_text, target_text, source_survey_itemid,target_survey_itemid, 
		source_pos_tagged_text, target_pos_tagged_text, source_ner_tagged_text, target_ner_tagged_text):
		self.source_text = source_text
		self.target_text = target_text
		self.source_survey_itemid = source_survey_itemid
		self.target_survey_itemid = target_survey_itemid
		self.source_pos_tagged_text = source_pos_tagged_text
		self.target_pos_tagged_text = target_pos_tagged_text
		self.source_ner_tagged_text = source_ner_tagged_text
		self.target_ner_tagged_text = target_ner_tagged_text

class Instruction(db.Model):
	__tablename__ = 'instruction'

	instructionid = db.Column(db.Integer, primary_key=True)
	text = db.Column(db.String)
	pos_tagged_text = db.Column(db.String)
	ner_tagged_text = db.Column(db.String)

	def __init__(self, instructionid, text, pos_tagged_text, ner_tagged_text):
		self.instructionid = instructionid
		self.text = text
		self.pos_tagged_text = pos_tagged_text
		self.ner_tagged_text = ner_tagged_text

class Introduction(db.Model):
	__tablename__ = 'introduction'

	introductionid = db.Column(db.Integer, primary_key=True)
	text = db.Column(db.String)
	pos_tagged_text = db.Column(db.String)
	ner_tagged_text = db.Column(db.String)

	def __init__(self, introductionid, text, pos_tagged_text, ner_tagged_text):
		self.introductionid = introductionid
		self.text = text
		self.pos_tagged_text = pos_tagged_text
		self.ner_tagged_text = ner_tagged_text

class Request(db.Model):
	__tablename__ = 'request'

	requestid = db.Column(db.Integer, primary_key=True)
	text = db.Column(db.String)
	pos_tagged_text = db.Column(db.String)
	ner_tagged_text = db.Column(db.String)

	def __init__(self, requestid, text, pos_tagged_text, ner_tagged_text):
		self.requestid = requestid
		self.text = text
		self.pos_tagged_text = pos_tagged_text
		self.ner_tagged_text = ner_tagged_text

class Response(db.Model):
	__tablename__ = 'response'

	responseid = db.Column(db.Integer, primary_key=True)
	text = db.Column(db.String)
	item_value = db.Column(db.String)
	pos_tagged_text = db.Column(db.String)
	ner_tagged_text = db.Column(db.String)

	def __init__(self, responseid, text, item_value, pos_tagged_text, ner_tagged_text):
		self.responseid = responseid
		self.text = text
		self.item_value = item_value
		self.pos_tagged_text = pos_tagged_text
		self.ner_tagged_text = ner_tagged_text


class Survey_item(db.Model):
	__tablename__ = 'survey_item'
	__table_args__ = (PrimaryKeyConstraint('survey_itemid'), 
	ForeignKeyConstraint(['responseid'], ['response.responseid']),
	ForeignKeyConstraint(['surveyid'], ['survey.surveyid']),
	ForeignKeyConstraint(['moduleid'], ['module.moduleid']),
	ForeignKeyConstraint(['requestid'], ['request.requestid']),
	ForeignKeyConstraint(['instructionid'], ['instruction.instructionid']),
	ForeignKeyConstraint(['introductionid'], ['introduction.introductionid']),
	)


	survey_itemid = db.Column(db.String, primary_key=True)
	surveyid = db.Column(db.String)
	text = db.Column(db.String)
	item_value = db.Column(db.String)
	moduleid = db.Column(db.Integer)
	requestid = db.Column(db.Integer)
	responseid = db.Column(db.Integer)
	instructionid = db.Column(db.Integer)
	introductionid = db.Column(db.Integer)
	country_language = db.Column(db.String)
	item_is_source = db.Column(db.Boolean)
	item_name = db.Column(db.String)
	item_type = db.Column(db.String)
	pos_tagged_text = db.Column(db.String)
	ner_tagged_text = db.Column(db.String)



	def __init__(self, survey_itemid, surveyid,text, item_value, moduleid, requestid, responseid, instructionid,
		introductionid, country_language, item_is_source, item_name, item_type, pos_tagged_text, ner_tagged_text):
		self.survey_itemid = survey_itemid
		self.surveyid = surveyid
		self.text = text
		self.item_value = item_value
		self.moduleid = moduleid
		self.requestid = requestid
		self.responseid = responseid
		self.instructionid = instructionid
		self.introductionid = introductionid
		self.country_language = country_language
		self.item_is_source = item_is_source
		self.item_name = item_name
		self.item_type = item_type
		self.pos_tagged_text = pos_tagged_text
		self.ner_tagged_text = ner_tagged_text
