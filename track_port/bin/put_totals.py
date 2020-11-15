#!/usr/bin/env python3

import sys
import os
import logging
import logging.config
import argparse
from decimal import Decimal
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
class Port(object):
    def __init__(self, portname, finance_quotes):
        self.logger = logging.getLogger('Port.__init__')
        self.portname = portname
        self.fqs = finance_quotes
        self.cash = Decimal(0)
        self.basis = Decimal(0)
        self.invested_total = Decimal(0)
        self.gain = Decimal(0)
        self.daygain = Decimal(0)
        self.initialize()
        self.total = self.cash + self.invested_total
        self.logger.info(f"{self.portname} cash={self.cash} basis={self.basis} total={self.total}")

    def initialize(self):
        self.logger = logging.getLogger('Port.initialize')
        self.logger.info(f"Initializing {self.portname}")
        self.get_transactions()
        self.parse_transactions()

    def get_transactions(self):
        self.query = session.query(TransactionLists).filter_by(fileportname=self.portname).all()

    def parse_transactions(self):
        self.logger = logging.getLogger('Port.parse_transaction')
        for transaction in self.query:
            if transaction.closed:
                self.handle_closed_transaction(transaction)
            elif transaction.position.lower() == 'cash':
                self.handle_cash_transaction(transaction)
            elif transaction.position.lower() == 'long':
                self.handle_open_position(transaction)
            else:
                self.logger.warning(f"Unhandled transaction id={transaction.id}")

    def handle_closed_transaction(self, transaction):
        self.cash += transaction.shares * (transaction.close_price - transaction.open_price)

    def handle_cash_transaction(self, transaction):
        self.cash += transaction.open_price

    def handle_open_position(self, transaction):
        self.logger = logging.getLogger('Port.handle_open_position')
        self.cash -= transaction.shares * transaction.open_price
        self.basis += transaction.shares * transaction.open_price
        fq = self.get_quote(transaction)
        if hasattr(fq, 'last'):
            self.invested_total += transaction.shares * fq.last
        else:
            self.logger.warning(f"Unable to find quote matching {fq}")


    def get_quote(self, transaction):
        symbol = transaction.symbol
        if transaction.descriptor !=  'stock':
            expiration = transaction.expiration.strftime("%y%m%d")
            option = transaction.descriptor[0].upper()
            strike = f"{int(transaction.strike * 1000):08d}"
            symbol += expiration + option + strike
        return self.fqs.get(symbol, symbol)



class PortParamTable(object):
    def __init__(self, ports):
        self.logger = logging.getLogger('PortParamTable')
        self.ports = ports

    def commit(self):
        pass


class PortHistoryTable(object):
    def __init__(self, ports):
        self.logger = logging.getLogger('PortHistoryTable')
        self.ports = ports

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

def get_finance_quotes():
    logger = logging.getLogger('get_finance_quotes')
    query = session.query(FinanceQuotes).all()
    return {row.symbol: row for row in query}

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
    logger.info('='*40 + " Start put_totals " + '='*40)

    # Check date, market holidays
    data_datetime, market_closed = check_date_market_holidays()

    # Get finance_quote data
    finance_quotes = get_finance_quotes()

    # Get ports and create a dict of FilePortName objects
    ports = {portname: Port(portname, finance_quotes) for portname in get_portnames()}

    port_param_table = PortParamTable(ports)
    port_param_table.commit()

    port_history_table = PortHistoryTable(ports)
    port_history_table.commit()


if __name__ == '__main__':
    parse_arguments()
    process_arguments()
    main()

