from pprint import pprint
import time     
import logging
import os, shutil
import pandas as pd
import numpy as np
import pymysql
import configparser
from flask import Flask, render_template, request, redirect, send_file, url_for, session, send_from_directory
from collections import OrderedDict
import csv
import json
import counter_graphs_module

DB_HOST_IP = '1.21.1.52'
# DB_HOST_IP = '10.110.169.149'
# DB_HOST_IP = 'localhost'
DB_USER = 'root'
DB_PASSWD = ''
DB_NAME = 'benchtooldb'
DB_PORT = 3306

# Uncomment this line for toggling debugging messages on the console
#logging.basicConfig(level=logging.DEBUG)

# from datetime import datetime
app = Flask(__name__)

# Just a random secret key. Created by md5 hashing the string 'secretactividad'
app.secret_key = "05ec4a13767ac57407c4000e55bdc32c"
pd.set_option('display.max_rows', 500)

# RETURNS the Table name for the given 'index' from the dictionary of lists
# example : from 'origin_param_list' -> return 'origin'
@app.context_processor
def table_name():
    def _table_name(list_of_keys, index):
        tablename = list(list_of_keys)[index]
        if tablename == "ram_details_param_list":
            return "RAM_details"
        return tablename[0: tablename.find("_param_list")].capitalize()

    return dict(table_name=_table_name)


# RESERVED FOR LATER (Not important as of now. DO it if time permits)
# @app.template_filter('readable_timestamp')
# def readable_timestamp(timestamp):
#     #type of timestamp is <class 'pandas._libs.tslibs.timestamps.Timestamp'>
#     dt = timestamp.to_pydatetime();
#     return dt.strftime("%d %B, %Y %I:%M:%S %p")

# Takes the originID, returns the testname
def get_test_name(originID):
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

    TEST_NAME_QUERY = """SELECT t.testname FROM testdescriptor as t 
                        INNER JOIN origin o on o.testdescriptor_testdescriptorID=t.testdescriptorID 
                        WHERE o.originID=""" + originID + ";"

    test_name_dataframe = pd.read_sql(TEST_NAME_QUERY, db)
    test_name = test_name_dataframe['testname'][0]

    # close the database connection
    try:
        db.close()
    except:
        pass

    return test_name

#Template filter for 'unique_list'
@app.template_filter('unique_list')
def unique_list_filter(input_list):
    return unique_list(input_list)

# Takes input as a list containg duplicate elements. 
# Returns a sorted list having unique elements
def unique_list(input_list, reverse=False):
    def str_is_int(s):
        try:
            int(s)
            return True
        except:
            return False

    def str_is_float(s):
        try:
            # This fails if string isn't float
            float(s) == int(s)
            return True
        except:
            return False

    # OrderedDict creates unique keys. It also preserves the order of insertion
    lst = list(OrderedDict.fromkeys(input_list))

    logging.debug(" = {}".format(lst))

    if all(str_is_int(x) for x in lst):
        logging.debug("WAS INSTANCE OF INT MAN")
        lst = [int(x) for x in lst]
    elif all(str_is_float(x) for x in lst):
        logging.debug("WAS INSTANCE OF FLOAT MAN")
        lst = [float(x) for x in lst]
    else:
        logging.debug("WAS INSTANCE OF NONE MAN")

    # Return all values as STR
    if reverse:
        return list(reversed(list(map(lambda x: str(x), sorted(lst)))))
    else:
        return list(map(lambda x: str(x), sorted(lst)))

@app.template_filter('no_of_rows')
def no_of_rows(dictionary):
    # this is a dictionary of lists
    # return length of the first list in the dictionary
    # fastest way
    return len(dictionary[next(iter(dictionary))])


def read_all_parameter_lists(parameter_lists, test_name):

    # read metadata from metadata.ini file
    env_metadata_file_path = '/mnt/nas/scripts/metadata.ini'
    env_metadata_parser = configparser.ConfigParser()
    env_metadata_parser.read(env_metadata_file_path)

    # Read metadata for results in wiki_description.ini file
    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    # Fill all parameter Lists in the dictionary
    for param_list_name in parameter_lists:
        if param_list_name == 'results_param_list':
            parameter_lists[param_list_name] = results_metadata_parser.get(test_name, 'description') \
                                                .replace('\"', '').replace(' ', '').split(',')
            parameter_lists[param_list_name].extend(['number', 'resultype', 'unit', 'qualifier'])

        elif param_list_name == 'qualifier':
            parameter_lists[param_list_name] = results_metadata_parser.get(test_name, 'fields') \
                                                .replace('\"','').lower().split(',')

        elif param_list_name == 'min_or_max':
            parameter_lists[param_list_name] = results_metadata_parser.get(test_name, 'higher_is_better') \
                                                .replace('\"','').split(',')

        else:
            # extracts 'example' from 'example_param_list'
            env_param_name = param_list_name[0:param_list_name.find("_param_list")]

            parameter_lists[param_list_name] = env_metadata_parser.get(env_param_name, 'db_variables') \
                                                .replace(' ', '').split(',')
    return parameter_lists


