import pprint
import pandas as pd
import pymysql
import configparser
from flask import Flask, render_template, request, redirect
app = Flask(__name__)
import csv

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
    query = "SELECT DISTINCT o.originID, o.testdate, o.notes from origin o INNER JOIN result r ON o.originID = r.origin_originID INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID where t.testname = \'" + \
        testname + "\' AND r.isvalid = 1 ORDER BY o.originID DESC"
    db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)

    dataframe = pd.read_sql(query, db)
    rows, columns = dataframe.shape  # returns a tuple (rows,columns)

    context = {
        'testname': testname,
        'data': dataframe.to_dict(orient='list'),
        'no_of_rows': rows,
        'no_of_columns': columns,
        'direct_data': dataframe.to_html(index=False),
    }

    return render_template('all-runs.html', context=context)

# View for handling Test details request
@app.route('/test-details/<originID>')
def showTestDetails(originID):
    db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)
    result_type_map = {0: "single thread", 1: 'single core',
                       2: 'single socket', 3: 'dual socket'}

    # Just get the TEST name
    TEST_NAME_QUERY = "SELECT t.testname FROM testdescriptor as t INNER JOIN origin o on o.testdescriptor_testdescriptorID=t.testdescriptorID WHERE o.originID=" + originID + ";"
    test_name_dataframe = pd.read_sql(TEST_NAME_QUERY, db)
    test_name = test_name_dataframe['testname'][0]

    # Get some System details
    SYSTEM_DETAILS_QUERY = "SELECT DISTINCT O.hostname, O.testdate, O.originID,  S.resultype FROM result R INNER JOIN subtest S ON S.subtestID=R.subtest_subtestID INNER JOIN origin O ON O.originID=R.origin_originID WHERE O.originID=" + originID + ";"
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

    for i in range(len(results_dataframe)):
        description_list = description_string.split(',')
        for j in range(len(description_list)):
            results_dataframe.at[i, description_list[j]] = results_dataframe.at[i, 'description'].split(',')[
                j]

    del results_dataframe['description']
    print(results_dataframe)
    print("RESULTS ARE ABOVE THIS")

    context = {
        'testname': test_name,
        'system_details': system_details_dataframe.to_dict(orient='list'),
        'description_list': description_string.split(','),
        'results': results_dataframe.to_html(index=False)
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

    context = {
        'hwdetails': hwdetails_dataframe.to_html(index=False),
        'toolchain': toolchain_dataframe.to_html(index=False),
        'ostunings': ostunings_dataframe.to_html(index=False),
        'node': node_dataframe.to_html(index=False),
        'bootenv': bootenv_dataframe.to_html(index=False),
    }
    return render_template('environment-details.html', context=context)


@app.route('/diff', methods=['GET', 'POST'])
def diffTests():
    if request.method == "POST":
        db = pymysql.connect(host='10.110.169.149', user='root',
                         passwd='', db='benchtooldb', port=3306)

        env_metadata_parser = configparser.ConfigParser()
        results_metadata_parser = configparser.ConfigParser()
        # take checked rows from table
        originID_compare_list = []
        
        for key, value in request.form.items():
            print(key, value)
            if("diff-checkbox" in key):
                originID_compare_list.append(value)

        print(originID_compare_list)
        
        #Mapping for Result type field
        result_type_map = {'0': "single thread", '1': 'single core',
                       '2': 'single socket', '3': 'dual socket'}

        # #GET TEST NAMES LIST
        TEST_NAME_QUERY = "SELECT t.testname FROM testdescriptor as t INNER JOIN origin o on o.testdescriptor_testdescriptorID=t.testdescriptorID WHERE o.originID=" + originID_compare_list[0] + ";"
        test_name_dataframe = pd.read_sql(TEST_NAME_QUERY, db)
        test_name = test_name_dataframe['testname'][0]

        JENKINS_QUERY = "SELECT J.jobname, J.runID FROM origin O INNER JOIN jenkins J ON O.jenkins_jenkinsID=J.jenkinsID AND O.originID in " + str(originID_compare_list).replace('[','(').replace(']',')') + ";"
        jenkins_details = pd.read_sql(JENKINS_QUERY, db)

        #Take reversed list because database gives Jenkins details in acsending order of originID.
        #We have lists in descending order of originID
        jobname_list = jenkins_details['jobname'].to_list()
        jobname_list.reverse()
        runID_list = jenkins_details['runID'].to_list()
        runID_list.reverse()

        # read metadata from metadata.ini file
        env_metadata_file_path = '/mnt/nas/scripts/metadata.ini'
        env_metadata_parser.read(env_metadata_file_path)

        results_metadata_file_path = '/mnt/nas/scripts/wiki_description.ini'
        results_metadata_parser.read(results_metadata_file_path)

        # create all parameter lists
        results_param_list = results_metadata_parser.get(
            test_name, 'description').replace('\"','').replace(' ', '').split(',')
        origin_param_list = env_metadata_parser.get(
            'origin', 'db_variables').replace(' ', '').split(',')
        bootenv_param_list = env_metadata_parser.get(
            'bootenv', 'db_variables').replace(' ', '').split(',')
        node_param_list = env_metadata_parser.get(
            'node', 'db_variables').replace(' ', '').split(',')
        hwdetails_param_list = env_metadata_parser.get(
            'hwdetails', 'db_variables').replace(' ', '').split(',')
        ostunings_param_list = env_metadata_parser.get(
            'ostunings', 'db_variables').replace(' ', '').split(',')
        toolchain_param_list = env_metadata_parser.get(
            'toolchain', 'db_variables').replace(' ', '').split(',')
        
        results_param_list.extend(['number','resultype','unit','qualifier'])

        # LIST of Dictionaries (tests) to be compared
        results_list = []
        origin_list = []
        bootenv_list = []
        node_list = []
        hwdetails_list = []
        ostunings_list = []
        toolchain_list = []

        #read csv files from NAS path
        # FOR Results
        for i in range(len(originID_compare_list)):
            result = dict()
            with open('/mnt/nas/dbresults/'+str(jobname_list[i])+'/'+str(runID_list[i]) + '/results/results.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(results_param_list)):
                        result[results_param_list[i]] = row[i]
                    break
            result['resultype'] = result_type_map[result['resultype']]
            results_list.append(result)
        
        # FOR origin
        for i in range(len(originID_compare_list)):
            origin = dict()
            with open('/mnt/nas/dbresults/'+str(jobname_list[i])+'/'+str(runID_list[i]) + '/origin.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(origin_param_list)):
                        origin[origin_param_list[i]] = row[i]
            origin_list.append(origin)

        #FOR BOOTENV
        for i in range(len(originID_compare_list)):
            bootenv = dict()
            with open('/mnt/nas/dbresults/'+str(jobname_list[i])+'/'+str(runID_list[i]) + '/bootenv.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(bootenv_param_list)):
                        bootenv[bootenv_param_list[i]] = row[i]
            bootenv_list.append(bootenv)

        # FOR NODE
        for i in range(len(originID_compare_list)):
            node = dict()
            with open('/mnt/nas/dbresults/'+str(jobname_list[i])+'/'+str(runID_list[i]) + '/node.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(node_param_list)):
                        node[node_param_list[i]] = row[i]
            node_list.append(node)

        # FOR HWDETAILS
        for i in range(len(originID_compare_list)):
            hwdetail = dict()
            with open('/mnt/nas/dbresults/'+str(jobname_list[i])+'/'+str(runID_list[i]) + '/hwdetails.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(hwdetails_param_list)):
                        hwdetail[hwdetails_param_list[i]] = row[i]
                    break
            hwdetails_list.append(hwdetail)

        # FOR OSTUNINGS
        for i in range(len(originID_compare_list)):
            ostuning = dict()
            with open('/mnt/nas/dbresults/'+str(jobname_list[i])+'/'+str(runID_list[i]) + '/ostunings.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(ostunings_param_list)):
                        ostuning[ostunings_param_list[i]] = row[i]
            ostunings_list.append(ostuning)

        # FOR TOOLCHAIN
        for i in range(len(originID_compare_list)):
            toolchain = dict()
            with open('/mnt/nas/dbresults/'+str(jobname_list[i])+'/'+str(runID_list[i]) + '/toolchain.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(toolchain_param_list)):
                        toolchain[toolchain_param_list[i]] = row[i]
            toolchain_list.append(toolchain)

        # send those files to the template compare.html (modify it first)

        context = {
            'originID_list':originID_compare_list,

            'results_param_list': results_param_list,
            'origin_param_list': origin_param_list,
            'bootenv_param_list': bootenv_param_list,
            'node_param_list': node_param_list,
            'hwdetails_param_list': hwdetails_param_list,
            'ostunings_param_list': ostunings_param_list,
            'toolchain_param_list': toolchain_param_list,

            'results': results_list,
            'origin': origin_list,
            'bootenvs': bootenv_list,
            'nodes': node_list,
            'hwdetails': hwdetails_list,
            'ostunings': ostunings_list,
            'toolchain': toolchain_list,
        }
        return render_template('compare.html', context=context)
    else:
        return redirect('/')
