#!/usr/bin/env python3

import sys
import os
import logging
import logging.config
import argparse
from decimal import Decimal
from datetime import datetime, date, time, timedelta

from sqlalchemy import create_engine, Table, MetaData, inspect, desc
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
class PortHistory(object):
    def __init__(self):
        logger = logging.getLogger('PortHistory.__init__')
        self.query = session.query(PortHistories)

    def get_total_cash(self, portname, days=None, date=None):
        logger = logging.getLogger('PortHistory.get_total_cash')
        if days is None and date is None:
            days = 1
        elif date:
            days =(datetime.now() - date).days

        latest_date = (datetime.now() - timedelta(days=days)).date()
        port_histories = self.query.filter_by(fileportname=portname).filter(PortHistories.date<=latest_date).order_by(desc(PortHistories.date)).all()
        if len(port_histories) == 0:
            logger.warning(f"called with portname={portname},days={days}, unable to match port_history")
            return Decimal(0)
        logger.info(f"called with portname={portname},days={days}, returning port_history for date={port_histories[0].date},total={port_histories[0].total},cash={port_histories[0].cash}")
        return port_histories[0].total, port_histories[0].cash

class Port(object):
    def __init__(self, portname, finance_quotes):
        logger = logging.getLogger('Port.__init__')
        self.portname = portname
        self.fqs = finance_quotes
        self.cash = Decimal(0)
        self.basis = Decimal(0)
        self.invested_total = Decimal(0)
        self.gain = Decimal(0)
        self.daygain = Decimal(0)
        self.port_history = PortHistory()
        self.initialize()
        logger.info(str(self))

    def __repr__(self):
        return "{cls}:n={name},c={cash},t={total},d%={pct_daygain},d={daygain},it={invested_total},g%={pct_gain},g={gain},pi={pct_invested},b={basis}".format(
                cls=__class__.__name__,
                name=self.portname,
                total=f"{self.total:.2f}",
                cash=f"{self.cash:.2f}",
                basis=f"{self.basis:.2f}",
                gain=f"{self.gain:.2f}",
                daygain=f"{self.daygain:.2f}",
                pct_gain=f"{Decimal(100.0) * self.pct_gain:.2f}",
                pct_daygain=f"{Decimal(100.0) * self.pct_daygain:.2f}",
                invested_total=f"{self.invested_total}",
                pct_invested=f"{Decimal(100.0) * self.pct_invested}",
                )

    def initialize(self):
        self.get_transactions()
        self.parse_transactions()
        self.calculate()

    def calculate(self):
        self.total = self.cash + self.invested_total
        self.pct_invested = self.invested_total / self.total
        previous_total_1d, previous_cash_1d = self.port_history.get_total_cash(self.portname, 1)
        self.daygain = self.total - previous_total_1d
        self.invested_total = self.total - self.cash
        try:
            self.pct_gain = self.gain / self.basis
        except:
            self.pct_gain = Decimal(0)
        try:
            self.pct_daygain = self.daygain / (previous_total_1d - previous_cash_1d)
        except:
            self.pct_daygain = Decimal(0)
        try:
            self.pct_invested = self.invested_total / self.total
        except:
            self.pct_invested = Decimal(0)

    def get_transactions(self):
        self.query = session.query(TransactionLists).filter_by(fileportname=self.portname).all()

    def parse_transactions(self):
        logger = logging.getLogger('Port.parse_transactions')
        for transaction in self.query:
            if transaction.closed:
                self.handle_closed_transaction(transaction)
            elif transaction.position.lower() == 'cash':
                self.handle_cash_transaction(transaction)
            elif transaction.position.lower() == 'long':
                self.handle_open_position(transaction)
            else:
                logger.warning(f"Unhandled transaction id={transaction.id}")

    def handle_closed_transaction(self, transaction):
        self.cash += transaction.shares * (transaction.close_price - transaction.open_price)

    def handle_cash_transaction(self, transaction):
        self.cash += transaction.open_price

    def handle_open_position(self, transaction):
        logger = logging.getLogger('Port.handle_open_position')
        self.cash -= transaction.shares * transaction.open_price
        self.basis += transaction.shares * transaction.open_price
        fq = self.get_quote(transaction)
        if hasattr(fq, 'last'):
            #self.daygain += transaction.shares * fq.net
            self.gain += transaction.shares * (fq.last - transaction.open_price)
            self.invested_total += transaction.shares * fq.last
        else:
            logger.warning(f"Unable to find quote matching {fq}")


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
        logger = logging.getLogger('PortParamTable')
        self.ports = ports
        self.port_params = self.query_port_param()
        self.handle_ports()

    def query_port_param(self):
        query = session.query(PortParams).all()
        return {row.fileportname: row for row in query}

    def handle_ports(self):
        for portname, port in self.ports.items():
            if portname in self.port_params:
                self.update_row(port)
            else:
                self.create_row(port)

    def update_row(self, port):
        logger = logging.getLogger('PortParamTable.update_row')
        logger.info(f"updating with port={port}")
        port_param = self.port_params[port.portname]
        port_param.cash = port.cash
        port_param.total = port.total
        port_param.pct_daygain = port.pct_daygain
        port_param.daygain = port.daygain
        port_param.invested_total = port.invested_total
        port_param.pct_gain = port.pct_gain
        port_param.gain = port.gain
        port_param.pct_invested = port.pct_invested
        port_param.basis = port.basis

    def create_row(self, port):
        logger = logging.getLogger('PortParamTable.create_row')
        logger.info(f"creating row with port={port}")
        pp = PortParams(
                fileportname=port.portname,
                cash=port.cash,
                total=port.total,
                pct_daygain=port.pct_daygain,
                daygain=port.daygain,
                invested_total=port.invested_total,
                pct_gain=port.pct_gain,
                gain=port.gain,
                pct_invested=port.pct_invested,
                basis=port.basis,
                portnum=len(ports),
                )

    def commit(self):
        logger = logging.getLogger('PortParamTable.commit')
        logger.info("called...placeholder only")
        pass


class PortHistoryTable(object):
    def __init__(self, ports):
        logger = logging.getLogger('PortHistoryTable')
        self.ports = ports
        #self.port_histories = self.query_port_history()
        #self.handle_ports()

    def query_port_history(self):
        query = session.query(PortHistories).all()

    def handle_ports(self):
        for portname, port in self.ports.items():
            if portname in self.port_params:
                self.update_row(port)
            else:
                self.create_row(port)

    def update_row(self, port):
        pass

    def create_row(self, port):
        pass

    def commit(self):
        logger = logging.getLogger('PortHistoryTable.commit')
        logger.info("called...placeholder only")
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
    #import pdb;pdb.set_trace()
    # TODO figure out how to use date/time from finance_quote

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

