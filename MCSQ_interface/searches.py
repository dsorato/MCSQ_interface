import os
import requests
import operator
import re
import pandas as pd
from flask import Flask, render_template, request,flash
from .models import db, Survey, Module, Alignment, Survey_item, Instruction, Introduction, Request, Response, User

def get_unique_language_country():
	"""
	Gets the unique language-country combinations from the MCSQ to be shown in the interface dropdown menus.
	Also adds 'No filter' as a possible option, in case the user does not want to use this metadata as a filter.

	Returns: 

		the language-country filtering options (list of strings).
	"""
	options = []
	results = db.session.execute("select distinct country_language from survey")
	for res in results:
		options.append(res[0])
	db.session.close()
	db.session.remove()

	options = sorted(options)
	options.insert(0, 'No filter')

	return options

def get_unique_year():
	"""
	Gets the unique years from the MCSQ to be shown in the interface dropdown menus.
	Also adds 'No filter' as a possible option, in case the user does not want to use this metadata as a filter.
		
	Returns: 

		the year filtering options (list of strings).
	"""
	options = []
	results = db.session.execute("select distinct year from survey")
	for res in results:
		options.append(str(res[0]))
	db.session.close()
	db.session.remove()

	options = sorted(options)
	options.insert(0, 'No filter')

	return options

def get_study_options():
	"""
	Returns a fixed list of study options to be shown in the interface dropdown menus.
	Also adds 'No filter' as a possible option, in case the user does not want to use this metadata as a filter.
	
	Returns: 

		the study filtering options (list of strings).
	"""
	options = ['No filter', 'ESS', 'EVS', 'SHARE', 'WIS']
	return options

def get_pos_tag_options():
	"""
	Returns a fixed list of Part-of-Speech tag options (Universal Dependencies Tagset) to be shown in the POS tag sequence search.
	Also adds 'No filter' as a possible option.

	Returns: 

		the POS tag filtering options (list of strings).
	"""
	options = ['No filter', 'ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ', 
	'PART', 'PROPN', 'PRON', 'PUNCT', 'NOUN', 'NUM', 'SCONJ', 'SYM', 'VERB', 'X']
	return options

def prepare_words_for_multiple_word_search(word):
	"""
	This method is used just if the 'Multiple word search' option is selected in the interface.
	It manipulates the portion of the query string concerning the words the user wants to search.
	In the interface, the user inputs each of the words separated by a semi-colon (;).
	This method checks if a word is not a blank space, then adds the '%' symbol where applicable. 

	Returns: 

		The manipulated portion , in a syntax appropriate for queries in PostgreSQL.
	"""
	words = word.split(';')
	clean_w = []
	for w in words:
		if w!='' and w!=' ':
			clean_w.append(w)
	multiple_words = '%'.join(clean_w)
	multiple_words = '%'+multiple_words+'%'

	return multiple_words

def adapt_for_search_type_case_sensitive(regex, word):
	"""
	Uses the correct operator for the specified case sensitive search.
	If common word search, uses 'like' operator, otherwise uses '~' operator
	
	Args:
		param1 regex (string): indicates if the user is doing a regex based search.
		param2 word (string): the word (or multiple words) that the user wants to search for.
		
	Returns: 

		A piece of the search query (string) using the correct operator.
	"""
	if regex:
		return " ~ \'"+str(word)+"\'"
	else: 
		return "like \'%"+str(word)+"%\'"

def adapt_for_search_type_case_insensitive(regex, word, partial):
	"""
	Uses the correct operator for the specified case insensitive search.
	If common word search allowing partial results, uses 'ilike' operator,
	if partial results are not allowed, use to_tsvector() and to_tsquery,
	otherwise uses '~*' operator.
	
	Args:
		param1 regex (string): indicates if the user is doing a regex based search.
		param2 word (string): the word (or multiple words) that the user wants to search for.
		param3 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).
		
	Returns: 

		A piece of the search query (string) using the correct operator.
	"""
	if regex:
		return "text ~* \'"+str(word)+"\'"
	elif not regex and partial:
		return "ilike \'%"+str(word)+"%\'"
	elif not regex and not partial:
		return "to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\')"