def read_all_csv_files(compare_lists, parameter_lists, originID_compare_list):
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

    JENKINS_QUERY = """SELECT J.jobname, J.runID FROM origin O
                        INNER JOIN jenkins J ON O.jenkins_jenkinsID=J.jenkinsID 
                        AND O.originID in """ + str(originID_compare_list).replace('[', '(').replace(']', ')') + ";"
    jenkins_details = pd.read_sql(JENKINS_QUERY, db)

    jobname_list = jenkins_details['jobname'].to_list()
    runID_list = jenkins_details['runID'].to_list()

    # The path on which file is to be read
    file_path = "/mnt/nas/dbresults/"

    # Fill all lists in the dictionary
    for i in range(len(originID_compare_list)):
        for j in range(len(compare_lists)):
            param_values_dictionary = dict()
            list_of_keys = list(compare_lists.keys())
            table_name = list_of_keys[j][0:list_of_keys[j].find("_list")]

            # Check if the file exists
            if (
            os.path.exists(file_path + str(jobname_list[i]) + '/' + str(runID_list[i]) + '/' + table_name + '.csv')):
                pass
            else:
                table_name = list_of_keys[j][0:list_of_keys[j].find("_details_list")]
            with open(file_path + str(jobname_list[i]) + '/' + str(runID_list[i]) + '/' + table_name + '.csv',
                      newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    try:
                        for k in range(0, len(parameter_lists[table_name + '_param_list'])):
                            param_values_dictionary[parameter_lists[table_name + '_param_list'][k]] = row[k]
                        break
                    except:
                        for k in range(0, len(parameter_lists[table_name + '_details_param_list'])):
                            param_values_dictionary[parameter_lists[table_name + '_details_param_list'][k]] = row[k]
                        break
            if (table_name + "_list" in compare_lists):
                compare_lists[table_name + "_list"].append(param_values_dictionary)
            else:
                compare_lists[table_name + "_details_list"].append(param_values_dictionary)
 
     # close the database connection
    try:
        db.close()
    except:
        pass

    return compare_lists

# Returns INPUT_FILTER_CONDITION from 'test_name' and 'input_filters_list'
def get_input_filter_condition(test_name, input_filters_list):
    INPUT_FILTER_CONDITION = ""

    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    # For the input filters
    input_parameters = results_metadata_parser.get(test_name, 'description') \
                                                .replace('\"', '').replace(' ', '').split(',')

    try:
        for index, input_filter in enumerate(input_filters_list):
            if(input_filter != "None"):
                if(input_filter.isnumeric()):
                    INPUT_FILTER_CONDITION += " and SUBSTRING_INDEX(SUBSTRING_INDEX(s.description,','," + str(index+1) +"),',',-1) LIKE \'%" + input_filter  + "%\'"
                else:
                    INPUT_FILTER_CONDITION += " and SUBSTRING_INDEX(SUBSTRING_INDEX(s.description,','," + str(index+1) +"),',',-1) LIKE \'%" + input_filter  + "%\'"
    except Exception as error_message:
        logging.debug("ERRORS::::::: {}".format(error_message))
        pass

    return INPUT_FILTER_CONDITION

# Request route for favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'images/favicon.ico', mimetype='image/vnd.microsoft.icon')

# Error 404 custom page not found
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404

# Get all-tests data
def get_all_tests_data():
    parser = configparser.ConfigParser()
    wiki_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    parser.read(wiki_metadata_file_path)

    # Reference for best_of_all_graph
    sku_file_path = '/mnt/nas/scripts/sku_definition.ini'
    sku_parser = configparser.ConfigParser()
    sku_parser.read(sku_file_path)

    reference_list = sku_parser.sections();
    logging.debug("SECTIONS")
    logging.debug("{}".format(reference_list))


    filter_labels_dict = {}
    filter_labels_list = []
    hpc_benchmarks_list = []
    cloud_benchmarks_list = []
    
    for section in parser.sections():
        filter_labels_list.extend(
            [label for label in parser.get(section, 'label').replace('\"', '').replace(' ', '').lower().split(',')
            if label != '' and label not in filter_labels_list])
        filter_labels_dict[section] = ','.join(
            [label for label in parser.get(section, 'label').replace('\"', '').replace(' ', '').lower().split(',')])
        
        type_of_benchmark = parser.get(section, 'model').strip()
        
        if type_of_benchmark == '\"hpc\"':
            hpc_benchmarks_list.append(section)
        else:
            cloud_benchmarks_list.append(section)


    hpc_benchmarks_list = sorted(hpc_benchmarks_list, key=str.lower)
    cloud_benchmarks_list = sorted(cloud_benchmarks_list, key=str.lower)
    filter_labels_list = sorted(filter_labels_list, key=str.lower)

    context = {
        'hpc_benchmarks_list': hpc_benchmarks_list,
        'cloud_benchmarks_list': cloud_benchmarks_list,
        'filter_labels_list': filter_labels_list,
        'filter_labels_dict': filter_labels_dict,
        'reference_list': reference_list,
    }

    return context

# ALL TESTS PAGE
@app.route('/')
def home_page():
    context = get_all_tests_data()

    return render_template('all-tests.html', context=context)

# Get data for All runs of the test 'testname' from database
def getAllRunsData(testname, secret=False):
    # Read metadata for results in wiki_description.ini file
    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    qualifier_list = results_metadata_parser.get(testname, 'fields').replace('\"', '').split(',')
    min_or_max_list = results_metadata_parser.get(testname, 'higher_is_better') \
                    .replace('\"', '').replace(' ', '').split(',')

    logging.debug("########PRINTING QUALIFIER LIST AND MIN OR MAX LIST#########")
    logging.debug("{}".format(qualifier_list))
    logging.debug("{}".format(min_or_max_list))

    if secret == True:
        RESULTS_VALIDITY_CONDITION = " "
    else:
        RESULTS_VALIDITY_CONDITION = " AND r.isvalid = 1 "

    if min_or_max_list[0] == '0':
        ALL_RUNS_QUERY = "SELECT DISTINCT o.originID, o.testdate, o.hostname, MIN(r.number) as \'Best" +\
                        qualifier_list[0].replace(" ",'') + """\', o.notes, r.isvalid from result r INNER JOIN display disp 
                        ON  r.display_displayID = disp.displayID
                        INNER JOIN origin o ON o.originID = r.origin_originID 
                        INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID 
                        where t.testname = \'""" + testname + """\' 
                        AND disp.qualifier LIKE \'%""" + qualifier_list[0] + "%\'" + \
                        RESULTS_VALIDITY_CONDITION + """ GROUP BY o.originID, o.testdate, o.hostname, o.notes, r.isvalid
                        ORDER BY o.originID DESC"""
    else:
        ALL_RUNS_QUERY = "SELECT DISTINCT o.originID, o.testdate, o.hostname, MAX(r.number) as \'Best" +\
                        qualifier_list[0].replace(" ",'') + """\', o.notes, r.isvalid from result r INNER JOIN display disp 
                        ON  r.display_displayID = disp.displayID 
                        INNER JOIN origin o ON o.originID = r.origin_originID 
                        INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID 
                        where t.testname = \'""" + testname + """\' 
                        AND disp.qualifier LIKE \'%""" + qualifier_list[0] + "%\'" + \
                        RESULTS_VALIDITY_CONDITION + """ GROUP BY o.originID, o.testdate, o.hostname, o.notes, r.isvalid
                        ORDER BY o.originID DESC"""
    
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

    dataframe = pd.read_sql(ALL_RUNS_QUERY, db)
    rows, columns = dataframe.shape  # returns a tuple (rows,columns)

    # For secret page, return only table data. The secret function will redirect to secret page
    if secret == True:
        secret_context = {
            'testname': testname,
            'data': dataframe.to_dict(orient='list'),
            'no_of_rows': rows,
            'no_of_columns': columns,
        }

        # close the database connection
        try:
            db.close()
        except:
            pass
        return secret_context
    # Else render all-runs.html
    else:
        del dataframe['isvalid']
        rows, columns = dataframe.shape  # returns a tuple (rows,columns)

        # Dropdown for input file
        input_parameters = results_metadata_parser.get(testname, 'description') \
                                                    .replace('\"', '').replace(' ', '').split(',')

        INPUT_FILE_QUERY = """SELECT DISTINCT s.description FROM origin o INNER JOIN testdescriptor t
                                ON t.testdescriptorID=o.testdescriptor_testdescriptorID  INNER JOIN result r
                                ON o.originID = r.origin_originID INNER JOIN subtest s
                                ON  r.subtest_subtestID = s.subtestID WHERE r.isvalid = 1 and t.testname = \'""" + testname + "\';"
        input_details_df = pd.read_sql(INPUT_FILE_QUERY, db)
        logging.debug("{}".format(input_parameters))
        logging.debug("{}".format(input_details_df))

        # Function which splits the description string into various parameters 
        # according to 'description' field of the '.ini' file
        def split_description(index, description):
            try:
                return description.split(',')[index]
            except Exception as error_message:
                logging.debug("{}".format(error_message))
                return np.nan

        # Split the 'description' column into multiple columns
        for index, param in enumerate(input_parameters):
            input_details_df[param] = input_details_df['description'].apply(lambda x: split_description(index, x))

        # Delete the 'description' column
        del input_details_df['description']
        
        # Drop all the rows which have NaN as an element
        input_details_df.dropna(inplace=True)
        
        # Get default_inputs from wiki_description.ini
        default_input_filters_list = results_metadata_parser.get(testname, 'default_input') \
                                                .replace('\"', '').split(',')

        # Read from test_summary.ini file
        test_summary_file_path = "./config/test_summary.ini"
        test_summary_parser = configparser.ConfigParser()
        test_summary_parser.read(test_summary_file_path)

        test_summary = {}
        test_summary['summary'] = test_summary_parser.get(testname, 'summary').replace('\"','')
        test_summary['source_code_link'] = test_summary_parser.get(testname, 'source_code_link')
        test_summary['type_of_workload'] = test_summary_parser.get(testname, 'type_of_workload')
        test_summary['default_input'] = test_summary_parser.get(testname, 'default_input')
        test_summary['latest_version'] = test_summary_parser.get(testname, 'latest_version')

        context = {
            'testname': testname,
            'data': dataframe.to_dict(orient='list'),
            'no_of_rows': rows,
            'no_of_columns': columns,
            'qualifier_list': qualifier_list,
            'input_details': input_details_df.to_dict(orient='list'),
            'default_input_filters': default_input_filters_list,
            'test_summary' : test_summary,
        }

        # close the database connection
        try:
            db.close()
        except:
            pass

        return context

# Show all runs of a test 'testname'
@app.route('/allruns/<testname>', methods=['GET'])
def showAllRuns(testname):
    try:
        context = getAllRunsData(testname)
        error = None
    except Exception as error_message:
        context = None
        error = error_message

    # For 'Go To Benchmark' Dropdown
    all_tests_data = get_all_tests_data()

    return render_template('all-runs.html', error=error, context=context, all_tests_data=all_tests_data)

# Page for marking a test 'originID' invalid
@app.route('/allruns/secret/<testname>', methods=['GET', 'POST'])
def showAllRunsSecret(testname):
    if request.method == 'GET':
        return render_template('secret-all-runs.html', testname={'name':testname}, context={})
    else:
        success = {}
        error = {}
        keyerror = {}
        logging.debug("#######POSTED###########")
        logging.debug("{}".format(request.args))
        
        # Get doesn't throw error. 
        # If key is not present it sets to default ('None' most of the times)
        success = session.get('success')
        error = session.get('error')
        keyerror = session.get('keyerror')
    
        logging.debug('success = {}'.format(success))
        logging.debug('error = {}'.format(error))
        logging.debug('keyerror = {}'.format(keyerror))

        logging.debug("#######SESSION BEFORE ####")
        logging.debug(' = {}'.format(session))
        logging.debug("########SESSION AFTER $$$$")
        # Clear the contents of the session (cookies)
        session.clear()
        logging.debug(' = {}'.format(session))

        context = context = getAllRunsData(testname, secret=True)
        
        return render_template('secret-all-runs.html', success=success, error=error, keyerror=keyerror, context=context)

@app.route('/mark-origin-id-invalid', methods=['POST'])
def markOriginIDInvalid():
    logging.debug("\n\n\n#REQUEST#########")
    logging.debug(" = {}".format(request.form))

    data = json.loads(request.form.get('data'))
    logging.debug("JSON STATHAM")
    logging.debug(" = {}".format(data))

    originID = data.get('originID')
    testname = data.get('testname')
    valid = data.get('valid')
    secret_key = data.get('secretKey')

    success = {}
    error = {}
    keyerror = {}

    if secret_key == 'secret_123':
        logging.debug("CAUTION!!! MArking result invalid")
        db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

        cursor = db.cursor()
        if not valid:
            success['message'] = """The originID """ + originID +""" was marked invalid successfully"""
            INVALID_ORIGINID_QUERY = "UPDATE result r SET r.isvalid=0 where r.origin_originID = " + originID + ";"
        else:
            success['message'] = """The originID """ + originID +""" was marked valid successfully"""
            INVALID_ORIGINID_QUERY = "UPDATE result r SET r.isvalid=1 where r.origin_originID = " + originID + ";"
        cursor.execute(INVALID_ORIGINID_QUERY)
        cursor.close()
        db.commit()
        db.close()

    else:
        keyerror['message'] = "BOOM! Wrong Password. This incident will be reported."


    session['success'] = success
    session['error'] = error
    session['keyerror'] = keyerror

    # code = 307 for keeping the original request type ('POST')
    return redirect(url_for('showAllRunsSecret', testname=testname), code=307)

# Get details for test with originID = 'originID' from database
def getTestDetailsData(originID, secret=False):
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)
    result_type_map = {0: "single thread", 1: 'single core',
                       2: 'single socket', 3: 'dual socket',
                       4: 'client scaling', 5: '1/8th socket',
                       6: '1/4th socket', 7: '1/2 socket',
                       8: '2 cores', 9: 'perf',
                       10: 'I/O utilization', 11: 'socmon',
                       12: 'OMP_MPI scaling', 20: 'Projection'}

    # Just get the TEST name
    test_name = get_test_name(originID)

    if secret == True:
        RESULTS_VALIDITY_CONDITION = " "
    else:
        RESULTS_VALIDITY_CONDITION = " AND R.isvalid = 1 "

    # Read the subtests description from the wiki_description
    config_file = "/mnt/nas/scripts/wiki_description.ini"
    config_options = configparser.ConfigParser()
    config_options.read(config_file)

    if config_options.has_section(test_name):
        description_string = config_options[test_name]['description'].replace(
            '\"', '')
    else:
        description_string = 'Description'

    print("BEFORE GETTING DATAFRAME")

    # RESULTS TABLE
    RESULTS_QUERY = """SELECT R.resultID, S.description, R.number, disp.unit, disp.qualifier, R.isvalid
                        FROM result R INNER JOIN subtest S ON S.subtestID=R.subtest_subtestID 
                        INNER JOIN display disp ON disp.displayID=R.display_displayID 
                        INNER JOIN origin O ON O.originID=R.origin_originID WHERE O.originID=""" + originID + \
                        RESULTS_VALIDITY_CONDITION + ";"
    results_dataframe = pd.read_sql(RESULTS_QUERY, db)

    print("GOT RESULTS DATAFRAME")
    # print("{}".format(results_dataframe))

    for col in reversed(description_string.split(',')):
        results_dataframe.insert(1, col, 'default value')

    # Function which splits the description string into various parameters 
    # according to 'description' field of the '.ini' file
    def split_description(index, description):
        try:
            return description.split(',')[index]
        except Exception as error_message:
            logging.debug("Error = {}".format(error_message))
            return np.nan

    # For all the rows in the dataframe, set the description_list values
    description_list = description_string.split(',')
    for j in range(len(description_list)):
        results_dataframe[description_list[j]] = results_dataframe['description'].apply(lambda x: split_description(j, x))

    # Drop the 'description' column as we have now split it into various columns according to description_string
    del results_dataframe['description']

    results_dataframe.dropna(inplace=True)

    # For secret page, return only table data. The secret function will redirect to secret page
    if secret == True:
        secret_context = {
            'testname': test_name,
            'description_list': description_string.split(','),
            'results': results_dataframe.to_dict(orient='list'),
            'originID': originID,
        }

        # close the database connection
        try:
            db.close()
        except:
            pass

        return secret_context
    # Else render test-details.html
    else:
        print("SECRET WAS FALSE")
        del results_dataframe['resultID']
        del results_dataframe['isvalid']

        # Get some System details
        SYSTEM_DETAILS_QUERY = """SELECT DISTINCT O.hostname, O.testdate, O.originID as 'Environment Details',  S.resultype 
                                FROM result R INNER JOIN subtest S ON S.subtestID=R.subtest_subtestID 
                                INNER JOIN origin O ON O.originID=R.origin_originID 
                                WHERE O.originID=""" + originID + ";"
        system_details_dataframe = pd.read_sql(SYSTEM_DETAILS_QUERY, db)

        # Update the Result type (E.g. 0->single thread)
        try:
            system_details_dataframe.update(pd.DataFrame(
                {'resultype': [result_type_map[system_details_dataframe['resultype'][0]]]}))

            # Get result_type and remove it from system_details_dataframe (pop)
            result_type = system_details_dataframe.pop('resultype')[0]
        except:
            result_type = None
            logging.warning('Couldn\'t get Result Type')

        logging.debug(" = {}".format(result_type))

        # Get Num_CPUs list if result_type is 'perf'
        if result_type == "perf":
            try:
                # Calls unique_list function on list of unique 'Num_CPUs'
                num_cpus_list = unique_list((results_dataframe['Num_CPUs']), reverse=True)
                logging.debug("GOT NUM CPUS")
                logging.debug(" = {}".format(num_cpus_list))
            except Exception as e:
                num_cpus_list = []
                logging.debug(" = {}".format(e))
                # logging.debug(results_dataframe)
                logging.debug("DIDNT GET NUM CPUS")
        else:
            num_cpus_list = []

        print("Result Type = {}".format(result_type))

        # Get the rest of the system details from jenkins table
        JENKINS_QUERY = """SELECT J.jobname, J.runID FROM origin O INNER JOIN jenkins J 
                            ON O.jenkins_jenkinsID=J.jenkinsID AND O.originID=""" + originID + ";"
        jenkins_details = pd.read_sql(JENKINS_QUERY, db)

        # list for creating a column in the system_details_dataframe
        nas_link = []
        nas_link.append("http://sm2650-2s-01/dbresults/" +
                        jenkins_details['jobname'][0] + "/" + str(jenkins_details['runID'][0]))
        jenkins_link = []
        jenkins_link.append("http://sm2650-2s-05:8080/view/Production_Pipeline/job/" +
                            jenkins_details['jobname'][0] + "/" + str(jenkins_details['runID'][0]))

        # Put the Jenkins details in the System Details Dataframe
        system_details_dataframe['NAS Link'] = nas_link
        system_details_dataframe['Jenkins Link'] = jenkins_link
        # SYSTEM details is now ready

        context = {
            'testname': test_name,
            'system_details': system_details_dataframe.to_dict(orient='list'),
            'description_list': description_string.split(','),
            'results': results_dataframe.to_dict(orient='list'),
            'originID': originID,
            
            # Used For 'perf' scaling result_type
            'result_type': result_type,
            'jenkins_details' : {
                'jobname' : jenkins_details['jobname'][0],
                'runID' : str(jenkins_details['runID'][0]),
            },
            'num_cpus_list' : num_cpus_list,
        }

        # close the database connection
        try:
            print("CLOSING CONNECTION FOR OriginID = {}".format(originID))
            db.close()
        except:
            pass

        return context

