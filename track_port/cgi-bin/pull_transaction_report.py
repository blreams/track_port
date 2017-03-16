#!/usr/bin/python
import time
import argparse
import cgi
import cgitb; cgitb.enable() # for troubleshooting

import os
import re
import jinja2
import datetime

from collections import OrderedDict
from decimal import Decimal

from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

##############################################################################
# This section of code handles database access.
##############################################################################
#time.sleep(20)

try:
    host = os.uname()[1]
except:
    host = None

if host and host == 'jkt-myth':
    engine = create_engine('mysql://blreams@localhost/track_port')
else:
    engine = create_engine('sqlite:///track_port.db')

Base = declarative_base(engine)
metadata = MetaData()
#finance_quotes = Table('finance_quote', metadata, autoload=True, autoload_with=engine)


def load_session():
    """
    """
    metadata = Base.metadata
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

class FinanceQuotes(Base):
    """
+------------+------------------+------+-----+---------+-------+
| Field      | Type             | Null | Key | Default | Extra |
+------------+------------------+------+-----+---------+-------+
| symbol     | varchar(32)      | NO   | PRI |         |       |
| name       | varchar(32)      | YES  |     | NULL    |       |
| last       | decimal(14,4)    | YES  |     | 0.0000  |       |
| high       | decimal(14,4)    | YES  |     | 0.0000  |       |
| low        | decimal(14,4)    | YES  |     | 0.0000  |       |
| date       | date             | YES  |     | NULL    |       |
| time       | time             | YES  |     | NULL    |       |
| net        | decimal(14,4)    | YES  |     | 0.0000  |       |
| p_change   | decimal(6,2)     | YES  |     | 0.00    |       |
| volume     | int(10) unsigned | YES  |     | 0       |       |
| avg_vol    | int(10) unsigned | YES  |     | 0       |       |
| bid        | decimal(14,4)    | YES  |     | 0.0000  |       |
| ask        | decimal(14,4)    | YES  |     | 0.0000  |       |
| close      | decimal(14,4)    | YES  |     | 0.0000  |       |
| open       | decimal(14,4)    | YES  |     | 0.0000  |       |
| day_range  | varchar(64)      | YES  |     | NULL    |       |
| year_range | varchar(64)      | YES  |     | NULL    |       |
| eps        | decimal(14,4)    | YES  |     | 0.0000  |       |
| pe         | decimal(14,4)    | YES  |     | 0.0000  |       |
| div_date   | date             | YES  |     | NULL    |       |
| dividend   | decimal(14,4)    | YES  |     | 0.0000  |       |
| div_yield  | decimal(14,4)    | YES  |     | 0.0000  |       |
| cap        | decimal(20,4)    | YES  |     | NULL    |       |
| ex_div     | date             | YES  |     | NULL    |       |
| nav        | decimal(14,4)    | YES  |     | 0.0000  |       |
| yield      | decimal(14,4)    | YES  |     | 0.0000  |       |
| exchange   | varchar(32)      | YES  |     | NULL    |       |
| success    | tinyint(1)       | YES  |     | 0       |       |
| errormsg   | varchar(40)      | YES  |     | NULL    |       |
| method     | varchar(32)      | YES  |     | NULL    |       |
+------------+------------------+------+-----+---------+-------+
    """
    __tablename__ = 'finance_quote'
    __table_args__ = {'autoload': True}

class PortParams(Base):
    """
    """
    __tablename__ = 'port_param'
    __table_args__ = {'autoload': True}

class TransactionLists(Base):
    """
    """
    __tablename__ = 'transaction_list'
    __table_args__ = {'autoload': True}

session = load_session()
ppq = session.query(PortParams).filter(PortParams.fileportname.endswith('_combined')).all()

##############################################################################
# This section of code deals with arguments, whether command line or CGI.
##############################################################################
# This is the preferred order of headings along with the tablesorter sort type.
possible_headings = OrderedDict([
        ('Symb', 'text'),
        ('Shrs', 'digit'),
        ('Purch', 'digit'),
        ('Last', 'digit'),
        ('Chg', 'digit'),
        ('Day%', 'percent'),
        ('Day', 'digit'),
        ('MktVal', 'digit'),
        ('Gain%', 'percent'),
        ('Gain', 'digit'),
        ('Basis', 'digit'),
        ('Port%', 'percent'),
        ('Low', 'digit'),
        ('HL%', 'percent'),
        ('High', 'digit'),
        ('Days', 'digit'),
        ('PurDate', 'isoDate'),
        ('P/E', 'digit'),
        ('Vol', 'digit'),
        ('MkCap', 'digit'),
        ('Low52', 'digit'),
        ('HL52%', 'percent'),
        ('High52', 'digit'),
        ('CAGR', 'percent'),
        ('DIV', 'digit'),
        ('YLD', 'percent'),
        ('ExDiv', 'isoDate'),
        ])

