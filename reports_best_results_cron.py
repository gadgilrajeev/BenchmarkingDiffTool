import time     
import logging
import os
import pandas as pd
import numpy as np
import multiprocessing                  #Processing on multiple cores
from functools import partial           #For passing extra arguments to pool.map 
import pymysql
import configparser
import openpyxl
from collections import OrderedDict
from packaging.version import LegacyVersion

DB_HOST_IP = '1.21.1.65'
# DB_HOST_IP = '10.110.169.149'
# DB_HOST_IP = 'localhost'
DB_USER = 'root'
DB_PASSWD = ''
DB_NAME = 'benchtooldb'
DB_PORT = 3306

# The number of cores to be used for multiprocessing
num_processes = 40

# Change the result_type according to result_type_map
# Mapping for Result type field
result_type_map = {0: "single thread", 1: 'single core',
                   2: 'single socket', 3: 'dual socket',
                   4: 'client scaling', 5: '1/8th socket',
                   6: '1/4th socket', 7: '1/2 socket',
                   8: '2 cores', 9: 'perf',
                   10: 'I/O utilization', 11: 'socmon',
                   12: 'OMP_MPI scaling', 20: 'Projection'}

# Returns INPUT_FILTER_CONDITION from 'test_name' and 'input_filters_list'
def get_input_filter_condition(test_name, input_filters_list, wiki_description_file='./config/wiki_description.ini'):
    INPUT_FILTER_CONDITION = ""

    results_metadata_file_path = wiki_description_file
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

