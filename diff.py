from pprint import pprint
import os
import pandas as pd
import pymysql
import configparser
from flask import Flask, render_template, request, redirect
from collections import OrderedDict
import csv

# from datetime import datetime
app = Flask(__name__)
pd.set_option('display.max_rows', 500)

#RETURNS the Table name for the given 'index' from the dictionary of lists
#example : from 'origin_param_list' -> return 'origin'
@app.context_processor
def table_name():
    def _table_name(list_of_keys, index):
        tablename = list(list_of_keys)[index]
        if(tablename == "ram_details_param_list"):
            return "RAM_details"
        return tablename[0: tablename.find("_param_list")].capitalize()
    return dict(table_name=_table_name)

#RESERVED FOR LATER (Not important as of now. DO it if time permits)
# @app.template_filter('readable_timestamp')
# def readable_timestamp(timestamp):
#     #type of timestamp is <class 'pandas._libs.tslibs.timestamps.Timestamp'>
#     dt = timestamp.to_pydatetime();
#     return dt.strftime("%d %B, %Y %I:%M:%S %p")

@app.template_filter('no_of_rows')
def no_of_rows(dictionary):
    #this is a dictionary of lists
    #return length of the first list in the dictionary
    #fastest way
    return len(dictionary[next(iter(dictionary))])

def read_all_parameter_lists(parameter_lists, test_name):
    db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)

    # read metadata from metadata.ini file
    env_metadata_file_path = '/mnt/nas/scripts/metadata.ini'
    env_metadata_parser = configparser.ConfigParser()
    env_metadata_parser.read(env_metadata_file_path)

    #Read metadata for results in wiki_description.ini file
    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)    

    #Fill all parameter Lists in the dictionary
    for param_list_name in parameter_lists:
        if param_list_name == 'results_param_list':
            parameter_lists[param_list_name] = results_metadata_parser.get(
                test_name, 'description').replace('\"','').replace(' ', '').split(',')
            parameter_lists[param_list_name].extend(['number','resultype','unit','qualifier'])

        elif param_list_name == 'qualifier':
            qualifier = results_metadata_parser.get(test_name, 'fields').replace('\"','').replace(' ', '').lower().split(',')[0]
        elif param_list_name == 'min_or_max':
            min_or_max = results_metadata_parser.get(test_name, 'higher_is_better').replace('\"','').replace(' ', '').split(',')[0]

        else:
            #extracts 'example' from 'example_param_list'
            env_param_name = param_list_name[0:param_list_name.find("_param_list")]

            parameter_lists[param_list_name] = env_metadata_parser.get(
            env_param_name, 'db_variables').replace(' ', '').split(',')
    return parameter_lists

def read_all_csv_files(compare_lists, parameter_lists, originID_compare_list):
    db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)

    JENKINS_QUERY = "SELECT J.jobname, J.runID FROM origin O INNER JOIN jenkins J ON O.jenkins_jenkinsID=J.jenkinsID AND O.originID in " + str(originID_compare_list).replace('[','(').replace(']',')') + ";"
    jenkins_details = pd.read_sql(JENKINS_QUERY, db)

    jobname_list = jenkins_details['jobname'].to_list()
    runID_list = jenkins_details['runID'].to_list()

    #The path on which file is to be read
    file_path = "/mnt/nas/dbresults/"

    #Fill all lists in the dictionary
    for i in range(len(originID_compare_list)):
        for j in range(len(compare_lists)):
            param_values_dictionary = dict()
            list_of_keys = list(compare_lists.keys())
            table_name = list_of_keys[j][0:list_of_keys[j].find("_list")]

            #Check if the file exists
            if(os.path.exists(file_path+str(jobname_list[i])+'/'+str(runID_list[i]) + '/' + table_name + '.csv')):
                pass
            else:
                table_name = list_of_keys[j][0:list_of_keys[j].find("_details_list")]
            with open(file_path+str(jobname_list[i])+'/'+str(runID_list[i]) + '/' + table_name + '.csv', newline='') as csvfile:
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
            if(table_name + "_list" in compare_lists):
                compare_lists[table_name + "_list"].append(param_values_dictionary)
            else:
                compare_lists[table_name + "_details_list"].append(param_values_dictionary)
    return compare_lists


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
        print(section + ":" + parser.get(section, 'model'))
        type_of_benchmark = parser.get(section, 'model').strip()
        print(type(type_of_benchmark))
        if(type_of_benchmark == '\"hpc\"'):
            hpc_benchmarks_list.append(section)
        else:
            cloud_benchmarks_list.append(section)

    print(hpc_benchmarks_list)
    print("\n\n\n")
    print(cloud_benchmarks_list)

    hpc_benchmarks_list = sorted(hpc_benchmarks_list, key=str.lower)
    cloud_benchmarks_list = sorted(cloud_benchmarks_list, key=str.lower)
    context = {
        'hpc_benchmarks_list': hpc_benchmarks_list,
        'cloud_benchmarks_list': cloud_benchmarks_list,
    }
    return render_template('all-tests.html', context=context)