# Use these headings when no columns are specified.
default_headings = ['Symb', 'Shrs', 'Purch', 'Last', 'Chg', 'Day%', 'Day', 'MktVal', 'Gain%', 'Gain', 'Basis', 'Port%',]

def handle_cols():
    """Return an OrderedDict indexed by column headings whose values are the
    tablesorter sort mode parameter accordingly:
      1. If no addcols args were specified, then return default_headings.
      2. Otherwise return default_headings plus others in addcols.
    """
    headings = OrderedDict()
    if args.addcols:
        for heading in possible_headings:
            if '_all_' in args.addcols or heading.lower() in args.addcols or heading.lower() in [h.lower() for h in default_headings]:
                headings[heading] = possible_headings[heading]
    else:
        for heading in default_headings:
            headings[heading] = possible_headings[heading]
    return headings

def handle_cgi_args(arguments):
    argdict = {}
    known_argkeys = ('method', 'combined', 'showname', 'showsector', 'sort', 'sold', 'handheld', 'viewname')
    fpns = [port_param.fileportname.replace('_combined', '') for port_param in ppq]
    knownfiles = set([fpn.split(':')[0] for fpn in fpns])
    argdict['fpns'] = []
    argdict['addcols'] = []
    for argkey in arguments.keys():
        if argkey in known_argkeys:
            argdict[argkey] = arguments[argkey].value
        elif argkey == 'addcols':
            for argval in arguments.getlist(argkey):
                argdict[argkey].append(argval.lower())
        elif argkey in knownfiles:
            for portname in arguments.getlist(argkey):
                if portname == '_ALL_':
                    for fpn in fpns:
                        if fpn.startswith(argkey + ':'):
                            argdict['fpns'].append(fpn)
                else:
                    fpn = argkey + ':' + portname
                    if fpn in fpns:
                        argdict['fpns'].append(fpn)
        else:
            pass
    return argdict

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--simulate', action='store_true', default=False, help="Used from command line to force arguments")
    parser.add_argument('--fpns', action='append', default=[], help="Add fileportname for querying db")
    parser.add_argument('-a', '--addcols', action='append', default=[], help="Add columns to the default list")
    args = parser.parse_args()
    if not args.fpns:
        args.fpns = ['port:fluffgazer']
    return args

###############################################################################
# classes supporting track_port access.
###############################################################################
class FinanceQuote(object):
    """These objects are effectively rows of the finance_quote table.
    """
    fieldlist = [
            'symbol', 'name', 'last', 'high', 'low', 'date', 'time', 'net', 'p_change', 'volume',
            'avg_vol', 'bid', 'ask', 'close', 'open', 'day_range', 'year_range', 'eps', 'pe',
            'div_date', 'dividend', 'div_yield', 'cap', 'ex_div', 'nav', 'yield', 'exchange',
            'success', 'errormsg', 'method',
            ]

    def __init__(self, quote_obj):
        for field in self.fieldlist:
            self.__setattr__(field, quote_obj.__getattribute__(field))

class FinanceQuoteList(object):
    """Container class that is essentially a dict indexed by symbol whose
    values are FinanceQuote objects.
    """
    def __init__(self):
        self._data = {}
        fqq = session.query(FinanceQuotes).all()
        for fq in fqq:
            self._data[fq.symbol] = FinanceQuote(fq)

    def get_by_symbol(self, symbol):
        """Simple lookup in _data by symbol.
        """
        return self._data[symbol]