# Query the database paralelly for each 'testname'
def parallel_test_report(params, **kwargs):
    db = pymysql.connect(host=DB_HOST_IP, user=DB_USER,
                         passwd=DB_PASSWD, db=DB_NAME, port=DB_PORT)

    # Unpack the params here
    test_section, testname, INPUT_FILTER_CONDITION = params

    print("################################################################################")
    print("Processing Paralelly for {}".format(test_section))

    results_metadata_file_path = './config/wiki_description.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    skuid_cpu_map = kwargs['skuid_cpu_map']
    all_skuidnames = kwargs['all_skuidnames']

    # Either 'best-results' or 'top-5'
    best_results_condition = kwargs['best_results_condition']

    # An empty dataframe
    results_dataframe = pd.DataFrame()


    # Get 'qualifier' and 'higher_is_better' value for the first "field" of testname
    qualifier = results_metadata_parser.get(testname, 'fields').replace('\"', '').split(',')[0]
    higher_is_better = results_metadata_parser.get(testname, 'higher_is_better').replace('\"', '').replace(' ','').split(',')[0]

    # For each skuid_list
    for skuid_list in all_skuidnames:
        
        SKUID_CRITERIA = " AND n.skuidname IN " + str(skuid_list).replace('[','(').replace(']',')')
        
        # r.number and order by conditions according to higher_is_better
        if higher_is_better == '0':
            R_NUMBER = " MIN(r.number) as number, "
            ORDER_BY_CONDITION = " order by r.number "
        else:
            R_NUMBER = " MAX(r.number) as number, "
            ORDER_BY_CONDITION = " order by r.number DESC "

        if best_results_condition == 'best-results':
            LIMIT_CONDITION = " limit 1 "
        elif best_results_condition == 'top-5':
            LIMIT_CONDITION = " limit 5 "

        QUALIFIER_CONDITION = "  AND disp.qualifier LIKE \'%" + qualifier + '%\''

        GROUP_BY_CONDITION = " group by t.testname, o.originID, os.kernelname, os.osversion, os.osdistro, " + \
                                "hw.fwversion, tc.toolchainname, tc.toolchainversion, tc.flags, b.smt, b.cores, " + \
                                "b.corefreq, b.ddrfreq, n.skuidname, o.hostname, s.resultype, o.testdate, " + \
                                "o.notes, s.description, r.number, disp.unit, disp.qualifier "

        start_time = time.time()

        RESULTS_QUERY = "SELECT t.testname, o.originID, os.kernelname, os.osversion, os.osdistro, hw.fwversion, " + \
                        "tc.toolchainname, tc.toolchainversion, tc.flags, b.smt, b.cores, b.corefreq, b.ddrfreq, " + \
                        "n.skuidname, o.hostname, s.resultype, o.testdate, o.notes, s.description," + R_NUMBER + \
                        """ disp.unit, disp.qualifier 
                        FROM result r INNER JOIN subtest s ON s.subtestID=r.subtest_subtestID 
                        INNER JOIN display disp ON disp.displayID=r.display_displayID 
                        INNER JOIN origin o ON o.originID=r.origin_originID 
                        INNER JOIN testdescriptor t ON t.testdescriptorID = o.testdescriptor_testdescriptorID 
                        INNER JOIN hwdetails hw ON o.hwdetails_hwdetailsID = hw.hwdetailsID
                        INNER JOIN bootenv b ON hw.bootenv_bootenvID = b.bootenvID
                        INNER JOIN node n ON hw.node_nodeID = n.nodeID 
                        INNER JOIN ostunings os ON o.ostunings_ostuningsID = os.ostuningsID
                        INNER JOIN toolchain tc ON o.toolchain_toolchainID = tc.toolchainID
                        WHERE t.testname = \'""" + testname + \
                        "\'" + INPUT_FILTER_CONDITION + SKUID_CRITERIA + " AND r.isvalid = 1 " + \
                        QUALIFIER_CONDITION + GROUP_BY_CONDITION + ORDER_BY_CONDITION + LIMIT_CONDITION + ";"

        logging.debug("\nFINAL QUERY = {}".format(RESULTS_QUERY))

        temp_df = pd.read_sql(RESULTS_QUERY, db)

        query_excecution_time = time.time() - start_time
        logging.debug("Query excecution took {} seconds".format(query_excecution_time))

        # Append the dataframe below the current dataframe
        results_dataframe = results_dataframe.append(temp_df, sort=False)

    # Replace testname with 'test_section' name
    if 'testname' in results_dataframe:
        results_dataframe.insert(0, "Test name", [test_section for item in results_dataframe['testname']])
        del results_dataframe['testname']

    results_dataframe = results_dataframe.reset_index(drop=True)

    # Convert resultype column into corresponding entry of result_type_map
    results_dataframe['resultype'] = results_dataframe['resultype'].apply(lambda result_type: result_type_map.get(result_type, "Unkown resultype"))

    # Do NOT split the description column
    # Since it causes a LOT of columns to be displayed in the final Excel Sheet
    # Rename 'description' to 'Input file Description'
    results_dataframe = results_dataframe.rename(columns = {'description':'Input File Description'})

    # Add "FACTS Link" column at the end
    index = len(results_dataframe.columns)
    results_dataframe.insert(index, "FACTS Link", ['http://gbt-2s-02:5000/test-details/' + str(originID) for originID in results_dataframe['originID']])

    return results_dataframe