# View for handling Test details request
@app.route('/test/<originID>', methods=['GET'])
def showTestDetailsOld(originID):
    return redirect('/test-details/' + originID)

@app.route('/test-details/<originID>', methods=['GET'])
def showTestDetails(originID):
    print("INSIDE TEST DETAILS FUNCTION = {}".format(originID))
    try:
        context = getTestDetailsData(originID)
        error = None
    except Exception as error_message:
        context = None
        error = error_message

    # For 'Go To Benchmark' Dropdown
    all_tests_data = get_all_tests_data()

    logging.debug("PRINTING CONTEXT = {}".format(context))

    return render_template('test-details.html', error=error, context=context, all_tests_data=all_tests_data)

# Page for marking Individual test 'result' as invalid 
@app.route('/test-details/secret/<originID>', methods=['GET', 'POST'])
def showTestDetailsSecret(originID):
    if request.method == 'GET':
        return render_template('secret-test-details.html', originID={'ID':originID}, context={})
    else:
        success = {}
        error = {}
        keyerror = {}
        logging.debug("#######POSTED###########")
        logging.debug(' = {}'.format(request.args))
        
        # Get doesn't throw error. 
        # If key is not present it sets to default ('None' most of the times)
        success = session.get('success')
        error = session.get('error')
        keyerror = session.get('keyerror')
    
        logging.debug('success = {}'.format(success))
        logging.debug('error = {}'.format(error))
        logging.debug('keyerror = {}'.format(keyerror))

        logging.debug("#######SESSION BEFORE ####")
        logging.debug(' = {}'.format(session))
        logging.debug("########SESSION AFTER $$$$")
        # Clear the contents of the session (cookies)
        session.clear()
        logging.debug(' = {}'.format(session))

        context = getTestDetailsData(originID, secret=True)
        
        return render_template('secret-test-details.html', success=success, error=error, keyerror=keyerror, context=context)

# Marks a single 'result' invalid
@app.route('/mark-result-id-invalid', methods=['POST'])
def markResultIDInvalid():
    logging.debug("\n\n\n#REQUEST#########")
    logging.debug(' = {}'.format(request.form))

    data = json.loads(request.form.get('data'))
    logging.debug("JSON STATHAM")
    logging.debug('Data = {}'.format(data))

    originID = data.get('originID')
    resultID = data.get('resultID')
    valid = data.get('valid')
    secret_key = data.get('secretKey')

    success = {}
    error = {}
    keyerror = {}

    if secret_key == 'secret_123':
        logging.debug("CAUTION!!! Marking resultID invalid")
        db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

        cursor = db.cursor()
        if not valid:
            success['message'] = """The resultID """ + resultID +""" was marked invalid successfully"""
            CHANGE_RESULTID_VALIDITY_QUERY = "UPDATE result r SET r.isvalid=0 where r.resultID = " + resultID + ";"
        else:
            success['message'] = """The resultID """ + resultID +""" was marked valid successfully"""
            CHANGE_RESULTID_VALIDITY_QUERY = "UPDATE result r SET r.isvalid=1 where r.resultID = " + resultID + ";"
        cursor.execute(CHANGE_RESULTID_VALIDITY_QUERY)
        cursor.close()
        db.commit()
        db.close()

    else:
        keyerror['message'] = "BOOM! Wrong Password. This incident will be reported."


    session['success'] = success
    session['error'] = error
    session['keyerror'] = keyerror

    # code = 307 for keeping the original request type ('POST')
    return redirect(url_for('showTestDetailsSecret', originID=originID), code=307)

# View for handling Environment details request
@app.route('/details/<originID>')
def showEnvDetailsOld(originID):
    return redirect('/environment-details/' + originID)

