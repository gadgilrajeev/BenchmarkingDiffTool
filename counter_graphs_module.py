import os, sys
import pandas as pd
import re, argparse
import numpy as np
from pprint import pprint
import time

bw_related_pattern = re.compile(r"L2D_CACHE_ACCESS|L2D_CACHE_REFILL|L1D_CACHE_ACCESS|L1D_CACHE_REFILL|L3_|DMC_|_ccpi",
                                re.IGNORECASE)
debug = 0
LLC_bw_events = ['L3_0 Writeback Requests', 'L3_1 Writeback Requests', 'L3_0 Read Request', 'L3_1 Read Request']
MEM_bw_events = ['DMC_0 Reads','DMC_1 Reads','DMC_0 Writes','DMC_0 Writes']
Slice = {'fwd': 0, 'rev': 0, 'state': 0, 'count': 0}
options = {}


# Handle params
def handle_params():
    parser = argparse.ArgumentParser(description='Process input options')
    parser.add_argument("-inc", "--include", nargs="+",
                        action="store", dest="include", default=["\.stat"], help="list of files to exclude")
    parser.add_argument("-ex", "--exclude", nargs="+",
                        action="store", dest="exclude", default=["\.log"], help="list of files to exclude")
    parser.add_argument("-p", "--path", nargs="+",
                        action="store", dest="path", default=".", help="list of files to exclude")
    parser.add_argument("--tshead", default = 0,
                        action="store", type=float, dest="ts_head", help="time stamp to start from")
    parser.add_argument("--tstail", default = 1e20,
                        action="store", type=float, dest="ts_tail", help="time stamp to end at")
    parser.add_argument("-o", "--out", default='perf_aggregate',
                        action="store", dest="out", help="output name precursor")
    parser.add_argument("-S", "--smt", type=int, default=1,
                        action="store", dest="smt", help="number of logical cores corresponding to smt")
    parser.add_argument("-ipc", "--ipc_threshold", type=float, default=0,
                        action="store", dest="ipc_threshold",
                        help="threshold of ipc to look for slice with data")
    parser.add_argument("--ipc_runlen", type=int, default=10,
                        action="store", dest="ipc_runlen",
                        help="number of samples with high ipc that will signal start of slice with data")
    parser.add_argument("-match", "--marker_mintime", type=int, default=10,
                        action="store", dest="marker_mintime",
                        help="length of time with low ipc that will signal start of slice with data")
    parser.add_argument("-slice", "--requested_slice", type=int, default=1,
                        action="store", dest="requested_slice", 
                        help="specific slice with data between low ipc runs to look for")

    parser.add_argument("-d", "--debug",
                        action="count", dest="debug", help="verbose debug output")

    # This adding of arguments is just a 'hack'
    # Please find a better way to solve this problem
    parser.add_argument("-z","--host", help="This is a hack", action="store")
    parser.add_argument("run")

    args = parser.parse_args()
    global debug
    debug = args.debug
    return args


# Calculate BW metrics
def add_bw(event_data, ts, types):
    if ts > 0:
        period = event_data['ts'][ts] - event_data['ts'][ts - 1]
    else:  # for first timestamp, just assume same as next
        try:
            period = event_data['ts'][ts+1] - event_data['ts'][ts]
        except IndexError:  # In case this is the first in the first file, nothing to rely on yet
            period = event_data['ts'][ts]
    bws = 1.0 / period  # BW scaling to get per second
    for e in types:
        if re.search(bw_related_pattern, e):
            event_data['bw'][e].append(bws * event_data['count'][e][ts] * 64 / 1e6)


# Add derived metrics
def extra_metrics(event_data, ts, types):
    try:
        pki = (1000 * event_data['count']['instructions'][ts])
    except IndexError:
        pki = (1000 * event_data['count']['instructions'][-1])
    if 'L1D_CACHE_ACCESS' in types:
        if ts == 0:
            event_data['count']['L1_DCACHE_APPROX'] = []
            event_data['pki']['L1_DCACHE_APPROX'] = []
            types.append('L1_DCACHE_APPROX')
        event_data['count']['L1_DCACHE_APPROX'].append(event_data['count']['L1D_CACHE_ACCESS'][ts] + event_data['count']['L1D_CACHE_REFILL'][ts])
        event_data['pki']['L1_DCACHE_APPROX'].append(event_data['count']['L1_DCACHE_APPROX'][ts] / pki)
    for N in ['0', '1']:
        hit_name = "L3_" + N + " Read Hit"
        req_name = "L3_" + N + " Read Request"
        miss_name = "L3_" + N + " Read Miss"
        if hit_name in types:
            if ts == 0:
                for n in ['count', 'bw', 'pki']:
                    event_data[n][miss_name] = []
                types.append(miss_name)
            miss_val = event_data['count'][req_name][ts] - event_data['count'][hit_name][ts]
            try:
                event_data['count'][miss_name][ts] = miss_val
                event_data['pki'][miss_name][ts] = miss_val / pki
            except IndexError:
                event_data['count'][miss_name].append(miss_val)
                event_data['pki'][miss_name].append(miss_val / pki)


