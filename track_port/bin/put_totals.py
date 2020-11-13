#!/usr/bin/env python3

import sys
import os
import logging
import logging.config
import argparse
from datetime import datetime, date, time, timedelta

from sqlalchemy import create_engine, Table, MetaData, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from finviz.screener import Screener

import urllib.parse
import requests
from bs4 import BeautifulSoup
import get_a_quote

#############################################################################
# This stuff needs to be done as globals
#############################################################################
try:
    host = os.uname()[1]
except:
    host = None

if host and host in ('skx-linux',):
    engine = create_engine('mysql://blreams@localhost/track_port')
else:
    engine = create_engine('sqlite:///track_port.db')
Base = declarative_base(engine)
metadata = Base.metadata
Session = sessionmaker(bind=engine)
session = Session()

#############################################################################
# Additional globals
#############################################################################
thisdir = os.path.dirname(__file__)

logging.config.fileConfig(os.path.join(thisdir, 'put_totals_logging.conf'))
arguments = argparse.Namespace

#############################################################################
# Classes related to database tables
#############################################################################
class TransactionLists(Base):
    __tablename__ = 'transaction_list'
    __table_args__ = {'autoload': True}

class TickerSymbols(Base):
    __tablename__ = 'ticker_symbols'
    __table_args__ = {'autoload': True}

class FinanceQuotes(Base):
    __tablename__ = 'finance_quote'
    __table_args__ = {'autoload': True}

class MarketHolidays(Base):
    __tablename__ = 'market_holiday'
    __table_args__ = {'autoload': True}

class PortParams(Base):
    __tablename__ = 'port_param'
    __table_args__ = {'autoload': True}

class PortHistories(Base):
    __tablename__ = 'port_history'
    __table_args__ = {'autoload': True}


#############################################################################
# Other classes
#############################################################################
class PortParamTable(object):
    def __init__(self):
        self.logger = logging.getLogger('PortParamTable')

    def get_fileportnames(self):
        pass

    def parse_transactions(self, fileportname):
        pass

    def calculate_stats(self, fileportname):
        pass

    def create_table_dict(self):
        pass

    def commit(self):
        pass


class PortHistoryTable(object):
    def __init__(self, port_param_table):
        self.logger = logging.getLogger('PortHistoryTable')
        self.port_param_table = port_param_table

    def create_table_dict(self):
        pass

    def commit(self):
        pass


#############################################################################
# Function definitions
#############################################################################
def check_date_market_holidays():
    today = datetime.now()
    data_datetime = today
    market_closed = False
    if today.isoweekday() >= 6:
        market_closed = True
        data_datetime -= timedelta(days=today.isoweekday() - 5)

    query = session.query(MarketHolidays).filter_by(date=data_datetime.date()).all()
    while query or data_datetime.isoweekday() >= 6:
        data_datetime -= timedelta(days=1)
        query = session.query(MarketHolidays).filter_by(date=data_datetime.date()).all()

    if data_datetime.date() != today.date():
        data_datetime = datetime.combine(data_datetime.date(), time(16, 30))
    return data_datetime, market_closed

def get_option_symbols(query):
    symbol_set = set()
    for row in query:
        expiration_year_month_date = row.expiration.strftime("%y%m%d")
        option_char = 'C' if row.descriptor == 'call' else 'P'
        strike_formatted = f"{int(row.strike) * 1000:08d}"
        symbol = f"{row.symbol}{expiration_year_month_date}{option_char}{strike_formatted}"
        symbol_set.add(symbol)
    return symbol_set

def get_portnames():
    logger = logging.getLogger('get_portnames')
    query = session.query(TransactionLists).all()
    portname_set = set([row.fileportname for row in query])
    return portname_set

def get_symbols(fileportnames):
    logger = logging.getLogger('get_symbols')
    stock_query = session.query(TransactionLists).filter_by(descriptor='stock', closed=False).filter(TransactionLists.fileportname.in_(fileportnames))
    option_query = session.query(TransactionLists).filter_by(closed=False).filter(TransactionLists.fileportname.in_(fileportnames)).filter(TransactionLists.descriptor.in_(('call', 'put')))
    symbol_set = set([row.symbol for row in stock_query])

    ticker_query = session.query(TickerSymbols).all()
    ticker_set = set([row.symbol for row in ticker_query])

    symbol_set = symbol_set.union(ticker_set)

    mf_symbols = {symbol for symbol in list(symbol_set) if len(symbol) == 5 and symbol.endswith('X') and not symbol.startswith('^')}
    index_symbols = {symbol for symbol in list(symbol_set) if symbol.startswith('^')}
    stock_symbols = symbol_set - mf_symbols - index_symbols
    option_symbols = get_option_symbols(option_query)

    logger.debug(f"stock_symbols({len(stock_symbols)})={sorted(list(stock_symbols))}")
    logger.debug(f"mf_symbols({len(mf_symbols)})={sorted(list(mf_symbols))}")
    logger.debug(f"index_symbols({len(index_symbols)})={sorted(list(index_symbols))}")
    logger.debug(f"option_symbols({len(option_symbols)})={sorted(list(option_symbols))}")
    return stock_symbols, mf_symbols, index_symbols, option_symbols


#############################################################################
# Argument processing
#############################################################################
def parse_arguments():
    global arguments
    logger = logging.getLogger('parse_arguments')
    parser = argparse.ArgumentParser(
            prog="quote_query",
            description="This is how we update stock quotes in the database"
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Run in debug mode")
    arguments = parser.parse_args()

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")

def process_arguments():
    global arguments
    logger = logging.getLogger('process_arguments')

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")


#############################################################################
# Main
#############################################################################
def main():
    logger = logging.getLogger('main')
    logger.info('='*40 + " Start quote_query " + '='*40)

    # Check date, market holidays
    data_datetime, market_closed = check_date_market_holidays()


if __name__ == '__main__':
    parse_arguments()
    process_arguments()
    main()

