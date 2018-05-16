from datetime import datetime, timedelta

import click
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from requests.auth import HTTPBasicAuth
from whoswho import who

MONTH_MAPPINGS = {
    1: 'Jan',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'Aug',
    9: 'Sep',
    10: 'Oct',
    11: 'Nov',
    12: 'Dec'
}

API_KEY = '[your_Bamboo_api_key_here]'
BAMBOO_BASE_URL = 'https://api.bamboohr.com/api/gateway.php/prodigyfinance/v1'


def get_people_off(start_date, end_date):
    bamboo_date_format = '%Y-%m-%d'
    url = '{base}/time_off/whos_out/?start={start_date}&end={end_date}'.format(
        base=BAMBOO_BASE_URL,
        start_date=start_date.strftime(bamboo_date_format),
        end_date=end_date.strftime(bamboo_date_format)
    )
    headers = {
        'Accept': 'application/json'
    }

    resp = requests.get(url, auth=HTTPBasicAuth(API_KEY, 'x'), headers=headers).json()
    return resp


def get_assigned_parkings(page_html, months):
    soup = BeautifulSoup(page_html, 'html.parser')
    table = soup.find(lambda tag: tag.name == 'table' and'confluenceTable' in tag['class'])
    rows = table.findAll(lambda tag: tag.name == 'tr')
    month_texts = [MONTH_MAPPINGS[x] for x in months]
    res = []
    for row in rows:
        cells = row.findChildren('td')
        if len(cells) > 0:
            # months
            if not any([str(cells[0].string) in x for x in month_texts]):
                continue
            entry = {
                'bay': cells[1].string,
                'name': cells[2].string,
                'car': cells[3].string
            }
            res.append(entry)
    return res


def find_gaps(parkings, people_off):
    matches = []
    for parking in parkings:
        for person in people_off:
            if person['type'] == 'holiday':
                continue
            if who.match(parking['name'], person['name']):
                matches.append({
                    'name': person['name'],
                    'bay': parking['bay'],
                    'date_from': date_parser.parse(person['start']),
                    'date_to': date_parser.parse(person['end'])
                })

    return matches


def build_schedule(gaps, date_from, date_to):
    schedule = {}
    for gap in gaps:
        day_deltas = gap['date_to'] - gap['date_from']
        for i in range(day_deltas.days + 1):
            new_date = gap['date_from'] + timedelta(days=i)
            if new_date > date_to or new_date < date_from:
                continue
            if new_date.weekday() in[5, 6]:  # Don't care about weekends
                continue
            if new_date not in schedule:
                schedule[new_date] = []
            schedule[new_date].append({'bay': gap['bay'], 'name': gap['name']})
    return schedule


def print_schedule(schedule):
    for key in sorted(schedule.keys()):
        print('%s - %s ' % (key, schedule[key]))


@click.command()
@click.option('--date-from', default=datetime.now(), help='Inclusive, date from which to scan')
@click.option('--date-to', default=datetime.now() + timedelta(days=30), help='Inclusive, ending/last date to scan to')
def main(date_from, date_to):
    date_from = date_parser.parse(date_from) if isinstance(date_from, str) else date_from
    date_to = date_parser.parse(date_to) if isinstance(date_to, str) else date_to
    html = open('parking.html', 'r').read().replace('\n', '')
    months = list(range(date_from.month, date_to.month + 1))
    parkings = get_assigned_parkings(html, months)
    if not parkings:
        raise Exception('Could not get parking information')
    people_off = get_people_off(date_from, date_to)
    gaps = find_gaps(parkings, people_off)
    schedule = build_schedule(gaps, date_from, date_to)
    print_schedule(schedule)

if __name__ == '__main__':
    main()