# After all captured add L3 and DMC BW
def final_extra_metrics(event_data):
    print("Adding final extra metrics")
    event_data['count']['L3 BW MB/s'] = []
    event_data['count']['DMC BW MB/s'] = []
    event_data['bw']['L3 BW MB/s'] = []
    event_data['bw']['DMC BW MB/s'] = []
    for ts in range(len(event_data['count']['instructions'])):
        bw = 0
        for e in LLC_bw_events:
            try:
                bw += event_data['bw'][e][ts]
            except (KeyError, IndexError):
                pass
        event_data['count']['L3 BW MB/s'].append(bw)
        event_data['bw']['L3 BW MB/s'].append(bw)
        bw = 0
        for e in MEM_bw_events:
            try:
                bw += event_data['bw'][e][ts]
            except (KeyError, IndexError):
                pass
        event_data['count']['DMC BW MB/s'].append(bw)
        event_data['bw']['DMC BW MB/s'].append(bw)


# At timestamp advance, calculate bw if there since bw relies on specific duration has to be per file
# and handle any odds and ends
def handle_timestamp(event_data, ts, event_ts, types):
    if ts >= 0:
        try:
            event_data['ts'][ts] = event_ts
        except IndexError:
            event_data['ts'].append(event_ts)
        extra_metrics(event_data, ts, types)
        add_bw(event_data, ts, types)


def reset_slice():
    Slice['fwd'] = 0
    Slice['rev'] = 0


# Identify slice of data for alignment purposes
def identify_slice(event_data, ts, types):
    global Slice
    if ts < 1 or options.ipc_threshold == 0:
        return ts
    ipc = event_data['count']['instructions'][ts] / event_data['count']['cycles'][ts]
    if ipc > options.ipc_threshold:
        Slice['fwd'] += 1
    if ipc <= options.ipc_threshold:
        Slice['rev'] += 1
    # State:1 looking for start of  slice identified by a run of ipc over threshold (end of the marker)
    run_duration = 0
    if Slice['state'] == 1:
        if Slice['rev'] > 0:  # TODO: Allow some flexibility here
            reset_slice()
        else:
            # run_duration = event_data['ts'][ts] - event_data['ts'][ts - Slice['fwd']]
            run_length = Slice['fwd']
            # Identified a slice of data after a run of length 'run' with ipc over threshold
            if run_length > options.ipc_runlen:
                Slice['state'] = 0
                Slice['count'] += 1
                match_start = ts - run_length
                ts_match = event_data['ts'][match_start]
                if debug:
                    print(" - Detected slice %d data start at ts %f" % (Slice['count'], ts_match))
                reset_slice()
                if Slice['count'] == options.requested_slice:
                    if 'id_start' not in Slice:  # First time, rest will need to align to this
                        Slice['id_start'] = match_start
                    # If this is the requested slice, align data to start
                    # at the same as previous files (handle multi file capture)
                    else:
                        id_start = Slice['id_start']
                        id_end = id_start + run_length
                        ts_start = event_data['ts'][Slice['id_start']]
                        print("Realign slice data from %f to %f" % (ts_match, ts_start))
                        for e in types:
                            if re.search(bw_related_pattern, e):
                                copy_types = ['count', 'pki', 'bw']
                            else:
                                copy_types = ['count', 'pki']
                            if match_start > id_start:  # copy backward
                                copy_id = id_start
                                for i in range(match_start,ts):
                                    for t in copy_types:
                                        event_data[t][e][copy_id] = event_data[t][e][i]
                                    event_data['ts'][i] = event_data['ts'][ts]
                                    copy_id += 1
                            else:
                                # First fill fake data
                                for i in range(ts+1, id_end+1):
                                    for t in copy_types:
                                        event_data[t][e].append(event_data[t][e][ts])
                                        try:
                                            event_data['ts'][i] = event_data['ts'][ts]
                                        except IndexError:
                                            event_data['ts'].append(event_data['ts'][ts])
                                # Then copy forward safely
                                for t in copy_types:
                                    tmp_data = event_data[t][e][match_start:ts]
                                    event_data[t][e][id_start:id_end] = tmp_data
                                tmp_data = event_data['ts'][match_start:ts]
                                event_data['ts'][id_start:id_end] = tmp_data
                        return id_end
    # State:0 looking for end of slice identified by a run of ipc below threshold (marker is assumed to be sleep)
    if Slice['state'] == 0:
        if Slice['fwd'] > 0:  # TODO: Allow some flexibility here
            reset_slice()
        else:
            run_duration = event_data['ts'][ts] - event_data['ts'][ts - Slice['rev']]
            run_length = Slice['rev']
            # Identified marker [a slice of data after a run of length 'run' with ipc below threshold]
            if run_duration > options.marker_mintime:
                match_start = ts - run_length
                ts_match = event_data['ts'][match_start]
                Slice['state'] = 1
                ts_len = ts
                if Slice['count'] > 0:
                    ts_len = ts - Slice['id_start'] - options.marker_mintime
                if Slice['count'] == options.requested_slice:
                    if 'id_end' not in Slice:
                        Slice['id_end'] = match_start
                    else:
                        Slice['id_end'] = max(match_start, Slice['id_end'])
                    print(" - Detected slice %d data end at ts %f [len=%d : %d-%d]" %
                          (Slice['count'], ts_match, ts_len, Slice['id_start'], Slice['id_end']))
                else:
                    print(" - Detected slice %d data end at ts %f [len=%d]" %
                          (Slice['count'], ts_match, ts_len))
                reset_slice()
    return ts


