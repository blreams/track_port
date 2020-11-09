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
    def __init__(self, data_datetime, market_closed, details_list, details_type):
        self.logger = logging.getLogger('FinanceQuoteTable')
        self.data_datetime = data_datetime
        self.market_closed = market_closed
        self.logger.info(f"details_list for {len(details_list)} {details_type} symbols")
        self.details_list = details_list
        self.details_type = details_type

    def __str__(self):
        return f"FinanceQuoteTable() with {len(details_list)} stock symbols"

    def delete_table_rows(self):
        self.logger = logging.getLogger('FinanceQuoteTable:delete_table_rows')
        deleted_rows = session.query(FinanceQuotes).delete()
        self.logger.info(f"Deleting {deleted_rows} rows from finance_quote table.")
        session.commit()

    def update_finance_quote_table(self):
        self.logger = logging.getLogger('FinanceQuoteTable:update_finance_quote_table')
        for details in self.details_list:
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
            cap = try_float(details['Market Cap'], method='magnitude', except_value=0.0)

            bid=0.0
            if 'Bid' in details:
                bid = try_float(details['Bid'], except_value=0.0)
            ask=0.0
            if 'Ask' in details:
                ask = try_float(details['Ask'], except_value=0.0)
        
            # we have to check for existing row
            query = session.query(FinanceQuotes).filter_by(symbol=symbol).all()
            if query:
                # We have an existing row, let's update it
                self.logger.info(f"updating finance_quote row for {symbol}")
                fq = query[0]
                fq.symbol=symbol
                fq.name=details['Company'][:32]
                fq.last=last
                fq.date=self.data_datetime.date()
                fq.time=self.data_datetime.time()
                fq.net=net
                fq.p_change=p_change
                fq.volume=volume
                fq.avg_vol=try_float(details['Avg Volume'], method='magnitude')
                fq.close=close
                fq.year_range=f"'{details['52W Range']}'"
                fq.eps=eps
                fq.pe=pe
                fq.dividend=dividend
                fq.div_yield=div_yield
                fq.cap=cap
                fq.bid=bid
                fq.ask=ask
        
                if 'Day Range' in details:
                    fq.day_range=f"'{details['Day Range']}'"
                else:
                    if fq.high < last:
                        fq.high = last
                    
                    if fq.low > last:
                        fq.low = last
                    
                    fq.day_range=f"'{fq.low:.2f} - {fq.high:.2f}'"

            else:
                # We are creating a new row
                self.logger.info(f"creating finance_quote row for {symbol}")
                if 'Day Range' in details:
                    day_range = f"'{details['Day Range']}'"
                else:
                    day_range = f"'{last:.2f} - {last:.2f}'"

                fq = FinanceQuotes(
                    symbol=symbol,
                    name=details['Company'][:32],
                    last=last,
                    high=last,
                    low=last,
                    date=self.data_datetime.date(),
                    time=self.data_datetime.time(),
                    net=net,
                    p_change=p_change,
                    volume=volume,
                    avg_vol=try_float(details['Avg Volume'], method='magnitude'),
                    close=close,
                    year_range=f"'{details['52W Range']}'",
                    eps=eps,
                    pe=pe,
                    dividend=dividend,
                    div_yield=div_yield,
                    cap=cap,
                    day_range=day_range,
                    bid=bid,
                    ask=ask,
                    )
                session.add(fq)

        session.commit()

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

