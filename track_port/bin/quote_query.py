#!/usr/bin/env python3

import sys
import os
import logging
import logging.config
import argparse
from datetime import datetime, date

from sqlalchemy import create_engine, Table, MetaData, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from finviz.screener import Screener

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

logging.config.fileConfig('quote_query_logging.conf')
arguments = argparse.Namespace

class TransactionLists(Base):
    __tablename__ = 'transaction_list'
    __table_args__ = {'autoload': True}

class TickerSymbols(Base):
    __tablename__ = 'ticker_symbols'
    __table_args__ = {'autoload': True}

class FinanceQuotes(Base):
    __tablename__ = 'finance_quote'
    __table_args__ = {'autoload': True}

class FinanceQuoteTable(object):
    def __init__(self, stock_details):
        self.stock_details = stock_details
        self.update_finance_quote_table()

    def update_finance_quote_table(self):
        for details in self.stock_details:
            symbol = details['Ticker']
            last = try_float(details['Price'])
            close = try_float(details['Prev Close'])
            net = last - close
            p_change = try_float(details['Change'][:-1]) / 100.0
            volume = int(details['Volume'].replace(',', ''))
            eps = try_float(details['EPS (ttm)'])
            pe = try_float(details['P/E'])
            dividend = try_float(details['Dividend'])

            # we have to check for existing row
            query = session.query(FinanceQuotes).filter_by(symbol=symbol).all()
            if query:
                fq = query[0]
                fq.symbol=symbol
                fq.name=details['Company']
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
                fq.div_yield=try_float(details['Dividend %'], method='pct')
                fq.cap=try_float(details['Market Cap'], method='magnitude')
            else:
                fq = FinanceQuotes(
                    symbol=symbol,
                    name=details['Company'],
                    last=last,
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
                    div_yield=try_float(details['Dividend %'], method='pct'),
                    cap=try_float(details['Market Cap'], method='magnitude'),
                    )
                session.add(fq)

        session.commit()

def try_float(s, method=None):
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
        f = None
    return f

def log_transaction_list(fileportname):
    logger = logging.getLogger('log_transaction_list')
    transaction_list_query = session.query(TransactionLists).filter_by(fileportname=fileportname, position='long', closed=False).order_by('open_date').all()

    for transaction_list_row in transaction_list_query:
        mapper = inspect(transaction_list_row)
        log_items = []
        for column in mapper.attrs:
            log_items.append(f"{column.key}={getattr(transaction_list_row, column.key)}")
        logger.debug(','.join(log_items))

def get_portnames():
    logger = logging.getLogger('get_portnames')
    query = session.query(TransactionLists).all()
    portname_set = set([row.fileportname for row in query])
    return portname_set

def get_option_symbols(query):
    symbol_set = set()
    for row in query:
        expiration_year_month_date = row.expiration.strftime("%y%m%d")
        option_char = 'C' if row.descriptor == 'call' else 'P'
        strike_formatted = f"{int(row.strike) * 1000:08d}"
        symbol = f"{row.symbol}{expiration_year_month_date}{option_char}{strike_formatted}"
        symbol_set.add(symbol)
    return symbol_set

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

def object_as_dict(obj):
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

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

def main():
    logger = logging.getLogger('main')
    logger.info('='*40 + " Start quote_query " + '='*40)

    process_arguments()

    #log_transaction_list('port:fluffgazer')

    # Get sets of symbols that will need quotes (stock, mutual fund, index, call, put)
    stock_symbols, mf_symbols, index_symbols, call_symbols, put_symbols = get_symbols(arguments.fileportnames)
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
        
        finance_quote_table = FinanceQuoteTable(stock_details)
        stock_symbols.difference_update(stock_list)

    screened_stocks = sorted(list(screened_stock_symbols))
    if stocks != screened_stocks:
        missing_symbols = set(stocks)
        missing_symbols.difference_update(screened_stock_symbols)
        logger.info(f"missing symbols: {missing_symbols}")
    

if __name__ == '__main__':
    arguments = parse_arguments()
    main()