@app.route('/allruns/<testname>')
def showAllRuns(testname):
    #Read metadata for results in wiki_description.ini file
    results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    qualifier = results_metadata_parser.get(testname, 'fields').replace('\"','').split(',')[0]
    min_or_max = results_metadata_parser.get(testname, 'higher_is_better').replace('\"','').replace(' ', '').split(',')[0]

    print(qualifier)
    print(min_or_max)

    if(min_or_max == '0'):
        ALL_RUNS_QUERY = "SELECT DISTINCT o.originID, o.testdate, o.hostname, MIN(r.number) as BestResult, o.notes from result r INNER JOIN display disp ON  r.display_displayID = disp.displayID INNER JOIN origin o ON o.originID = r.origin_originID INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID where t.testname = \'" + \
            testname + "\' AND disp.qualifier LIKE \'%" +qualifier+ "%\' AND r.isvalid = 1 GROUP BY o.originID, o.testdate, o.hostname, o.notes ORDER BY o.originID DESC"
    else:
        ALL_RUNS_QUERY = "SELECT DISTINCT o.originID, o.testdate, o.hostname, MAX(r.number) as BestResult, o.notes from result r INNER JOIN display disp ON  r.display_displayID = disp.displayID INNER JOIN origin o ON o.originID = r.origin_originID INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID where t.testname = \'" + \
            testname + "\' AND disp.qualifier LIKE \'%" +qualifier+ "%\' AND r.isvalid = 1 GROUP BY o.originID, o.testdate, o.hostname, o.notes ORDER BY o.originID DESC"
    db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)

    dataframe = pd.read_sql(ALL_RUNS_QUERY, db)
    rows, columns = dataframe.shape  # returns a tuple (rows,columns)

    context = {
        'testname': testname,
        'data': dataframe.to_dict(orient='list'),
        'no_of_rows': rows,
        'no_of_columns': columns,
    }

    return render_template('all-runs.html', context=context)

