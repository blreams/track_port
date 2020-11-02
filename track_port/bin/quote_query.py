#!/usr/bin/env python3

import sys
import os
import logging
import logging.config
import argparse

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

def get_symbols(fileportnames):
    logger = logging.getLogger('get_symbols')
    if not fileportnames:
        stock_query = session.query(TransactionLists).filter_by(descriptor='stock', closed=False, expiration=None).all()
        call_query = session.query(TransactionLists).filter_by(descriptor='call', closed=False, expiration=None).all()
        put_query = session.query(TransactionLists).filter_by(descriptor='put', closed=False, expiration=None).all()
    else:
        stock_query = session.query(TransactionLists).filter_by(descriptor='stock', closed=False).filter(TransactionLists.fileportname.in_(fileportnames))
        call_query = session.query(TransactionLists).filter_by(descriptor='call', closed=False).filter(TransactionLists.fileportname.in_(fileportnames))
        put_query = session.query(TransactionLists).filter_by(descriptor='put', closed=False).filter(TransactionLists.fileportname.in_(fileportnames))
    symbol_set = set([row.symbol for row in stock_query])
    mf_symbols = {symbol for symbol in list(symbol_set) if len(symbol) == 5 and '-' not in symbol and not symbol.startswith('^')}
    index_symbols = {symbol for symbol in list(symbol_set) if symbol.startswith('^')}
    stock_symbols = symbol_set - mf_symbols - index_symbols
    call_symbols = set([row.symbol for row in call_query])
    put_symbols = set([row.symbol for row in put_query])
    return stock_symbols, mf_symbols, index_symbols, call_symbols, put_symbols

def parse_arguments():
    logger = logging.getLogger('parse_arguments')
    parser = argparse.ArgumentParser(
            prog="quote_query",
            description="This is how we update stock quotes in the database"
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Run in debug mode")
    parser.add_argument('--fileportnames', action='append', default=[], help="Limit update to symbols from one (or more) file:port names. Default is all fpns")
    arguments = parser.parse_args()

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")

    return arguments

def main():
    logger = logging.getLogger('main')
    logger.info('='*40 + " Start quote_query " + '='*40)

    #log_transaction_list('port:fluffgazer')
    import pdb;pdb.set_trace()

    # Get sets of symbols that will need quotes (stock, mutual fund, index, call, put)
    stock_symbols, mf_symbols, index_symbols, call_symbols, put_symbols = get_symbols(arguments.fileportnames)

    stock_screener = Screener(tickers=stock_symbols)
    stock_details = stock_screener.get_ticker_details()
    

if __name__ == '__main__':
    arguments = parse_arguments()
    main()