def generic_case_sensitive_search(tableid, word, country_language, year, study, multiplew, displaytagged, regex):
	"""
	This is a generic case sensitive word search that works for all tables containing questionnaire text, except for the Alignment and Survey item, which have their own methods.
	The search query is built depending on the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.
	
	Args:
		param1 tableid (string): indicates from which table the results should be retrieved.
		param2 word (string): the word (or multiple words) that the user wants to search for.
		param3 country_language (string): country and language questionnaire metadata.
		param4 year (string): year metadata. Indicates in which year a given study was released.
		param5 study (string): study questionnaire metadata.
		param6 multiplew (string): indicates if the user is searching for a single words or multiple words.
		param7 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations or not.
		param8 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""

	if multiplew:
		word = prepare_words_for_multiple_word_search(word)

	if study == 'SHARE':
		study = 'SHA'

	if displaytagged:
		tagged_column = 'pos_tagged_text, ner_tagged_text, '
	else:
		tagged_column = ''

	operator = adapt_for_search_type_case_sensitive(regex, word)

	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\' and "+tableid+" is not null")	
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%"+str(country_language)+"%\' and "+tableid+" is not null")	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\' and "+tableid+" is not null")
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\' and "+tableid+" is not null")
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%\' and "+tableid+" is not null")	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\' and "+tableid+" is not null")	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%_"+str(year)+"_%\' and "+tableid+" is not null")
	#country_language=N, study=N, year=N
	else:
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and "+tableid+" is not null")

	lst = []
	if displaytagged:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1],  'POS Tagged Text':result[2], 'NER Tagged Text':result[3], 
			'item_name': result[4], 'country_language': result[5], 'moduleid': result[6]}
			lst.append(item)
	else:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
			'country_language': result[3], 'moduleid': result[4]}
			lst.append(item)
	
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df



def generic_case_insensitive_search(tableid, word, country_language, year, study, multiple_words, partial, displaytagged, regex):
	"""
	This is a generic case insensitive word search that works for all tables containing questionnaire text, except for the Alignment and Survey item, which have their own methods.
	The search query is built depending on the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.

	Args:
		param1 tableid (string): indicates from which table the results should be retrieved.
		param2 word (string): the word (or multiple words) that the user wants to search for.
		param3 country_language (string): country and language questionnaire metadata.
		param4 year (string): year metadata. Indicates in which year a given study was released.
		param5 study (string): study questionnaire metadata.
		param6 multiplew (string): indicates if the user is searching for a single words or multiple words.
		param7 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).
		param8 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations or not.
		param9 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if multiple_words and partial:
		word = prepare_words_for_multiple_word_search(word)
	elif multiple_words and not partial:
		words = word.split(';')
		clean_w = []
		for w in words:
			if w!='' and w!=' ':
				clean_w.append(w)
		word = ' & '.join(clean_w)

	if study == 'SHARE':
		study = 'SHA'

	if displaytagged:
		tagged_column = 'pos_tagged_text, ner_tagged_text, '
	else:
		tagged_column = ''

	operator = adapt_for_search_type_case_insensitive(regex, word, partial)

	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text  "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\' and "+tableid+" is not null")	
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\' and "+tableid+" is not null")
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%"+str(country_language)+"%\' and "+tableid+" is not null")	
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'%"+str(country_language)+"%\' and "+tableid+" is not null")	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text  "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\' and "+tableid+" is not null")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\' and "+tableid+" is not null")
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text  "+operator+" and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\' and "+tableid+" is not null")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\' and "+tableid+" is not null")
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text  "+operator+" and survey_itemid ilike \'"+str(study)+"%\' and "+tableid+" is not null")	
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%\' and "+tableid+" is not null")	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text  "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\' and "+tableid+" is not null")	
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\' and "+tableid+" is not null")	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text  "+operator+" and survey_itemid ilike \'%_"+str(year)+"_%\' and "+tableid+" is not null")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'%"+str(year)+"%\' and "+tableid+" is not null")
	#country_language=N, study=N, year=N
	else:
		if partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where text  "+operator+" and "+tableid+" is not null")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where "+operator+" and "+tableid+" is not null")


	lst = []
	if displaytagged:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1],  'POS Tagged Text':result[2], 'NER Tagged Text':result[3], 
			'item_name': result[4], 'country_language': result[5], 'moduleid': result[6]}
			lst.append(item)
	else:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
			'country_language': result[3], 'moduleid': result[4]}
			lst.append(item)
	
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df



def customize_query_sensitive(source_word, target_word, regex):
	"""
	Customizes the query for a case sensitive search in the Alignment table.
	Since the user can choose to search for a source word, for a target word, or both, this method constructs 
	the portion of the query concerning the source and target words according to which words the user inputed in the form.
	
	Args:
		param1 source_word (string): the word (or multiple words) that the user wants to search for in the source text.
		param2 target_word (string): the word (or multiple words) that the user wants to search for in the target text.
		param3 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		partial search query (string), that refers to the words inputed by the user.
	"""
	if regex:
		if source_word and target_word:
			return "source_text ~ \'"+str(source_word)+"\' and target_text ~ \'"+str(target_word)+"\' "
		elif source_word and not target_word:
			return "source_text ~ \'"+str(source_word)+"\' "
		elif target_word  and not source_word:
			return "target_text ~ \'"+str(target_word)+"\' "
	else:
		if source_word and target_word:
			return "source_text like \'%"+str(source_word)+"%\' and target_text like \'%"+str(target_word)+"%\' "
		elif source_word and not target_word:
			return "source_text like \'%"+str(source_word)+"%\' "
		elif target_word  and not source_word:
			return "target_text like \'%"+str(target_word)+"%\' "




def customize_query_insensitive(partial, source_word, target_word, regex):
	"""
	Customizes the query for a case insensitive search in the Alignment table.
	Since the user can choose to search for a source word, for a target word, or both, this method constructs 
	the portion of the query concerning the source and target words according to which words the user inputed in the form.
	
	Args:
		param1 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).
		param2 source_word (string): the word (or multiple words) that the user wants to search for in the source text.
		param3 target_word (string): the word (or multiple words) that the user wants to search for in the target text.
		param4 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		A piece of the search query (string), that refers to the words inputed by the user.
	"""
	if regex:
		if source_word and target_word:
			return "source_text ~* \'"+str(source_word)+"\' and target_text ~* \'"+str(target_word)+"\' "
		elif source_word and not target_word:
			return "source_text ~* \'"+str(source_word)+"\' "
		elif target_word  and not source_word:
			return "target_text ~* \'"+str(target_word)+"\' "
	if partial and not regex:
		if source_word and target_word:
			return "source_text ilike \'%"+str(source_word)+"%\' and target_text ilike \'%"+str(target_word)+"%\' "
		elif source_word and not target_word:
			return "source_text ilike \'%"+str(source_word)+"%\' "
		elif target_word  and not source_word:
			return "target_text ilike \'%"+str(target_word)+"%\' "
	if not partial and not regex:
		if source_word and target_word:
			return "to_tsvector(source_text) @@ to_tsquery(\'"+str(source_word)+"\') and to_tsvector(target_text) @@ to_tsquery(\'"+str(target_word)+"\') "
		elif source_word and not target_word:
			return "to_tsvector(source_text) @@ to_tsquery(\'"+str(source_word)+"\') "
		elif target_word  and not source_word:
			return "to_tsvector(target_text) @@ to_tsquery(\'"+str(target_word)+"\') "

