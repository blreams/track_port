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
from bokeh.models import ColumnDataSource, NumeralTickFormatter

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


def main():
    session = load_session()
    df_fg = pd.read_sql(session.query(PortHistory).filter(PortHistory.fileportname == 'port:fluffgazer').order_by('date').statement, session.bind)
    df_xc = pd.read_sql(session.query(PortHistory).filter(PortHistory.fileportname == 'port:xcargot').order_by('date').statement, session.bind)
    fg = ColumnDataSource(df_fg)
    xc = ColumnDataSource(df_xc)

    if host and host in ('jkt-myth', 'skx-linux',):
        output_file('www/daneel.homelinux.net/cgi-bin/port_plot.html')
    else:
        output_file('../cgi-bin/port_plot.html')
    f = figure(title='Port History', x_axis_type='datetime')
    f.line(x='date', y='total', source=fg, legend='fluffgazer', color='blue')
    f.line(x='date', y='total', source=xc, legend='xcargot', color='purple')

    f.border_fill_color = 'beige'
    f.background_fill_color = 'grey'
    f.background_fill_alpha = 0.3
    f.xaxis.axis_label = 'Date'
    f.yaxis.axis_label = 'Total'
    f.yaxis[0].formatter = NumeralTickFormatter(format="$0")
    f.sizing_mode = 'stretch_both'
    f.legend.title = 'Ports'
    f.legend.location = 'bottom_right'


    save(f)

if __name__ == '__main__':
    main()