def lookup_index(symbol):
    company_descriptor = { 'tag': 'h1', }
    last_descriptor = { 'tag': 'span', 'attrs': {'class': "Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)"}, }
    table_descriptor = { 'tag': 'td', 'attrs': {"class": "Ta(end) Fw(600) Lh(14px)"}, }
    request = f"//in.finance.yahoo.com/quote/{symbol}?p={symbol}"
    url = urllib.parse.quote(request)
    response = requests.get("https:" + url, timeout=30)
    page_content = BeautifulSoup(response.content, "html.parser")

    elem = page_content.find(company_descriptor['tag'])
    l_company = elem.text
    elem = page_content.find(last_descriptor['tag'], attrs=last_descriptor['attrs'])
    l_last = float(elem.text.replace(',', ''))
    elem_list = page_content.find_all(table_descriptor['tag'], attrs=table_descriptor['attrs'])
    elem = elem_list[0].find('span')
    l_previous_close = float(elem.text.replace(',', ''))
    elem = elem_list[1].find('span')
    l_open = float(elem.text.replace(',', ''))
    elem = elem_list[2].find('span')
    l_volume = elem.text
    elem = elem_list[3]
    l_day_range = elem.text
    elem = elem_list[4]
    l_year_range = elem.text
    elem = elem_list[5].find('span')
    l_avg_volume = elem.text

    l_change = l_last - l_previous_close

    return_dict = {
            'Ticker': symbol,
            'Company': l_company,
            'Price': l_last,
            'Prev Close': l_previous_close,
            'Change': f"{(l_change / l_previous_close) * 100.0:.2f}",
            'Volume': l_volume,
            'Avg Volume': l_avg_volume,
            '52W Range': l_year_range,
            'Day Range': l_day_range,
            'EPS (ttm)': 0.0,
            'P/E': 0.0,
            'Dividend': 0.0,
            'Dividend %': "0.0%",
            'Market Cap': "0",
            }

    return return_dict

def lookup_mf(symbol):
    company_descriptor = { 'tag': 'h1', }
    last_descriptor = { 'tag': 'span', 'attrs': {'class': "Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)"}, }
    table_descriptor = { 'tag': 'td', 'attrs': {"class": "Ta(end) Fw(600) Lh(14px)"}, }
    request = f"//in.finance.yahoo.com/quote/{symbol}?p={symbol}"
    url = urllib.parse.quote(request)
    response = requests.get("https:" + url, timeout=30)
    page_content = BeautifulSoup(response.content, "html.parser")

    elem = page_content.find(company_descriptor['tag'])
    l_company = elem.text
    elem = page_content.find(last_descriptor['tag'], attrs=last_descriptor['attrs'])
    l_last = float(elem.text.replace(',', ''))
    elem_list = page_content.find_all(table_descriptor['tag'], attrs=table_descriptor['attrs'])
    elem = elem_list[0].find('span')
    l_previous_close = float(elem.text.replace(',', ''))
    l_change = l_last - l_previous_close
    return_dict = {
            'Ticker': symbol,
            'Company': l_company,
            'Price': l_last,
            'Prev Close': l_previous_close,
            'Change': f"{(l_change / l_previous_close) * 100.0:.2f}",
            'Volume': "0",
            'Avg Volume': "0",
            '52W Range': "'0.00 - 0.00'",
            'Day Range': "'0.00 - 0.00'",
            'EPS (ttm)': 0.0,
            'P/E': 0.0,
            'Dividend': 0.0,
            'Dividend %': "0.0%",
            'Market Cap': "0",
            }

    return return_dict

def lookup_option(symbol):
    company_descriptor = { 'tag': 'h1', }
    last_descriptor = { 'tag': 'span', 'attrs': {'class': "Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)"}, }
    table_descriptor = { 'tag': 'td', 'attrs': {"class": "Ta(end) Fw(600) Lh(14px)"}, }
    request = f"//in.finance.yahoo.com/quote/{symbol}?p={symbol}"
    url = urllib.parse.quote(request)
    response = requests.get("https:" + url, timeout=30)
    page_content = BeautifulSoup(response.content, "html.parser")

    elem = page_content.find(company_descriptor['tag'])
    l_company = elem.text
    elem = page_content.find(last_descriptor['tag'], attrs=last_descriptor['attrs'])
    l_last = float(elem.text.replace(',', ''))
    elem_list = page_content.find_all(table_descriptor['tag'], attrs=table_descriptor['attrs'])
    elem = elem_list[0].find('span')
    l_previous_close = float(elem.text.replace(',', ''))
    elem = elem_list[2].find('span')
    l_bid = float(elem.text.replace(',', ''))
    elem = elem_list[3].find('span')
    l_ask = float(elem.text.replace(',', ''))
    elem = elem_list[6]
    l_day_range = elem.text
    elem = elem_list[8].find('span')
    l_volume = elem.text
    l_change = l_last - l_previous_close
    return_dict = {
            'Ticker': symbol,
            'Company': l_company,
            'Price': l_last,
            'Prev Close': l_previous_close,
            'Change': f"{(l_change / l_previous_close) * 100.0:.2f}",
            'Volume': f"{l_volume}",
            'Avg Volume': "0",
            '52W Range': "'0.00 - 0.00'",
            'Day Range': f"'{l_day_range}'",
            'EPS (ttm)': 0.0,
            'P/E': 0.0,
            'Dividend': 0.0,
            'Dividend %': "0.0%",
            'Market Cap': "0",
            'Bid': l_bid,
            'Ask': l_ask,
            }
    return return_dict

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