def alignment_search(source_word, target_word, langcountrytarget, year, study, multiple_words, partial, case_sensitive, displaytagged, regex):
	"""
	Implements a word search in the Alignment table. The search query is built depending on the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.
	
	Args:
		param1 source_word (string): the word (or multiple words) that the user wants to search for in the source text.
		param2 target_word (string): the word (or multiple words) that the user wants to search for in the target text.
		param3 langcountrytarget (string): country and language metadata of the target questionnaire.
		param4 year (string): year metadata. Indicates in which year a given study was released.
		param5 study (string): study questionnaire metadata.
		param6 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param7 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).
		param8 case_sensitive (string): indicates if the user wants to do a case sensitive word search.
		param9 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations.
		param10 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if multiple_words and partial:
		if source_word:
			source_word = prepare_words_for_multiple_word_search(source_word)
		if target_word:
			target_word = prepare_words_for_multiple_word_search(target_word)
	elif multiple_words and not partial:
		if source_word:
			words = source_word.split(';')
			clean_w = []
			for w in words:
				if w!='' and w!=' ':
					clean_w.append(w)
			source_word = ' & '.join(clean_w)
		if target_word:
			words = target_word.split(';')
			clean_w = []
			for w in words:
				if w!='' and w!=' ':
					clean_w.append(w)
			target_word = ' & '.join(clean_w)

	if study == 'SHARE':
		study = 'SHA'	

	if displaytagged:
		tagged_column = ', source_pos_tagged_text, target_pos_tagged_text, source_ner_tagged_text, target_ner_tagged_text '
	else:
		tagged_column = ''

	if case_sensitive:
		custom_query = customize_query_sensitive(source_word, target_word, regex)
	else:
		custom_query = customize_query_insensitive(partial, source_word, target_word, regex)

	#study=Y, year=Y, langcountrytarget=Y
	if study != 'No filter' and year != 'No filter' and langcountrytarget != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query+" and source_survey_itemid ilike  \'"+str(study)+"%"+str(year)+"%\' and target_survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(langcountrytarget)+"%\'")	
	#study=Y, year=N, langcountrytarget=N
	elif study != 'No filter' and year == 'No filter' and langcountrytarget == 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query+" and source_survey_itemid ilike  \'"+str(study)+"%\' and target_survey_itemid ilike \'"+str(study)+"%\'")	
	#study=N, year=Y, langcountrytarget=N
	elif study == 'No filter' and year != 'No filter' and langcountrytarget == 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query+" and source_survey_itemid ilike  \'%_"+str(year)+"_%\' and target_survey_itemid ilike \'%_"+str(year)+"_%\'")	
	#study=N, year=N, langcountrytarget=Y
	elif study == 'No filter' and year == 'No filter' and langcountrytarget != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query+" and target_survey_itemid ilike \'%_"+str(langcountrytarget)+"_%\'")	
	#study=Y, year=Y, langcountrytarget=N
	elif study != 'No filter' and year != 'No filter' and langcountrytarget == 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query+" and source_survey_itemid ilike  \'"+str(study)+"%"+str(year)+"%\' and target_survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
	#study=Y, year=N, langcountrytarget=Y
	elif study != 'No filter' and year == 'No filter' and langcountrytarget != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query+" and source_survey_itemid ilike  \'"+str(study)+"%\' and target_survey_itemid ilike \'"+str(study)+"%"+str(langcountrytarget)+"%\'")	
	#study=N, year=Y, langcountrytarget=Y
	elif study == 'No filter' and year != 'No filter' and langcountrytarget != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query+" and source_survey_itemid ilike  \'%_"+str(year)+"_%\' and target_survey_itemid ilike  \'%_"+str(year)+"%"+str(langcountrytarget)+"%\'")	
	#study=N, year=N, langcountrytarget=N
	else:
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text, target_text  "+tagged_column+" from alignment where "+custom_query)	

	lst = []
	if displaytagged:
		for result in results:
			item = {'source_survey_itemid': result[0], 'target_survey_itemid':result[1],  
			'Source Text': result[2], 'Target Text': result[3], 'POS Tagged Source Text': result[4], 'POS Tagged Target Text': result[5], 
			'NER Tagged Source Text': result[6], 'NER Tagged Target Text': result[7]}
			lst.append(item)
	else:
		for result in results:
			item = {'source_survey_itemid': result[0], 'target_survey_itemid':result[1],  
			'Source Text': result[2], 'Target Text': result[3]}
			lst.append(item)

	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df


def case_sensitive_search_item_type_independent(word, country_language, year, study, multiple_words, displaytagged, regex):
	"""
	This is a sensitive word search for the Survey item table.
	Implements a word search in the Survey Item table. The search query is built depending on the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.
	
	Args:
		param1 word (string): the word (or multiple words) that the user wants to search for.
		param2 country_language (string): country and language questionnaire metadata.
		param3 year (string): year metadata. Indicates in which year a given study was released.
		param4 study (string): study questionnaire metadata.
		param5 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param6 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations or not.
		param7 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if multiple_words:
		word = prepare_words_for_multiple_word_search(word)

	if study == 'SHARE':
		study = 'SHA'

	if displaytagged:
		tagged_column = 'pos_tagged_text, ner_tagged_text, '
	else:
		tagged_column = ''

	operator = adapt_for_search_type_case_sensitive(regex, word) 

	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")	
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%"+str(country_language)+"%\'")	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%\'")	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike  \'%_"+str(year)+"_%\'")
	#country_language=N, study=N, year=N
	else:
		results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+"")


	lst = []
	if displaytagged:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1], 'POS Tagged Text':result[2], 'NER Tagged Text':result[3], 
			'item_name': result[4], 'item_type': result[5], 'country_language': result[6], 'moduleid': result[7]}
			lst.append(item)
	else:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
			'item_type': result[3], 'country_language': result[4], 'moduleid': result[5]}
			lst.append(item)
	
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df


