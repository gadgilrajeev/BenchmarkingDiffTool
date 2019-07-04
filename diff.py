import os
import configparser
import csv
from flask import Flask
from flask import render_template
from flask import request
app = Flask(__name__)

@app.route('/',methods=['GET','POST'])
def home():
    if(request.method == 'GET'):
        #print("\nGET\n");
        return render_template('base.html',context={})
    elif(request.method == 'POST'):
        #print("\nPOST\n");
        parser = configparser.ConfigParser()

        test_numbers = []

        #get all the test numbers passed from the form
        while (True):
            if (request.form.get('test_' + str(len(test_numbers)+1))):
                test_numbers.append(request.form.get('test_' + str(len(test_numbers)+1)))
            else:
                break

        #just for debugging stuff
        #print(test_numbers)

        #PERFORM EXCEPTION HANDLING HERE AND PROCESS ACCORDINGLY
        try:
            #check if test number exists
            for t in test_numbers:
                if not os.path.isdir('../tests/test_'+t):
                    raise Exception("Test number " + t + " does not exist yet")

            #check for duplicate entries
            if( len(test_numbers) > len(list(dict.fromkeys(test_numbers)))):
                raise Exception("Please enter distinct values")
        except Exception as error_message:
            error = {
                'message': error_message,
            }
            #render the page with error messages
            return render_template('base.html', error=error, context={})

        #IF everything OK proceed further
        #retrieve and read metadata.ini file from ../tests directory
        parser.read('../tests/metadata.ini')

        #create all parameter lists
        bootenv_param_list = parser.get('bootenv', 'db_variables').replace(' ','').split(',')
        node_param_list = parser.get('node', 'db_variables').replace(' ','').split(',')
        hwdetails_param_list = parser.get('hwdetails', 'db_variables').replace(' ','').split(',')
        ostunings_param_list = parser.get('ostunings', 'db_variables').replace(' ', '').split(',')
        toolchain_param_list = parser.get('toolchain', 'db_variables').replace(' ', '').split(',')
        testdescriptor_param_list = parser.get('testdescriptor', 'db_variables').replace(' ', '').split(',')
        jenkins_param_list = parser.get('jenkins', 'db_variables').replace(' ', '').split(',')
        origin_param_list = parser.get('origin', 'db_variables').replace(' ', '').split(',')

        #LIST of Dictionaries (tests) to be compared
        bootenv_list = []
        node_list = []
        hwdetails_list = []
        ostunings_list = []
        toolchain_list = []
        testdescriptor_list = []
        jenkins_list = []
        origin_list = []

        #retrieve the metadata for EACH .csv FILE using the csv module
        #FOR BOOTENV
        for t_no in test_numbers:
            bootenv = dict()
            with open('../tests/test_' + t_no +'/bootenv.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(bootenv_param_list)):
                        bootenv[bootenv_param_list[i]] = row[i]
            bootenv_list.append(bootenv)

        #FOR NODE
        for t_no in test_numbers:
            node = dict()
            with open('../tests/test_' + t_no + '/node.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(node_param_list)):
                        node[node_param_list[i]] = row[i]
            node_list.append(node)

        # FOR HWDETAILS
        for t_no in test_numbers:
            hwdetail = dict()
            with open('../tests/test_' + t_no + '/hwdetails.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(hwdetails_param_list)):
                        hwdetail[hwdetails_param_list[i]] = row[i]
                    break
            hwdetails_list.append(hwdetail)

        # FOR OSTUNINGS
        for t_no in test_numbers:
            ostuning = dict()
            with open('../tests/test_' + t_no + '/ostunings.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(ostunings_param_list)):
                        ostuning[ostunings_param_list[i]] = row[i]
            ostunings_list.append(ostuning)

        #FOR TOOLCHAIN
        for t_no in test_numbers:
            toolchain = dict()
            with open('../tests/test_' + t_no + '/toolchain.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(toolchain_param_list)):
                        toolchain[toolchain_param_list[i]] = row[i]
            toolchain_list.append(toolchain)

        #FOR TESTDESCRIPTOR
        for t_no in test_numbers:
            testdescriptor = dict()
            with open('../tests/test_' + t_no + '/testdescriptor.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(testdescriptor_param_list)):
                        testdescriptor[testdescriptor_param_list[i]] = row[i]
            testdescriptor_list.append(testdescriptor)

        #FOR JENKINS
        for t_no in test_numbers:
            jenkins = dict()
            with open('../tests/test_' + t_no + '/jenkins.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(jenkins_param_list)):
                        jenkins[jenkins_param_list[i]] = row[i]
            jenkins_list.append(jenkins)

        #FOR origin
        for t_no in test_numbers:
            origin = dict()
            with open('../tests/test_' + t_no + '/origin.csv', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    for i in range(0, len(origin_param_list)):
                        origin[origin_param_list[i]] = row[i]
            origin_list.append(origin)

        #create a dictionary 'context'. This is what will be displayed in the form of tables
        context = {
            'test_numbers': test_numbers,

            'bootenv_param_list': bootenv_param_list,
            'node_param_list': node_param_list,
            'hwdetails_param_list': hwdetails_param_list,
            'ostunings_param_list': ostunings_param_list,
            'toolchain_param_list': toolchain_param_list,
            'testdescriptor_param_list': testdescriptor_param_list,
            'jenkins_param_list': jenkins_param_list,
            'origin_param_list': origin_param_list,

            'bootenvs': bootenv_list,
            'nodes': node_list,
            'hwdetails':hwdetails_list,
            'ostunings':ostunings_list,
            'toolchain':toolchain_list,
            'testdescriptor':testdescriptor_list,
            'jenkins':jenkins_list,
            'origin':origin_list,

        }

        return render_template('base.html',context=context)
