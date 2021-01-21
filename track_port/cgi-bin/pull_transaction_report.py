#!/usr/bin/python3
import time
import argparse
import cgi
#import cgitb; cgitb.enable(display=0, logdir='/home/blreams') # for troubleshooting

import os
import re
import jinja2
import datetime
#import htmlmin

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

if host and host in ('jkt-myth', 'skx-linux',):
    engine = create_engine('mysql://blreams@localhost/track_port')
else:
    engine = create_engine('sqlite:///../port.db')

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

class ColorSchemes(Base):
    """
    """
    __tablename__ = 'color_scheme'
    __table_args__ = {'autoload': True}

class TickerSymbols(Base):
    """
    """
    __tablename__ = 'ticker_symbols'
    __table_args__ = {'autoload': True}

class FilePortNames(Base):
    """
    """
    __tablename__ = 'port_fileportname'
    __table_args__ = {'autoload': True}


session = load_session()
fpnq = session.query(FilePortNames).all()
ticker_symbols = [ts.symbol for ts in session.query(TickerSymbols).all()]

schemes = ['garnet', 'green', 'purple', 'blue', 'ice', 'gray',]
schemeset = set(schemes)

tclasses = ['main', 'ticker', 'summary']
tclassset = set(tclasses)

mwd = {}