def case_insensitive_search_item_type_independent(word, country_language, year, study, multiple_words, partial, displaytagged, regex):
	"""
	This is a insensitive word search for the Survey item table.
	Implements a word search in the Survey Item table. The search query is built depending on the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.
	
	Args:
		param1 word (string): the word (or multiple words) that the user wants to search for.
		param2 country_language (string): country and language questionnaire metadata.
		param3 year (string): year metadata. Indicates in which year a given study was released.
		param4 study (string): study questionnaire metadata.
		param5 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param6 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).
		param7 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations or not.
		param8 regex (string): indicates if the user is doing a regex based search.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if multiple_words and partial:
		word = prepare_words_for_multiple_word_search(word)
	elif multiple_words and not partial:
		words = word.split(';')
		clean_w = []
		for w in words:
			if w!='' and w!=' ':
				clean_w.append(w)
		word = ' & '.join(clean_w)

	if study == 'SHARE':
		study = 'SHA'

	if displaytagged:
		tagged_column = 'pos_tagged_text, ner_tagged_text, '
	else:
		tagged_column = ''

	operator = adapt_for_search_type_case_insensitive(regex, word, partial)
	
	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		if not partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")	
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		if not partial:
			results = db.session.execute("select survey_itemid, text,"+tagged_column+"  item_name, item_type, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'%"+str(country_language)+"%\'")	
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%"+str(country_language)+"%\'")	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		if not partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		if not partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		if not partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%\'")	
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%\'")	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		if not partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		if not partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where "+operator+" and survey_itemid ilike \'%"+str(year)+"%\'")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+" and survey_itemid ilike \'%_"+str(year)+"_%\'")
	#country_language=N, study=N, year=N
	else:
		if not partial:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where "+operator+"")
		else:
			results = db.session.execute("select survey_itemid, text, "+tagged_column+" item_name, item_type, country_language, moduleid from survey_item where text "+operator+"")


	lst = []
	if displaytagged:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1], 'POS Tagged Text':result[2],'NER Tagged Text':result[3],
			'item_name': result[4], 'item_type': result[5], 'country_language': result[6], 'moduleid': result[7]}
			lst.append(item)
	else:
		for result in results:
			item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
			'item_type': result[3], 'country_language': result[4], 'moduleid': result[5]}
			lst.append(item)
	
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df

def compute_word_frequency(word, country_language, year, study, multiple_words, combined, item_type):
	"""
	This is a insensitive word count search to compute the frequency of either a word or a set of words.
	In the case of multiple words, the frequency can be computed individually for each word, or the combined frequency for all words.
	The search query is built depending on the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.
	
	Args:
		param1 word (string): the word (or multiple words) that the user wants to search for.
		param2 country_language (string): country and language questionnaire metadata.
		param3 year (string): year metadata filter. Indicates in which year a given study was released.
		param4 study (string): study questionnaire metadata.
		param5 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param6 combined (string): just for multiple words. Indicates if the frequency to be computed is combined.
		param7 item_type (string): item type metadata filter. Can be INTRODUCTION, INSTRUCTION, REQUEST or RESPONSE.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if study == 'SHARE':
		study = 'SHA'

	lst = []

	if multiple_words:
		words = word.split(';')
		for word in words:
			if country_language != 'No filter' and study != 'No filter' and year != 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")
			elif country_language != 'No filter' and study == 'No filter' and year == 'No filter' and item_type == 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(country_language)+"%\'")	
			elif country_language == 'No filter' and study != 'No filter' and year == 'No filter' and item_type == 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%\'")
			elif country_language == 'No filter' and study == 'No filter' and year != 'No filter' and item_type == 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(year)+"%\'")
			elif country_language == 'No filter' and study == 'No filter' and year == 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\'")
			elif country_language != 'No filter' and study != 'No filter' and year == 'No filter' and item_type == 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
			elif country_language != 'No filter' and study == 'No filter' and year != 'No filter' and item_type == 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
			elif country_language != 'No filter' and study == 'No filter' and year == 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'%"+str(country_language)+"%\'")	
			elif country_language != 'No filter' and study != 'No filter' and year != 'No filter' and item_type == 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")
			elif country_language != 'No filter' and study != 'No filter' and year == 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
			elif country_language != 'No filter' and study == 'No filter' and year != 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
			elif country_language == 'No filter' and study != 'No filter' and year != 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
			elif country_language == 'No filter' and study != 'No filter' and year != 'No filter' and item_type == 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
			elif country_language == 'No filter' and study != 'No filter' and year == 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%\'")
			elif country_language == 'No filter' and study == 'No filter' and year != 'No filter' and item_type != 'No filter':
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'%"+str(year)+"%\'")
			else:
				results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\')")
		
			for result in results:
				item = {'Word': word, 'Frequency':result[0]}
				lst.append(item)
	else:
		if country_language != 'No filter' and study != 'No filter' and year != 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")
		elif country_language != 'No filter' and study == 'No filter' and year == 'No filter' and item_type == 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(country_language)+"%\'")	
		elif country_language == 'No filter' and study != 'No filter' and year == 'No filter' and item_type == 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%\'")
		elif country_language == 'No filter' and study == 'No filter' and year != 'No filter' and item_type == 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(year)+"%\'")
		elif country_language == 'No filter' and study == 'No filter' and year == 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\'")
		elif country_language != 'No filter' and study != 'No filter' and year == 'No filter' and item_type == 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
		elif country_language != 'No filter' and study == 'No filter' and year != 'No filter' and item_type == 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
		elif country_language != 'No filter' and study == 'No filter' and year == 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'%"+str(country_language)+"%\'")	
		elif country_language != 'No filter' and study != 'No filter' and year != 'No filter' and item_type == 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")
		elif country_language != 'No filter' and study != 'No filter' and year == 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
		elif country_language != 'No filter' and study == 'No filter' and year != 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
		elif country_language == 'No filter' and study != 'No filter' and year != 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
		elif country_language == 'No filter' and study != 'No filter' and year != 'No filter' and item_type == 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
		elif country_language == 'No filter' and study != 'No filter' and year == 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'"+str(study)+"%\'")
		elif country_language == 'No filter' and study == 'No filter' and year != 'No filter' and item_type != 'No filter':
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and item_type ilike \'"+str(item_type)+"\' and survey_itemid ilike \'%"+str(year)+"%\'")
		else:
			results = db.session.execute("select count(*) from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\')")
		for result in results:
			item = {'Word': word, 'Frequency':result[0]}
			lst.append(item)
	

	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()

	return df