@app.route('/environment-details/<originID>')
def showEnvDetails(originID):
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)
    HWDETAILS_QUERY = """SELECT H.fwversion, H.bmcversion, H.biosversion FROM hwdetails H INNER JOIN origin O 
                         ON O.hwdetails_hwdetailsID = H.hwdetailsID AND O.originID = """ + originID + ";"
    hwdetails_dataframe = pd.read_sql(HWDETAILS_QUERY, db)

    TOOLCHAIN_QUERY = """SELECT T.toolchainname, T.toolchainversion, T.flags FROM toolchain as T INNER JOIN origin O
                                 ON O.toolchain_toolchainID = T.toolchainID AND O.originID = """ + originID + ";"
    toolchain_dataframe = pd.read_sql(TOOLCHAIN_QUERY, db)

    OSTUNINGS_QUERY = """SELECT OS.osdistro, OS.osversion, OS.kernelname, OS.pagesize, OS.thp FROM ostunings OS 
                                 INNER JOIN origin O ON O.ostunings_ostuningsID = OS.ostuningsID 
                                 AND O.originID = """ + originID + ";"
    ostunings_dataframe = pd.read_sql(OSTUNINGS_QUERY, db)

    NODE_QUERY = """SELECT N.numsockets, N.skuidname, N.cpuver, N.cpu0serial FROM node as N INNER JOIN hwdetails as H
                            INNER JOIN origin O ON O.hwdetails_hwdetailsID = H.hwdetailsID AND N.nodeID = H.node_nodeID 
                            AND O.originID = """ + originID + ";"
    node_dataframe = pd.read_sql(NODE_QUERY, db)

    BOOTENV_QUERY = """SELECT bootenv.corefreq, bootenv.ddrfreq, bootenv.memnetfreq, bootenv.smt, bootenv.turbo, 
                               bootenv.cores, bootenv.tdp FROM bootenv INNER JOIN hwdetails H 
                               INNER JOIN origin O ON O.hwdetails_hwdetailsID = H.hwdetailsID 
                               AND H.bootenv_bootenvID = bootenv.bootenvID AND O.originID = """ + originID + ";"
    bootenv_dataframe = pd.read_sql(BOOTENV_QUERY, db)

    JENKINS_QUERY = """SELECT J.jobname, J.runID FROM origin O INNER JOIN jenkins J ON O.jenkins_jenkinsID=J.jenkinsID 
                        AND O.originID = """ + originID + ";"
    jenkins_dataframe = pd.read_sql(JENKINS_QUERY, db)

    #Get the jobname and runID from jenkins_dataframe
    jobname = jenkins_dataframe['jobname'][0]
    runID = jenkins_dataframe['runID'][0]

    # Read RAM, disk and nic details from csv files
    parameter_lists = OrderedDict({
        'ram_details_param_list': [],
        'nic_details_param_list': [],
        'disk_details_param_list': [],

    })

    test_name = get_test_name(originID)

    parameter_lists = read_all_parameter_lists(parameter_lists, test_name)

    results_file_path = '/mnt/nas/dbresults/' + str(jobname) + '/' + str(runID);

    # READ RAM.CSV file and add the size to get total RAM in GB
    ram_dataframe = pd.read_csv(results_file_path + '/ram.csv', header=None,
                                names=parameter_lists['ram_details_param_list'])

    #CUSTOM FILTER
    # Returns boolean True if the group has all 'ramsize' entries as 'float'
    def only_numeric_groups(df):
        ramsize_series = df['ramsize'].astype(str).str.isnumeric().isin([True])
        return ramsize_series.all()


    ram_dataframe = ram_dataframe.groupby(by=parameter_lists['ram_details_param_list'][0:2]).filter(only_numeric_groups).reset_index(drop=True)

    # Convert each entry of 'ramsize' column to float
    ram_dataframe['ramsize'] = ram_dataframe['ramsize'].apply(lambda x: float(x))

    ram_dataframe = ram_dataframe.groupby(by=parameter_lists['ram_details_param_list'][0:2]) \
                        .apply(lambda x: x.sum()/1024).reset_index()

    #Add ' GB' to the size
    try:
        ram_dataframe['ramsize'] = ram_dataframe['ramsize'].apply(lambda x: str(x) + " GB")
    except:
        logging.warning("Couldn't add 'GB' to RAM SIZE")
        pass
    # Read disk dataframe
    disk_dataframe = pd.read_csv(results_file_path + '/disk.csv', header=None,
                                 names=parameter_lists['disk_details_param_list'])
    nic_dataframe = pd.read_csv(results_file_path + '/nic.csv', header=None,
                                names=parameter_lists['nic_details_param_list'])

    context = {
        'originID' : originID,
        'hwdetails': hwdetails_dataframe.to_dict(orient='list'),
        'toolchain': toolchain_dataframe.to_dict(orient='list'),
        'ostunings': ostunings_dataframe.to_dict(orient='list'),
        'node':      node_dataframe.to_dict(orient='list'),
        'bootenv':   bootenv_dataframe.to_dict(orient='list'),
        'ram':       ram_dataframe.to_dict(orient='list'),
        'disk':      disk_dataframe.to_dict(orient='list'),
        'nic':       nic_dataframe.to_dict(orient='list'),
    }

    # close the database connection
    try:
        db.close()
    except:
        pass

    # For 'Go To Benchmark' Dropdown
    all_tests_data = get_all_tests_data()

    return render_template('environment-details.html', context=context, all_tests_data=all_tests_data)

# Compare two or more tests
@app.route('/diff', methods=['GET', 'POST'])
def diffTests():
    if request.method == "GET":
        db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                             passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

        # take checked rows from table
        originID_compare_list = [value for key, value in request.args.items() if "diff-checkbox" in key]

        originID_compare_list.sort()
        logging.debug(' = {}'.format(originID_compare_list))

        # Get the Test name
        test_name = get_test_name(originID_compare_list[0])

        JENKINS_QUERY = """SELECT J.jobname, J.runID FROM origin O INNER JOIN jenkins J 
                            ON O.jenkins_jenkinsID=J.jenkinsID AND O.originID in """ \
                            + str(originID_compare_list).replace('[', '(').replace(']', ')') + ";"
        jenkins_details = pd.read_sql(JENKINS_QUERY, db)

        #Get the jobname and runID from jenkins details
        jobname_list = jenkins_details['jobname'].to_list()
        runID_list = jenkins_details['runID'].to_list()

        # create all parameter lists
        parameter_lists = OrderedDict({
            'results_param_list': [],
            'origin_param_list': [],
            'bootenv_param_list': [],
            'node_param_list': [],
            'hwdetails_param_list': [],
            'ostunings_param_list': [],
            'toolchain_param_list': [],
            'ram_details_param_list': [],
            'nic_details_param_list': [],
            'disk_details_param_list': [],

            'qualifier': [],
            'min_or_max': [],
        })

        parameter_lists = read_all_parameter_lists(parameter_lists, test_name)

        # removes 'qualifier' from parameter_lists and assigns to qualifier_list variable (a list)
        qualifier_list = parameter_lists.pop('qualifier')
        min_or_max_list = parameter_lists.pop('min_or_max')

        # Dictionary of List of Dictionaries (tests) to be compared
        compare_lists = OrderedDict({
            'origin_list': [],
            'bootenv_list': [],
            'node_list': [],
            'hwdetails_list': [],
            'ostunings_list': [],
            'toolchain_list': [],
            'ram_details_list': [],
            'nic_details_list': [],
            'disk_details_list': [],

        })

        # Read all results. Store in a dataframe
        join_on_columns_list = parameter_lists['results_param_list'][0:-4]
        join_on_columns_list.extend(['resultype', 'unit', 'qualifier'])

        # read the first results file
        results_file_path = '/mnt/nas/dbresults/' + str(jobname_list[0]) + '/' \
                            + str(runID_list[0]) + '/results/results.csv'
        first_results_dataframe = pd.read_csv(results_file_path, header=None,
                                              names=parameter_lists['results_param_list'])

        # LOWERCASE THE QUALIFIER COLUMN
        first_results_dataframe['qualifier'] = first_results_dataframe['qualifier'].apply(lambda x: x.lower().strip())

        # GROUP BY join_on_columns_list AND FIND MIN/MAX OF EACH GROUP
        if min_or_max_list[0] == '0':
            first_results_dataframe = first_results_dataframe.groupby(by=join_on_columns_list).min()
        else:
            first_results_dataframe = first_results_dataframe.groupby(by=join_on_columns_list).max()

        # Assign first results_dataframe to intermediate_dataframe for merging
        intermediate_dataframe = first_results_dataframe

        logging.debug('\n\nDONE\n\n')

        # for each subsequent results file, merge with the already exsiting dataframe on "description" columns
        for jobname, runID in zip(jobname_list[1:], runID_list[1:]):
            results_file_path = '/mnt/nas/dbresults/' + str(jobname) + '/' + str(runID) + '/results/results.csv'

            next_dataframe = pd.read_csv(results_file_path, header=None, names=parameter_lists['results_param_list'])
            next_dataframe['qualifier'] = next_dataframe['qualifier'].apply(lambda x: x.lower().strip())

            # GROUP BY join_on_columns_list AND FIND MIN/MAX OF EACH GROUP
            if min_or_max_list[0] == '0':
                next_dataframe = next_dataframe.groupby(by=join_on_columns_list).min()
            else:
                next_dataframe = next_dataframe.groupby(by=join_on_columns_list).max()

            # Merge the next_dataframe with previous
            intermediate_dataframe = intermediate_dataframe.merge(next_dataframe, how='outer', on=join_on_columns_list,
                                                                  validate="many_to_many")

        # Change column names according to OriginID
        intermediate_dataframe = intermediate_dataframe.reset_index()
        intermediate_dataframe.columns = join_on_columns_list + ["number_" + originID for originID in
                                                                 originID_compare_list]

        # Change the result_type according to result_type_map
        # Mapping for Result type field
        result_type_map = {0: "single thread", 1: 'single core',
                       2: 'single socket', 3: 'dual socket',
                       4: 'client scaling', 5: '1/8th socket',
                       6: '1/4th socket', 7: '1/2 socket',
                       8: '2 cores', 9: 'perf',
                       10: 'I/O utilization', 11: 'socmon',
                       12: 'OMP_MPI scaling', 20: 'Projection'}

        def apply_result_type(x):
            try:
                return result_type_map[x]
            except:
                logging.warning("Couldn't parse result type")
                return None

        intermediate_dataframe['resultype'] = intermediate_dataframe['resultype'].apply(lambda x: apply_result_type(x))

        final_results_dataframe = pd.DataFrame(columns=intermediate_dataframe.columns)
        # SUBSET OF ROWS WHICH HAVE "qualifier" IN QUALIFIER LIST
        for q in qualifier_list:
            mask = (intermediate_dataframe['qualifier'] == pd.Series([q] * len(intermediate_dataframe)))
            dataframe = intermediate_dataframe[mask]

            final_results_dataframe = final_results_dataframe.append(dataframe)

        logging.debug("PRINTING THE FINAL DATAFRAME")
        logging.debug(' = {}'.format(final_results_dataframe))
        logging.debug("DONE")

        # DROP THE NAN rows for comparing results in graphs
        comparable_results = final_results_dataframe.dropna()
        comparable_results = comparable_results[
            ['qualifier'] + [column for column in comparable_results.columns if column not in join_on_columns_list]]

        comparable_results.columns = ['qualifier'] + ["Test_" + originID for originID in originID_compare_list]

        # FILL NAN cells with ""
        final_results_dataframe = final_results_dataframe.fillna("")

        logging.debug("PRINTING COMPARABLE RESULTS")
        logging.debug(' = {}'.format(comparable_results))
        logging.debug("DONE")

        # Delete the results_param_list as it is no longer needed
        del parameter_lists['results_param_list']

        # read csv files from NAS path
        compare_lists = read_all_csv_files(compare_lists, parameter_lists, originID_compare_list)

        # send data to the template compare.html
        context = {
            'originID_list': originID_compare_list,
            'testname': test_name,

            'index_columns': join_on_columns_list,

            'parameter_lists': parameter_lists,
            'compare_lists': compare_lists,

            'comparable_results': comparable_results.to_dict(orient='list'),
            'results': final_results_dataframe.to_dict(orient='list'),
        }
        # close the database connection
        try:
            db.close()
        except:
            pass

        return render_template('compare.html', context=context)
    else:
        return redirect('/')

