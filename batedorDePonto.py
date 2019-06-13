#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import calendar
import sys
import argparse
import pandas
import csv


point_date_format = '%Y-%m-%d %H:%M'
point_key_format = '%Y-%m-%d'
csv_format = point_key_format
time_format = '%H:%M'
arg_date_format = '%m/%Y'
preferences_suffix = '###PREFERENCES_END'


def arg_to_date(arg):
    return datetime.datetime.strptime(arg, arg_date_format)


def set_last_day_of_month(date):
    first, last = calendar.monthrange(date.year, date.month)
    return date.replace(day=last)


def is_point_valid(point):
   if point == '':
       return False
   try:
       datetime.datetime.strptime(point, point_date_format)
       return True
   except:
       return False


def point_line_to_date(line):
    return datetime.datetime.strptime(line.split(';')[0], point_date_format)


def get_point_lines(lines):
    after_preferences = lines[lines.index(preferences_suffix) + 1:]
    return [
       line.split(';')[0]
       for line in after_preferences
    ]


def read_series(filename):
    with open(filename) as fin:
        lines = [line.strip() for line in fin]
        point_lines = get_point_lines(lines)
        valid_point_lines = filter(is_point_valid, point_lines)
        series = [point_line_to_date(point_line) for point_line in valid_point_lines]
        series.sort()
        return series


def filter_points_inside_range(series, start_date, end_date):
    return [
        point
        for point in series
        if start_date <= point and point <= end_date
    ]


def is_business_day(date):
    return bool(len(pandas.bdate_range(date, date)))


def get_min_max_dates(dates):
    min_date = pandas.Timestamp.max
    max_date = pandas.Timestamp.min
    
    for date in dates:
        if date < min_date:
            min_date = date
        if date > max_date:
            max_date = date

    return min_date, max_date


def point_to_key(point):
    return point.strftime(point_key_format)


def get_empty_grouped_points(start_date, end_date):
    dates_in_range = pandas.date_range(start=start_date, end=end_date).to_pydatetime().tolist()
    return {
        point_to_key(date): {
            'working': False,
            'original_date': date
        }
        for date in dates_in_range
    }


def update_day_stats(day_stats, point):
    if day_stats['working']:
        day_stats['seconds'] += (point - day_stats['last_point']).total_seconds()
        day_stats['working'] = False
    else:
        day_stats['working'] = True
        day_stats['last_point'] = point
        if 'seconds' not in day_stats:
            day_stats['first_point'] = point
            day_stats['seconds'] = 0

    return day_stats


def group_points(series, start_date, end_date):
    inside_range = filter_points_inside_range(series, start_date, end_date)
    min_date, max_date = get_min_max_dates(inside_range)
    partial_grouped_points = get_empty_grouped_points(min_date, max_date)
    
    for point in series:
        update_day_stats(partial_grouped_points[point_to_key(point)], point)

    return partial_grouped_points


def point_to_row(p):
    point_date = datetime.datetime.strftime(p['original_date'], csv_format)
    weekday = p['original_date'].weekday()

    if 'first_point' not in p or p['working']:
        if weekday >= 5:
            day_name = 'SÁBADO' if weekday == 5 else 'DOMINGO'
            return [point_date] + ([day_name] * 4)
        else:
            return [point_date, '', '12:00', '13:00', '']

    breaks_in_seconds = 90 * 60
    exit_time = p['first_point'] + datetime.timedelta(0, breaks_in_seconds + p['seconds'])
    return [
        point_date,
        datetime.datetime.strftime(p['first_point'], time_format),
        '12:00',
        '13:00',
        datetime.datetime.strftime(exit_time, time_format)
    ]


def generate_csv(grouped_points, output_filename):
    with open(output_filename, 'w') as csvfile:
        writer = csv.writer(csvfile)
        rows = list(map(point_to_row, grouped_points.values()))
        print(rows)
        for row in rows:
            writer.writerow(row)



parser_desc = 'Transforma backup do app "Ponto Fácil" em um CSV no formato para inserção na planilha de ponto da WayCarbon.'
parser = argparse.ArgumentParser(description=parser_desc)
parser.add_argument(
    '-f', '--file',
    dest='filename',
    required=True,
    help='Caminho do arquivo de backup do app'
)
parser.add_argument(
    '-o', '--output',
    dest='output_filename',
    default='agregado.csv',
    help='Caminho do CSV a ser criado'
)
parser.add_argument(
    '-s', '--start',
    dest='start_date',
    type=arg_to_date,
    default=pandas.Timestamp.min,
    help='Mês início opcional para a análise. Formato: MM/YYYY'
)
parser.add_argument(
    '-e', '--end',
    dest='end_date',
    type=lambda x: set_last_day_of_month(arg_to_date(x)),
    default=pandas.Timestamp.max,
    help='Mês fim opcional para a análise. Formato: MM/YYYY'
)


args = parser.parse_args()
series = read_series(args.filename)
grouped_points = group_points(series, args.start_date, args.end_date)


still_open_days = list(filter(lambda agg_tup: agg_tup[1]['working'], grouped_points.items()))
if len(still_open_days) > 0:
    print('ERRO! Os seguintes dias não tiveram um ponto de fechamento:')
    print('\n'.join([key for key, agg in still_open_days]))
    print('\nATENÇÃO: O CSV será criado ignorando os dias sem ponto de fechamento.\n')


generate_csv(grouped_points, args.output_filename)