# View for handling Test details request
@app.route('/test-details/<originID>')
def showTestDetails(originID):
    db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)
    result_type_map = {0: "single thread", 1: 'single core',
                       2: 'single socket', 3: 'dual socket',
                       4: 'Scaling'}

    # Just get the TEST name
    TEST_NAME_QUERY = "SELECT t.testname FROM testdescriptor as t INNER JOIN origin o on o.testdescriptor_testdescriptorID=t.testdescriptorID WHERE o.originID=" + originID + ";"
    test_name_dataframe = pd.read_sql(TEST_NAME_QUERY, db)
    test_name = test_name_dataframe['testname'][0]

    # Get some System details
    SYSTEM_DETAILS_QUERY = "SELECT DISTINCT O.hostname, O.testdate, O.originID as 'Environment Details',  S.resultype FROM result R INNER JOIN subtest S ON S.subtestID=R.subtest_subtestID INNER JOIN origin O ON O.originID=R.origin_originID WHERE O.originID=" + originID + ";"
    system_details_dataframe = pd.read_sql(SYSTEM_DETAILS_QUERY, db)

    # Update the Result type (E.g. 0->single thread)
    system_details_dataframe.update(pd.DataFrame(
        {'resultype': [result_type_map[system_details_dataframe['resultype'][0]]]}))

    # Get the rest of the system details from jenkins table
    JENKINS_QUERY = "SELECT J.jobname, J.runID FROM origin O INNER JOIN jenkins J ON O.jenkins_jenkinsID=J.jenkinsID AND O.originID=" + originID + ";"
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

    # Read the subtests description from the wiki_description
    config_file = "/mnt/nas/scripts/wiki_description.ini"
    config_options = configparser.ConfigParser()
    config_options.read(config_file)
    config_sections = config_options.sections()
    if config_options.has_section(test_name):
        description_string = config_options[test_name]['description'].replace(
            '\"', '')
    else:
        description_string = 'Description'

    # RESULTS TABLE
    RESULTS_QUERY = "SELECT S.description, R.number, disp.unit, disp.qualifier FROM result R INNER JOIN subtest S ON S.subtestID=R.subtest_subtestID INNER JOIN display disp ON disp.displayID=R.display_displayID INNER JOIN origin O ON O.originID=R.origin_originID WHERE O.originID=" + originID + ";"
    results_dataframe = pd.read_sql(RESULTS_QUERY, db)

    for col in reversed(description_string.split(',')):
        results_dataframe.insert(0, col, 'default value')

    #CHANGE THIS STUPID ALGORITHM !!!!!!!!!!!!!!!!!!!!
    #USE LIST COMPREHENSIONS
    # https://chrisalbon.com/python/data_wrangling/pandas_list_comprehension/
    #For all the rows in the dataframe, set the description_list values
    for i in range(len(results_dataframe)):
        description_list = description_string.split(',')
        for j in range(len(description_list)):
            results_dataframe.at[i, description_list[j]] = results_dataframe.at[i, 'description'].split(',')[
                j]

    #Drop the 'description' column as we have now split it into various columns according to description_string
    del results_dataframe['description']
    
    #Debugging stuff
    # print(results_dataframe)
    # print("RESULTS ARE ABOVE THIS")

    context = {
        'testname': test_name,
        'system_details': system_details_dataframe.to_dict(orient='list'),
        'description_list': description_string.split(','),
        'results': results_dataframe.to_dict(orient='list'),
    }
    return render_template('test-details.html', context=context)