# This function handles the AJAX request for Comparison graph data. 
# JS then draws the graph using this data
@app.route('/get_data_for_graph', methods=['POST'])
def get_data_for_graph():
    print("GOT THE REQUEST FOR GET DATA FOR GRAPH")
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

    data = request.get_json()
    xParameter = data['xParameter']
    yParameter = data['yParameter']

    testname = data['testname']

    # Get input_filter_condition by calling the function
    input_filters_list = data['inputFiltersList']
    INPUT_FILTER_CONDITION = get_input_filter_condition(testname, input_filters_list)

    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    # GET qualifier_list and min_max_list from 'fields' and 'higher_is_better' the section 'testname'
    qualifier_list = results_metadata_parser.get(testname, 'fields').replace('\"', '').split(',')
    min_or_max_list = results_metadata_parser.get(testname, 'higher_is_better') \
                    .replace('\"', '').replace(' ', '').split(',')
    index = qualifier_list.index(yParameter)

    sku_file_path = '/mnt/nas/scripts/sku_definition.ini'
    sku_parser = configparser.ConfigParser()
    sku_parser.read(sku_file_path)

    # Dictionary mapping from 'skuidname' : 'server_cpu_name'
    # Example 'Cavium ThunderX2(R) CPU CN9980 v2.2 @ 2.20 GHz' : Marvell TX2-B2
    skuid_cpu_map = OrderedDict({section: sku_parser.get(section, 'SKUID').replace('\"', '').split(',') for section in sku_parser.sections()})
    
    # Fill the sku_cpu_map with all "sku->section" mapping entries
    for section in sku_parser.sections():
        skus = sku_parser.get(section, 'SKUID').replace('\"','').split(',')
        for sku in skus:
            skuid_cpu_map[sku] = section


    parameter_map = {
        "Kernel Version": 'os.kernelname', 
        'OS Version': 'os.osversion', 
        'OS Name': 'os.osdistro', 
        "Firmware Version": 'hw.fwversion' , 
        "ToolChain Name": 'tc.toolchainname', 
        "ToolChain Version" : 'tc.toolchainversion', 
        "Flags": 'tc.flags',
        "SMT" : 'b.smt',
        "Cores": 'b.cores',
        "Corefreq": 'b.corefreq',
        "DDRfreq": 'b.ddrfreq',
        "SKUID": 'n1.skuidname',
        "Hostname": 'o1.hostname',
    }
    table_map = {
        "Kernel Version": 'ostunings os', 
        'OS Version': 'ostunings os', 
        'OS Name': 'ostunings os', 
        "Firmware Version": 'hwdetails hw', 
        "ToolChain Name": 'toolchain tc', 
        "ToolChain Version" : 'toolchain tc', 
        "Flags": 'toolchain tc',
        "SMT" : 'bootenv b',
        "Cores": 'bootenv b',
        "Corefreq": 'bootenv b',
        "DDRfreq": 'bootenv b',
        "SKUID": 'node n1',
        "Hostname": 'origin o1'
    }
    join_on_map = {
        'Kernel Version': 'o.ostunings_ostuningsID = os.ostuningsID', 
        'OS Version': 'o.ostunings_ostuningsID = os.ostuningsID', 
        'OS Name': 'o.ostunings_ostuningsID = os.ostuningsID',
        "Firmware Version": 'o.hwdetails_hwdetailsID = hw.hwdetailsID', 
        "ToolChain Name": 'o.toolchain_toolchainID = tc.toolchainID', 
        "ToolChain Version" : 'o.toolchain_toolchainID = tc.toolchainID', 
        "Flags": 'o.toolchain_toolchainID = tc.toolchainID',
        "SMT" : 'o.hwdetails_bootenv_bootenvID = b.bootenvID',
        "Cores": 'o.hwdetails_bootenv_bootenvID = b.bootenvID',
        "Corefreq": 'o.hwdetails_bootenv_bootenvID = b.bootenvID',
        "DDRfreq": 'o.hwdetails_bootenv_bootenvID = b.bootenvID',
        "SKUID": 'o.hwdetails_node_nodeID = n1.nodeID',
        "Hostname" : 'o1.originID = o.originID'
    }

    server_cpu_list = []

    # List of lists
    # Each list has entries for a single CPU Manufacturer
    x_list_list = []
    y_list_list = []
    originID_list_list = []

    # For each cpu manufacturer
    for section in sku_parser.sections():
        skus = sku_parser.get(section, 'SKUID').replace('\"','').split(',')

        X_LIST_QUERY = "SELECT DISTINCT " + parameter_map[xParameter] + " as \'" + parameter_map[xParameter] + \
                        "\' from " + table_map[xParameter] + " INNER JOIN origin o ON " + \
                        join_on_map[xParameter] + """ INNER JOIN result r ON o.originID = r.origin_originID 
                        INNER JOIN testdescriptor t ON t.testdescriptorID=o.testdescriptor_testdescriptorID 
                        WHERE t.testname=\'""" + testname + "\';"

        x_df = pd.read_sql(X_LIST_QUERY, db)
        x_list = sorted(x_df[parameter_map[xParameter]].to_list())
        
        # Convert each element to type "str"
        x_list = list(map(lambda x: str(x), x_list))

        
        # Remove ALL the entries which are '' in the list 
        while True:
            try:
                x_list.remove('')
            except:
                break

        logging.debug("\nAFTER REMOVING wrong entries \n")
        logging.debug("\nPRINTING X LIST  = {}".format(x_list))

        y_list = []
        originID_list = []
        skuid_list = []     

        # For removing 'not found' entries from x_list
        x_list_rm = []
        
        for x_param in x_list:
            # max or min
            if min_or_max_list[index] == '0':
                Y_LIST_QUERY = """SELECT MIN(r.number) as number, o.originID as originID, n.skuidname as skuidname 
                                    FROM result r INNER JOIN origin o on o.originID = r.origin_originID 
                                    INNER JOIN """ + table_map[xParameter] + " ON " + join_on_map[xParameter] + \
                                    """ INNER JOIN display disp ON  r.display_displayID = disp.displayID 
                                    INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID 
                                    INNER JOIN hwdetails hw1 ON o.hwdetails_hwdetailsID = hw1.hwdetailsID
                                    INNER JOIN node n ON hw1.node_nodeID = n.nodeID 
                                    INNER JOIN subtest s ON r.subtest_subtestID=s.subtestID 
                                    WHERE n.skuidname in """ + str(skus).replace('[', '(').replace(']', ')') + \
                                    " and " + parameter_map[xParameter] + " = \'" + x_param + \
                                    "\' and t.testname = \'" + testname + \
                                    "\' AND r.number > 0 AND r.isvalid = 1 AND disp.qualifier LIKE \'%" + qualifier_list[index] + "%\'" + \
                                    INPUT_FILTER_CONDITION + \
                                    " group by " + parameter_map[xParameter]  + ", o.originID, n.skuidname, r.number order by r.number limit 1;"
            else:
                Y_LIST_QUERY = """SELECT MAX(r.number) as number, o.originID as originID, n.skuidname as skuidname 
                                    FROM result r INNER JOIN origin o on o.originID = r.origin_originID 
                                    INNER JOIN """ + table_map[xParameter] + " ON " + join_on_map[xParameter] + \
                                    """ INNER JOIN display disp ON  r.display_displayID = disp.displayID 
                                    INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID  
                                    INNER JOIN hwdetails hw1 ON o.hwdetails_hwdetailsID = hw1.hwdetailsID
                                    INNER JOIN node n ON hw1.node_nodeID = n.nodeID 
                                    INNER JOIN subtest s ON r.subtest_subtestID=s.subtestID 
                                    WHERE n.skuidname in """ + str(skus).replace('[', '(').replace(']', ')') + \
                                    " and " + parameter_map[xParameter] + " = \'" + x_param + \
                                    "\' and t.testname = \'" + testname + "\' AND r.isvalid = 1 " + \
                                    " AND disp.qualifier LIKE \'%" + qualifier_list[index] + "%\'" + \
                                    INPUT_FILTER_CONDITION + \
                                    " group by " + parameter_map[xParameter]  + ", o.originID, n.skuidname, r.number order by r.number DESC limit 1;"

            y_df = pd.read_sql(Y_LIST_QUERY, db)

            if y_df.empty is True:
                x_list_rm.append(x_param)
            else:
                y_list.extend(y_df['number'].to_list())
                originID_list.extend(y_df['originID'].to_list())
                skuid_list.extend(y_df['skuidname'].to_list())
                skuid_list[-1] = skuid_list[-1].strip()

        logging.debug("PRINTING Y LIST = {}".format(y_list))
        logging.debug("PRINTING ORIGIN LIST= {}".format(originID_list))
        logging.debug("PRINTING SKUID LIST = {}".format(skuid_list))

        # Remove all the entries where skuid = ''
        while True:
            try:
                index = skuid_list.index('')
                skuid_list.remove(skuid_list[index])
                y_list.remove(y_list[index])
                originID_list.remove(originID_list[index])
            except:
                logging.debug("DONE REMOVING")
                break
    
        logging.debug("\n\n###############\n\nPrinting after removing wrong entries")
        logging.debug("PRINTING Y LIST = {}".format(y_list))
        logging.debug("PRINTING ORIGIN LIST = {}".format(originID_list))
        logging.debug("PRINTING SKUID LIST = {}".format(skuid_list))

        #Remove everything that has an empty set returned
        for rm_elem in x_list_rm:
            x_list.remove(rm_elem)

        # Do not append Empty Lists
        if(x_list):
            x_list_list.append(x_list)
            y_list_list.append(y_list)
            originID_list_list.append(originID_list)
            server_cpu_list.append(section)


    logging.debug("PRINTING FINAL SERVER CPU LIST")
    logging.debug("= {}".format(server_cpu_list))
    # Get colours for cpu manufacturer
    color_list = []
    visibile_list = []
    for section in server_cpu_list:
        color_list.extend(sku_parser.get(section, 'color').replace('\"','').split(','))
        visibile_list.extend(sku_parser.get(section, 'visible').replace('\"','').split(','))
    logging.debug("= {}".format(color_list))
    logging.debug("= {}".format(visibile_list))

    # Get the unit for the selected yParamter (qualifier)
    UNIT_QUERY = """SELECT disp.qualifier, disp.unit FROM origin o INNER JOIN testdescriptor t 
                    ON t.testdescriptorID=o.testdescriptor_testdescriptorID  INNER JOIN result r 
                    ON o.originID = r.origin_originID  INNER JOIN display disp ON  r.display_displayID = disp.displayID 
                    where t.testname = \'""" + testname + "\' and disp.qualifier LIKE \'%" + yParameter.strip() +"%\' limit 1;"
    unit_df = pd.read_sql(UNIT_QUERY, db)
    try:
        y_axis_unit = unit_df['unit'][0]
    except Exception as error_message:
        logging.debug("\n\n\n\n\n\n\nTHERE SEEMES TO BE AN ERROR IN YOUR APPLICATOIN")
        logging.debug("= {}".format(error_message))

    response = {
        'x_list_list': x_list_list, 
        'y_list_list': y_list_list,
        'y_axis_unit': y_axis_unit,
        'xParameter': xParameter,
        'yParameter': yParameter,
        'originID_list_list': originID_list_list,
        'server_cpu_list': server_cpu_list,
        'color_list': color_list,
        'visible_list':visibile_list,
    }

    # close the database connection
    try:
        print("CLOSING CONNECTION FOR get_data_for_graph {}".format(testname))
        db.close()
    except:
        pass

    return response

