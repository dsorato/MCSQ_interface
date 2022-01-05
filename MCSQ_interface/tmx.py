import csv
from xml.etree import ElementTree as ET  
from xml.etree.ElementTree import ElementTree
from xml.etree.ElementTree import Element, SubElement, Comment, tostring, ElementTree
import datetime
import pandas as pd 


def createTMX(df, srclang, targetlang, adminlang='en', segtype='phrase', datatype='PlainText', oEncoding='UTF-8'):
    """
    Creates a translation memory (a XML file in Translation Memory eXchange specification) using the MCSQ aligment data.
    The TMX files created with this method were tested in Matecat (https://www.matecat.com/).

    Args:

        param1 df (pandas dataframe): a dataframe that holds the aligned MCSQ data, filtered using the interface options.
        param2 srclang (string): in the case of MCSQ, the source is always English. ENG_SOURCE for majority of datasets, ENG_GB for EVS.
        param3 targetlang (string): the target language.
    
    Returns: 

        A TMX file (XML). 
    """
    generated_on = str(datetime.datetime.now())

    root = Element('tmx')
    root.set('version', '1.4')

    header = SubElement(root, 'header')
    header.set('creationtool','')
    header.set('creationtoolversion', '')
    header.set('segtype', segtype)
    header.set('o-tmf', '')
    header.set('adminlang', adminlang)
    header.set('srclang', srclang)
    header.set('datatype', datatype)
    header.set('o-encoding', oEncoding)


    body = SubElement(root, 'body')

    for i, row in df.iterrows():
        tu = SubElement(body, 'tu')
        tuv_src = SubElement(tu, 'tuv')
        tuv_src.set('xml:lang', srclang)
        seg_src = SubElement(tuv_src, 'seg')
        seg_src.text = row[srclang]
        if row[srclang]:
            seg_src.set('id', row[srclang+'_id'])
        else:
            seg_src.set('id', '')
            
        tuv_target = SubElement(tu, 'tuv')
        tuv_target.set('xml:lang', targetlang)
        seg_target = SubElement(tuv_target, 'seg')
        seg_target.text = row[targetlang]
        if row[targetlang]:
            seg_target.set('id', row[targetlang+'_id'])
        else:
            seg_target.set('id',  '')


    return ET.tostring(root)