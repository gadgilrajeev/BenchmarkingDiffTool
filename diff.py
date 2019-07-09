import pandas as pd
import pymysql
import configparser
from flask import Flask, render_template, request
app = Flask(__name__)
import pprint

@app.route('/')
def home_page():
	parser = configparser.ConfigParser()
	wiki_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
	parser.read(wiki_metadata_file_path)

	hpc_benchmarks_list = []
	cloud_benchmarks_list = []
	print("###############################")
	print("PRINTING SECTIONS AND MODELS")
	print("###############################")
	for section in parser.sections():
		print(section + ":" + parser.get(section,'model'))
		type_of_benchmark = parser.get(section,'model').strip()
		print(type(type_of_benchmark))
		if(type_of_benchmark == '\"hpc\"'):
			hpc_benchmarks_list.append(section)
		else:
			cloud_benchmarks_list.append(section)

	print(hpc_benchmarks_list)
	print("\n\n\n")
	print(cloud_benchmarks_list)

	hpc_benchmarks_list = sorted(hpc_benchmarks_list,key=str.lower)
	cloud_benchmarks_list = sorted(cloud_benchmarks_list,key=str.lower)
	context = {
	'hpc_benchmarks_list':hpc_benchmarks_list,
	'cloud_benchmarks_list':cloud_benchmarks_list,
	}
	return render_template('all-tests.html',context=context)

@app.route('/allruns/<testname>')
def showAllRuns(testname):
	query = "SELECT DISTINCT o.originID, o.testdate, o.notes from origin o INNER JOIN result r ON o.originID = r.origin_originID INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID where t.testname = \'" + testname + "\' AND r.isvalid = 1 ORDER BY o.originID DESC" 
	db = pymysql.connect(host = '10.110.169.149', user = 'root', passwd = '', db = 'benchtooldb', port = 3306)

	dataframe = pd.read_sql(query, db)
	rows,columns = dataframe.shape		#returns a tuple (rows,columns)

	context = {
	'testname':testname,
	'data' : dataframe.to_dict(orient='list'),
	'no_of_rows': rows,
	'no_of_columns': columns,
	'direct_data':dataframe.to_html(index=False),
	}

	return render_template('all-runs.html', context = context)

@app.route('/test-details/<originID>')
def showTestDetails(originID):
	query = ""
	db = pymysql.connect(host = '10.110.169.149', user = 'root', passwd = '', db = 'benchtooldb', port = 3306)

	df = pd.read_sql(query, db)

@app.route('/environment-details/<originID>')
def showEnvDetails(originID):
	query = ""