class Transaction(object):
    """These objects are effectively rows of the transaction_list table.
    """
    def __init__(self, trl_obj):
        # I did not create this as a class attribute because each instance gets
        # extended to include FinanceQuote.fieldlist columns.
        self.fieldlist = [
                'symbol', 'fileportname', 'sector', 'position', 'descriptor', 'shares', 'open_price',
                'open_date', 'closed', 'close_price', 'close_date', 'expiration', 'strike',
                              ]
        for field in self.fieldlist:
            self.__setattr__(field, trl_obj.__getattribute__(field))

    def apply_quote(self, fq_obj):
        """For a given transaction, this is how the quote data for the
        corresponding symbol is added.
        """
        for field in fq_obj.fieldlist:
            if field not in self.fieldlist:
                self.__setattr__(field, fq_obj.__getattribute__(field))
        self.fieldlist.extend(fq_obj.fieldlist[1:])

class TransactionList(object):
    """Container class that will eventually hold all the data used to create
    the web page.
    """
    def __init__(self, fileportname):
        self.fileportname = fileportname
        self.combined_positions = {'longs': {}, 'shorts': {}, 'options': {}, 'cash': {}, 'closed': {}}

    def query_positions(self, quotes):
        """This gets all the open, long transactions.
        """
        self.open_positions = []
        tlq = session.query(TransactionLists).filter_by(fileportname=self.fileportname, closed=False, position='long').all()
        for t in tlq:
            self.open_positions.append(Transaction(t))
            self.open_positions[-1].apply_quote(quotes.get_by_symbol(t.symbol))

    def query_cash(self):
        """This gets all the cash transactions.
        """
        self.cash_positions = []
        tlq = session.query(TransactionLists).filter_by(fileportname=self.fileportname, position='cash').all()
        for t in tlq:
            self.cash_positions.append(Transaction(t))

    def query_closed(self):
        """This gets all the closed transactions.
        """
        self.closed_positions = []
        tlq = session.query(TransactionLists).filter_by(fileportname=self.fileportname, closed=True).all()
        for t in tlq:
            self.closed_positions.append(Transaction(t))

    def combine_positions(self):
        """Aggregates transactions for like symbols into combined positions.
        A position can be one or more transactions for the same symbol. Along
        the way, we also aggregate cash and openvalue (the current value of
        open positions). At the end we total up the portfolio value into
        totalvalue.
        """
        self.cash = 0
        self.openvalue = 0

        for t in self.open_positions:
            if not t.expiration:
                if t.shares > 0:
                    positiontype = 'longs'
                elif t.shares < 0:
                    positiontype = 'shorts'
            else:
                positiontype = 'options'
                t.symbol = '{s}{e}{t}{k}'.format(
                        s=t.symbol,
                        e=t.expiration.strftime("%y%m%d"),
                        t=t.descriptor[0].upper(),
                        k='{:05d}{:03d}'.format(int(t.strike), int((t.strike - int(t.strike)) * 1000))
                        )
            position = self.combined_positions[positiontype].get(t.symbol, Position(t.symbol))
            position.add_transaction(t)
            position.normalize_quote(quotes.get_by_symbol(t.symbol))
            self.combined_positions[positiontype][t.symbol] = position
            self.cash -= t.open_price * t.shares
            self.openvalue += t.shares * quotes.get_by_symbol(t.symbol).last

        for t in self.cash_positions:
            self.cash += t.open_price
            cashposition = self.combined_positions['cash'].get('CASH', CashPosition('CASH'))
            cashposition.add_transaction(t)
            self.combined_positions['cash']['CASH'] = cashposition

        for t in self.closed_positions:
            self.cash += (t.close_price - t.open_price) * t.shares
            closedposition = self.combined_positions['closed'].get(t.symbol, ClosedPosition(t.symbol))
            closedposition.add_transaction(t)
            self.combined_positions['closed'][t.symbol] = closedposition

        self.totalvalue = self.cash + self.openvalue

    def finalize_positions(self, quotes):
        """Because we cannot calculate port_pct until we know the portfolio
        totalvalue, this is where that happens (must be called AFTER calling
        combine_positions().
        """
        for positiontype in ('longs', 'shorts', 'options'):
            for symbol in self.combined_positions[positiontype]:
                position = self.combined_positions[positiontype][symbol]
                position.port_pct = Decimal(100.0) * position.shares * quotes.get_by_symbol(symbol).last / self.totalvalue
                position.gen_report_line(quotes.get_by_symbol(symbol))


