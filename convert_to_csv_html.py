#!/usr/bin/python
import os
import yaml
import argparse
import numpy as np
import pandas as pd
from collections import OrderedDict

# Set pandas options
pd.set_option('mode.chained_assignment', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 1000)

# ReadItem, if not exists, set 0 value


def readItem(item, itemname):
    if itemname not in item['donneesNationales']:
        return 0

    return item['donneesNationales'][itemname]


def formatInt(value):
    change = str(value)
    change = change.replace('.0', '')

    if 'nan' in change:
        change = '?'

    return change


def formatDiff(value):
    change = str(value)
    change = change.replace('.0', '')
    if change != '' and change != '0' and '-' not in change:
        change = f'+{change}'

    if 'inf' in change:
        change = '?'

    return change


def formatVariation(value):
    if value == '':
        return ''

    change = str(value)
    change = change.replace('.0', '')
    if change != '' and change != '0' and '-' not in change:
        change = f'+{change}'

    if 'inf' in change:
        change = '?'

    if change != '' and change != '?':
        change += '%'

    return change


def formatStyle(value, **kwargs):
    change = str(value)
    change = change.replace('.0', '')
    if change != '' and change != '0' and '-' not in change:
        change = f'+{change}'

    if 'inf' in change:
        change = '?'

    state = ['bad', 'good', 'unknow']

    if '+' in change:
        # Bad
        styleidx = 0
        if kwargs['variation'] and value < 5:
            # unknow
            styleidx = 2

    elif '-' in change:
        # Good
        styleidx = 1
        if kwargs['variation'] and value > -5:
            # unknow
            styleidx = 2
    else:
        # unknow
        styleidx = 2

    # Reverse trend if needed
    if kwargs['reverse'] and styleidx != 2:
        styleidx = styleidx ^ 1

    return state[styleidx]


# Argument options
ap = argparse.ArgumentParser()
ap.add_argument("-p", "--path",	help="Git repo Path")
args = vars(ap.parse_args())

# Init columns informations
options = {'reverse': []}
days = [1, 7, 15, 30]
fieldscolumn = OrderedDict()
fieldscolumn = {
    'cas_confirmes': {
        'total': True,

    },
    'hospitalises': {
        'total': False,

    },
    'nouvelles_hospitalisations': {
        'total': False,

    },
    'gueris': {
        'total': True,
        'reverse': True,

    },
    'reanimation': {
        'total': False,

    },
    'nouvelles_reanimations': {
        'total': False,

    },
    'deces': {
        'total': True,


    },
    'cas_ehpad': {
        'total': True,


    },
    'cas_confirmes_ehpad': {
        'total': True,


    },
    'deces_ehpad': {
        'total': True,

    }
}


# Read OpenCovid19 datas
orig = pd.read_csv(
    'https://raw.githubusercontent.com/opencovid19-fr/data/master/dist/chiffres-cles.csv',
    sep=','
)
orig = orig.set_index('date')

# Create mask
mask_MSS = (orig['source_type'] ==
            'ministere-sante') & (orig['granularite'] == 'pays')

mask_OC19 = (orig['source_type'] ==
             'opencovid19-fr') & (orig['granularite'] == 'pays')

df_MSS = orig[mask_MSS]
df_OC19 = orig[mask_OC19]

# Merge datas
dfall = df_MSS
dfall['nouvelles_hospitalisations'] = df_OC19['nouvelles_hospitalisations']
dfall['nouvelles_reanimations'] = df_OC19['nouvelles_reanimations']

