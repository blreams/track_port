#!/usr/bin/env python3

import sys
import os
import time as _time
import logging
import logging.handlers
import argparse
from datetime import datetime, date, time, timedelta

from sqlalchemy import create_engine, Table, MetaData
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
    #engine = create_engine('sqlite:////home/blreams/bin/track_port.db')
else:
    engine = create_engine('sqlite:///track_port.db')
Base = declarative_base(engine)
metadata = Base.metadata
Session = sessionmaker(bind=engine)
session = Session()
file_port_names = None  # TODO get rid of this global

#############################################################################
# Additional globals
#############################################################################
thisdir = os.path.dirname(__file__)
arguments = argparse.Namespace
logger = None

#############################################################################
# Logging Configuration
#############################################################################
def configure_logging():
    global logger
    # Let's get a logger
    logger = logging.getLogger(__name__)
    # Set the level to the lowest in any handler
    logger.setLevel(logging.DEBUG)
    # Create separate formatters for console/file
    consFormatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fileFormatter = logging.Formatter("%(asctime)s %(levelname)-8s: [%(module)s %(process)s %(name)s %(lineno)d] %(message)s")
    # Create and configure console handler
    consHandler = logging.StreamHandler(sys.stderr)
    consHandler.setFormatter(consFormatter)
    consHandler.setLevel(logging.INFO)
    # Create and configure file handler
    logger_filename = os.path.abspath(os.path.join(thisdir, 'quote_query.log'))
    fileHandler = logging.handlers.RotatingFileHandler(filename=logger_filename, maxBytes=100000000, backupCount=10)
    fileHandler.setFormatter(fileFormatter)
    fileHandler.setLevel(logging.DEBUG)
    # Add handlers to the logger
    logger.addHandler(consHandler)
    logger.addHandler(fileHandler)
    # Test messages
    first_message = f"STARTING {__file__}"
    prefix_suffix_length = (80 - len(first_message)) // 2
    logger.info('='*80)
    logger.info('='*prefix_suffix_length + first_message + '='*prefix_suffix_length)
    logger.info('='*80)

#############################################################################
# Classes related to database tables
#############################################################################
class FilePortNames(Base):
    __tablename__ = 'port_fileportname'
    __table_args__ = {'autoload': True}

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
class FilePortName(object):
    def __init__(self):
        logger = logging.getLogger(__name__ + '.' + 'FilePortName')
        self.query = session.query(FilePortNames)
        self.create_map()

    def create_map(self):
        """Create a map of fileportnames to ids"""
        file_port_names = self.query.all()
        self.fpn_id_map = {f"{fpn.filename}:{fpn.portname}": fpn.id for fpn in file_port_names}
        self.id_fpn_map = {fpn.id: f"{fpn.filename}:{fpn.portname}" for fpn in file_port_names}


class FinanceQuoteTable(object):
    def __init__(self, data_datetime, market_closed, details_list, details_type):
        logger = logging.getLogger(__name__ + '.' + 'FinanceQuoteTable')
        self.data_datetime = data_datetime
        self.market_closed = market_closed
        logger.debug(f"details_list for {len(details_list)} {details_type} symbols")
        self.details_list = details_list
        self.details_type = details_type

    def __str__(self):
        return f"FinanceQuoteTable() with {len(details_list)} stock symbols"

    def delete_table_rows(self):
        logger = logging.getLogger(__name__ + '.' + 'FinanceQuoteTable.delete_table_rows')
        deleted_rows = session.query(FinanceQuotes).delete()
        logger.debug(f"Deleting {deleted_rows} rows from finance_quote table.")
        session.commit()

    def update_finance_quote_table(self):
        logger = logging.getLogger(__name__ + '.' + 'FinanceQuoteTable.update_finance_quote_table')
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
                logger.debug(f"updating finance_quote row for {symbol}")
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
                logger.debug(f"creating finance_quote row for {symbol}")
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

