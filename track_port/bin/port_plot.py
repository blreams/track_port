#!/usr/bin/python
import time
import argparse
import cgi
import cgitb; cgitb.enable() # for troubleshooting

import os
import re
import jinja2
import datetime
import htmlmin

from collections import OrderedDict
from decimal import Decimal

from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from bokeh.plotting import figure
from bokeh.io import output_file, save
from bokeh.models import ColumnDataSource, NumeralTickFormatter, ZoomInTool, ZoomOutTool
from bokeh.models.annotations import Span

import pandas as pd

##############################################################################
# This section of code handles database access.
##############################################################################
try:
    host = os.uname()[1]
except:
    host = None

if host and host in ('jkt-myth', 'skx-linux',):
    engine = create_engine('mysql://blreams@localhost/track_port')
else:
    engine = create_engine('sqlite:///../cgi-bin/track_port.db')

Base = declarative_base(engine)
metadata = MetaData()


def load_session():
    """
    """
    metadata = Base.metadata
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

class PortHistory(Base):
    """
    """
    __tablename__ = 'port_history'
    __table_args__ = {'autoload': True}

def get_df(fileportname):
    return pd.read_sql(session.query(PortHistory).filter(PortHistory.fileportname == fileportname).order_by('date').statement, session.bind)

def get_x_range():
    earliest = max(df_fg['date'].min(), df_xc['date'].min())
    latest = min(df_fg['date'].max(), df_xc['date'].max())
    today = datetime.datetime.now().date()
    first_in_year = datetime.date(today.year, 1, 1)
    days_in = (today - first_in_year).days
    one_year_ago = datetime.date(today.year - 1, today.month, today.day)
    begin = earliest
    end = latest
    if days_in > 30:
        if earliest <= first_in_year:
            begin = first_in_year
            end = latest
    else:
        if earliest <= one_year_ago:
            begin = one_year_ago
            end = latest
    return begin, end

def get_y_range(x_range):
    df_fg_range = df_fg[(df_fg.date >= x_range[0]) & (df_fg.date <= x_range[1])]
    df_xc_range = df_xc[(df_xc.date >= x_range[0]) & (df_xc.date <= x_range[1])]
    lowest = min(df_fg_range.total.min(), df_xc_range.total.min())
    highest = max(df_fg_range.total.max(), df_xc_range.total.max())
    lowest = lowest - (highest * 0.01)
    highest = highest + (highest * 0.01)
    return lowest, highest

def main():
    global session
    global df_fg
    global df_xc
    session = load_session()
    df_fg = get_df('port:fluffgazer')
    df_xc = get_df('port:xcargot')
    fg = ColumnDataSource(df_fg)
    xc = ColumnDataSource(df_xc)

    x_range = get_x_range()
    y_range = get_y_range(x_range)
    if host and host in ('jkt-myth', 'skx-linux',):
        output_file('www/daneel.homelinux.net/web/port_plot.html')
    else:
        output_file('../cgi-bin/port_plot.html')
    f = figure(title='Port History', x_axis_type='datetime', x_range=x_range, y_range=y_range)
    f.line(x='date', y='total', source=fg, legend='fluffgazer', color='blue')
    f.line(x='date', y='total', source=xc, legend='xcargot', color='purple')

    max_span_fg = Span(location=df_fg.max()['total'], dimension='width', line_color='blue', line_dash='dashed', line_alpha=0.3)
    max_span_xc = Span(location=df_xc.max()['total'], dimension='width', line_color='purple', line_dash='dashed', line_alpha=0.3)
    min_span_fg = Span(location=df_fg.min()['total'], dimension='width', line_color='blue', line_dash='dashed', line_alpha=0.3)
    min_span_xc = Span(location=df_xc.min()['total'], dimension='width', line_color='purple', line_dash='dashed', line_alpha=0.3)
    f.add_layout(max_span_fg)
    f.add_layout(max_span_xc)
    f.add_layout(min_span_fg)
    f.add_layout(min_span_xc)

    f.border_fill_color = 'beige'
    f.background_fill_color = 'grey'
    f.background_fill_alpha = 0.3
    f.xaxis.axis_label = 'Date'
    f.yaxis.axis_label = 'Total'
    f.yaxis[0].formatter = NumeralTickFormatter(format="$0")
    f.sizing_mode = 'stretch_both'
    f.legend.title = 'Ports'
    f.legend.location = 'bottom_right'

    f.add_tools(ZoomInTool())
    f.add_tools(ZoomOutTool())

    save(f)

if __name__ == '__main__':
    main()