# View for handling Environment details request
@app.route('/environment-details/<originID>')
def showEnvDetails(originID):
    db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)
    HWDETAILS_QUERY = "SELECT H.fwversion, H.bmcversion, H.biosversion FROM hwdetails H INNER JOIN origin O ON O.hwdetails_hwdetailsID = H.hwdetailsID AND O.originID = " + originID + ";"
    hwdetails_dataframe = pd.read_sql(HWDETAILS_QUERY, db)

    TOOLCHAIN_DETAILS_QUERY = "SELECT T.toolchainname, T.toolchainversion, T.flags FROM toolchain as T INNER JOIN origin O ON O.toolchain_toolchainID = T.toolchainID AND O.originID = " + originID + ";"
    toolchain_dataframe = pd.read_sql(TOOLCHAIN_DETAILS_QUERY, db)

    OSTUNINGS_DETAILS_QUERY = "SELECT OS.osdistro, OS.osversion, OS.kernelname, OS.pagesize, OS.thp FROM ostunings OS INNER JOIN origin O ON O.ostunings_ostuningsID = OS.ostuningsID AND O.originID = " + originID + ";"
    ostunings_dataframe = pd.read_sql(OSTUNINGS_DETAILS_QUERY, db)

    NODE_DETAILS_QUERY = "SELECT N.numsockets, N.skuidname, N.cpuver, N.cpu0serial FROM node as N INNER JOIN hwdetails as H INNER JOIN origin O ON O.hwdetails_hwdetailsID = H.hwdetailsID AND N.nodeID = H.node_nodeID AND O.originID = " + originID + ";"
    node_dataframe = pd.read_sql(NODE_DETAILS_QUERY, db)

    BOOTENV_DETAILS_QUERY = "SELECT bootenv.corefreq, bootenv.ddrfreq, bootenv.memnetfreq, bootenv.smt, bootenv.turbo, bootenv.cores, bootenv.tdp FROM bootenv INNER JOIN hwdetails H  INNER JOIN origin O ON O.hwdetails_hwdetailsID = H.hwdetailsID AND H.bootenv_bootenvID = bootenv.bootenvID AND O.originID = " + originID + ";"
    bootenv_dataframe = pd.read_sql(BOOTENV_DETAILS_QUERY, db)

    ram_details = {}
    disk_details = {}
    nic_details = {}

    context = {
        'hwdetails': hwdetails_dataframe.to_dict(orient='list'),
        'toolchain': toolchain_dataframe.to_dict(orient='list'),
        'ostunings': ostunings_dataframe.to_dict(orient='list'),
        'node': node_dataframe.to_dict(orient='list'),
        'bootenv': bootenv_dataframe.to_dict(orient='list'),
        'ram':ram_details,
        'disk':disk_details,
        'nic':nic_details,
    }
    return render_template('environment-details.html', context=context)