##############################################################################
# Classes supporting position and transaction calculations.
##############################################################################
class Position(object):
    """These objects are what gets reported on the web page. A position is one
    or more transactions for the same symbol. This is where the magic happens
    for combining multiple transactions into a single position.
    """
    def __init__(self, symbol):
        self.symbol = symbol
        self.shares = 0
        self.basis = 0
        self.mktval = 0
        self.open_price = None
        self.open_date = None
        self.transactions = []

    def __repr__(self):
        return 'symb={sy},shs={sh},bs={b},mv={mv},op={op},od={od}'.format(sy=self.symbol, sh=self.shares, b=self.basis, od=self.open_date, op=self.open_price, mv=self.mktval)

    def parse_range(self, quoterange, part='low'):
        """Helper function that takes a quote range string and returns the
        designated part (high/low).
        """
        rv = Decimal(0.0)
        if quoterange:
            rangematch = re.match(r"'(?P<low>\d+\.?\d*) - (?P<high>\d+\.?\d*)'", quoterange)
            if rangematch:
                rv = Decimal(rangematch.group(part))
        return rv

    def add_transaction(self, transaction):
        """This is where the combining happens.
        1. Add shares.
        2. Add to basis.
        3. Calculate new open_price as basis / shares.
        4. Only set open_date if it is earlier.
        5. Append the transaction to list.
        """
        self.shares += transaction.shares
        self.basis += transaction.shares * transaction.open_price
        self.open_price = self.basis / self.shares
        if not self.open_date:
            self.open_date = transaction.open_date
        elif self.open_date > transaction.open_date:
            self.open_date = transaction.open_date
        self.transactions.append(transaction)

    def normalize_quote(self, quote):
        """This is where we fill in other quote-based fields as needed.
        """
        quote.low = self.parse_range(quote.day_range, part='low')
        quote.high = self.parse_range(quote.day_range, part='high')
        if quote.high != quote.low:
            quote.hl_pct = Decimal(100.0) * ((quote.last - quote.low) / (quote.high - quote.low))
        else:
            quote.hl_pct = Decimal(0.0)
        quote.low52 = self.parse_range(quote.year_range, part='low')
        quote.high52 = self.parse_range(quote.year_range, part='high')
        if quote.high52 != quote.low52:
            quote.hl52_pct = Decimal(100.0) * ((quote.last - quote.low52) / (quote.high52 - quote.low52))
        else:
            quote.hl52_pct = Decimal(0.0)

    def gen_report_line(self, quote):
        """A report item is a tuple that contains the value to be displayed
        along with a string formatter to tell how to display it. The tuple is
        (format, value).

        Along the way we also create subreport items which are done when a
        position has multiple transactions.
        """
        #import pdb;pdb.set_trace()
        datefmt = '%Y-%m-%d'
        ex_div = '' if not quote.ex_div else quote.ex_div.strftime(datefmt)
        report = {}
        report['Symb'] = ('{}', self.symbol)
        report['Shrs'] = ('{:.0f}', self.shares)
        report['Purch'] = ('{:.2f}', self.open_price)
        report['Last'] = ('{:.2f}', quote.last)
        report['Chg'] = ('{:+.2f}', quote.net)
        report['Day%'] = ('{:+.2f}%', quote.p_change)
        report['Day'] = ('{:+.2f}', self.shares * quote.net)
        report['MktVal'] = ('{:+.2f}', self.shares * quote.last)
        report['Gain'] = ('{:+.2f}', (self.shares * quote.last) - self.basis)
        report['Gain%'] = ('{:+.1f}%', ((self.shares * quote.last) - self.basis) * Decimal(100.0) / abs(self.basis))
        report['Basis'] = ('{:.2f}', self.basis)
        report['Port%'] = ('{:+.1f}%', self.port_pct)
        report['Low'] = ('{:.2f}', quote.low)
        report['High'] = ('{:.2f}', quote.high)
        report['HL%'] = ('{:.1f}%', quote.hl_pct)
        report['Days'] = ('{:d}', (datetime.date.today() - self.open_date).days)
        report['PurDate'] = ('{:s}', self.open_date.strftime(datefmt))
        report['P/E'] = ('{:.2f}', quote.pe)
        report['Vol'] = ('{:d}', quote.volume)
        report['MkCap'] = ('{:.0f}', quote.cap)
        report['Low52'] = ('{:.2f}', quote.low52)
        report['High52'] = ('{:.2f}', quote.high52)
        report['HL52%'] = ('{:.1f}%', quote.hl52_pct)
        report['CAGR'] = ('{:.1f}%', Decimal(10.1))
        report['DIV'] = ('{:.2f}', quote.dividend)
        report['YLD'] = ('{:.2f}', quote.div_yield)
        report['ExDiv'] = ('{:s}', ex_div)

        report['transactions'] = []
        if len(self.transactions) > 1:
            for transaction in self.transactions:
                subreport = {}
                subreport['Symb'] = ('{}', '')
                subreport['Shrs'] = ('{:.0f}', transaction.shares)
                subreport['Purch'] = ('{:.2f}', transaction.open_price)
                subreport['Last'] = ('{}', '')
                subreport['Chg'] = ('{}', '')
                subreport['Day%'] = ('{}', '')
                subreport['Day'] = ('{:+.2f}', transaction.shares * quote.net)
                subreport['MktVal'] = ('{:+.2f}', transaction.shares * quote.last)
                subreport['Gain'] = ('{:+.2f}', transaction.shares * (quote.last - transaction.open_price))
                subreport['Gain%'] = ('{:+.1f}%', (((transaction.shares * quote.last) / (transaction.shares * transaction.open_price)) - Decimal(1.0)) * Decimal(100.0))
                subreport['Basis'] = ('{:.2f}', transaction.shares * transaction.open_price)
                subreport['Port%'] = ('{}', '')
                subreport['Low'] = ('{}', '')
                subreport['High'] = ('{}', '')
                subreport['HL%'] = ('{}', '')
                subreport['Days'] = ('{:d}', (datetime.date.today() - transaction.open_date).days)
                subreport['PurDate'] = ('{:s}', transaction.open_date.strftime(datefmt))
                subreport['P/E'] = ('{}', '')
                subreport['Vol'] = ('{}', '')
                subreport['MkCap'] = ('{}', '')
                subreport['Low52'] = ('{}', '')
                subreport['High52'] = ('{}', '')
                subreport['HL52%'] = ('{}', '')
                subreport['CAGR'] = ('{}', '')
                subreport['DIV'] = ('{}', '')
                subreport['YLD'] = ('{}', '')
                subreport['ExDiv'] = ('{}', '')
                report['transactions'].append(subreport)

        #TODO Figure out how to show purchase that happened today

        self.report = report