def delay_start():
    logger = logging.getLogger(__name__ + '.' + 'delay_start')
    if arguments.delay:
        logger.info(f"Delaying start for {arguments.delay} seconds...")
        _time.sleep(arguments.delay)

def get_option_symbols(query):
    symbol_set = set()
    for row in query:
        expiration_year_month_date = row.expiration.strftime("%y%m%d")
        option_char = 'C' if row.descriptor == 'call' else 'P'
        strike_formatted = f"{int(row.strike * 1000):08d}"
        symbol = f"{row.symbol}{expiration_year_month_date}{option_char}{strike_formatted}"
        symbol_set.add(symbol)
    return symbol_set

def get_portnames():
    logger = logging.getLogger(__name__ + '.' + 'get_portnames')
    query = session.query(TransactionLists).all()
    portname_set = set([file_port_names.id_fpn_map[row.fileportname_id] for row in query])
    return portname_set

def get_symbols(fileportnames):
    logger = logging.getLogger(__name__ + '.' + 'get_symbols')
    fileportname_ids = set([file_port_names.fpn_id_map[fpn] for fpn in fileportnames])
    stock_query = session.query(TransactionLists).filter_by(descriptor='stock', closed=False).filter(TransactionLists.fileportname_id.in_(fileportname_ids))
    option_query = session.query(TransactionLists).filter_by(closed=False).filter(TransactionLists.fileportname_id.in_(fileportname_ids)).filter(TransactionLists.descriptor.in_(('call', 'put')))
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
    if response.status_code != 200:
        return {}

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

def lookup_stock(symbol):
    logger = logging.getLogger(__name__ + '.' + 'lookup_stock')
    company_descriptor = { 'tag': 'h1', }
    last_descriptor = { 'tag': 'span', 'attrs': {'class': "Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)"}, }
    table_descriptor = { 'tag': 'td', 'attrs': {"class": "Ta(end) Fw(600) Lh(14px)"}, }
    request = f"//in.finance.yahoo.com/quote/{symbol}?p={symbol}"
    url = urllib.parse.quote(request)
    response = requests.get("https:" + url, timeout=30)
    good_status = True
    if response.status_code != 200:
        logger.warning(f"yahoo fetch bad response for {symbol}")
        return {}

    page_content = BeautifulSoup(response.content, "html.parser")
    try:
        l_last = float(page_content.find(last_descriptor['tag'], attrs=last_descriptor['attrs']).text.replace(',', ''))
        elem_list = page_content.find_all(table_descriptor['tag'], attrs=table_descriptor['attrs'])
        l_previous_close = float(elem_list[0].find("span").text.replace(',', ''))
    except:
        logger.warning(f"Unable to get good yahoo fetch for {symbol}")
        return {}


    elem = page_content.find(company_descriptor['tag'])
    l_company = elem.text
    elem = elem_list[1].find('span')
    l_open = float(elem.text.replace(',', ''))
    elem = elem_list[4]
    l_day_range = elem.text
    elem = elem_list[5]
    l_year_range = elem.text
    elem = elem_list[6].find('span')
    l_volume = elem.text
    elem = elem_list[7].find('span')
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
    logger = logging.getLogger(__name__ + '.' + 'update_indexes')
    logger.debug(f"fetching info for {len(index_symbols)} index symbols")
    finance_quote_table_list = []
    index_details = []
    for index_symbol in index_symbols:
        index_details_item = lookup_index(index_symbol)
        if index_details_item:
            index_details.append(index_details_item)
        else:
            logger.warning(f"Unable to fetch details for {index_symbol}")
    logger.debug(f"fetched info for {len(index_details)} index symbols")
    finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, index_details, 'index'))
    return finance_quote_table_list

def update_mfs(data_datetime, market_closed, mf_symbols):
    logger = logging.getLogger(__name__ + '.' + 'update_mfs')
    logger.debug(f"fetching info for {len(mf_symbols)} mf symbols")
    finance_quote_table_list = []
    mf_details = []
    for mf_symbol in mf_symbols:
        mf_details_item = lookup_mf(mf_symbol)
        if mf_details_item:
            mf_details.append(mf_details_item)
        else:
            logger.warning(f"Unable to fetch details for {mf_symbol}")
    logger.debug(f"fetched info for {len(mf_details)} mf symbols")
    finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, mf_details, 'mf'))
    return finance_quote_table_list

