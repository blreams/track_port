#!/usr/bin/env python3

import sys
import os
import logging
import logging.config
import argparse
from datetime import datetime, date, timedelta

from sqlalchemy import create_engine, Table, MetaData, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from finviz.screener import Screener

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

logging.config.fileConfig(os.path.join(thisdir, 'quote_query_logging.conf'))
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

#############################################################################
# Other classes
#############################################################################
class FinanceQuoteTable(object):
    def __init__(self, data_date, market_closed, stock_details=None, index_details=None, mf_details=None):
        self.logger = logging.getLogger('FinanceQuoteTable')
        self.data_date = data_date
        self.market_closed = market_closed
        if stock_details is not None:
            self.logger.info(f"stock_details for {len(stock_details)} symbols")
            self.stock_details = stock_details
        if index_details is not None:
            self.logger.info(f"index_details for {len(index_details)} symbols")
            self.index_details = index_details
        if mf_details is not None:
            self.logger.info(f"index_details for {len(index_details)} symbols")
            self.mf_details = mf_details

    def __str__(self):
        return f"FinanceQuoteTable() with {len(stock_details)} stock symbols"

    def update_finance_quote_table(self, update_type):
        self.logger = logging.getLogger('FinanceQuoteTable:update_finance_quote_table')
        if update_type == 'stock':
            for details in self.stock_details:
                symbol = details['Ticker']
                last = try_float(details['Price'])
                close = try_float(details['Prev Close'])
                if self.market_closed:
                    pass
                net = last - close
                p_change = try_float(details['Change'][:-1])
                volume = int(details['Volume'].replace(',', ''))
                eps = try_float(details['EPS (ttm)'])
                pe = try_float(details['P/E'], except_value=0.0)
                dividend = try_float(details['Dividend'], except_value=0.0)
                div_yield = try_float(details['Dividend %'], method='pct', except_value=0.0)
            
                # we have to check for existing row
                query = session.query(FinanceQuotes).filter_by(symbol=symbol).all()
                if query:
                    # We have an existing row, let's update it
                    self.logger.info(f"updating finance_quote row for {symbol}")
                    fq = query[0]
                    fq.symbol=symbol
                    fq.name=details['Company'][:32]
                    fq.last=last
                    fq.date=datetime.now().date()
                    fq.time=datetime.now().time()
                    fq.net=net
                    fq.p_change=p_change
                    fq.volume=volume
                    fq.avg_vol=try_float(details['Avg Volume'], method='magnitude')
                    fq.close=close
                    fq.year_range=details['52W Range']
                    fq.eps=eps
                    fq.pe=pe
                    fq.dividend=dividend
                    fq.div_yield=div_yield
                    fq.cap=try_float(details['Market Cap'], method='magnitude')
            
                    if fq.high < last:
                        fq.high = last
            
                    if fq.low > last:
                        fq.low = last
            
                    fq.day_range=f"'{fq.low:.2f} - {fq.high:.2f}'"
            
                else:
                    # We are creating a new row
                    self.logger.info(f"creating finance_quote row for {symbol}")
                    fq = FinanceQuotes(
                        symbol=symbol,
                        name=details['Company'][:32],
                        last=last,
                        high=last,
                        low=last,
                        date=datetime.now().date(),
                        time=datetime.now().time(),
                        net=net,
                        p_change=p_change,
                        volume=volume,
                        avg_vol=try_float(details['Avg Volume'], method='magnitude'),
                        close=close,
                        year_range=details['52W Range'],
                        eps=eps,
                        pe=pe,
                        dividend=dividend,
                        div_yield=div_yield,
                        cap=try_float(details['Market Cap'], method='magnitude'),
                        day_range=f"{last:.2f} - {last:.2f}"
                        )
                    session.add(fq)

        session.commit()

#############################################################################
# Function definitions
#############################################################################
def check_date_market_holidays():
    today = datetime.now()
    data_date = today.date()
    market_closed = False
    if today.isoweekday() >= 6:
        market_closed = True
        data_date -= timedelta(days=today.isoweekday() - 5)

    query = session.query(MarketHolidays).filter_by(date=data_date).all()
    while query or data_date.isoweekday() >= 6:
        data_date -= timedelta(days=1)
        query = session.query(MarketHolidays).filter_by(date=data_date).all()

    return data_date, market_closed

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
    call_query = session.query(TransactionLists).filter_by(descriptor='call', closed=False).filter(TransactionLists.fileportname.in_(fileportnames))
    put_query = session.query(TransactionLists).filter_by(descriptor='put', closed=False).filter(TransactionLists.fileportname.in_(fileportnames))
    symbol_set = set([row.symbol for row in stock_query])

    ticker_query = session.query(TickerSymbols).all()
    ticker_set = set([row.symbol for row in ticker_query])

    symbol_set = symbol_set.union(ticker_set)

    mf_symbols = {symbol for symbol in list(symbol_set) if len(symbol) == 5 and symbol.endswith('X') and not symbol.startswith('^')}
    index_symbols = {symbol for symbol in list(symbol_set) if symbol.startswith('^')}
    stock_symbols = symbol_set - mf_symbols - index_symbols
    call_symbols = get_option_symbols(call_query)
    put_symbols = get_option_symbols(put_query)

    logger.debug(f"stock_symbols({len(stock_symbols)})={sorted(list(stock_symbols))}")
    logger.debug(f"mf_symbols({len(mf_symbols)})={sorted(list(mf_symbols))}")
    logger.debug(f"index_symbols({len(index_symbols)})={sorted(list(index_symbols))}")
    logger.debug(f"call_symbols({len(call_symbols)})={sorted(list(call_symbols))}")
    logger.debug(f"put_symbols({len(put_symbols)})={sorted(list(put_symbols))}")
    return stock_symbols, mf_symbols, index_symbols, call_symbols, put_symbols

