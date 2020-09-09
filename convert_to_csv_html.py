#!/usr/bin/python
import os
import re
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

COUNTER=1
GAUGE=2
SRCIMAGE="src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='"

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
    change = re.sub(r'\.0+$','',change)
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
        if kwargs['minvariation'] and value < 5:
            # unknow
            styleidx = 2

    elif '-' in change:
        # Good
        styleidx = 1
        if kwargs['minvariation'] and value > -5:
            # unknow
            styleidx = 2
    else:
        # unknow
        styleidx = 2

    # Reverse trend if needed
    if kwargs['reverse'] and styleidx != 2:
        styleidx = styleidx ^ 1

    return state[styleidx]


def getPowerImage(value):
    height = 18
    width = 50
    emptyimage=f"""<img {SRCIMAGE} width={width}px height={height} style="background-color:#808080;"/>"""
    separator=f"""<img {SRCIMAGE} width=2px height={height}"/>"""

    if isinstance(value,str):
        image = f'{emptyimage}{emptyimage}'
    else:
        realwidth = int(abs(value) / 100*width)
        emptywidth = width-realwidth
        if value < 0:
            image = f"""<img {SRCIMAGE} width={emptywidth}px height={height} style="background-color:#808080;"/><img {SRCIMAGE} width={realwidth}px height={height} style="background-color:#00FF00;"/>"""
            image += f'{separator}{emptyimage}'
        else:
            image = f'{emptyimage}{separator}'
            image += f"""<img {SRCIMAGE} width={realwidth}px height={height} style="background-color:#FF0000;"/><img {SRCIMAGE} width={emptywidth}px height={height} style="background-color:#808080;"/>"""

    return image

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
        'type': COUNTER,

    },
    'hospitalises': {
        'type': GAUGE,

    },
    'nouvelles_hospitalisations': {
        'type': GAUGE,

    },
    'gueris': {
        'type': COUNTER,
        'reverse': True,

    },
    'reanimation': {
        'type': GAUGE,

    },
    'nouvelles_reanimations': {
        'type': GAUGE,

    },
    'deces': {
        'type': COUNTER,


    },
    'cas_ehpad': {
        'type': COUNTER,


    },
    'cas_confirmes_ehpad': {
        'type': COUNTER,


    },
    'deces_ehpad': {
        'type': COUNTER,

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


# flag empty values
for field in fieldscolumn:
    dfall[f'{field}_isna'] = dfall[field].isna()


# Replace empty values
for field in fieldscolumn:
    #dfall[field] = dfall[field].fillna(method='ffill')
    dfall[field] = dfall[field].interpolate().fillna(0).astype(int)


# Calc computed fields
# ex: avg, diff, var, var_diff, etc ..
for field in fieldscolumn:
    for d in days:
        # Commons
        dfall[f'diff_{field}_{d}j'] = dfall[field].diff(periods=d)

        # Counter
        if fieldscolumn[field]['type'] == COUNTER:
            dfall[f'sum_{field}_{d}j'] = dfall[f'diff_{field}_1j'].rolling(
                window=d).sum().round(2)

        # Gauge
        if fieldscolumn[field]['type'] == GAUGE:
            # SUM
            dfall[f'sum_{field}_{d}j'] = dfall[field].rolling(
                window=d).sum().round(2)

        # Commons
        dfall[f'prev_{field}_{d}j'] = dfall[field].shift(-d)

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

        # Sum
        dfall[f'diff_sum_{field}_{d}j'] = dfall[f'sum_{field}_{d}j'].diff(periods=1)

        dfall[f'var_sum_{field}_{d}j'] = (dfall[f'sum_{field}_{d}j'].pct_change(
            periods=1)*100).round(2)
        dfall[f'cummax_sum_{field}_{d}j'] = dfall[f'sum_{field}_{d}j'].cummax().round(2)

        dfall[f'power_sum_{field}_{d}j'] = ((dfall[f'sum_{field}_{d}j']/dfall[f'cummax_sum_{field}_{d}j'])*100).round(2).abs()*np.sign(dfall[f'diff_sum_{field}_{d}j'])

        dfall[f'avg_{field}_{d}j'] = dfall[field].rolling(
            window=d).mean().round(2)


        dfall[f'cummax_avg_{field}_{d}j'] = dfall[f'avg_{field}_{d}j'].cummax().round(2)

        dfall[f'prev_avg_{field}_{d}j'] = dfall[f'avg_{field}_{d}j'].shift(-d)

        # options
        if 'reverse' in fieldscolumn[field] and fieldscolumn[field]['reverse']:
            options['reverse'].append(f'diff_{field}_{d}j')
            options['reverse'].append(f'var_{field}_{d}j')
            options['reverse'].append(f'var_diff_{field}_{d}j')

# Order columns for exporting CSV file
dfcolumns = []
subfields = ['var','diff','var_diff','sum','diff_sum','cummax_sum','power_sum', 'var_sum','avg', 'cummax_avg' ,'prev']
#for field in fieldscolumn:

for field in fieldscolumn:
    dfcolumns.append(field)
    dfcolumns.append(f'{field}_isna')
    for d in days:
        for subfield in subfields:
            # Global Variation
            if subfield == 'var':
                # Keep only positive value
                if fieldscolumn[field]['type'] == GAUGE:
                    mask = dfall[f'{subfield}_{field}_{d}j'] < 0
                    dfall[mask][f'{subfield}_{field}_{d}j'] = ""

                dfcolumns.append(f'{subfield}_{field}_{d}j')
                continue

            # Diff
            if subfield in ['diff','var_diff','prev']:
                dfcolumns.append(f'{subfield}_{field}_{d}j')
                continue

            # Other fields
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

#outcolumns = outfieldcolumns.copy()
outcolumns = []
for outfield in outfieldcolumns:
    outcolumns.append(outfield)
    for statcolumn in outstatscolumns:
        for d in days:
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
            formatStyle, reverse=column in options['reverse'], minvariation=False)

    if column.startswith('var_'):
        dfall[f'txt_{column}'] = dfall[column].apply(formatVariation)
        dfall[f'{column}_color'] = dfall[column].apply(
            formatStyle, reverse=column in options['reverse'], minvariation=True)

    if column.startswith('power_'):
        dfall[f'txt_{column}'] = dfall[column].apply(formatVariation)
        dfall[f'{column}_color'] = dfall[column].apply(
            formatStyle, reverse=column in options['reverse'], minvariation=False)

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