def update_options(data_datetime, market_closed, option_symbols):
    logger = logging.getLogger(__name__ + '.' + 'update_options')
    logger.debug(f"fetching info for {len(option_symbols)} option symbols")
    finance_quote_table_list = []
    option_details = []
    for option_symbol in option_symbols:
        option_details_item = lookup_option(option_symbol)
        if option_details_item:
            option_details.append(option_details_item)
        else:
            logger.warning(f"Unable to fetch details for {option_symbol}")
    logger.debug(f"fetched info for {len(option_details)} option symbols")
    finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, option_details, 'option'))
    return finance_quote_table_list

def update_stocks_last_ditch(data_datetime, market_closed, stock_symbols):
    logger = logging.getLogger(__name__ + '.' + 'update_stocks_last_ditch')
    logger.info(f"Last ditch, fetching info for {len(stock_symbols)} stock symbols, {stock_symbols}")
    finance_quote_table_list = []
    stock_details = []
    for stock_symbol in stock_symbols:
        stock_details_item = lookup_stock(stock_symbol)
        if stock_details_item:
            stock_details.append(stock_details_item)
        else:
            logger.warning(f"Unable to fetch details for {stock_symbol}")
    logger.debug(f"fetched info for {len(stock_details)} stock symbols")
    finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, stock_details, 'stock'))
    return finance_quote_table_list

def update_stocks(data_datetime, market_closed, stock_symbols):
    logger = logging.getLogger(__name__ + '.' + 'update_stocks')
    stock_symbols_to_fetch = set(stock_symbols)
    max_chunk = arguments.chunk
    finance_quote_table_list = []
    stocks = sorted(list(stock_symbols_to_fetch))
    iterations = len(stock_symbols_to_fetch) // max_chunk
    if (len(stock_symbols_to_fetch) % max_chunk) > 0:
        iterations += 1
    chunk_size = len(stock_symbols_to_fetch) // iterations
    if (len(stock_symbols_to_fetch) % iterations) > 0:
        chunk_size += 1
    logger.debug(f"iterations={iterations},chunk_size={chunk_size}")
    screened_stock_symbols = set()
    while len(stock_symbols_to_fetch) > 0:
        if len(stock_symbols_to_fetch) >= chunk_size:
            stock_list = list(stock_symbols_to_fetch)[:chunk_size]
        else:
            stock_list = list(stock_symbols_to_fetch)
        logger.debug(f"stock_list({len(stock_list)})={','.join(stock_list)}")
        for retry_attempt in range(arguments.retries):
            logger.debug(f"Screener retry attempt {retry_attempt}")
            try:
                stock_screener = Screener(tickers=stock_list)
                stock_details = stock_screener.get_ticker_details()
                logger.debug(f"Screener successful")
                break
            except:
                if retry_attempt == (arguments.retries - 1):
                    stock_details = []
                    logger.debug(f"Screener retry attempts exhausted, giving up")

        screened_symbols = [detail['Ticker'] for detail in stock_details]
        screened_stock_symbols = screened_stock_symbols.union(screened_symbols)
        
        finance_quote_table_list.append(FinanceQuoteTable(data_datetime, market_closed, stock_details, 'stock'))
        stock_symbols_to_fetch.difference_update(stock_list)

    screened_stocks = sorted(list(screened_stock_symbols))
    missing_symbols = set(stocks)
    missing_symbols.difference_update(screened_stock_symbols)
    if stocks != screened_stocks:
        logger.debug(f"missing symbols: {missing_symbols}")

    return finance_quote_table_list, missing_symbols