# Calc computed fields
# ex: avg, diff, var, var_diff, etc ..
for field in fieldscolumn:
    for d in days:
        dfall[f'prev_{field}_{d}j'] = dfall[field].shift(-d)
        if not fieldscolumn[field]['total'] and d > 1:
            dfall[f'avg_{field}_{d}j'] = dfall[field].rolling(
                window=d).mean().round(2)
            dfall[f'prev_avg_{field}_{d}j'] = dfall[f'avg_{field}_{d}j'].shift(-d)

        dfall[f'diff_{field}_{d}j'] = dfall[field].diff(periods=d)
        dfall[f'prev_diff_{field}_{d}j'] = dfall[f'diff_{field}_{d}j'].shift(-d)

        dfall[f'diff_diff_{field}_{d}j'] = dfall[f'diff_{field}_{d}j'].diff(
            periods=d)
        dfall[f'prev_diff_diff_{field}_{d}j'] = dfall[f'diff_diff_{field}_{d}j'].shift(-d)


        dfall[f'var_{field}_{d}j'] = (dfall[field].pct_change(
            periods=d)*100).round(2)
        dfall[f'prev_var_{field}_{d}j'] = dfall[f'var_{field}_{d}j'].shift(-d)

        dfall[f'var_diff_{field}_{d}j'] = (dfall[f'diff_{field}_{d}j'].pct_change(
            periods=1)*100).round(2)
        dfall[f'prev_var_diff_{field}_{d}j'] = dfall[f'var_diff_{field}_{d}j'].shift(-d)

        # options
        if 'reverse' in fieldscolumn[field] and fieldscolumn[field]['reverse']:
            options['reverse'].append(f'diff_{field}_{d}j')
            options['reverse'].append(f'var_{field}_{d}j')
            options['reverse'].append(f'var_diff_{field}_{d}j')

# Order columns for exporting CSV file
dfcolumns = []
subfields = ['var', 'diff', 'avg', 'var_diff','prev']
for field in fieldscolumn:
    dfcolumns.append(field)

for subfield in subfields:
    for d in days:
        for field in fieldscolumn:
            # Avg
            if subfield == 'avg':
                if not fieldscolumn[field]['total']:
                    if d > 1:
                        dfcolumns.append(f'{subfield}_{field}_{d}j')

            # Global Variation
            if subfield == 'var':
                # Keep only positive value
                if not fieldscolumn[field]['total']:
                    mask = dfall[f'{subfield}_{field}_{d}j'] < 0
                    dfall[mask][f'{subfield}_{field}_{d}j'] = ""

                dfcolumns.append(f'{subfield}_{field}_{d}j')

            # Diff
            if subfield in ['diff','var_diff','prev']:
                dfcolumns.append(f'{subfield}_{field}_{d}j')



# Save to CSV Raw
df = dfall[dfcolumns]
df.to_csv('/tmp/summary.csv', sep=';')

####################
# Compute trend
####################

# Add trend column
for column in df.columns:
    if 'var_' in column:
        # # Convert to percent
        # dfall[column] = (dfall[column]*100.0).round(2)

        # Compute trend
        trendcol = column.replace('var_', 'trend_')

        # positive=['⬌','⬈','⬈⬈','⬈⬈⬈']
        # negative=['⬌','⬊','⬊⬊','⬊⬊⬊']

        notrend = '⬌'
        positive = [notrend, '⬈', '⬈', '⬈']
        negative = [notrend, '⬊', '⬊', '⬊']

        # Init new colmn
        unknow = '?'
        dfall[trendcol] = unknow

        mask = (dfall[column] <= -5) & (dfall[column] > -25)
        dfall[trendcol][mask] = negative[1]

        mask = (dfall[column] <= -25) & (dfall[column] > -50)
        dfall[trendcol][mask] = negative[2]

        mask = dfall[column] <= -50
        dfall[trendcol][mask] = negative[3]

        mask = (dfall[column] >= -5) & (dfall[column] < 5)
        dfall[trendcol][mask] = positive[0]

        mask = (dfall[column] >= 5) & (dfall[column] < 25)
        dfall[trendcol][mask] = positive[1]

        mask = (dfall[column] >= 25) & (dfall[column] < 50)
        dfall[trendcol][mask] = positive[2]

        mask = dfall[column] >= 50
        dfall[trendcol][mask] = positive[3]


# No mouvement
for field in fieldscolumn:
    for d in days:
        mask = (dfall[f'diff_{field}_{d}j'] == 0) & (
            dfall[f'trend_diff_{field}_{d}j'] == unknow)
        dfall[f'var_diff_{field}_{d}j'][mask] = 0
        dfall[f'trend_diff_{field}_{d}j'][mask] = notrend

outfieldcolumns = [
    'cas_confirmes',
    'hospitalises',
    'nouvelles_hospitalisations',
    'gueris',
    'reanimation',
    'nouvelles_reanimations',
    'deces',
    'cas_confirmes_ehpad',
    'cas_ehpad',
    'deces_ehpad']

outstatscolumns = ['diff', 'var_diff', 'trend_diff']