def verify_is_study_exists(year, study):
	"""
	This is a preliminary search to make sure there are questionnaires in the MCSQ that correspond to the survey project (hereby called study)
	plus year combination that was inputed by the user. This method is used in the functionalities for questionnaires comparison.
	
	Args:
		param1 year (string): year metadata filter. Indicates in which year a given study was released.
		param2 study (string): study questionnaire metadata. Can be ESS, EVS, SHARE or WIS.

	Returns: 

		A pandas dataframe containing the IDs of all available questionnaires for the inputed study+year combination
	"""
	if study == 'SHARE':
		study = 'SHA'

	results = db.session.execute("select surveyid from survey where study ilike \'"+str(study)+"\' and year="+str(year))

	lst = []
	for result in results:
		item = {'surveyid': result[0]}
		lst.append(item)
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()

	return df


def search_to_compare_item_type_independent(country_language, year, study):
	"""
	Retrieves survey items to later on be used on the compare_whole() method, which refers to the functionality of 
	comparing whole questionnaires. Country and language, year, and study metadata are obligatory for this search.
	
	Args:
		param1 country_language (string): country and language questionnaire metadata.
		param2 year (string): year metadata filter. Indicates in which year a given study was released.
		param3 study (string): study questionnaire metadata. Can be ESS, EVS, SHARE or WIS.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if study == 'SHARE':
		study = 'SHA'

	results = db.session.execute("select survey_itemid, text, item_name, item_type from survey_item where survey_itemid ilike \'"+str(study)+"%_"+str(year)+"_%"+str(country_language)+"%\'")

	lst = []
	for result in results:
		item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
		'item_type': result[3]}
		lst.append(item)
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()

	return df

def search_to_compare_by_item_type(country_language, year, study, item_type):
	"""
	Retrieves survey items to later on be used on the compare_by_item_type() method, which refers to the functionality of 
	comparing questionnaires with item type filtering. Country and language, year, and study metadata are obligatory for this search.
	
	Args:
		param1 country_language (string): country and language questionnaire metadata.
		param2 year (string): year metadata filter. Indicates in which year a given study was released.
		param3 study (string): study questionnaire metadata. Can be ESS, EVS, SHARE or WIS.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if study == 'SHARE':
		study = 'SHA'

	results = db.session.execute("select survey_itemid, text, item_name, item_type from survey_item where survey_itemid ilike \'"+str(study)+"%_"+str(year)+"_%"+str(country_language)+"%\' and item_type ilike \'"+item_type+"\'")

	lst = []
	for result in results:
		item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
		'item_type': result[3]}
		lst.append(item)
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()

	return df