@app.route('/diff', methods=['GET', 'POST'])
def diffTests():
    if request.method == "POST":
        db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)

        # take checked rows from table
        originID_compare_list = []
        
        for key, value in request.form.items():
            print(key, value)
            if("diff-checkbox" in key):
                originID_compare_list.append(value)

        originID_compare_list.sort()
        print(originID_compare_list)

        # #GET TEST NAMES LIST
        TEST_NAME_QUERY = "SELECT t.testname FROM testdescriptor as t INNER JOIN origin o on o.testdescriptor_testdescriptorID=t.testdescriptorID WHERE o.originID=" + originID_compare_list[0] + ";"
        test_name_dataframe = pd.read_sql(TEST_NAME_QUERY, db)
        test_name = test_name_dataframe['testname'][0]

        JENKINS_QUERY = "SELECT J.jobname, J.runID FROM origin O INNER JOIN jenkins J ON O.jenkins_jenkinsID=J.jenkinsID AND O.originID in " + str(originID_compare_list).replace('[','(').replace(']',')') + ";"
        jenkins_details = pd.read_sql(JENKINS_QUERY, db)

        jobname_list = jenkins_details['jobname'].to_list()
        runID_list = jenkins_details['runID'].to_list()

        # create all parameter lists
        parameter_lists = OrderedDict({
            'results_param_list' : [],
            'origin_param_list' : [],
            'bootenv_param_list' : [],
            'node_param_list' : [],
            'hwdetails_param_list' : [],
            'ostunings_param_list' : [],
            'toolchain_param_list' : [],
            'ram_details_param_list' : [],
            'nic_details_param_list' : [],
            'disk_details_param_list' : [],

            'qualifier' : None,
            'min_or_max': None,
        })

        parameter_lists = read_all_parameter_lists(parameter_lists, test_name)

        #removes 'qualifier' from parameter_lists and assigns to qualifier variable 
        qualifier = parameter_lists.pop('qualifier')
        min_or_max = parameter_lists.pop('min_or_max')

        # Dictionary of List of Dictionaries (tests) to be compared
        compare_lists = OrderedDict({
            'origin_list' : [],
            'bootenv_list' : [],
            'node_list' : [],
            'hwdetails_list' : [],
            'ostunings_list' : [],
            'toolchain_list' : [],
            'ram_details_list' : [],
            'nic_details_list' : [],
            'disk_details_list' : [],

        })


        #Read all results. Store in a dataframe
        join_on_columns_list = parameter_lists['results_param_list'][0:-4]
        join_on_columns_list.extend(['resultype','unit','qualifier'])
        print("JOIN ON COLUMNS LIST IS : " + str(join_on_columns_list) + str(type(join_on_columns_list[0])))

        #read the first results file 
        results_file_path = '/mnt/nas/dbresults/'+str(jobname_list[0])+'/'+str(runID_list[0]) + '/results/results.csv'
        first_results_dataframe = pd.read_csv(results_file_path, header=None, names = parameter_lists['results_param_list']) 
        
        #LOWERCASE THE QUALIFIER COLUMN
        first_results_dataframe['qualifier'] = first_results_dataframe['qualifier'].apply(lambda x: x.lower().strip())
        
        #GROUP BY join_on_columns_list AND FIND MIN/MAX OF EACH GROUP
        if(min_or_max == '0'):
            first_results_dataframe = first_results_dataframe.groupby(by=join_on_columns_list).min()
        else:
            first_results_dataframe = first_results_dataframe.groupby(by=join_on_columns_list).max()

        #DEBUGGING STUFF
        print("PRINTING INITIAL INTITIAL DATAFRAME")
        print(first_results_dataframe)

        final_results_dataframe = first_results_dataframe

        print('\n\nDONE\n\n')

        # for each subsequent results file, merge with the already exsiting dataframe on "description" columns
        for jobname, runID in zip(jobname_list[1:], runID_list[1:]):
            results_file_path = '/mnt/nas/dbresults/'+str(jobname)+'/'+str(runID) + '/results/results.csv'
            print("PRINTING JOBNAME : " + str(jobname) + " RUNID : "  + str(runID))
            next_dataframe = pd.read_csv(results_file_path, header=None, names = parameter_lists['results_param_list']) 
            next_dataframe['qualifier'] = next_dataframe['qualifier'].apply(lambda x: x.lower().strip())

            next_dataframe = next_dataframe.groupby(by=join_on_columns_list).max()
            #GROUP BY join_on_columns_list AND FIND MIN/MAX OF EACH GROUP
            if(min_or_max == '0'):
                next_dataframe = next_dataframe.groupby(by=join_on_columns_list).min()
            else:
                next_dataframe = next_dataframe.groupby(by=join_on_columns_list).max()


            final_results_dataframe = final_results_dataframe.merge(next_dataframe, how = 'outer', on = join_on_columns_list, validate="many_to_many")


        print("PRINTING RESULTS DATAFRAME\n\n")
        final_results_dataframe = final_results_dataframe.fillna("").reset_index()
        print(final_results_dataframe)

        #Change column names according to OriginID
        # del final_results_dataframe['index']
        final_results_dataframe.columns = join_on_columns_list + ["number_" + originID for originID in originID_compare_list]

        #Change the result_type according to result_type_map
        #Mapping for Result type field
        result_type_map = {0: "single thread", 1: 'single core',
                       2: 'single socket', 3: 'dual socket',
                       4: 'Scaling'}

        final_results_dataframe['resultype'] = final_results_dataframe['resultype'].apply(lambda x: result_type_map[x])

        #SUBSET OF ROWS WHICH HAVE "qualifier" AS QUALIFIER
        performance_mask = (final_results_dataframe['qualifier'] == pd.Series([qualifier] *len(final_results_dataframe)))
        performance_dataframe = final_results_dataframe[performance_mask]

        #Delete the results_param_list as it is no longer needed
        del parameter_lists['results_param_list']

        #read csv files from NAS path
        compare_lists = read_all_csv_files(compare_lists, parameter_lists, originID_compare_list)
        

        # send data to the template compare.html
        context = {
            'originID_list':originID_compare_list,
            'testname':test_name,

            'index_columns':join_on_columns_list,

            'parameter_lists': parameter_lists,
            'compare_lists': compare_lists,

            'results': final_results_dataframe.to_dict(orient='list'),
        }
        return render_template('compare.html', context=context)
    else:
        return redirect('/')