class CashPosition(Position):
    """Position subclass specifically for cash positions.
    """
    #TODO This is a work-in-progress.
    def add_transaction(self, transaction):
        self.shares += transaction.open_price
        self.basis = self.shares
        self.open_price = 1
        if not self.open_date:
            self.open_date = transaction.open_date
        elif transaction.open_date and self.open_date > transaction.open_date:
            self.open_date = transaction.open_date
        self.transactions.append(transaction)

    def gen_report_line(self):
        report = OrderedDict()
        self.report = report


class ClosedPosition(Position):
    """Position subclass specifically for closed positions.
    """
    #TODO This is a work-in-progress.
    def add_transaction(self, transaction):
        self.basis += transaction.shares * transaction.open_price
        self.mktval += transaction.shares * transaction.close_price
        self.transactions.append(transaction)

def render(tpl_path, context):
    """Helper function to render page using Jinja2.
    """
    path, filename = os.path.split(tpl_path)
    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')).get_template(filename).render(context)

def main():
    global args
    global quotes

    args = parse_args()
    if not args.simulate:
        cgi_args = handle_cgi_args(cgi.FieldStorage())
        args.fpns = cgi_args['fpns']
        args.addcols = cgi_args['addcols']

    lheadings = handle_cols()

    quotes = FinanceQuoteList()

    tldict = {}
    for fpn in args.fpns:
        tldict[fpn] = TransactionList(fpn)
        tldict[fpn].query_positions(quotes)
        tldict[fpn].query_cash()
        tldict[fpn].query_closed()
        tldict[fpn].combine_positions()
        tldict[fpn].finalize_positions(quotes)

    #import pdb;pdb.set_trace()
    context = {
        'tldict': tldict,
        'lheadings': lheadings,
        'simulate': args.simulate,
        }

    #import pdb;pdb.set_trace()
    result = render(r'ptr_layout.html', context)
    if not args.simulate:
        print "Content-type: text/html"
        print
    print result


if __name__ == '__main__':
    main()