# Process output from perf stat -x,
def process_perf_stat(filename, translate_event, event_data):
    print("Processing %s" % filename)
    all_data = pd.read_csv(filename, comment='#', header=None, skipinitialspace=True, na_values='Not Supported')
    single = pd.DataFrame(all_data).loc[0]
    id_ts = 0
    id_val = 1
    id_event = 2
    Slice['count'] = 0
    # First find columns with the data, will be different depending on how data was captured
    try:
        if 'S' in single[id_val]:  # captured with per core
            id_val += 2
            id_event += 2
    except TypeError:
        pass
    try:
        if np.isnan(single[id_event]):  # units column
            id_event += 1
    except TypeError:
        pass
    data = pd.DataFrame(all_data, columns=[id_ts, id_val, id_event])
    last_ts = -1
    ts = -1
    types = []
    strip_r0 = re.compile(r'r0+')
    for index, row in data.iterrows():
        pmu_event = row[id_event]
        event_ts = row[id_ts]
        try:
            val = int(row[id_val])
        except ValueError:
            if ts <= 0:
                print("- Found unsupported event %s" % pmu_event)
            continue
        pmu_event = pmu_event.lower()
        pmu_event = re.sub(strip_r0, 'r', pmu_event)
        try:
            event = translate_event[pmu_event]
        except KeyError:
            event = pmu_event
        # Handle new timestamp
        if event_ts != last_ts:
            handle_timestamp(event_data, ts, last_ts, types)
            ts = identify_slice(event_data, ts, types)
            ts += 1
            last_ts = event_ts
        # First time we encounter each event instead of try/except
        if ts == 0 and event not in event_data['count']:
            event_data['count'][event] = []
            event_data['pki'][event] = []
            if re.search(bw_related_pattern, event):
                event_data['bw'][event] = []
            types.append(event)
        # Collect event data, including timestamp and pki, override with new data if it appears in multiple files
        try:
            event_data['count'][event][ts] = val
        except IndexError:
            event_data['count'][event].append(val)
        try:
            ki = event_data['count']['instructions'][ts] / 1000
        except KeyError:
            ki = 1000
        except IndexError:
            ki = event_data['count']['instructions'][-1] / 1000
        try:
            event_data['pki'][event][ts] = (val / ki)
        except IndexError:
            event_data['pki'][event].append(val / ki)
    # And handle last timestamp extras
    handle_timestamp(event_data, ts, last_ts, types)

