#!/bin/bash

source .venv/bin/activate
python convert_to_csv_html.py -p /tmp/opencovid19/ministere-sante
git pull &&
git add . &&
git commit -m "update data (cron job)"
git push