def compare_by_word_case_sensitive(word, country_language, year, study, multiplew):
	"""
	Retrieves survey items to later on be used on the compare_by_word() method in case sensitive mode, which refers to the functionality of 
	comparing questionnaires with word filtering. Country and language, year, and study metadata are obligatory for this search.
	
	Args:

		param1 word (string): the word (or multiple words) that the user wants to search for.
		param2 country_language (string): country and language questionnaire metadata.
		param3 year (string): year metadata filter. Indicates in which year a given study was released.
		param4 study (string): study questionnaire metadata. Can be ESS, EVS, SHARE or WIS.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if multiplew:
		word = prepare_words_for_multiple_word_search(word)

	if study == 'SHARE':
		study = 'SHA'

	results = db.session.execute("select survey_itemid, text, item_name,item_type from survey_item where text like \'%"+str(word)+"%\' and survey_itemid ilike \'"+str(study)+"%_"+str(year)+"_%"+str(country_language)+"%\'")	

	lst = []
	for result in results:
		item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
		'item_type': result[3]}
		lst.append(item)

	df = pd.DataFrame.from_dict(lst)


	db.session.close()
	db.session.remove()

	return df

def compare_by_word_case_insensitive(word, country_language, year, study, multiple_words, partial):
	"""
	Retrieves survey items to later on be used on the compare_by_word() method in case insensitive mode, which refers to the functionality of 
	comparing questionnaires with word filtering. Country and language, year, and study metadata are obligatory for this search.
	
	Args:
	
		param1 word (string): the word (or multiple words) that the user wants to search for.
		param2 country_language (string): country and language questionnaire metadata.
		param3 year (string): year metadata filter. Indicates in which year a given study was released.
		param4 study (string): study questionnaire metadata. Can be ESS, EVS, SHARE or WIS.
		param5 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param6 partial (string): indicates if the user wants see partial results (e.g. running, runs when searching for run).

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if multiple_words and partial:
		word = prepare_words_for_multiple_word_search(word)
	elif multiple_words and not partial:
		words = word.split(';')
		clean_w = []
		for w in words:
			if w!='' and w!=' ':
				clean_w.append(w)
		word = ' & '.join(clean_w)

	if study == 'SHARE':
		study = 'SHA'

	if partial:
		results = db.session.execute("select survey_itemid, text, item_name, item_type from survey_item where text ilike \'%"+str(word)+"%\' and survey_itemid ilike \'"+str(study)+"%_"+str(year)+"_%"+str(country_language)+"%\'")
	else:
		results = db.session.execute("select survey_itemid, text, item_name, item_type from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%_"+str(year)+"_%"+str(country_language)+"%\'")
			

	lst = []
	for result in results:
		item = {'survey_itemid': result[0], 'Text':result[1],  'item_name': result[2], 
		'item_type': result[3]}
		lst.append(item)
		
	df = pd.DataFrame.from_dict(lst)

	print(df)

	db.session.close()
	db.session.remove()

	return df



def get_columnid_name(item_type):
	"""
	Returns the name of the column ID based on the item type filter.
	
	Args:
		param1 item_type (string): item type metadata filter. Can be INTRODUCTION, INSTRUCTION, REQUEST or RESPONSE.

	Returns: 

		The name of the column ID that corresponds to a given item type.
	"""
	columnid = None
	if item_type ==  'INTRODUCTION':
		columnid = 'introductionid'
	elif item_type ==  'INSTRUCTION':
		columnid = 'instructionid'
	elif item_type ==  'REQUEST':
		columnid = 'requestid'
	elif item_type ==  'RESPONSE':
		columnid = 'responseid'


	return columnid


def compute_word_search_for_collocation(word, country_language, year, study, item_type):
	"""
	This is a insensitive word count search to compute the word collocations.
	The search query is built depending on the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.
	
	Args:
		param1 word (string): the word that will be used to compute collocations-
		param2 country_language (string): country and language questionnaire metadata.
		param3 year (string): year metadata filter. Indicates in which year a given study was released.
		param4 study (string): study questionnaire metadata. Can be ESS, EVS, SHARE or WIS.
		param5 item_type (string): item type metadata filter. Can be INTRODUCTION, INSTRUCTION, REQUEST or RESPONSE.

	Returns: 

		A pandas dataframe containing the results of the search query, that will then be used to compute the collocations.
	"""
	if study == 'SHARE':
		study = 'SHA'

	lst = []

	columnid_type = get_columnid_name(item_type)

	#C=y S=y Y=y I=y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter' and item_type != 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\' and "+columnid_type+" is not null")
	#C=y S=n Y=n I=n
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter' and item_type == 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(country_language)+"%\'")	
	#C=y S=y Y=n I=n
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter' and item_type == 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
	#C=y S=n Y=y I=n
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter' and item_type == 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
	#C=y S=n Y=n I=y
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter' and item_type != 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(country_language)+"%\' and "+columnid_type+" is not null")
	#C=y S=y Y=y I=n
	elif country_language != 'No filter' and study != 'No filter' and year != 'No filter' and item_type == 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")
	#C=y S=y Y=n I=y
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter' and item_type != 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\' and "+columnid_type+" is not null")
	#C=y S=n Y=y I=y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter' and item_type != 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\' and "+columnid_type+" is not null")
	#C=n S=y Y=n I=n
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter' and item_type == 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%\'")	
	#C=n S=y Y=y I=n
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter' and item_type == 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
	#C=n S=y Y=n I=y
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter' and item_type != 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'"+str(study)+"%\' and "+columnid_type+" is not null")	
	#C=n S=n Y=y I=n
	elif country_language == 'No filter' and study == 'No filter' and year != 'No filter' and item_type == 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and survey_itemid ilike \'%"+str(year)+"%\'")
	#C=n S=n Y=n I=y
	elif country_language == 'No filter' and study == 'No filter' and year == 'No filter' and item_type != 'No filter':
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\') and "+columnid_type+" is not null") 
	else:
		results = db.session.execute("select text from survey_item where to_tsvector(text) @@ to_tsquery(\'"+str(word)+"\')")
		
	for result in results:
		lst.append(result[0])
	

	db.session.close()
	db.session.remove()

	return lst