# Translate from event counter to event name
def read_events(filename):
    all_data = pd.read_csv(filename, comment='#', skipinitialspace=True)
    df = pd.DataFrame(data=all_data)
    names = {}
    for index, row in df.iterrows():
        names[row['id']] = row['name']
    return names

# Stack Plot
def get_stack_graph_data(data, timestamps, bases):
    x_list = []
    y_list_list = []
    legend_list = []

    for i, bn in enumerate(bases):
        y_list = []
        if bn not in data:
            print('No data for %s when plotting %s' % (bn, filename))
            continue
        # label_name = bn + ' pki'
        y_list = data[bn]

        y_list_list.append(y_list)
        legend_list.append(bn)
        # plot_labels.append(label_name)
    
    x_list = timestamps
    
    return (x_list, y_list_list, legend_list)

# Get data for line graphs (ratio)
def get_line_graph_data_ratio(data, timestamps, bases, refs):
    x_list_list = []
    y_list_list = []
    legend_list = []

    for i, bn in enumerate(bases):
        x_list = []
        y_list = []
        rn = refs[i]
        if bn not in data or rn not in data:
            print('No data for %s/%s when plotting %s' % (bn, rn, filename))
            continue

        x_list = timestamps[plots_start_id:plots_end_id]
        # divide, and convert to list
        y_list = np.divide(data[bn][plots_start_id:plots_end_id], data[rn][plots_start_id:plots_end_id]).tolist()
        
        # Append to _list_list
        x_list_list.append(x_list)
        y_list_list.append(y_list)
        legend_list.append(bn + '/' + rn)

    return (x_list_list, y_list_list, legend_list)

# Get data for line graphs
def get_line_graph_data(data, timestamps, bases):
    x_list_list = []
    y_list_list = []
    legend_list = []

    for i, bn in enumerate(bases):
        x_list = []
        y_list = []
        if bn not in data:
            print('No data for %s when plotting %s' % (bn, filename))
            continue

        x_list = timestamps
        y_list = data[bn]

        # Append to _list_list
        x_list_list.append(x_list)
        y_list_list.append(y_list)
        legend_list.append(bn)

    return (x_list_list, y_list_list, legend_list)

# THIS FUNCTION IS INCOMPLETE. Do NOT USE
# Get data for histogram
def get_histogram_data(data, bases):
    x_list_list = []
    legend_list = []
    bin_size = []

    for i, bn in enumerate(bases):
        x_list = []
        if bn not in data:
            print('No data for %s when plotting %s' % (bn, filename))
            return "error"
        print("PRINTING HISTOGRAM DATA")
        x_list = sorted(data[bn][plots_start_id:plots_end_id])

        # For 20 Number of bins, we calculate bin size as (max-min)/20
        bin_size.append((x_list[-1] - x_list[0])/20)

        x_list_list.append(x_list)
        legend_list.append(bn)
        # n, bins, patches = plt.hist(data[bn][plots_start_id:plots_end_id], 50, density=False, facecolor='g', alpha=0.75, label=bn)
        # print("N = ", n)
        # print("BINS = ", bins)
        # print("PATCHES = ", patches)

    return (x_list_list, legend_list, bin_size)

