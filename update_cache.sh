#!/bin/bash
script_dir=`dirname "${BASH_SOURCE[0]}"`
echo "`date` Executing Cron job" >> /tmp/log_1.txt
source "$script_dir/venv/bin/activate"
python3 "$script_dir/reports_best_results_cron.py"
deactivate
