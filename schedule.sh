#!/bin/bash

python3 -m pip install -r requirements.txt &&
python3 convert_to_csv.py > index.html &&
git add . &&
git commit -m "update data (cron job)"
git push