# Returns data of 'x_list_list' and 'y_list_list' for all the graphs
def get_all_counter_graphs_data(data, numCPUs):

    counter_graph_data = {
        'ipc_data_' + numCPUs  : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'Ratio'},
        'dmc_bandwidth_data_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'MB/s'},
        'dmc_histogram_data_' + numCPUs : {'x_list_list':[], 'legend_list':[], 'bin_size': [],'graph_type': 'histogram', 'xParameter': 'MB/s', 'yParameter': 'Percentage'},
        'l3c_bandwidth_data_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'MB/s'},
        'cache_miss_rates_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'Ratio'},
        'map_stall_cmp_data_' + numCPUs : {'x_list' : [], 'y_list_list':[], 'legend_list':[], 'graph_type': 'stack', 'xParameter': 'Timestamp', 'yParameter': 'pki'},
        'feu_stall_cmp_data_' + numCPUs : {'x_list' : [], 'y_list_list':[], 'legend_list':[], 'graph_type': 'stack', 'xParameter': 'Timestamp', 'yParameter': 'pki'},
        'itype_stacked_graph_' + numCPUs : {'x_list' : [], 'y_list_list':[], 'legend_list':[], 'graph_type': 'stack', 'xParameter': 'Timestamp', 'yParameter': 'pki'},
        'private_mpki_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'pki'},
        'L2_Latency_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'Ratio'},
        'stall_cmp_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'pki'},
        'Branch mispredict ratio_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'Ratio'},
        'Branch mpki_' + numCPUs : {'x_list_list':[], 'y_list_list':[], 'legend_list':[], 'graph_type': 'line', 'xParameter': 'Timestamp', 'yParameter': 'pki'},
    }

    # For readability 

    # IPC - Line Graph (Ratio)
    counter_graph_data['ipc_data_' + numCPUs]['x_list_list'], \
    counter_graph_data['ipc_data_' + numCPUs]['y_list_list'], \
    counter_graph_data['ipc_data_' + numCPUs]['legend_list'] = \
    get_line_graph_data_ratio(data['count'], data['ts'], ['instructions','INST_SPEC'], ['cycles','cycles'])

    # DMC Bandwidth - Line Graph
    counter_graph_data['dmc_bandwidth_data_' + numCPUs]['x_list_list'], \
    counter_graph_data['dmc_bandwidth_data_' + numCPUs]['y_list_list'], \
    counter_graph_data['dmc_bandwidth_data_' + numCPUs]['legend_list'] = \
    get_line_graph_data(data['bw'], data['ts'], ['DMC BW MB/s'])
    
    # DMC Histogram - Histogram
    counter_graph_data['dmc_histogram_data_' + numCPUs]['x_list_list'], \
    counter_graph_data['dmc_histogram_data_' + numCPUs]['legend_list'], \
    counter_graph_data['dmc_histogram_data_' + numCPUs]['bin_size'] =\
    get_histogram_data(data['bw'], ['DMC BW MB/s'])

    # L3C BW - Line Graph
    counter_graph_data['l3c_bandwidth_data_' + numCPUs]['x_list_list'], \
    counter_graph_data['l3c_bandwidth_data_' + numCPUs]['y_list_list'], \
    counter_graph_data['l3c_bandwidth_data_' + numCPUs]['legend_list'] = \
    get_line_graph_data(data['bw'], data['ts'], ['L3 BW MB/s'])

    # Cache Miss - Line Graph
    counter_graph_data['cache_miss_rates_' + numCPUs]['x_list_list'], \
    counter_graph_data['cache_miss_rates_' + numCPUs]['y_list_list'], \
    counter_graph_data['cache_miss_rates_' + numCPUs]['legend_list'] = \
    get_line_graph_data_ratio(data['count'], data['ts'], \
                        ['L1D_CACHE_REFILL','L2D_CACHE_REFILL','L3_0 Read Miss', 'L3_1 Read Miss'], \
                        ['L1_DCACHE_APPROX','L2D_CACHE_ACCESS','L3_0 Read Request', 'L3_1 Read Request'])

    # Private MPKI - Line Graph
    counter_graph_data['private_mpki_' + numCPUs]['x_list_list'], \
    counter_graph_data['private_mpki_' + numCPUs]['y_list_list'], \
    counter_graph_data['private_mpki_' + numCPUs]['legend_list'] = \
    get_line_graph_data(data['count'], data['ts'], ['L1D_CACHE_REFILL', 'L2D_CACHE_REFILL'])

    # L2 Latency - Line Graph (Ratio)
    counter_graph_data['L2_Latency_' + numCPUs]['x_list_list'], \
    counter_graph_data['L2_Latency_' + numCPUs]['y_list_list'], \
    counter_graph_data['L2_Latency_' + numCPUs]['legend_list'] = \
    get_line_graph_data_ratio(data['count'], data['ts'], ['L2 MSQ Valid Cycles'], ['L2 MSQ Alloc'])

    # Stall FE - Stall BE - Line Graph
    counter_graph_data['stall_cmp_' + numCPUs]['x_list_list'], \
    counter_graph_data['stall_cmp_' + numCPUs]['y_list_list'], \
    counter_graph_data['stall_cmp_' + numCPUs]['legend_list'] = \
    get_line_graph_data(data['pki'], data['ts'], ['STALL_FE', 'STALL_BE'])

    # Branch misprediction ratio - Line graph
    counter_graph_data['Branch mispredict ratio_' + numCPUs]['x_list_list'], \
    counter_graph_data['Branch mispredict ratio_' + numCPUs]['y_list_list'], \
    counter_graph_data['Branch mispredict ratio_' + numCPUs]['legend_list'] = \
    get_line_graph_data_ratio(data['count'], data['ts'], ['BR_MIS_PRED_RETIRED'], ['BR_RETIRED'])

    # Branch Misprediction PKI - Line Graph
    counter_graph_data['Branch mpki_' + numCPUs]['x_list_list'], \
    counter_graph_data['Branch mpki_' + numCPUs]['y_list_list'], \
    counter_graph_data['Branch mpki_' + numCPUs]['legend_list'] = \
    get_line_graph_data(data['pki'], data['ts'], ['BR_MIS_PRED_RETIRED'])

    # MAP Stall CMP - Stack Graph
    counter_graph_data['map_stall_cmp_data_' + numCPUs]['x_list'], \
    counter_graph_data['map_stall_cmp_data_' + numCPUs]['y_list_list'], \
    counter_graph_data['map_stall_cmp_data_' + numCPUs]['legend_list'] = \
    get_stack_graph_data(data['pki'], data['ts'], \
        ['MAP_ROB_RECYCLE', 'MAP_ISSQ_RECYCLE', 'MAP_LRQ_RECYCLE', 'MAP_SRQ_RECYCLE', 'MAP_GPR_RECYCLE', 'MAP_FPR_RECYCLE', 'MAP_BUB_RECYCLE'])

    # Feu Stall CMP - Stack Graph
    counter_graph_data['feu_stall_cmp_data_' + numCPUs]['x_list'], \
    counter_graph_data['feu_stall_cmp_data_' + numCPUs]['y_list_list'], \
    counter_graph_data['feu_stall_cmp_data_' + numCPUs]['legend_list'] = \
    get_stack_graph_data(data['pki'], data['ts'], \
        ['ALN_resteer', 'TAGE_resteer', 'DCD_resteer'])

    # IType - Stacked Graph
    counter_graph_data['itype_stacked_graph_' + numCPUs]['x_list'], \
    counter_graph_data['itype_stacked_graph_' + numCPUs]['y_list_list'], \
    counter_graph_data['itype_stacked_graph_' + numCPUs]['legend_list'] = \
    get_stack_graph_data(data['pki'], data['ts'], \
        ['Loads', 'Stores', 'BR_RETIRED', 'ASE_SPEC', 'VFP_SPEC'])

    return counter_graph_data

