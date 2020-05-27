#!/usr/bin/python3
import time
import argparse
#import cgi
#import cgitb; cgitb.enable() # for troubleshooting

import sys
import os
import re
import six
import logging
import logging.config
import decimal
import copy

from datetime import datetime, timedelta
from dateutil import parser
import dateparser
import get_a_quote

from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from pandas_datareader import data as pdr_data

##############################################################################
# This stuff needs to be done as globals
##############################################################################
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

logging.config.fileConfig('build_port_history_logging.conf')
logger = logging.getLogger('main')
##############################################################################


class PortParams(Base):
    __tablename__ = 'port_param'
    __table_args__ = {'autoload': True}

class TransactionLists(Base):
    __tablename__ = 'transaction_list'
    __table_args__ = {'autoload': True}

class Transaction(object):
    """Effectively a row of the transaction_list table."""
    def __repr__(self):
        return '{},{},{},{},{},{},{},{},{},{},{}'.format(
                self.fileportname,
                self.symbol,
                self.sector.replace(',','|'),
                self.position,
                self.descriptor,
                self.shares,
                self.open_date,
                self.open_price,
                self.closed,
                self.close_date,
                self.close_price,
                )

    def __init__(self, transaction_list, **kwargs):
        self.fieldlist = [
                'symbol',
                'fileportname',
                'sector',
                'position',
                'descriptor',
                'shares',
                'open_price',
                'open_date',
                'closed',
                'close_price',
                'close_date',
                'expiration',
                'strike',
                ]
        if isinstance(transaction_list, TransactionLists):
            for field in self.fieldlist:
                self.__setattr__(field, transaction_list.__getattribute__(field))
        elif isinstance(transaction_list, six.string_types):
            for field in kwargs:
                self.__setattr__(field, kwargs[field])