# headdays = ""
# for d in days:
#     headdays += f"J-{d} "

stylecols = ['odd','even']
colidx = 0
for column in htmlcolumn:
    stylecol = stylecols[colidx % 2]
    colidx += 1
    html += f"""<th class='center {stylecol}' scope="col" colspan={len(days)+1}>{column}</th>"""

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
    colidx = 0
    for column in htmlcolumn:
        stylecol = stylecols[colidx % 2]
        colidx += 1
        # if fieldscolumn[column]['type']==COUNTER:
        #     html += f"""<td class="center field {stylecol}" scope="row" data-label="{column}">{item[column]} (<span class="{item[f'diff_{column}_1j_color']}">{item[f'txt_diff_{column}_1j']}</span>)</td>"""
        # else:
        #     html += f"""<td class="center field {stylecol}" scope="row" data-label="{column}">{item[column]}</td>"""

        # Show Empty value
        if item[f'{column}_isna']:
            html += f"""<td class="center field {stylecol}" scope="row" data-label="{column}"><span class='empty'>({item[column]})</span></td>"""
        else:
            html += f"""<td class="center field {stylecol}" scope="row" data-label="{column}">{item[column]}</td>"""


        # html += f"""<td class="right" scope="row" data-label="day">"""
        # for d in days:
        #     html += f"J-{d}</br>"
        # html += "</td>"


        for d in days:
            html += f"""<td class="left {stylecol}" scope="row" data-label="{column}_trend">"""
            # if fieldscolumn[column]['type']==COUNTER:
            #     html += f"""<span class="{item[f'var_diff_{column}_{d}j_color']}">{item[f'trend_diff_{column}_{d}j']} {item[f'var_diff_{column}_{d}j']}</span>&nbsp;({item[f'txt_diff_diff_{column}_{d}j']})</br>"""
            # else:
            #     value = 0
            #     if not isinstance(item[f'power_sum_{column}_{d}j'],str):
            #         value = item[f'power_sum_{column}_{d}j']

            #     html += f"""J-{d}&nbsp;{getPowerImage(value)}&nbsp;(<span class="{item[f'power_sum_{column}_{d}j_color']}">&nbsp;{item[f'power_sum_{column}_{d}j']}</span> / {item[f'sum_{column}_{d}j']}) &nbsp; ({item[f'txt_diff_sum_{column}_{d}j']}/<span class="{item[f'diff_sum_{column}_{d}j_color']}">{item[f'txt_var_sum_{column}_{d}j']}</span>)</br>"""


            value = 0
            if not isinstance(item[f'power_sum_{column}_{d}j'],str):
                value = item[f'power_sum_{column}_{d}j']

            html += f"""J-{d}&nbsp;{getPowerImage(value)}&nbsp;P:(<span class="{item[f'power_sum_{column}_{d}j_color']}">&nbsp;{item[f'power_sum_{column}_{d}j']}%</span> / {item[f'sum_{column}_{d}j']}) &nbsp; V-1:({item[f'txt_diff_sum_{column}_{d}j']}/<span class="{item[f'diff_sum_{column}_{d}j_color']}">{item[f'txt_var_sum_{column}_{d}j']}</span>)</br>"""


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