def get_questionnaire(country_language, year, study, displaytagged):
	"""
	Retrieves a given questionnaire (or set of questionnaires) to be either displayed to, or downloaded by the user (display_questionnaire() and download_questionnaire()).
	
	Args:
	
		param1 country_language (string): country and language questionnaire metadata.
		param2 year (string): year metadata. Indicates in which year a given study was released.
		param3 study (string): study questionnaire metadata.
		param4 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations or not.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if study == 'SHARE':
		study = 'SHA'

	if displaytagged:
		tagged_column = 'pos_tagged_text, ner_tagged_text, '
	else:
		tagged_column = ''

	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, item_type, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")	
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, item_type, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where survey_itemid ilike \'%"+str(country_language)+"%\'")	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, item_type, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, item_type, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, item_type, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where survey_itemid ilike \'"+str(study)+"%\'")	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, item_type, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, item_type, text, "+tagged_column+" item_name, country_language, moduleid from survey_item where survey_itemid ilike \'%_"+str(year)+"_%\'")
	
	lst = []
	if displaytagged:
		for result in results:
			item = {'survey_itemid': result[0], 'item_type':  result[1], 'Text':result[2],  'POS Tagged Text':result[3],  'NER Tagged Text':result[4],
			'item_name': result[5], 'country_language': result[6], 'moduleid': result[7]}
			lst.append(item)
	else:
		for result in results:
			item = {'survey_itemid': result[0], 'item_type':  result[1], 'Text':result[2],  'item_name': result[3], 
			'country_language': result[4], 'moduleid': result[5]}
			lst.append(item)
	

	lst = sorted(lst, key=lambda x: int(x['survey_itemid'].split("_")[-1]))
	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df

def get_alignment(country_language, year, study, displaytagged):
	"""
	Retrieves a given questionnaire (or set of questionnaires) alignment to be either displayed to, or downloaded by the user (display_alignment() and download_alignment()).
	
	Args:
	
		param1 country_language (string): country and language questionnaire metadata.
		param2 year (string): year metadata. Indicates in which year a given study was released.
		param3 study (string): study questionnaire metadata.
		param4 displaytagged (string): indicates if the user wants the results to include Part-of-Speech and Named Entity Recognition annotations or not.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if study == 'SHARE':
		study = 'SHA'

	if displaytagged:
		tagged_column = ', source_pos_tagged_text, target_pos_tagged_text, source_ner_tagged_text, target_ner_tagged_text '
	else:
		tagged_column = ''

	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text,target_text "+tagged_column+" from alignment  where target_survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")	
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text,target_text "+tagged_column+" from alignment  where target_survey_itemid ilike \'%"+str(country_language)+"%\'")	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text,target_text "+tagged_column+" from alignment  where target_survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text,target_text "+tagged_column+" from alignment  where target_survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text,target_text "+tagged_column+" from alignment  where target_survey_itemid ilike \'"+str(study)+"%\'")	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text,target_text "+tagged_column+" from alignment  where target_survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		results = db.session.execute("select source_survey_itemid, target_survey_itemid, source_text,target_text "+tagged_column+" from alignment  where target_survey_itemid ilike \'%_"+str(year)+"_%\'")
	
	lst = []
	if displaytagged:
		for result in results:
			item = {'source_survey_itemid': result[0], 'target_survey_itemid':result[1],  
			'Source Text': result[2], 'Target Text': result[3], 'POS Tagged Source Text': result[4], 'POS Tagged Target Text': result[5],
			'NER Tagged Source Text': result[6], 'NER Tagged Target Text': result[7]}
			lst.append(item)
	else:
		for result in results:
			item = {'source_survey_itemid': result[0], 'target_survey_itemid':result[1],  
			'Source Text': result[2], 'Target Text': result[3]}
			lst.append(item)

	df = pd.DataFrame.from_dict(lst)


	db.session.close()
	db.session.remove()
	return df