class TransactionList(object):
    """Container class that will hold all the transactions from transaction_list."""
    def __init__(self, fileportname):
        self.log = logging.getLogger('TransactionList')
        self.fileportname = fileportname
        self.combined_positions = {'longs': {}, 'shorts': {}, 'options': {}, 'cash': {}, 'closed': {}}
        (self.filename, self.portname) = fileportname.split(':')

    def query(self):
        """This gets all transactions."""
        header = [
                'fileportname',
                'symbol',
                'sector',
                'position',
                'descriptor',
                'shares',
                'open_date',
                'open_price',
                'closed',
                'close_date',
                'close_price',
                ]
        with open("transactions_by_open.csv", "w") as TFILE:
            TFILE.write(f"{','.join(header)}\n")
            transaction_list_query = session.query(TransactionLists).filter_by(fileportname=self.fileportname).order_by('open_date').all()
            for t in transaction_list_query:
                transaction = Transaction(t)
                TFILE.write(f"{transaction}\n")
            
        with open("transactions_by_close.csv", "w") as TFILE:
            TFILE.write(f"{','.join(header)}\n")
            transaction_list_query = session.query(TransactionLists).filter_by(fileportname=self.fileportname).order_by('close_date').all()
            for t in transaction_list_query:
                transaction = Transaction(t)
                TFILE.write(f"{transaction}\n")

    def cash_analysis(self):
        """Generates list of dates and cash positions per date."""
        if arguments.verbose: self.log.info("Call cash_analysis()")
        self.cash_date = {}
        self.cash_initial = None
        cash_changes = []
        transaction_list_query = session.query(TransactionLists).filter_by(fileportname=self.fileportname).order_by('open_date').all()

        for t in transaction_list_query:
            transaction = Transaction(t)
            self.log.debug(f"Transaction {transaction}")

            if transaction.position == 'cash' and transaction.descriptor == 'initial':
                self.cash_initial = transaction.open_price

            elif transaction.position == 'cash' and transaction.descriptor == 'intermediate':
                # dividends, interest, commissions, adjustments
                negative = 0
                if transaction.open_price < 0:
                    negative = 1
                cash_change = transaction.open_date, negative, transaction.open_price
                cash_changes.append(cash_change)

            elif transaction.position == 'long':
                open_cash_change = -1 * transaction.shares * transaction.open_price
                cash_change = transaction.open_date, -open_cash_change, open_cash_change
                cash_changes.append(cash_change)
                if transaction.closed:
                    close_cash_change = transaction.shares * transaction.close_price
                    cash_change = transaction.close_date, -close_cash_change, close_cash_change
                    cash_changes.append(cash_change)


            else:
                self.log.warning(f"Transaction had no cash implication: {transaction}")


        self.cash_accum = self.cash_initial
        self.cash_changes = sorted(cash_changes)

        # we need to preload first entry with initial_cash
        date_of_change, negative, change = self.cash_changes[0]
        current_date = date_of_change - timedelta(days=1)
        self.cash_date[current_date] = self.cash_accum

        for date_of_change, negative, change in self.cash_changes:
            while current_date < date_of_change:
                current_date += timedelta(days=1)
                self.cash_date[current_date] = self.cash_accum
            self.cash_accum += change
            self.cash_date[date_of_change] = self.cash_accum
            self.log.debug(f"Cash change on date {date_of_change} to {self.cash_accum}")

        while current_date < datetime.date(datetime.now()):
            current_date += timedelta(days=1)
            self.cash_date[current_date] = self.cash_accum

        self.log.info(f"Initial Date = {list(self.cash_date.keys())[0]}")
        self.log.info(f"Initial Cash = {self.cash_initial}")
        self.log.info(f"Final Date = {list(self.cash_date.keys())[-1]}")
        self.log.info(f"Final Cash = {self.cash_accum}")

    def position_analysis(self):
        """Generates list of dates and open positions per date."""

        # On any given date, there are a set of "open" positions. Each open
        # position can be characterized by traits: symbol, descriptor, strike,
        # and expiration. Thus the accumulator will be a dict using a tuple
        # of these traits as the index, and a number of shares as the value.
        #
        # Let's create two lists of transactions, one for opens, one for
        # closes. The list elements will be tuples: date, close_open, 
        # symbol, descriptor, strike, expiration, shares. We can join the
        # lists and sort.
        #
        # Then it is just a matter of looping over the resulting list,
        # filling in the intermediate dates, tracking the accumulated
        # open positions and adding the result to the position_date dict. 

        if arguments.verbose: self.log.info("Call position_analysis()")
        self.position_date = {}
        self.symbol_ranges = {}
        half_transactions = []
        transaction_list_query = session.query(TransactionLists).filter_by(fileportname=self.fileportname, position='long').order_by('open_date').all()

        for t in transaction_list_query:
            transaction = Transaction(t)
            if transaction.position == 'long':
                self.update_symbol_range(transaction)
            open_tuple = (
                    transaction.open_date,
                    'o',
                    transaction.symbol,
                    transaction.descriptor,
                    transaction.strike,
                    transaction.expiration,
                    transaction.shares,
                    )
            half_transactions.append(open_tuple)
            if transaction.closed:
                close_tuple = (
                        transaction.close_date,
                        'c',
                        transaction.symbol,
                        transaction.descriptor,
                        transaction.strike,
                        transaction.expiration,
                        transaction.shares,
                        )
                half_transactions.append(close_tuple)

        position_accum = {}
        current_date = None
        for half_transaction in sorted(half_transactions):
            self.log.debug(f"Half: {half_transaction}")
            if current_date is None:
                current_date = half_transaction[0]
                self.log.info(f"Initializing current_date as {current_date}")
                self.log.info(f"Initial position_accum = {position_accum}")
            while current_date < half_transaction[0]:
                self.position_date[current_date] = copy.copy(position_accum)
                current_date += timedelta(days=1)

            # Build trait
            symbol = half_transaction[2]
            descriptor = half_transaction[3]
            strike = half_transaction[4]
            expiration = half_transaction[5]
            trait = symbol, descriptor, strike, expiration
            shares = half_transaction[6]
            if half_transaction[1] == 'c':
                shares *= -1
            if position_accum.get(trait) is None:
                position_accum[trait] = 0
                self.log.debug(f"Creating new position {trait}:{shares} on {current_date}")
            position_accum[trait] += shares
            self.log.debug(f"Adding {shares} of {trait} to position_accum on {current_date}")
            if position_accum[trait] == 0:
                del(position_accum[trait])
                self.log.debug(f"Removing position {trait} on {current_date}")
            self.position_date[current_date] = copy.copy(position_accum)

        current_date = sorted(list(self.position_date.keys()))[-1]
        self.log.info(f"Current Date = {current_date}")
        while current_date < datetime.date(datetime.now()):
            current_date += timedelta(days=1)
            self.position_date[current_date] = copy.copy(position_accum)

        with open('position_date.csv', 'w') as PD:
            for date, positions in self.position_date.items():
                PD.write(f"{date}")
                for position in sorted(positions):
                    symbol = position[0]
                    shares = positions[position]
                    PD.write(f",{symbol}:{shares}")
                PD.write("\n")

        self.initial_date = sorted(list(self.position_date.keys()))[0]
        self.log.info(f"Initial Date = {self.initial_date}")
        self.log.info(f"Initial Positions = {self.position_date[self.initial_date]}")
        self.final_date = sorted(list(self.position_date.keys()))[-1]
        self.log.info(f"Final Date = {self.final_date}")
        self.log.info(f"Final Positions = {position_accum}")
        self.close_symbol_ranges()
        self.get_symbol_prices()

    def update_symbol_range(self, transaction):
        """Given a transaction:
        If there is no symbol_range, create one using open_date and open_price.
        If there is a symbol_range, change open_date/open_price if open_date is earlier.
        If transaction is closed, add a close_date/close_price or update it if later.
        """
        # Work on range start
        if self.symbol_ranges.get(transaction.symbol) is None:
            self.symbol_ranges[transaction.symbol] = {'start': transaction.open_date, 'start_price': transaction.open_price}
            self.log.info(f"Creating range for {transaction.symbol}")
            self.log.info(f"Setting range start for {transaction.symbol} to {transaction.open_date}, {transaction.open_price}")
        elif self.symbol_ranges[transaction.symbol]['start'] > transaction.open_date:
            self.symbol_ranges[transaction.symbol]['start'] = transaction.open_date
            self.symbol_ranges[transaction.symbol]['start_price'] = transaction.open_price
            self.log.info(f"Updating range start for {transaction.symbol} to {transaction.open_date}, {transaction.open_price}")

        # Work on range end
        if transaction.closed:
            if self.symbol_ranges.get(transaction.symbol).get('end') is None or self.symbol_ranges[transaction.symbol]['end'] < transaction.close_date:
                self.symbol_ranges[transaction.symbol]['end'] = transaction.close_date
                self.symbol_ranges[transaction.symbol]['end_price'] = transaction.close_price
                self.log.info(f"Updating range end for {transaction.symbol} to {transaction.close_date}, {transaction.close_price}")

    def close_symbol_ranges(self):
        """For the open positions, create end and end_price by calling get_a_quote."""
        for trait in self.position_date[self.final_date]:
            expiration = trait[3]
            if expiration is None:
                symbol = trait[0]
                get_a_quote_out = get_a_quote.main(args=f'--symbol={symbol} --call')
                self.symbol_ranges[symbol]['end'] = self.final_date
                self.symbol_ranges[symbol]['end_price'] = decimal.Decimal(get_a_quote_out.split()[0])
                self.log.info(f"Updating range end for {symbol} to {self.symbol_ranges[symbol]['end']}, {self.symbol_ranges[symbol]['end_price']}")

    def get_symbol_prices(self):
        """For all symbol_ranges, use pandas_datareader to get historical
        Adj Close prices. Use this to create symbol_prices.
        """
        self.symbol_prices = {}
        for symbol, symbol_range in self.symbol_ranges.items():
            try:
                self.symbol_prices[symbol] = pdr_data.DataReader(symbol, start=symbol_range['start'], end=symbol_range['end'], data_source='yahoo')['Adj Close']
                self.log.info(f"Got Adj Close for {symbol}")
            except:
                self.symbol_prices[symbol] = None
                self.log.info(f"Problem getting Adj Close for {symbol}")


def get_arguments():
    global arguments
    parser = argparse.ArgumentParser(
            prog='build_port_history',
            description='Use this for recreating portfolio history based on transactions in transaction_list table'
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Show debug messages")
    parser.add_argument('-r', '--report_date', help="Report date")
    parser.add_argument('-f', '--fileportname', default='port:fluffgazer', help="fileportname (ie. port:fluffgazer)")
    arguments = parser.parse_args()
    pass

def main():
    log = logging.getLogger('main')
    log.debug('='*150)

    get_arguments()

    tl = TransactionList(arguments.fileportname)
    tl.cash_analysis()
    #tl.query()
    tl.position_analysis()

if __name__ == '__main__':
    main()