#############################################################################
# Argument processing
#############################################################################
def parse_arguments():
    global arguments
    logger = logging.getLogger(__name__ + '.' + 'parse_arguments')
    parser = argparse.ArgumentParser(
            prog="quote_query",
            description="This is how we update stock quotes in the database"
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Run in debug mode")
    parser.add_argument('--fileportnames', action='append', default=[], help="Limit update to symbols from one (or more) file:port names. Default is all fpns")
    parser.add_argument('--filenames', action='append', default=[], help="Use file:ports where file is in this list")
    parser.add_argument('--stock_only', action='store_true', default=False, help="Only get stock quotes (no index, mf or option)")
    parser.add_argument('--index_skip', action='store_true', default=False, help="Skip quotes for indexes")
    parser.add_argument('--mf_skip', action='store_true', default=False, help="Skip quotes for mutual funds")
    parser.add_argument('--option_skip', action='store_true', default=False, help="Skip quotes for options")
    parser.add_argument('--clean', action='store_true', default=False, help="Delete rows from finance_quote table before committing new updates. Ignores arguments that limit fileportnames.")
    parser.add_argument('--delay', type=int, default=0, help="Seconds to delay before starting")
    parser.add_argument('--chunk', type=int, default=100, help="Limits the number of symbols passed to finviz in one chunk, default=100")
    parser.add_argument('--retries', type=int, default=5, help="Specifies number of retry attempts for Screener data.")
    arguments = parser.parse_args()

    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")

def process_arguments():
    global arguments
    global file_port_names
    logger = logging.getLogger(__name__ + '.' + 'process_arguments')

    # Get port_fileportname data
    file_port_names = FilePortName()

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
    logger = logging.getLogger(__name__)

    # Delay
    delay_start()

    # Check date, market holidays
    data_datetime, market_closed = check_date_market_holidays()

    # Get sets of symbols that will need quotes (stock, mutual fund, index, call, put)
    stock_symbols, mf_symbols, index_symbols, option_symbols = get_symbols(arguments.fileportnames)

    finance_quote_table_list = []

    # Call for stock info
    if stock_symbols:
        logger.info(f"Fetching quotes for {len(stock_symbols)} stock symbols")
        for retry_attempt in range(arguments.retries):
            logger.debug(f"update_stocks() attempt {retry_attempt}")
            finance_quote_table_sublist, missing_symbols = update_stocks(data_datetime, market_closed, stock_symbols)
            finance_quote_table_list.extend(finance_quote_table_sublist)
            logger.debug(f"Got info for {len(stock_symbols)-len(missing_symbols)} of {len(stock_symbols)} symbols")
            stock_symbols = missing_symbols
            if len(stock_symbols) == 0:
                break
            if retry_attempt == (arguments.retries - 1):
                logger.info("update_stocks() retry attempts exhausted, giving up")

        if stock_symbols:
            finance_quote_table_list.extend(update_stocks_last_ditch(data_datetime, market_closed, stock_symbols))

    if not arguments.stock_only:
        # Call for index info
        if not arguments.index_skip and index_symbols:
            logger.info(f"Fetching quotes for {len(index_symbols)} index symbols")
            finance_quote_table_list.extend(update_indexes(data_datetime, market_closed, index_symbols))
        
        # Call for mf info
        if not arguments.mf_skip and mf_symbols:
            logger.info(f"Fetching quotes for {len(mf_symbols)} mutual fund symbols")
            finance_quote_table_list.extend(update_mfs(data_datetime, market_closed, mf_symbols))

        # Call for option info
        if not arguments.option_skip and option_symbols:
            logger.info(f"Fetching quotes for {len(option_symbols)} option symbols")
            finance_quote_table_list.extend(update_options(data_datetime, market_closed, option_symbols))

    if arguments.clean and len(finance_quote_table_list) > 0:
        finance_quote_table_list[0].delete_table_rows()

    for finance_quote_table in finance_quote_table_list:
        finance_quote_table.update_finance_quote_table()

    

if __name__ == '__main__':
    configure_logging()
    parse_arguments()
    process_arguments()
    main()