# This function handles the AJAX request for Best SKU Graph data.
# JS then draws the graph using this data
@app.route('/best_sku_graph', methods=['POST'])
def best_sku_graph():
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

    data = request.get_json()
    xParameter = data['xParameter']
    yParameter = data['yParameter']
    testname = data['testname']

    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    # For the input filters
    input_parameters = results_metadata_parser.get(testname, 'description') \
                                                .replace('\"', '').replace(' ', '').split(',')
    try:
        input_filters_list = data['inputFiltersList']
        
        INPUT_FILTER_CONDITION = ""
        for index, input_filter in enumerate(input_filters_list):
            if(input_filter != "None"):
                if(input_filter.isnumeric()):
                    INPUT_FILTER_CONDITION += " and SUBSTRING_INDEX(SUBSTRING_INDEX(s.description,','," + str(index+1) +"),',',-1)=" + input_filter 
                else:
                    INPUT_FILTER_CONDITION += " and SUBSTRING_INDEX(SUBSTRING_INDEX(s.description,','," + str(index+1) +"),',',-1)=\'" + input_filter  + "\'"
    except:
        pass

    # GET First qualifier from 'fields' and its corresponding min_or_max from 'higher_is_better' for section 'testname'
    qualifier = results_metadata_parser.get(testname, 'fields').replace('\"', '').split(',')[0]
    min_or_max = results_metadata_parser.get(testname, 'higher_is_better') \
                    .replace('\"', '').replace(' ', '').split(',')[0]


    sku_file_path = '/mnt/nas/scripts/sku_definition.ini'
    sku_parser = configparser.ConfigParser()
    sku_parser.read(sku_file_path)

    cpu_data = OrderedDict({section: None for section in sku_parser.sections()})
    originID_list = []
    rm_key_list = []

    for section in cpu_data:
        skuid_list = sku_parser.get(section, 'SKUID').replace('\"', '').split(',')
        if min_or_max == '0':
            # Fix this hack
            BEST_RESULT_QUERY = """SELECT MIN(r.number) as number, o.originID as originID from origin o inner join hwdetails hw
                                    on hw.hwdetailsID = o.hwdetails_hwdetailsID inner join node n
                                    on n.nodeID = hw.node_nodeID inner join testdescriptor t
                                    on t.testdescriptorID = o.testdescriptor_testdescriptorID inner join result r
                                    on r.origin_originID = o.originID INNER JOIN display disp 
                                    ON  r.display_displayID = disp.displayID INNER JOIN subtest s 
                                    ON r.subtest_subtestID=s.subtestID where r.number > 0 AND r.isvalid = 1 
                                    AND t.testname = \'""" + testname + "\' AND disp.qualifier LIKE \'%" + qualifier + \
                                    "%\' AND n.skuidname in """ + str(skuid_list).replace('[', '(').replace(']', ')') + \
                                    INPUT_FILTER_CONDITION + \
                                    " group by o.originID, r.number order by r.number;"

        else:
            BEST_RESULT_QUERY = """SELECT MAX(r.number) as number, o.originID as originID from origin o inner join hwdetails hw
                                    on hw.hwdetailsID = o.hwdetails_hwdetailsID inner join node n
                                    on n.nodeID = hw.node_nodeID inner join testdescriptor t
                                    on t.testdescriptorID = o.testdescriptor_testdescriptorID inner join result r
                                    on r.origin_originID = o.originID INNER JOIN display disp 
                                    ON  r.display_displayID = disp.displayID INNER JOIN subtest s 
                                    ON r.subtest_subtestID=s.subtestID where r.isvalid = 1 
                                    AND t.testname = \'""" + testname + "\' AND disp.qualifier LIKE \'%" + qualifier + \
                                    "%\' AND n.skuidname in """ + str(skuid_list).replace('[', '(').replace(']', ')') + \
                                    INPUT_FILTER_CONDITION + \
                                    " group by o.originID, r.number order by r.number DESC;"


        results_df = pd.read_sql(BEST_RESULT_QUERY, db)
        if results_df.empty is True:
            rm_key_list.append(section)
        else:
            cpu_data[section] = results_df['number'].to_list()[0]
            originID_list.append(results_df['originID'].to_list()[0])

    logging.debug("= {}".format(cpu_data))
    logging.debug("ORIGIN ID LIST IN BEST RESULTS GRAPH")
    logging.debug("= {}".format(originID_list))

    # Remove the entries from dictionary whose values are empty
    
    for key in rm_key_list:
        del cpu_data[key]

    color_list = []
    for section in cpu_data:
        color_list.extend(sku_parser.get(section, 'color').replace('\"','').split(','))
    logging.debug("= {}".format(color_list))

    # Get the unit for the selected yParamter (qualifier)
    UNIT_QUERY = """SELECT disp.qualifier, disp.unit FROM origin o INNER JOIN testdescriptor t 
                    ON t.testdescriptorID=o.testdescriptor_testdescriptorID  INNER JOIN result r 
                    ON o.originID = r.origin_originID  INNER JOIN display disp ON  r.display_displayID = disp.displayID 
                    where t.testname = \'""" + testname + "\' and disp.qualifier LIKE \'%" + qualifier +"%\' limit 1;"
    unit_df = pd.read_sql(UNIT_QUERY, db)
    y_axis_unit = unit_df['unit'][0]

    response = {
        'x_list': list(cpu_data.keys()), 
        'y_list': list(cpu_data.values()),
        'y_axis_unit': y_axis_unit,
        'color_list': color_list,
        'xParameter': xParameter,
        'yParameter': 'Best ' + qualifier,
        'originID_list': originID_list,
        'higher_is_better': min_or_max,
    }

    # close the database connection
    try:
        db.close()
    except:
        pass

    return response