##############################################################################
# This section of code deals with arguments, whether command line or CGI.
##############################################################################
# This is the preferred order of headings along with the tablesorter sort type.
possible_headings = OrderedDict([
        ('Symb', 'text'),
        ('Links', 'text'),
        ('Sector', 'text'),
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
default_headings = ['Symb', 'Links', 'Shrs', 'Purch', 'Last', 'Chg', 'Day%', 'Day', 'MktVal', 'Gain%', 'Gain', 'Basis', 'Days', 'CAGR', 'Port%',]

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

legacy_link = r'http://daneel.homelinux.net/cgi-bin/pull_transaction_report.cgi?port=_ALL_&method=diff&combined=TRUE&sort=pct_chg'
all_cols_link = r'http://daneel.homelinux.net/cgi-bin/pull_transaction_report.py?port=_ALL_&method=diff&combined=TRUE&sort=pct_chg&addcols=_all_'
def handle_cgi_args(arguments):
    global legacy_link
    global all_cols_link
    argdict = {}
    known_argkeys = ('method', 'combined', 'showname', 'showsector', 'sort', 'sold', 'handheld', 'viewname', 'cashdetail')
    fpns = [f"{fpn.filename}:{fpn.portname}" for fpn in fpnq if not fpn.portname.endswith('_combined')]
    knownfiles = set([fpn.split(':')[0] for fpn in fpns])
    argdict['fpns'] = []
    argdict['addcols'] = []
    argdict['cashdetail'] = False
    argdict['sort'] = 'pct_chg'
    argdict['showsector'] = False
    argdict['showname'] = False
    link_args = []
    for argkey in arguments.keys():
        if argkey in known_argkeys:
            if arguments[argkey].value.lower() == 'true':
                argdict[argkey] = True
            elif arguments[argkey].value.lower() == 'false':
                argdict[argkey] = False
            else:
                argdict[argkey] = arguments[argkey].value
            link_args.append("{}={}".format(argkey, arguments[argkey].value))
        elif argkey == 'addcols':
            for argval in arguments.getlist(argkey):
                argdict[argkey].append(argval.lower())
        elif argkey in knownfiles:
            for portname in arguments.getlist(argkey):
                link_args.append("{}={}".format(argkey, portname))
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
    if argdict['sort'] == 'pct_chg':
        argdict['sort'] = 'Day%'

    legacy_link = r'http://daneel.homelinux.net/cgi-bin/pull_transaction_report.cgi?' + '&'.join(link_args)
    all_cols_link = r'http://daneel.homelinux.net/cgi-bin/pull_transaction_report.py?' + '&'.join(link_args) + '&addcols=_all_'
    return argdict

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--simulate', action='store_true', default=False, help="Used from command line to force arguments")
    parser.add_argument('--fpns', action='append', default=[], help="Add fileportname for querying db")
    parser.add_argument('--addcols', action='append', default=[], help="Add columns to the default list")
    parser.add_argument('--cashdetail', action='store_true', default=False, help="Show cash detail sub transactions")
    parser.add_argument('--sort', dest='sortcol', default='Day%', help="Specify column for initial sort")
    parser.add_argument('--summary', dest='summary_method', default='diff', help="diff|sum|none")
    args = parser.parse_args()
    if not args.fpns:
        args.fpns = ['port:fluffgazer']
    return args

def whee_doggie_checker(tld):
    rv = {}
    if 'port:fluffgazer' in tld and 'port:xcargot' in tld:
        good_daygain = tld['port:fluffgazer'].daygain
        bad_daygain = tld['port:xcargot'].daygain
        port_diff = good_daygain - bad_daygain
        if good_daygain > 0.0 and good_daygain > bad_daygain:
            if port_diff > 1000.0:
                rv['port:fluffgazer'] = 'Mighty Whee Doggies!!!'
            elif port_diff > 0.0:
                rv['port:fluffgazer'] = 'Whee Doggies!!!'
        elif bad_daygain > 0.0 and bad_daygain > good_daygain:
            if port_diff < -1000.0:
                rv['port:xcargot'] = '!!!seiggoD eehW ythgiM'
            elif port_diff < 0.0:
                rv['port:xcargot'] = '!!!seiggoD eehW'

    return rv

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

    def __init__(self, symbol, quote_obj):
        #if isinstance(quote_obj, basestring):
        if isinstance(quote_obj, str):
            if quote_obj == 'CASH':
                self.__setattr__('symbol', 'CASH')
                self.__setattr__('name', 'The Green Stuff')
                self.__setattr__('last', Decimal(1.00))
            elif quote_obj == 'BOGUS':
                self.symbol = symbol
                self.name = 'This is a bogus entry'
                self.last = Decimal(0.0)
                self.high = Decimal(0.0)
                self.low = Decimal(0.0)
                self.date = ''
                self.time = ''
                self.net = Decimal(0.0)
                self.p_change = Decimal(0.0)
                self.volume = 0
                self.avg_vol = 0
                self.bid = Decimal(0.0)
                self.ask = Decimal(0.0)
                self.close = Decimal(0.0)
                self.open = Decimal(0.0)
                self.day_range = "'1.00 - 0.00'"
                self.year_range = "'1.00 - 0.00'"
                self.eps = Decimal(0.0)
                self.pe = Decimal(0.0)
                self.div_date = ''
                self.dividend = Decimal(0.0)
                self.div_yield = Decimal(0.0)
                self.cap = 0
                self.ex_div = ''
                self.nav = ''
                self.__setattr__('yield', Decimal(0.0))
                self.exchange = 'BOGUS'
                self.success = True
                self.errormsg = ''
                self.method = ''
        else:
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
            self._data[fq.symbol] = FinanceQuote(fq.symbol, fq)
        self._data['CASH'] = FinanceQuote('CASH', 'CASH')

    def get_by_symbol(self, symbol):
        """Simple lookup in _data by symbol.
        """
        if self._data.get(symbol) is None:
            self._data[symbol] = FinanceQuote(symbol, 'BOGUS')
        return self._data.get(symbol)

class Transaction(object):
    """These objects are effectively rows of the transaction_list table.
    """
    def __repr__(self):
        return "{fpn},{symbol},{shrs},{od}".format(fpn=self.fileportname, symbol=self.symbol, shrs=self.shares, od=self.open_date)

    def __init__(self, trl_obj, **kwargs):
        # I did not create this as a class attribute because each instance gets
        # extended to include FinanceQuote.fieldlist columns.
        self.fieldlist = [
                'symbol', 'fileportname', 'sector', 'position', 'descriptor', 'shares', 'open_price',
                'open_date', 'closed', 'close_price', 'close_date', 'expiration', 'strike',
                              ]
        if isinstance(trl_obj, TransactionLists):
            for field in self.fieldlist:
                self.__setattr__(field, trl_obj.__getattribute__(field))
        #elif isinstance(trl_obj, basestring):
        elif isinstance(trl_obj, str):
            for field in kwargs:
                self.__setattr__(field, kwargs[field])

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
        (self.filename, self.portname) = fileportname.split(':')

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
        self.invested_capital = 0
        self.realized_gain = 0
        self.openvalue = 0
        self.daygain = 0
        self.sector = ''

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
            self.invested_capital += t.open_price * t.shares
            self.openvalue += t.shares * quotes.get_by_symbol(t.symbol).last
            self.daygain += t.shares * quotes.get_by_symbol(t.symbol).net

        for t in self.closed_positions:
            self.realized_gain += (t.close_price - t.open_price) * t.shares
            closedposition = self.combined_positions['closed'].get(t.symbol, ClosedPosition(t.symbol))
            closedposition.add_transaction(t)
            self.combined_positions['closed'][t.symbol] = closedposition

        for t in self.cash_positions:
            self.cash += t.open_price
            cashposition = self.combined_positions['cash'].get('CASH', CashPosition('CASH'))
            cashposition.add_transaction(t)
            self.combined_positions['cash']['CASH'] = cashposition

        cashposition = self.combined_positions['cash'].get('CASH', CashPosition('CASH'))
        # Add a cash transaction representing invested capital.
        t = Transaction('CASH', symbol='CASH', fileportname=self.fileportname, sector='invested capital', position='cash', descriptor='intermediate', shares=Decimal(0.0), open_price=-self.invested_capital, open_date=datetime.date.today())
        cashposition.add_transaction(t)
        # Add a cash transaction representing realized gain.
        t = Transaction('CASH', symbol='CASH', fileportname=self.fileportname, sector='realized gain', position='cash', descriptor='intermediate', shares=Decimal(0.0), open_price=self.realized_gain, open_date=datetime.date.today())
        cashposition.add_transaction(t)

        self.totalvalue = self.cash - self.invested_capital + self.realized_gain + self.openvalue

    def finalize_positions(self, quotes):
        """Because we cannot calculate port_pct until we know the portfolio
        totalvalue, this is where that happens (must be called AFTER calling
        combine_positions().
        """
        self.cum_port_pct = 0
        for positiontype in ('longs', 'shorts', 'options', 'cash'):
            for symbol in self.combined_positions[positiontype]:
                position = self.combined_positions[positiontype][symbol]
                position.port_pct = Decimal(100.0) * position.shares * quotes.get_by_symbol(symbol).last / self.totalvalue
                position.gen_report_line(quotes.get_by_symbol(symbol))
                self.cum_port_pct += position.port_pct

    def create_totals(self):
        """This is where we tot up columns. The only columns we total are
        Day, MktVal, Gain, Port% and Basis. We also calculate Day% and Gain%.
        """
        try:
            daypct = Decimal(100.0) * self.daygain / self.totalvalue
        except:
            assert False, f"help me, {self.fileportname}"
        daycolor = calc_bgcolor(daypct, 0.1, 5.0)
        gainpct = Decimal(100.0) * self.realized_gain / self.totalvalue
        gaincolor = calc_bgcolor(gainpct, 1.0, 50.0)
        self.totals = {}
        self.totals['MktVal'] = (self.totalvalue, '{:.2f}', 'right', )
        self.totals['Gain'] = (self.realized_gain, '{:+.2f}', 'right', gaincolor, )
        self.totals['Basis'] = (self.invested_capital, '{:.2f}', 'right', )
        self.totals['Day'] = (self.daygain, '{:+.2f}', 'right', daycolor, )
        self.totals['Port%'] = (self.cum_port_pct, '{:.1f}%', 'right', )
        self.totals['Day%'] = (daypct, '{:+.2f}%', 'right', daycolor, )
        self.totals['Gain%'] = (gainpct, '{:+.2f}%', 'right', gaincolor, )


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
        self.sector = ''
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
        self.sector = transaction.sector

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
        daycolor = calc_bgcolor(quote.p_change, 0.1, 5.0)
        gainpct = ((self.shares * quote.last) - self.basis) * Decimal(100.0) / abs(self.basis)
        gaincolor = calc_bgcolor(gainpct, 1.0, 50.0)
        #import pdb;pdb.set_trace()
        datefmt = '%Y-%m-%d'
        ex_div = '' if not quote.ex_div else quote.ex_div.strftime(datefmt)
        days = (datetime.date.today() - self.open_date).days
        if days > 1:
            cagr = (float(quote.last / self.open_price) ** (1.0 / (days / 365.0)) - 1.0) * 100.0
        else:
            cagr = 0.0
        report = {}
        report['Symb'] = (self.symbol, '{}', 'center', )
        report['Links'] = (self.create_list_of_links(self.symbol), '{}', 'center', )
        report['Sector'] = (self.sector, '{}', 'left', )
        if self.shares == int(self.shares):
            report['Shrs'] = (self.shares, '{:.0f}', 'right', )
        else:
            report['Shrs'] = (self.shares, '{:.3f}', 'right', )
        report['Purch'] = (self.open_price, '{:.2f}', 'right', )
        report['Last'] = (quote.last, '{:.2f}', 'right', daycolor, )
        report['Chg'] = (quote.net, '{:+.2f}', 'right', daycolor, )
        report['Day%'] = (quote.p_change, '{:+.2f}%', 'right', daycolor, )
        report['Day'] = (self.shares * quote.net, '{:+.2f}', 'right', daycolor, )
        report['MktVal'] = (self.shares * quote.last, '{:+.2f}', 'right', )
        report['Gain'] = ((self.shares * quote.last) - self.basis, '{:+.2f}', 'right', gaincolor, )
        report['Gain%'] = (gainpct, '{:+.1f}%', 'right', gaincolor, )
        report['Basis'] = (self.basis, '{:.2f}', 'right', )
        report['Port%'] = (self.port_pct, '{:+.1f}%', 'right', )
        report['Low'] = (quote.low, '{:.2f}', 'right', )
        report['High'] = (quote.high, '{:.2f}', 'right', )
        report['HL%'] = (quote.hl_pct, '{:.1f}%', 'right', )
        report['Days'] = (days, '{:d}', 'right', )
        report['PurDate'] = (self.open_date.strftime(datefmt), '{:s}', 'center', )
        report['P/E'] = (quote.pe, '{:.2f}', 'right', )
        report['Vol'] = (quote.volume, '{:d}', 'right', )
        report['MkCap'] = (quote.cap, '{:.0f}', 'right', )
        report['Low52'] = (quote.low52, '{:.2f}', 'right', )
        report['High52'] = (quote.high52, '{:.2f}', 'right', )
        report['HL52%'] = (quote.hl52_pct, '{:.1f}%', 'right', )
        report['CAGR'] = (Decimal(cagr), '{:.1f}%', 'right', )
        report['DIV'] = (quote.dividend, '{:.2f}', 'right', )
        report['YLD'] = (quote.div_yield, '{:.2f}', 'right', )
        report['ExDiv'] = (ex_div, '{:s}', 'center', )

        report['transactions'] = []
        if len(self.transactions) > 1:
            for transaction in self.transactions:
                subreport = {}
                subreport['Symb'] = ('', '{}', 'center', )
                subreport['Sector'] = (transaction.sector, '{}', 'left', )
                if transaction.shares == int(transaction.shares):
                    subreport['Shrs'] = (transaction.shares, '{:.0f}', 'right', )
                else:
                    subreport['Shrs'] = (transaction.shares, '{:.3f}', 'right', )
                subreport['Purch'] = (transaction.open_price, '{:.2f}', 'right', )
                subreport['Last'] = ('', '{}', 'center', )
                subreport['Chg'] = ('', '{}', 'center', )
                subreport['Day%'] = ('', '{}', 'center', )
                subreport['Day'] = (transaction.shares * quote.net, '{:+.2f}', 'right', )
                subreport['MktVal'] = (transaction.shares * quote.last, '{:+.2f}', 'right', )
                subreport['Gain'] = (transaction.shares * (quote.last - transaction.open_price), '{:+.2f}', 'right', )
                subreport['Gain%'] = ((((transaction.shares * quote.last) / (transaction.shares * transaction.open_price)) - Decimal(1.0)) * Decimal(100.0), '{:+.1f}%', 'right', )
                subreport['Basis'] = (transaction.shares * transaction.open_price, '{:.2f}', 'right', )
                subreport['Port%'] = ('', '{}', 'center', )
                subreport['Low'] = ('', '{}', 'center', )
                subreport['High'] = ('', '{}', 'center', )
                subreport['HL%'] = ('', '{}', 'center', )
                subreport['Days'] = ((datetime.date.today() - transaction.open_date).days, '{:d}', 'right', )
                subreport['PurDate'] = (transaction.open_date.strftime(datefmt), '{:s}', 'center', )
                subreport['P/E'] = ('', '{}', 'center', )
                subreport['Vol'] = ('', '{}', 'center', )
                subreport['MkCap'] = ('', '{}', 'center', )
                subreport['Low52'] = ('', '{}', 'center', )
                subreport['High52'] = ('', '{}', 'center', )
                subreport['HL52%'] = ('', '{}', 'center', )
                subreport['CAGR'] = ('', '{}', 'center', )
                subreport['DIV'] = ('', '{}', 'center', )
                subreport['YLD'] = ('', '{}', 'center', )
                subreport['ExDiv'] = ('', '{}', 'center', )
                report['transactions'].append(subreport)

        #TODO Figure out how to show purchase that happened today

        self.report = report

    def create_list_of_links(self, symbol):
        ll = []
        ll.append(('google', '/pics/google_finance_icon_14x14.png', 'finance.google.com/finance?q=NYSE:{0}'.format(symbol.replace('^', '%5e'))))
        ll.append(('yahoo', '/pics/yahoo_finance_icon_14x14.jpg', 'finance.yahoo.com/q?s={0}'.format(symbol.replace('^', '%5e'))))
        ll.append(('marketwatch', '/pics/marketwatch_finance_icon_14x14.png', 'www.marketwatch.com/investing/stock/{0}'.format(symbol.replace('^', '%5e'))))
        return ll

class CashPosition(Position):
    """Position subclass specifically for cash positions.
    """
    def add_transaction(self, transaction):
        self.shares += transaction.open_price
        self.basis = self.shares
        self.open_price = 1
        if not self.open_date:
            self.open_date = transaction.open_date
        elif transaction.open_date and self.open_date > transaction.open_date:
            self.open_date = transaction.open_date
        self.transactions.append(transaction)

    def gen_report_line(self, quote):
        report = {}
        report['Symb'] = (self.symbol, '{}', 'left', )
        report['Shrs'] = (self.shares, '{:.2f}', 'right', )
        report['Purch'] = (self.open_price, '{}', 'right', )
        report['Last'] = ('1.00', '{}', 'right', )
        report['Chg'] = ('0.00', '{}', 'right', )
        report['MktVal'] = (self.shares, '{:.2f}', 'right', )
        report['Basis'] = (self.basis, '{:.2f}', 'right', )
        report['Port%'] = (self.port_pct, '{:+.1f}%', 'right', )

        report['transactions'] = []
        if args.cashdetail:
            if len(self.transactions) > 1:
                for transaction in self.transactions:
                    subreport = {}
                    subreport['Symb'] = ('', '{}', 'left', )
                    subreport['Shrs'] = (transaction.symbol, '{}', 'center', )
                    subreport['Last'] = (transaction.sector.lower(), '{}', 'center', )
                    subreport['Purch'] = (transaction.open_price, '{:.2f}', 'right', )
                    subreport['MktVal'] = (transaction.open_price, '{:.2f}', 'right', )
                    subreport['Basis'] = (transaction.open_price, '{:.2f}', 'right', )
                    report['transactions'].append(subreport)

        self.report = report


class ClosedPosition(Position):
    """Position subclass specifically for closed positions.
    """
    #TODO This is a work-in-progress.
    def add_transaction(self, transaction):
        self.basis += transaction.shares * transaction.open_price
        self.mktval += transaction.shares * transaction.close_price
        self.transactions.append(transaction)

def calc_bgcolor(pct, minval, maxval):
    #import pdb;pdb.set_trace()
    pct = float(pct)
    if pct <= minval and pct >= -minval:
        red = 0xcc; grn = 0xcc; blu = 0xcc
    elif pct >= maxval:
        red = 0x00; grn = 0xf8; blu = 0x00
    elif pct <= -maxval:
        red = 0xf8; grn = 0x00; blu = 0x00
    else:
        if pct > 0.0:
            normalizer = pct / maxval
            red = 0xe0 - int(0xe0 * normalizer);
            grn = 0xff
            blu = 0xe0 - int(0xe0 * normalizer);
        else:
            normalizer = pct / -maxval
            red = 0xf8
            grn = 0xe0 - int(0xe0 * normalizer);
            blu = 0xe0 - int(0xe0 * normalizer);

    return "background-color: {bg}; color:{fg};".format(bg="#{red:02x}{grn:02x}{blu:02x}".format(red=red, grn=grn, blu=blu), fg="#000")

def abort_html():
    s = ''
    s += 'Content-type: text/html\n\n'
    s += '<html><head></head><body>\n'
    s += '<p>There was a problem fetching quotes. Could be temporary.</p>\n'
    s += '<p>TRY AGAIN LATER!</p>\n'
    s += '</body>\n'
    print(s)

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
        args.cashdetail = cgi_args['cashdetail']
        args.summary_method = cgi_args['method']
        args.sortcol = cgi_args['sort']
        if cgi_args['showsector']:
            args.addcols.append('sector')
        if cgi_args['showname']:
            args.addcols.append('name')

    lheadings = handle_cols()

    headersvals = []
    for i, heading in enumerate(lheadings.keys()):
        if heading == args.sortcol:
            sortlist = '[[{},1]]'.format(i)
        headersvals.append('{key}: {{ sorter: "{stype}" }}'.format(key=i, stype=lheadings[heading]))

    summaryheadersvals = [
        '0: {sorter: "text"}',
        '1: {sorter: "digit"}',
        '2: {sorter: "digit"}',
        '3: {sorter: "digit"}',
        '4: {sorter: "digit"}',
        '5: {sorter: "digit"}',
    ]

    tickerheadersvals = [
        '0: {sorter: "text"}',
        '1: {sorter: "digit"}',
        '2: {sorter: "digit"}',
        '3: {sorter: "digit"}',
        '4: {sorter: "digit"}',
        '5: {sorter: "digit"}',
    ]

    tsconfig = {
        'main': {
            'debug': 'true',
            'cssChildRow': '"tablesorter-childRow"',
            'cssInfoBlock': '"tablesorter-no-sort"',
            'sortInitialOrder': '"desc"',
            'sortList': sortlist,
            'widgets': '["zebra"]',
            'widgetOptions': '{zebra: ["odd", "even"],}',
            'headers': '{' + ','.join(headersvals) + '}',
        },
        'summary': {
            'debug': 'true',
            'cssChildRow': '"tablesorter-childRow"',
            'cssInfoBlock': '"tablesorter-no-sort"',
            'sortInitialOrder': '"desc"',
            'sortList': '[[2,1]]',
            'widgets': '["zebra"]',
            'widgetOptions': '{zebra: ["odd", "even"],}',
            'headers': '{' + ','.join(summaryheadersvals) + '}',
        },
        'ticker': {
            'debug': 'true',
            'cssChildRow': '"tablesorter-childRow"',
            'cssInfoBlock': '"tablesorter-no-sort"',
            'sortInitialOrder': '"desc"',
            'sortList': '[[3,1]]',
            'widgets': '["zebra"]',
            'widgetOptions': '{zebra: ["odd", "even"],}',
            'headers': '{' + ','.join(tickerheadersvals) + '}',
        },
    }

    quotes = FinanceQuoteList()

    tickerdict = OrderedDict()
    #import pdb;pdb.set_trace()
    try:
        test_get = quotes.get_by_symbol('^GSPC')
    except:
        abort_html()
        return

    for symbol in ticker_symbols:
        quote = quotes.get_by_symbol(symbol)
        tickercolor = calc_bgcolor(quote.p_change, 0.1, 5.0)
        tickerdict[symbol] = OrderedDict()
        tickerdict[symbol]['Last'] = (quote.last, '{:.2f}', 'right')
        tickerdict[symbol]['Chg'] = (quote.net, '{:.2f}', 'right', tickercolor)
        tickerdict[symbol]['Chg%'] = (quote.p_change, '{:.1f}%', 'right', tickercolor)
        tickerdict[symbol]['High'] = (quote.high, '{:.2f}', 'right')
        tickerdict[symbol]['Low'] = (quote.low, '{:.2f}', 'right')

    #import pdb;pdb.set_trace()
    tldict = OrderedDict()
    summarydict_footer = OrderedDict()
    summarydict = OrderedDict()
    cum_total = Decimal(0.0)
    cum_day = Decimal(0.0)
    cum_gain = Decimal(0.0)
    for fpn in args.fpns:
        tldict[fpn] = TransactionList(fpn)
        tldict[fpn].query_positions(quotes)
        tldict[fpn].query_cash()
        tldict[fpn].query_closed()
        tldict[fpn].combine_positions()
        tldict[fpn].finalize_positions(quotes)
        tldict[fpn].create_totals()

        summarydict[fpn] = OrderedDict()
        daypct = Decimal(100.0) * tldict[fpn].daygain / tldict[fpn].totalvalue
        daycolor = calc_bgcolor(daypct, 0.1, 5.0)
        gainpct = Decimal(100.0) * tldict[fpn].realized_gain / tldict[fpn].totalvalue
        gaincolor = calc_bgcolor(gainpct, 1.0, 50.0)
        summarydict[fpn]['Total'] = (tldict[fpn].totalvalue, '{:.2f}', 'right', )
        summarydict[fpn]['Day'] = (tldict[fpn].daygain, '{:+.2f}', 'right', daycolor, )
        summarydict[fpn]['Day%'] = (daypct, '{:+.2f}%', 'right', daycolor, )
        summarydict[fpn]['Gain'] = (tldict[fpn].realized_gain, '{:+.2f}', 'right', gaincolor, )
        summarydict[fpn]['Gain%'] = (gainpct, '{:+.2f}%', 'right', gaincolor, )

        if args.summary_method == 'sum':
            cum_total += tldict[fpn].totalvalue
            cum_day += tldict[fpn].daygain
            cum_gain += tldict[fpn].realized_gain
        elif args.summary_method == 'diff':
            if abs(cum_total) < 0.01:
                cum_total += tldict[fpn].totalvalue
                cum_day += tldict[fpn].daygain
                cum_gain += tldict[fpn].realized_gain
            else:
                cum_total -= tldict[fpn].totalvalue
                cum_day -= tldict[fpn].daygain
                cum_gain -= tldict[fpn].realized_gain

    if args.summary_method in ('sum', 'diff'):
        summarydict_footer['Total'] = (cum_total, '{:.2f}', 'right', )
        summarydict_footer['Day'] = (cum_day, '{:.2f}', 'right',)
        summarydict_footer['Day%'] = (" ", '{}', 'left',)
        summarydict_footer['Gain'] = (cum_gain, '{:.2f}', 'right',)
        summarydict_footer['Gain%'] = (" ", '{}', 'left',)

    mwd = whee_doggie_checker(tldict)

    #import pdb;pdb.set_trace()
    lastweekday = datetime.date(datetime.date.today().year-1, 12, 31)
    if (datetime.date.today() - lastweekday).days < 30:
        lastweekday = datetime.date.today() - datetime.timedelta(days=90)
    while lastweekday.weekday() >= 5:
        lastweekday -= datetime.timedelta(days=1)
    porteditstart = lastweekday.strftime('%m/%d/%Y')
    porteditend = datetime.date.today().strftime('%m/%d/%Y')
    context = {
        'legacy_link': legacy_link,
        'all_cols_link': all_cols_link,
        'tickerdict': tickerdict,
        'summarydict': summarydict,
        'summarydict_footer' : summarydict_footer,
        'tldict': tldict,
        'schemes': schemes,
        'schemeset': schemeset,
        'tclassset': tclassset,
        'lheadings': lheadings,
        'args': args,
        'tsconfig': tsconfig,
        'porteditstart': porteditstart,
        'porteditend': porteditend,
        'mwd': mwd,
        }

    #import pdb;pdb.set_trace()
    result = render(r'ptr_layout.html', context)
    if not args.simulate:
        print("Content-type: text/html\n\n")
        #result = htmlmin.minify(result)
    print(result)


if __name__ == '__main__':
    main()