outcolumns = outfieldcolumns.copy()
for outfield in outfieldcolumns:
    for d in days:
        for statcolumn in outstatscolumns:
            outcolumns.append(f'{statcolumn}_{outfield}_{d}j')


df = dfall[outcolumns]
df.to_csv('/tmp/trend.csv', sep=';')

###########################
# Format text columns
###########################


dfall = dfall.replace(np.nan, '', regex=True)
for column in dfall.columns:
    if column in fieldscolumn:
        dfall[column] = dfall[column].apply(formatInt)

    if column.startswith('diff_'):
        dfall[f'txt_{column}'] = dfall[column].apply(formatDiff)
        dfall[f'{column}_color'] = dfall[column].apply(
            formatStyle, reverse=column in options['reverse'], variation=False)

    if column.startswith('var_'):
        dfall[f'txt_{column}'] = dfall[column].apply(formatVariation)
        dfall[f'{column}_color'] = dfall[column].apply(
            formatStyle, reverse=column in options['reverse'], variation=True)


###########################
# Generate HTML index pages
###########################
htmlcolumn = ['cas_confirmes', 'hospitalises', 'nouvelles_hospitalisations',
              'gueris', 'reanimation', 'nouvelles_reanimations', 'deces',
              'cas_ehpad', 'cas_confirmes_ehpad', 'deces_ehpad']


html = """<html lang="fr">
<head>
  <meta charset="utf-8">

  <title>Report</title>
  <meta name="description" content="Covid report">
  <link rel="stylesheet" href="./style.css">

</head>

<body>

<table width="100%">
  <caption>Rapport</caption>
  <thead>
    <tr>
      <th class='center' scope="col" >Date</th>
"""
for column in htmlcolumn:
    html += f"""<th class='center' scope="col" colspan=3>{column}</th>"""

html += f"""
    </tr>
  </thead>
  <tbody>
"""


df = dfall.iloc[::-1]

for idx, item in df.iterrows():
    html += f"""
    <tr>
      <td class="center" scope="row" data-label="date">{idx}</td>
"""

    for column in htmlcolumn:
        html += f"""<td class="center field" scope="row" data-label="{column}">{item[column]} (<span class="{item[f'diff_{column}_1j_color']}">{item[f'txt_diff_{column}_1j']}</span>)</td>"""

        html += f"""<td class="right" scope="row" data-label="day">"""
        for d in days:
            html += f"J-{d}</br>"
        html += "</td>"


        html += f"""<td class="left" scope="row" data-label="{column}_trend">"""

        for d in days:
            html += f"""<span class="{item[f'var_diff_{column}_{d}j_color']}">{item[f'trend_diff_{column}_{d}j']} {item[f'var_diff_{column}_{d}j']}</span>&nbsp;({item[f'txt_diff_diff_{column}_{d}j']})</br>"""

        html += "</td>"

    html += "</tr>"

html += """</tbody>
</table>"""

with open('index.html', 'w') as f:
    f.write(html)

###########################
# Generate HTML day page
###########################


df = dfall

last = None
for idx, item in df.iterrows():
    html = f"""<html lang="fr">
    <head>
    <meta charset="utf-8">

    <title>Report</title>
    <meta name="description" content="Résumé pour {idx}">
    <link rel="stylesheet" href="./style.css">
    </head>

    <body>
    """



    html += f"""<h1>Rapport journalier pour {idx}</h1>"""
    html += f"""{item['cas_confirmes']} cas confirmés en France"""
    html += "<ul>"
    for d in days:
        if last is not None and not pd.isna(item[f'diff_cas_confirmes_{d}j']):
            html += f"""<li>Sur {d}j : Variation ({item[f'txt_diff_cas_confirmes_{d}j']} / <span class="{item[f'diff_cas_confirmes_{d}j_color']}">{item[f'txt_var_cas_confirmes_{d}j']}</span>), variation de la tendance {item[f'txt_var_diff_cas_confirmes_{d}j']} (Prec.: {last[f'txt_diff_cas_confirmes_{d}j']})</li>"""
        else:
            html += f"""<li>Sur {d}j : Variation ({item[f'txt_diff_cas_confirmes_{d}j']} / <span class="bad">{item[f'txt_var_cas_confirmes_{d}j']}</span>)</li>"""

        last = item

    html += "</ul>"
    html += """
    < /body > </html >
    """

    filename = f'index-{idx}.html'
    with open(filename, 'w') as f:
        f.write(html)