# Returns the NORMALIZED version of the graph with respect to a xParameter
@app.route('/best_sku_graph_normalized', methods=['POST'])
def best_sku_graph_normalized():
    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    data = request.get_json()

    # X-Axis, Y-Axis values lists and its parameters
    x_list = data['xList']
    y_list = data['yList']
    xParameter = data['xParameter']
    yParameter = data['yParameter']
    originID_list = data['originIDList']
    testname = data['testname']

    # Normalized with respect to this parameter
    normalized_wrt = data['normalizedWRT']

    # Higher is better => 0 or 1
    higher_is_better = results_metadata_parser.get(testname, 'higher_is_better') \
                        .replace('\"', '').replace(' ', '').split(',')[0]

    # If lower is better, then take the inverse of the normalized values
    index = x_list.index(normalized_wrt)
    logging.debug("PRINTING X LIST= {}".format(x_list))
    logging.debug("FOUND AT INDEX = {}".format(index))
    if higher_is_better == "1":
        logging.debug("HIGHER IS BETTER")
        normalized_y_list = [value/y_list[index] for value in y_list]
    else:
        # Inverse
        logging.debug("LOWER IS BETTER")
        normalized_y_list = [y_list[index]/value for value in y_list]

    # Colors for the graphs
    sku_file_path = '/mnt/nas/scripts/sku_definition.ini'
    sku_parser = configparser.ConfigParser()
    sku_parser.read(sku_file_path)

    color_list = []
    for section in x_list:
        color_list.extend(sku_parser.get(section, 'color').replace('\"','').split(','))
    logging.debug(" = {}".format(color_list))

    logging.debug("Normalized Y list = {}".format(normalized_y_list))

    response = {
        'x_list': x_list, 
        'y_list': normalized_y_list,
        'y_axis_unit': "ratio",
        'color_list': color_list,
        'xParameter': xParameter,
        'yParameter': yParameter,
        'originID_list': originID_list,
        'higher_is_better': higher_is_better,
    }

    return response

@app.route('/best_of_all_graph', methods=['POST'])
def best_of_all_graph():
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                     passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

    # Just for testing the speed
    start_time = time.time()

    wiki_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(wiki_metadata_file_path)    

    sku_file_path = '/mnt/nas/scripts/sku_definition.ini'
    sku_parser = configparser.ConfigParser()
    sku_parser.read(sku_file_path)

    data = request.get_json()
    
    logging.debug(" = {}".format(data))

    # Apply DATE - FILTERS
    from_date = data['from_date_filter']
    to_date = data['to_date_filter']
    print(" = {}".format(from_date))
    print(" = {}".format(to_date))

    if from_date:
        FROM_DATE_FILTER = " and o.testdate > \'" + from_date + " 00:00:00\' "
    else:
        print("empty")
        FROM_DATE_FILTER = " "

    if to_date:
        TO_DATE_FILTER = " and o.testdate < \'" + to_date + " 23:59:59\' "
    else:
        print("empty")
        TO_DATE_FILTER = " "


    normalized_wrt = data['normalizedWRT']

    # If No filters are applied, select all tests
    try:
        test_name_list = [test_name.strip() for test_name in data['test_name_list']]

        # If test_name_list is empty, read everything
        if(not test_name_list):
            raise Exception
    except:
        # Read all test names from .ini file
        test_name_list = [test_name.strip() for test_name in results_metadata_parser.sections()]

    # The list of the first qualifier for all tests
    # and the corresponding higher_is_better
    qualifier_list = [results_metadata_parser.get(test_name, 'fields').replace('\"', '').split(',')[0] for test_name in test_name_list]
    higher_is_better_list = [results_metadata_parser.get(test_name, 'higher_is_better').replace('\"', '').replace(' ','').split(',')[0] for test_name in test_name_list]

    # Remove all the entries where fields = ""
    while True:
        try:
            index = qualifier_list.index('')
            qualifier_list.remove(qualifier_list[index])
            higher_is_better_list.remove(higher_is_better_list[index])
            test_name_list.remove(test_name_list[index])
        except:
            logging.debug("DONE REMOVING")
            break

    # logging.debug(" = {}".format(test_name_list))
    # logging.debug(" = {}".format(qualifier_list))
    #logging.debug(" = {}".format(higher_is_better_list))

    # Create a reference_results_map having entries for "testname" -> best_result
    # This will be for the selected reference CPU manufacturer i.e. normalized_wrt
    reference_results_map = {test_name: None for test_name in test_name_list}

    # Get colour and skuid_list for reference Cpu 
    reference_color = sku_parser.get(normalized_wrt, 'color').replace('\"', '').split(',')[0]
    reference_skuid_list = sku_parser.get(normalized_wrt, 'SKUID').replace('\"', '').split(',')
    
    for test_name, qualifier, higher_is_better in zip(test_name_list, qualifier_list, higher_is_better_list):
        # Get input_filter_condition by calling the function
        input_filters_list = results_metadata_parser.get(test_name, 'default_input') \
                                                    .replace('\"', '').split(',')
        INPUT_FILTER_CONDITION = get_input_filter_condition(test_name, input_filters_list)

        # Build the query along with the input filters condition
        if higher_is_better == '0':
            # Fix this hack
            # logging.debug("SELECTING MIN = {}".format(higher_is_better))
            BEST_RESULT_QUERY = """SELECT MIN(r.number) as number, o.originID as originID from origin o inner join hwdetails hw
                                    on hw.hwdetailsID = o.hwdetails_hwdetailsID inner join node n
                                    on n.nodeID = hw.node_nodeID inner join testdescriptor t
                                    on t.testdescriptorID = o.testdescriptor_testdescriptorID inner join result r
                                    on r.origin_originID = o.originID INNER JOIN display disp 
                                    ON  r.display_displayID = disp.displayID INNER JOIN subtest s 
                                    ON r.subtest_subtestID=s.subtestID where r.number > 0 AND r.isvalid = 1 
                                    AND t.testname = \'""" + test_name + "\' AND disp.qualifier LIKE \'%" + qualifier + \
                                    "%\' AND n.skuidname in """ + str(reference_skuid_list).replace('[', '(').replace(']', ')') + \
                                    INPUT_FILTER_CONDITION + \
                                    FROM_DATE_FILTER + \
                                    TO_DATE_FILTER + \
                                    " group by o.originID, r.number order by r.number limit 1;"

        else:
            # logging.debug("SELECTING MAX = {}".format(higher_is_better))
            BEST_RESULT_QUERY = """SELECT MAX(r.number) as number, o.originID as originID from origin o inner join hwdetails hw
                                    on hw.hwdetailsID = o.hwdetails_hwdetailsID inner join node n
                                    on n.nodeID = hw.node_nodeID inner join testdescriptor t
                                    on t.testdescriptorID = o.testdescriptor_testdescriptorID inner join result r
                                    on r.origin_originID = o.originID INNER JOIN display disp 
                                    ON  r.display_displayID = disp.displayID INNER JOIN subtest s 
                                    ON r.subtest_subtestID=s.subtestID where r.isvalid = 1 
                                    AND t.testname = \'""" + test_name + "\' AND disp.qualifier LIKE \'%" + qualifier + \
                                    "%\' AND n.skuidname in """ + str(reference_skuid_list).replace('[', '(').replace(']', ')') + \
                                    INPUT_FILTER_CONDITION + \
                                    FROM_DATE_FILTER + \
                                    TO_DATE_FILTER + \
                                    " group by o.originID, r.number order by r.number DESC limit 1;"


        results_df = pd.read_sql(BEST_RESULT_QUERY, db)
        # logging.debug("PRINTING RESULTS DF for= {}".format(test_name))
        # logging.debug("= {}".format(results_df))

        if not results_df.empty:
            reference_results_map[test_name] = results_df['number'][0]

    # logging.debug("\n\nPRINTING FINAL REFERENCE MAP")
    for k,v in reference_results_map.items():
        if v:
            # logging.debug("{} : {}".format(k,v))
            pass


    x_list_list = []
    y_list_list = []
    originID_list_list = []
    server_cpu_list = []
    color_list = []
    # Start querying the database for best of each CPU MANUFACTURER
    for section in sku_parser.sections():
        # Only for sections other than selected 'reference'
        if section != normalized_wrt:
            # logging.debug("SECTION DID NOT MATCH. Proceeding with queries {} : {}  ".format(section, normalized_wrt))
            skuid_list = sku_parser.get(section, 'SKUID').replace('\"', '').split(',')
            x_list = []
            y_list = []
            originID_list = []

            for test_name, qualifier, higher_is_better in zip(test_name_list, qualifier_list, higher_is_better_list):
                # If the test_result is not Empty (None) in the reference_results_map
                if reference_results_map[test_name]:
                    # Get input_filter_condition by calling the function
                    input_filters_list = results_metadata_parser.get(test_name, 'default_input') \
                                                                .replace('\"', '').split(',')                                                    
                    INPUT_FILTER_CONDITION = get_input_filter_condition(test_name, input_filters_list)


                    # logging.debug("RESULT {} exists in REFERENCE".format(test_name))
                    if higher_is_better == '0':
                        # Fix this hack
                        BEST_RESULT_QUERY = """SELECT MIN(r.number) as number, o.originID as originID from origin o inner join hwdetails hw
                                                on hw.hwdetailsID = o.hwdetails_hwdetailsID inner join node n
                                                on n.nodeID = hw.node_nodeID inner join testdescriptor t
                                                on t.testdescriptorID = o.testdescriptor_testdescriptorID inner join result r
                                                on r.origin_originID = o.originID INNER JOIN display disp 
                                                ON  r.display_displayID = disp.displayID INNER JOIN subtest s 
                                                ON r.subtest_subtestID=s.subtestID where r.number > 0 AND r.isvalid = 1 
                                                AND t.testname = \'""" + test_name + "\' AND disp.qualifier LIKE \'%" + qualifier + \
                                                "%\' AND n.skuidname in """ + str(skuid_list).replace('[', '(').replace(']', ')') + \
                                                INPUT_FILTER_CONDITION + \
                                                FROM_DATE_FILTER + \
                                                TO_DATE_FILTER + \
                                                " group by o.originID, r.number order by r.number limit 1;"

                    else:
                        BEST_RESULT_QUERY = """SELECT MAX(r.number) as number, o.originID as originID from origin o inner join hwdetails hw
                                                on hw.hwdetailsID = o.hwdetails_hwdetailsID inner join node n
                                                on n.nodeID = hw.node_nodeID inner join testdescriptor t
                                                on t.testdescriptorID = o.testdescriptor_testdescriptorID inner join result r
                                                on r.origin_originID = o.originID INNER JOIN display disp 
                                                ON  r.display_displayID = disp.displayID INNER JOIN subtest s 
                                                ON r.subtest_subtestID=s.subtestID where r.isvalid = 1 
                                                AND t.testname = \'""" + test_name + "\' AND disp.qualifier LIKE \'%" + qualifier + \
                                                "%\' AND n.skuidname in """ + str(skuid_list).replace('[', '(').replace(']', ')') + \
                                                INPUT_FILTER_CONDITION + \
                                                FROM_DATE_FILTER + \
                                                TO_DATE_FILTER + \
                                                " group by o.originID, r.number order by r.number DESC limit 1;"
            

                    results_df = pd.read_sql(BEST_RESULT_QUERY, db)
                    # logging.debug("\n\n########################\n\nPRINTING RESULTS DF for ={}".format(section))
                    # logging.debug(" ={}".format(results_df))

                    # A function which returns the normalized value y_list[-1] w.r.t. reference_results_map[test_name] 
                    def normalized_value():
                        try:
                            # Take inverse if lower is better
                            if higher_is_better == '0':
                                return reference_results_map[test_name]/y_list[-1]
                            else:
                                return y_list[-1]/reference_results_map[test_name]
                        except:
                            # If divide by zero what to do????
                            pass

                    if not results_df.empty:
                        # logging.debug("ENTERING")
                        x_list.append(test_name)
                        y_list.extend(results_df['number'])
                        logging.debug("Y_LIST ={}".format(y_list, test_name))

                        # Normalize IT
                        y_list[-1] = normalized_value()
                        logging.debug("AFTER NORMALIZING")
                        logging.debug("Y_LIST ={} {}".format(y_list, test_name))
                        originID_list.extend(results_df['originID'])
                    else:
                        pass
                        # logging.debug("NOT ENTERING")

                else:
                    pass
                    # logging.debug("######################RESULT {} DOES NOT EXIST in REFERENCE".format(test_name))
                
            logging.debug("\n\n####################\nSection: {} \n\nAPPENDING Y_LIST : {}".format(section, y_list))
            x_list_list.append(x_list)
            y_list_list.append(y_list)
            originID_list_list.append(originID_list)
            server_cpu_list.append(section)
            color_list.extend(sku_parser.get(section, 'color').replace('\"','').split(','))

        else:
            logging.debug("SECTION MATCHED {} .\tSkipping".format(section))


    response = {
        'x_list_list': x_list_list, 
        'y_list_list': y_list_list,
        'y_axis_unit': "ratio",
        'xParameter': "All Tests",
        'yParameter': "",
        'originID_list_list': originID_list_list,
        'server_cpu_list': server_cpu_list,
        'color_list': color_list,
        'reference_color' : reference_color,
        'normalized_wrt' : normalized_wrt,
    }

    # close the database connection
    try:
        db.close()
    except:
        pass

    print("Best of All Graph took {} seconds".format(time.time() - start_time))    

    return response