# Write best results to excel file in 'cached_results' directory 
def write_best_results_excel():
    results_metadata_file_path = './config/best_of_all_graph.ini'
    results_metadata_parser = configparser.ConfigParser()
    results_metadata_parser.read(results_metadata_file_path)

    sku_file_path = './config/sku_definition.ini'
    sku_parser = configparser.ConfigParser()
    sku_parser.read(sku_file_path)

    #  Map from CPU Section->list(skuidname) in sku_definition.ini 
    skuid_cpu_map = OrderedDict({section: sku_parser.get(section, 'SKUID').replace('\"', '').split(',') for section in sku_parser.sections()})

    # Also a map from skuidname->Cpu Section. We need both in diff scenarios
    for section in sku_parser.sections():
        skuids = sku_parser.get(section, 'SKUID').replace('\"','').split(',')
        for skuid in skuids:
            skuid_cpu_map[skuid] = section

    # Map from filter label -> testname_list Eg. ncar -> ['clubb', 'mg2', 'waccm', 'wrf']
    label_testname_map = {}
    for section in results_metadata_parser.sections():
        labels = results_metadata_parser.get(section, 'label').replace('\"','').replace(' ', '').lower().split(',')

        # Remove empty strings
        labels = list(filter(None, labels))
        for label in labels:
            # If the list doesn't exist, create one
            if label not in label_testname_map:
                label_testname_map[label] = []
            label_testname_map[label].append(section)

    # best_results_condition = 'best-results' here
    best_results_condition = 'best-results'

    # Get all 'skuidnames' from each section of sku_definition.ini
    # Its a list of lists
    all_skuidnames = []
    for sku in sku_parser.sections():
        all_skuidnames.append(skuid_cpu_map[sku])

    # Get all test_sections from 'best_of_all_graph.ini'
    all_test_sections = results_metadata_parser.sections()

    # Sort the selected_tests_list alphabetically
    all_test_sections.sort()
    # Get the INPUT_FILTER_CONDITION for each selected test
    input_filters_list_list = [results_metadata_parser.get(test_section, 'default_input') \
                                .replace('\"', '').split(',') for test_section in all_test_sections]
    INPUT_FILTER_CONDITION_LIST = [get_input_filter_condition(test_section, input_filters_list, \
                                    wiki_description_file="./config/best_of_all_graph.ini") \
                                    for test_section, input_filters_list in zip(all_test_sections, input_filters_list_list)]

    # After we get INPUT_FILTER_CONDITION_LIST, change selected_tests_list
    # to a list having actual 'testnames' and not sections from best_of_all_graph.ini
    # Read all test names from .ini file
    all_test_names = [results_metadata_parser.get(section, 'testname').strip() for section in all_test_sections] 

    # The directory where cached excel files will be stored
    base_path = os.getcwd() + '/cached_results/'
    # If directory doesn't exist, create it
    if not os.path.exists(base_path):
        os.mkdir(base_path)         

    # Filename .xlsx
    filename = 'reports_best_results_cached.xlsx'
    absolute_file_path = base_path + filename

    # Delete the already existing file
    try:
        os.remove(absolute_file_path)
    except:
        pass

    parallel_start_time = time.time()

    # Parallel excecution 
    results_dataframe_list = []
    pool = multiprocessing.Pool(num_processes)
    try:
        results_dataframe_list = pool.map(partial(parallel_test_report, skuid_cpu_map=skuid_cpu_map, best_results_condition=best_results_condition,  \
                                all_skuidnames=all_skuidnames), zip(all_test_sections, all_test_names, INPUT_FILTER_CONDITION_LIST))
    finally:
        print("Closing Pool")
        pool.close()
        pool.join()

    print("Parallelism took {} seconds".format(time.time() - parallel_start_time))

    start_time2 = time.time()

    print("Writing excel sheets")
    # Write all results in a single excel file

    final_results_dataframe = pd.DataFrame()

    # Append all the dataframes from the list to final_results_dataframe
    for results_dataframe in results_dataframe_list:
        final_results_dataframe = final_results_dataframe.append(results_dataframe, sort=False)

        # Append an empty row to the final_results_dataframe
        final_results_dataframe = final_results_dataframe.append(pd.Series(), ignore_index=True, sort=False)

    # Reset Index
    final_results_dataframe = final_results_dataframe.reset_index(drop=True)

    # Write the entire dataframe in a single sheet
    with pd.ExcelWriter(absolute_file_path, engine='openpyxl') as writer:
        final_results_dataframe.to_excel(writer, sheet_name="Best results")

    print("Writing all excel files took {} seconds".format(time.time() - start_time2))
    

if __name__ == "__main__":
    write_best_results_excel()

    # write_top_5_results_excel()
