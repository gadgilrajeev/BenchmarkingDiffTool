#!/bin/bash
echo "`date` Executing Cron job" >> /tmp/log_1.txt
source ./venv/bin/activate
python3 reports_best_results_cron.py
deactivate