def try_float(s, method=None, except_value=None):
    if method == 'magnitude' and s.endswith(('K', 'M', 'B', 'T',)):
        if s.endswith('K'):
            f = float(s[:-1]) * 1000.0
        elif s.endswith('M'):
            f = float(s[:-1]) * 1000000.0
        elif s.endswith('B'):
            f = float(s[:-1]) * 1000000000.0
        elif s.endswith('T'):
            f = float(s[:-1]) * 1000000000000.0
        return f

    s_in = s
    if method == 'pct':
        s_in = s[:-1]

    try:
        f = float(s_in)
    except ValueError:
        f = except_value
    return f

def update_indexes(data_date, market_closed, index_symbols):
    logger = logging.getLogger('update_indexes')
    finance_quote_table_list = []

    return finance_quote_table_list

def update_stocks(data_date, market_closed, stock_symbols):
    logger = logging.getLogger('update_stocks')
    finance_quote_table_list = []
    stocks = sorted(list(stock_symbols))
    passes = len(stock_symbols) // 100
    if (len(stock_symbols) % 100) > 0:
        passes += 1
    chunk_size = len(stock_symbols) // passes
    if (len(stock_symbols) % passes) > 0:
        chunk_size += 1
    logger.info(f"passes={passes},chunk_size={chunk_size}")
    screened_stock_symbols = set()
    while len(stock_symbols) > 0:
        if len(stock_symbols) >= chunk_size:
            stock_list = list(stock_symbols)[:chunk_size]
        else:
            stock_list = list(stock_symbols)
        logger.info(f"stock_list={','.join(stock_list)}")
        stock_screener = Screener(tickers=stock_list)
        stock_details = stock_screener.get_ticker_details()
        screened_symbols = [detail['Ticker'] for detail in stock_details]
        screened_stock_symbols = screened_stock_symbols.union(screened_symbols)
        
        finance_quote_table_list.append(FinanceQuoteTable(data_date, market_closed, stock_details=stock_details))
        stock_symbols.difference_update(stock_list)

    screened_stocks = sorted(list(screened_stock_symbols))
    if stocks != screened_stocks:
        missing_symbols = set(stocks)
        missing_symbols.difference_update(screened_stock_symbols)
        logger.info(f"missing symbols: {missing_symbols}")

    return finance_quote_table_list

#############################################################################
# Argument processing
#############################################################################
def process_arguments():
    global arguments
    logger = logging.getLogger('process_arguments')

    available_fileportnames = get_portnames()
    enabled_fileportnames = set()

    if arguments.filenames:
        enabled_fileportnames = {fpn for fpn in available_fileportnames if fpn.startswith(*[f"{fn}:" for fn in arguments.filenames])}

    if arguments.fileportnames:
        fileport_based_set = available_fileportnames.intersection(arguments.fileportnames)
        enabled_fileportnames = enabled_fileportnames.union(fileport_based_set)

    if arguments.fileportnames or arguments.filenames:
        arguments.fileportnames = enabled_fileportnames
    else:
        arguments.fileportnames = available_fileportnames

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")


def parse_arguments():
    logger = logging.getLogger('parse_arguments')
    parser = argparse.ArgumentParser(
            prog="quote_query",
            description="This is how we update stock quotes in the database"
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Run in debug mode")
    parser.add_argument('--fileportnames', action='append', default=[], help="Limit update to symbols from one (or more) file:port names. Default is all fpns")
    parser.add_argument('--filenames', action='append', default=[], help="Use file:ports where file is in this list")
    arguments = parser.parse_args()

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")

    return arguments

#############################################################################
# Main
#############################################################################
def main():
    logger = logging.getLogger('main')
    logger.info('='*40 + " Start quote_query " + '='*40)

    process_arguments()

    # Check date, market holidays
    data_date, market_closed = check_date_market_holidays()

    # Get sets of symbols that will need quotes (stock, mutual fund, index, call, put)
    stock_symbols, mf_symbols, index_symbols, call_symbols, put_symbols = get_symbols(arguments.fileportnames)

    finance_quote_table_dict = {}

    # Call for stock info
    if stock_symbols:
        finance_quote_table_dict['stock'] = []
        finance_quote_table_dict['stock'].extend(update_stocks(data_date, market_closed, stock_symbols))

    # Call for index info
    if index_symbols:
        finance_quote_table_dict['index'] = []
        finance_quote_table_dict['index'].extend(update_indexes(data_date, market_closed, index_symbols))

    for update_type, finance_quote_table_list in finance_quote_table_dict.items():
        for finance_quote_table in finance_quote_table_list:
            finance_quote_table.update_finance_quote_table(update_type=update_type)

    

if __name__ == '__main__':
    arguments = parse_arguments()
    main()

