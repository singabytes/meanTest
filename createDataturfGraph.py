#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep  6 23:15:32 2019

@author: Apple
"""

import hashlib
import pandas as pd
from sqlalchemy import create_engine
from arango import ArangoClient
import pickle
import sys
import datetime

db_connection_str = 'mysql+pymysql://api:apimaster@vps36407.ovh.net/BigHorse'
ipLinuxAzure = "23.97.57.179"
portArango = "8529"

def handleNonASCII(text):
    tmp = ''.join([i if ord(i) < 128 else '?' for i in text])
    tmp = tmp.encode('ascii')
    return tmp.decode('ascii') #TODO

def hashString(text):
    # hash on 16 degits (change the **16)
    text = handleNonASCII(text.replace(" ",''))
    entier = int(hashlib.sha1(text).hexdigest(), 16) % (10 ** 16)
    return str(entier)

def string2key(text):
    text = handleNonASCII(text.lower())
    text = text.replace(' ','_').replace('-','_')
    text = text.replace('/','_').replace('&','_')
    text = text.replace('<','_').replace('>','_')
    text = text.replace('#','_')#.replace('-','_')
    return text

def key4Course(prix, hippodrome):
    return string2key(prix + '-at-' + hippodrome)
def key4Trotteur(trotteur):
    return string2key(trotteur)
def key4CourseParam(prix, hippodrome, date):
    return string2key(prix + '-at-' + hippodrome + '-on-' + date)
def key4TrotteurParam(trotteur, date):
    return string2key(trotteur + '-on-' + date)
def key4EdgeTrotteurTrotteurParam(trotteur, date):
    return string2key('edge -for-' + trotteur + '-on-' + date)
def key4EdgeCourseCourseParam(course, date):
    return string2key('edge -for-' + course + '-on-' + date)
def key4EdgeCourseTrotteur(trotteur, prix, date):
    return string2key('edge -for-' + trotteur + '-at-' + prix + '-on-' + date)
# Define some string
ID = 'ID'
DATE = 'DATE'
HIPPODROME = 'HIPPODROME'
NUM_REUNION = 'NUM_REUNION'
NUM_COURSE = 'NUM_COURSE'
NBRE_COURSE = 'NBRE_COURSE'
ALLOCATION = 'ALLOCATION'
CATEGORIE = 'CATEGORIE'
CLASSEMENT = 'CLASSEMENT' 
CONDITION = 'CONDITION'
DISCIPLINE = 'DISCIPLINE'
DISTANCE = 'DISTANCE'
HEURE = 'HEURE'
PRIX = 'PRIX'
AUTOSTART = 'AUTOSTART'

NUM_REUNION = 'NUM_REUNION', 
NUM_COURSE ='NUM_COURSE'
NUM = 'NUM' 
TROTTEUR = 'TROTTEUR'
PROPRIETAIRE = 'PROPRIETAIRE'
DEFERRAGE = 'DEFERRAGE' 
PREMIER_FER = 'PREMIER_FER' 
SEXE = 'SEXE'
AGE = 'AGE'
DISTANCE = 'DISTANCE'
DRIVER = 'DRIVER' 
POIDS = 'POIDS' 
ENTRAINEUR = 'ENTRAINEUR'
MUSIQUE = 'MUSIQUE'
RECORD = 'RECORD'
GAIN = 'GAIN'
CRACKSERIE = 'CRACKSERIE'
PLACE = 'PLACE'

# Connnect to the SQL DB to pull the table content
print('Load SQL data')
read_backup = True
if (read_backup == False):
    print('Load data from SQL database')
    db_connection = create_engine(db_connection_str)
    allCourses = pd.read_sql("SELECT * FROM TROT_COURSES WHERE DATE LIKE '%2019%'", con=db_connection)
    allPartants = pd.read_sql("SELECT * FROM TROT_PARTANTS WHERE DATE LIKE '%2019%'", con=db_connection)

    # keep only 2019 courses
    tmp = []
    for index, rows in allCourses.iterrows():
        if ('2019' not in rows[DATE]):
            tmp.append(index)
    allCourses = allCourses.drop(tmp)
    tmp.clear()
    for index, rows in allPartants.iterrows():
        if ('2019' not in rows[DATE]):
            tmp.append(index)
    allPartants = allPartants.drop(tmp)
    
    # Store the data for next time (faster)
    with open(r'./allCoursesDF.pkl','wb') as output:
        pickle.dump(allCourses, output, pickle.HIGHEST_PROTOCOL)
    with open(r'./allPartantsDF.pkl','wb') as output:
        pickle.dump(allPartants, output, pickle.HIGHEST_PROTOCOL)
else:
    print('Loading data from backup')
    with open(r'./allCoursesDF.pkl','rb') as input:
        allCourses = pickle.load(input)
    with open(r'./allPartantsDF.pkl','rb') as input:
        allPartants = pickle.load(input)
       
print('Loading done...')

# initialize le client Arango
client = ArangoClient(hosts = "http://" + ipLinuxAzure + ":" + portArango)
sys_db = client.db('_system', username = 'root', password ='root')
# connecte a la base 
DB = "dataturf_graph"

if sys_db.has_database(DB):
    sys_db.delete_database(DB) # TODO
sys_db.create_database(DB)

db = client.db(DB, username = 'root', password ='root')

# get the client wrapper
graph = db.create_graph('dataturf')
dataturf = db.graph('dataturf')

# creation vertex = noeuds
course = graph.create_vertex_collection('course')
trotteur = graph.create_vertex_collection('trotteur')
trotteurParam = graph.create_vertex_collection('trotteurParam')
courseParam = graph.create_vertex_collection('courseParam')

# creation des edges = liens
course2trotteur = dataturf.create_edge_definition(
        edge_collection = 'course2trotteur',
        from_vertex_collections = ['course'],
        to_vertex_collections = ['trotteur'])

course2courseParam = dataturf.create_edge_definition(
        edge_collection = 'course2courseParam',
        from_vertex_collections = ['course'],
        to_vertex_collections = ['courseParam'])

trotteur2trotteurParam = dataturf.create_edge_definition(
        edge_collection = 'trotteur2trotteurParam',
        from_vertex_collections = ['trotteur'],
        to_vertex_collections = ['trotteurParam'])

# Creation vertex Course
keyAlreadyAdded = set()
for index, rows in allCourses.iterrows():
    prix = rows[PRIX]
    hippodrome = rows[HIPPODROME]
    key = key4Course(prix, hippodrome)
    if (key not in keyAlreadyAdded):
        try:
            course.insert({
                '_key': key,
                'hippodrome' : hippodrome,
                'prix': prix,
            })
        except Exception as e:
            msg = prix + " - " + hippodrome + " --- " + key4Course(prix, hippodrome)
            print('Error :' + msg)
            print(sys.exc_info()[0])
            print(str(e))
     
    keyAlreadyAdded.add(key)

# Creation vertex Trotteur
print('Create trotteur')
print(datetime.datetime.now())

trotteurUnique = set()
for name in allChevaux['trotteur']:
    trotteurUnique.add(name)

for name in trotteurUnique: 
    try:
        trotteur.insert({
           '_key': key4Trotteur(name),
           'trotteur': name
        })
    except Exception as e:
        msg = "trotteur : " + name + " --- " + key4Trotteur(name)
        print('Error :' + msg)
        print(sys.exc_info()[0])
        print(str(e))

#—– Creation vertex param course + edge course > courseParam
print("CourseParam + edge course > courseParam") 
print(datetime.datetime.now())

for index, rows in allCourses.iterrows():
    hippodrome = rows[HIPPODROME]
    prix = rows[PRIX]
    date = str(rows[DATE])
    allocation = str(rows[ALLOCATION].replace(" ",''))
    categorie = str(rows[CATEGORIE])
    discipline = str(rows[DISCIPLINE])
    distance = str(rows[DISTANCE])
    heure = str(rows[HEURE])
    autostart = str(rows[AUTOSTART])
    if ('O' not in autostart):
        autostart = 'N'

    key4CourseParam(prix, hippodrome, date)
  
    try:
        courseParam.insert({
            '_key': key4CourseParam,
            'date' : date,
            'heure' : heure,
            'distance' : distance,
            'allocation' : allocation,
            'categorie' : categorie,
            'discipline' : discipline,
            'autostart' : autostart
        })
    except Exception as e:
        print("Error (paramCourse) : ", key4CourseParam, prix, date, allocation, categorie, discipline, distance, heure, autostart)
        print(sys.exc_info()[0])
        print(str(e))

    keyEdge = key4EdgeCourseCourseParam(prix, date)
    if not (course2courseParam.has(keyEdge)):
        try:
            course2courseParam.insert({
                '_key': keyEdge,
                '_from': 'course/' + key4Course(prix, hippodrome),
                '_to': 'courseParam/' + keyCourseParam
            })
        except Exception as e:
            print('Error :', rows[PRIX] , str(rows[DATE]), keyEdge)
            print(sys.exc_info()[0])
            print(str(e))

#—– Creation vertex param cheval + edge cheval > chevalParam
for index, rows in allChevaux.iterrows():
    trotteur = rows[TROTTEUR]
    date = str(rows[DATE])
    num = str(rows[NUM])
    proprietaire = str(rows[PROPRIETAIRE])
    deferrage = str(rows[DEFERRAGE])
    driver = str(rows[DRIVER])
    premierFer = str(rows[PREMIER_FER])
    sexe = str(rows[SEXE])
    age = str(rows[AGE])
    distance = str(rows[DISTANCE])
    driver = str(rows[DRIVER])
    poids = str(rows[POIDS])
    entraineur = str(rows[ENTRAINEUR])
    musique = str(rows[MUSIQUE])
    gain = str(rows[GAIN])
    record = str(rows[RECORD])
    crackSerie = str(rows[CRACKSERIE])
    place = str(rows[PLACE])

    keyTrotteurParam = key4TrotteurParam(trotteur, date)

    try:
        trotteurParam.insert({
            '_key': keyTrotteurParam,
            'num ' : num,
            'proprietaire' : proprietaire,
            'deferrage' : deferrage,
            'driver' : driver,
            'premierFer' : premierFer,
            'sexe' : sexe,
            'age' : age,
            'distance' : distance,
            'driver' : driver,
            'poids' : poids,
            'entraineur' : entraineur,
            'musique' : musique,
            'gain' : gain,
            'record' : record,
            'crackSeries' : crackSerie,
            'place' : place
        })
    except Exception as e:
        print("Error (paramCourse) : ", keyTrotteurParam, num, driver)
        print(sys.exc_info()[0])
        print(str(e))

    keyEdge = key4EdgeTrotteurTrotteurParam(trotteur, date)
    if not (trotteur2trotteurParam.has(keyEdge)):
        try:
            trotteur2trotteurParam.insert({
                '_key': keyEdge,
                '_from': 'trotteur/' + key4Trotteur(trotteur),
                '_to': 'trotteurParam/' + keyTrotteurParam
            })
        except Exception as e:
            print('Error :', trotteur, date, keyEdge)
            print(sys.exc_info()[0])
            print(str(e))

print(datetime.datetime.now())

# Creation edge course > trotteur
count = 0
for index, rows in allCourses.iterrows():
    count = count + 1
    print(count, (len(allCourses)))
    for numCheval in range(1, 20):
        courseKey = str(rows[DATE]) + "-" + str(rows[NUM_REUNION]) \
            + "-" + str(rows[NUM_COURSE]) + "-" + str(numCheval)
        print(courseKey)
        if (courseKey in allChevaux.index):
            cheval = allChevaux[allChevaux.index == courseKey]
            
            key = key4EdgeCourseTrotteur(cheval[TROTTEUR][0], rows[PRIX], str(rows[DATE]))
            if not (course2Trotteur.has(key)):
                try:
                    course2Trotteur.insert({
                        '_key': key,
                        'date': rows[DATE],
                        'num' : cheval[NUM][0],
                        '_from': 'course/' + key4Course(rows[PRIX], rows[HIPPODROME]),
                        '_to': 'trotteur/' + key4Trotteur(cheval[TROTTEUR][0])
                    })
                except Exception as e:
                    print('Error :', key, len(key))
                    print(sys.exc_info()[0])
                    print(str(e))

print("All done !")