@app.route('/counter_graphs', methods=['POST'])
def counter_graphs():
    start_time = time.time()
    data = request.get_json()

    logging.debug("DATA = {}".format(data))

    jobname = data['jobname']
    runID = data['runID']
    numCPUs = data['numCPUs']

    # Generate nas_path from received data
    nas_path = "/mnt/nas/dbresults/" + jobname + '/' + runID + '/results/' + numCPUs;
    logging.debug("NAS PATH = {}".format(nas_path))

    # Get counter_graphs_data from the nas_path
    counter_graphs_data = counter_graphs_module.process_perf_stat_files(nas_path, numCPUs)

    logging.debug("COUNTERS HISTOGRAM DATA")
    logging.debug(counter_graphs_data['dmc_histogram_data_' + numCPUs])

    logging.debug("IT took {} seconds for counter graph".format(time.time() - start_time))

    return counter_graphs_data

@app.route('/cpu_utilization_graphs', methods=['POST'])
def cpu_utilization_graphs():
    print("Got request for heatmap")
    start_time = time.time()

    data = request.get_json()
    print("DATA = {}".format(data))

    # Generate nas_path from received data
    nas_path = "/mnt/nas/dbresults/" + data['jobname'] + '/' + data['runID'] + '/results/CPU_heatmap.csv'
    logging.debug("NAS PATH = {}".format(nas_path))

    cpu_utilization_df = pd.read_csv(nas_path, usecols=['timestamp','CPU', '%idle'])

    cpu_utilization_df['%busy'] = cpu_utilization_df['%idle'].apply(lambda x: 100 - x)
    cpu_utilization_df.pop('%idle')

    try:
        # Get data for bar graph from average_cpu_ut_df
        bar_graph_data = {
            'graph_type' : 'bar',
            'x_list' : [],
            'y_list' : [],
            'xParameter' : 'Cores',
            'yParameter' : 'AVG. % Utilization'
        }

        cpu_utilization_df = cpu_utilization_df.set_index('timestamp')
        # For bar graph having average entries of all Cores and average of 'all'
        average_cpu_ut_df = cpu_utilization_df.loc['Average:']
        # Drop all those columns
        cpu_utilization_df = cpu_utilization_df.drop('Average:')

        bar_graph_data['x_list'] = average_cpu_ut_df['CPU'].tolist()
        bar_graph_data['y_list'] = average_cpu_ut_df['%busy'].tolist()
        # Bar graph is done
    except:
        pass
    finally:
        # Reset index
        cpu_utilization_df = cpu_utilization_df.reset_index()

    # Set 'CPU' as index
    cpu_utilization_df = cpu_utilization_df.set_index('CPU')
    # AVG. Data of all cores at all timestamps
    all_cores_df = cpu_utilization_df.loc['all']
    # Drop all those columns
    cpu_utilization_df = cpu_utilization_df.drop('all')
    # Reset index
    cpu_utilization_df = cpu_utilization_df.reset_index()

    # Get data for heatmap
    heatmap_data = {
        'graph_type' : 'heatmap',
        'x_list' : [],
        'y_list' : [],
        'z_list_list' : [],
        'xParameter' : 'Timestamp',
        'yParameter' : 'Cores'
    }

    heatmap_data['x_list'] = cpu_utilization_df['timestamp'].unique().tolist()
    heatmap_data['y_list'] = cpu_utilization_df['CPU'].unique().tolist()

    heatmap_data['z_list_list'] = [cpu_utilization_df['%busy'].tolist()[x:x+len(heatmap_data['y_list'])]\
                                for x in range(0,len(cpu_utilization_df['%busy']), len(heatmap_data['y_list']))]

    # Take transpose of the list_list
    heatmap_data['z_list_list'] = np.array(heatmap_data['z_list_list']).T.tolist()
    # Heatmap is done

    # Get data for line graph from all_cores_df
    line_graph_data = {
        'graph_type' : 'line',
        'x_list_list' : [],
        'y_list_list' : [],     #list_list because the JS function is written for multiple lines
        'xParameter' : 'Timestamp',
        'yParameter' : '% Utilization'
    }
    line_graph_data['x_list_list'].append(all_cores_df['timestamp'].tolist())
    line_graph_data['y_list_list'].append(all_cores_df['%busy'].tolist())
    # Line graph data is done
    

    cpu_ut_graphs_data = {
        '1) heatmap_data' : heatmap_data,
        '2) line_graph_data' : line_graph_data,
        '3) bar_graph_data' : bar_graph_data,
    }

    logging.debug("Time taken {}".format(time.time() - start_time))

    return cpu_ut_graphs_data


# One function for downloading everything as CSV
@app.route('/download_as_csv', methods=['POST'])
def download_as_csv():
    logging.debug("\n\n\n#REQUEST#########")
    logging.debug("= {}".format(request))
    logging.debug("= {}".format(request.form))
    json_data = json.loads(request.form.get('data'))
    logging.debug("JSON STATHAM")
    logging.debug(" = {}".format(json_data))
    data = json_data['data']

    logging.debug(" = {}".format(data))
    logging.debug(" = {}".format(type(data)))
    logging.debug("\n\n\n")

    csv_df = pd.DataFrame(columns=data.keys());

    for column in data:
        csv_df[column] = data[column]

    # Clear the csv_temp_files directory
    base_path = os.getcwd() + '/csv_temp_files/'
    shutil.rmtree(base_path)    #this removes the directory too
    os.mkdir(base_path)         #So create it again

    # Save the current csv file there
    logging.debug("= {}".format(csv_df))
    logging.debug(" = {}".format(os.getcwd()))

    # "CLEAN" the filename.
    # Example -> if the file is 'Mop/s vs OSName', then replace '/' with '-per-'
    filename = base_path + json_data['filename'].replace('/', '_per_') + '.csv'
    
    logging.debug("PRINTING FILENAME AFTER = {}".format(filename))

    csv_df.to_csv(filename, index=False, header=True)
    logging.debug("\n\n\n")

    try:
        return send_file(filename,
            mimetype='text/csv',
            attachment_filename= json_data['filename'].replace('/', '_per_') + '.csv',
            as_attachment=True)

    except Exception as error_message:
        return error_message, 404