def get_alignment_for_tmx(country_language, year, study):
	"""
	Retrieves a given questionnaire (or set of questionnaires) alignment to build a translation memory on create_tmx() method.
	
	Args:
	
		param1 country_language (string): country and language questionnaire metadata.
		param2 year (string): year metadata. Indicates in which year a given study was released.
		param3 study (string): study questionnaire metadata.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if study == 'SHARE':
		study = 'SHA'

	
	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select source_text, source_survey_itemid, target_text, target_survey_itemid from alignment  where target_survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'")	
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		results = db.session.execute("select source_text, source_survey_itemid, target_text, target_survey_itemid from alignment  where target_survey_itemid ilike \'%"+str(country_language)+"%\'")	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select source_text, source_survey_itemid, target_text, target_survey_itemid from alignment  where target_survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'")
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		results = db.session.execute("select source_text, source_survey_itemid, target_text, target_survey_itemid from alignment  where target_survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'")
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select source_text, source_survey_itemid, target_text, target_survey_itemid from alignment  where target_survey_itemid ilike \'"+str(study)+"%\'")	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select source_text, source_survey_itemid, target_text, target_survey_itemid from alignment  where target_survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'")	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		results = db.session.execute("select source_text, source_survey_itemid, target_text, target_survey_itemid from alignment  where target_survey_itemid ilike \'%_"+str(year)+"_%\'")
	
	lst = []
	if "_" in country_language:
		target_lang = country_language.split("_")[0].lower()
	else:
		target_lang =country_language.lower()

	for result in results:
		item = {'en': result[0], 'en_id': result[1],  target_lang:result[2],  target_lang+'_id':result[3]}
		lst.append(item)

	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df, target_lang

def prepare_tag_sequence_for_search(tags):
	"""
	Prepares the query string that concerns to the tags, to put it in the correct format accepted by PostgreSQL.
	
	Args:
	
		param1 tags (list): list of tags (strings), as specified by the user in the search form.

	Returns: 

		A portion of the search query (string) that refers to the tag sequence. 
	"""
	if len(tags) == 1:
		return " and pos_tagged_text ilike \'%"+str(tags[0])+"%\'" 
	else:
		query = " and pos_tagged_text ilike \'%"+str(tags[0])+"%"
		for tag in tags[1:]:
			query = query+str(tag)+"%"
		query = query+"\'" 
		return query

def get_tag_sequence(text):
	"""
	Extracts only the tags from a given text segment.
	
	Args:
	
		param1 text (string): a text segment from a given questionnaire, containing part of speech tagging annotations.

	Returns: 

		A sequence of part of speech tags extracted from the text segment (string).
	"""
	pos_tag_sequence = re.findall('<.*?>',text)
	pos_tag_sequence = ' '.join(pos_tag_sequence)

	return pos_tag_sequence

def filter_results(results, tags, partial):
	"""
	Filters the results of the pos tag sequence search. If the search type selected was partial,
	then a partial match will be considered in the results, otherwise only exact matches will be considered.
	
	Args:
		param1 results (list): a list of text segments (strings) from questionnaires.
		param2 tags (list): list of tags (strings).
		param3 partial (string): indicates if the user wants see partial results e.g. a tag sequence that is part of a larger sequence.

	Returns: 

		A list of results (strings) filtered according to the search type (partial or not partial).
	"""
	tag_sequence = ' '.join(tags)
	filtered_results = []
	if partial:
		for ret in results:
			t = get_tag_sequence(ret[2])
			t = t.replace(">", "")
			t = t.replace("<", "") 
			
			if tag_sequence in t:
				filtered_results.append(ret)
	else:
		for ret in results:
			t = get_tag_sequence(ret[2])
			t = t.replace(">", "")
			t = t.replace("<", "") 
			
			if t == tag_sequence:
				filtered_results.append(ret)


	return filtered_results

def search_by_pos_tag_sequence(tags, country_language, year, study, item_type, partial):
	"""
	Searches for a Part-of-Speech (POS) tag sequence in the pos_tagged_text column.
	The tag sequence is manipulated to the approriate format for a query in the prepare_tag_sequence_for_search() method.
	Then, this method builds the remaining search query according the metadata selected by the user. 
	This method considers all possible combinations between the set of metadata available for this search.
	
	Args:
		param1 tags (list of strings): the list of POS tags that form the sequence.
		param2 country_language (string): country and language questionnaire metadata.
		param3 year (string): year metadata. Indicates in which year a given study was released.
		param4 study (string): study questionnaire metadata.
		param5 item_type (string): item_type segment metadata. Can be INTRODUCTION,	 INSTRUCTION, REQUEST or RESPONSE.	
		param5 multiple_words (string): indicates if the user is searching for a single words or multiple words.
		param6 partial (string): indicates if the user wants to search for the exact inputed sequence or if more tags are allowed.

	Returns: 

		A pandas dataframe containing the results of the search query.
	"""
	if study == 'SHARE':
		study = 'SHA'

	if item_type != 'No filter':
		add_item_type = " and item_type ilike \'" +item_type+"\'" 
	else:
		add_item_type = ''

	tag_query = prepare_tag_sequence_for_search(tags)

	
	
	#country_language=Y, study=Y, year=Y
	if country_language != 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, pos_tagged_text from survey_item where survey_itemid ilike \'"+str(study)+"%"+str(year)+"%"+str(country_language)+"%\'"+tag_query+add_item_type)	
	#country_language=Y, study=N, year=N
	elif country_language != 'No filter' and study == 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, pos_tagged_text from survey_item where survey_itemid ilike \'%"+str(country_language)+"%\'"+tag_query+add_item_type)	
	#country_language=Y, study=Y, year=N
	elif country_language != 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, pos_tagged_text from survey_item where survey_itemid ilike \'"+str(study)+"%"+str(country_language)+"%\'"+tag_query+add_item_type)
	#country_language=Y, study=N, year=Y
	elif country_language != 'No filter' and study == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, pos_tagged_text from survey_item where survey_itemid ilike \'%"+str(year)+"%"+str(country_language)+"%\'"+tag_query+add_item_type)
	#country_language=N, study=Y, year=N
	elif country_language == 'No filter' and study != 'No filter' and year == 'No filter':
		results = db.session.execute("select survey_itemid, text, pos_tagged_text from survey_item where survey_itemid ilike \'"+str(study)+"%\'"+tag_query+add_item_type)	
	#country_language=N, study=Y, year=Y
	elif country_language == 'No filter' and study != 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, pos_tagged_text from survey_item where survey_itemid ilike \'"+str(study)+"%"+str(year)+"%\'"+tag_query+add_item_type)	
	#country_language=N, study=N, year=Y
	elif study == 'No filter' and country_language == 'No filter' and year != 'No filter':
		results = db.session.execute("select survey_itemid, text, pos_tagged_text from survey_item where survey_itemid ilike \'%_"+str(year)+"_%\'"+tag_query+add_item_type)
	
	results = filter_results(results, tags, partial)


	lst = []
	for result in results:
		item = {'survey_itemid': result[0], 'Text': result[1], 'POS Tagged Target Text': result[2]}
		lst.append(item)

	df = pd.DataFrame.from_dict(lst)

	db.session.close()
	db.session.remove()
	return df