def process_perf_stat_files(nas_path, numCPUs):
    global options
    options = handle_params()
    options.path = [nas_path]

    # Manually add '.csv' files in include
    options.include.append('.csv')
    options.exclude.append('aggr')
 
    # The data that is captured from csv files
    event_data = {'count': {}, 'pki': {}, 'ts': [], 'bw': {}}
    global event_ids
    dict_file = './tx2_event_dict.csv'
    event_ids = read_events(dict_file)
    inc_pattern = re.compile('|'.join(options.include), re.IGNORECASE)
    exc_pattern = re.compile('|'.join(options.exclude), re.IGNORECASE)

    # For each file in that path
    for path in options.path:
        for file in os.listdir(path):
            # print("FILE = ", file)
            # Only consider files which match criteria
            if re.search(inc_pattern, file) and not re.search(exc_pattern, file):
                current = os.path.join(path, file)

                if os.path.isfile(current):
                    # Check whether current .csv files can be processed (Ignore files which can't be)
                    try:
                        process_perf_stat(current, event_ids, event_data)
                    except:
                        pass
    final_extra_metrics(event_data)
    # We have got full event_data now

    # if slice wanted and found, setup markers to use that,
    global plots_start_id, plots_end_id
    if 'id_end' in Slice:
        plots_start_id = Slice['id_start']
        plots_end_id = Slice['id_end']
    else:
        plots_start_id = options.ts_head
        if options.ts_tail < event_data['ts'][-1]:
            plots_end_id = next(x[0] for x in enumerate(event_data['ts']) if x[1] > options.ts_tail)
        else:
            plots_end_id = len(event_data['ts'])

    for e, ed in event_data['count'].items():
        plots_end_id = min(len(ed), plots_end_id)
    
    
    # Return data for all counter graphs
    return get_all_counter_graphs_data(event_data, numCPUs)