def update_indexes(data_datetime, market_closed, index_symbols):
    logger = logging.getLogger('update_indexes')
    finance_quote_table_list = []
    index_details = []
    for index_symbol in index_symbols:
        index_details.append(lookup_index(index_symbol))
    finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, index_details, 'index'))
    return finance_quote_table_list

def update_mfs(data_datetime, market_closed, mf_symbols):
    logger = logging.getLogger('update_mfs')
    finance_quote_table_list = []
    mf_details = []
    for mf_symbol in mf_symbols:
        mf_details.append(lookup_mf(mf_symbol))
    finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, mf_details, 'mf'))
    return finance_quote_table_list

def update_options(data_datetime, market_closed, option_symbols):
    logger = logging.getLogger('update_options')
    finance_quote_table_list = []
    option_details = []
    for option_symbol in option_symbols:
        option_details.append(lookup_option(option_symbol))
    finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, option_details, 'option'))
    return finance_quote_table_list

def update_stocks(data_datetime, market_closed, stock_symbols):
    max_chunk = arguments.chunk
    logger = logging.getLogger('update_stocks')
    finance_quote_table_list = []
    stocks = sorted(list(stock_symbols))
    passes = len(stock_symbols) // max_chunk
    if (len(stock_symbols) % max_chunk) > 0:
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
        
        finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, stock_details, 'stock'))
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
def parse_arguments():
    global arguments
    logger = logging.getLogger('parse_arguments')
    parser = argparse.ArgumentParser(
            prog="quote_query",
            description="This is how we update stock quotes in the database"
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Run in debug mode")
    parser.add_argument('--fileportnames', action='append', default=[], help="Limit update to symbols from one (or more) file:port names. Default is all fpns")
    parser.add_argument('--filenames', action='append', default=[], help="Use file:ports where file is in this list")
    parser.add_argument('--stock_only', action='store_true', default=False, help="Only get stock quotes (no index, mf or option)")
    parser.add_argument('--clean', action='store_true', default=False, help="Delete rows from finance_quote table before committing new updates. Ignores arguments that limit fileportnames.")
    parser.add_argument('--chunk', type=int, default=100, help="Limits the number of symbols passed to finviz in one chunk, default=100")
    arguments = parser.parse_args()

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")

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

    if arguments.clean:
        arguments.fileportnames = available_fileportnames

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")


#############################################################################
# Main
#############################################################################
def main():
    logger = logging.getLogger('main')
    logger.info('='*40 + " Start quote_query " + '='*40)

    process_arguments()

    # Check date, market holidays
    data_datetime, market_closed = check_date_market_holidays()

    # Get sets of symbols that will need quotes (stock, mutual fund, index, call, put)
    stock_symbols, mf_symbols, index_symbols, option_symbols = get_symbols(arguments.fileportnames)

    finance_quote_table_list = []

    # Call for stock info
    if stock_symbols:
        finance_quote_table_list.extend(update_stocks(data_datetime, market_closed, stock_symbols))

    if not arguments.stock_only:
        # Call for index info
        if index_symbols:
            finance_quote_table_list.extend(update_indexes(data_datetime, market_closed, index_symbols))
        
        # Call for mf info
        if mf_symbols:
            finance_quote_table_list.extend(update_mfs(data_datetime, market_closed, mf_symbols))

        # Call for option info
        if option_symbols:
            finance_quote_table_list.extend(update_options(data_datetime, market_closed, option_symbols))

    if arguments.clean and len(finance_quote_table_list) > 0:
        finance_quote_table_list[0].delete_table_rows()

    for finance_quote_table in finance_quote_table_list:
        finance_quote_table.update_finance_quote_table()

    

if __name__ == '__main__':
    parse_arguments()
    process_arguments()
    main()

