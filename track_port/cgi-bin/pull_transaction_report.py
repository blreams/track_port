#!/usr/bin/python
import time
import argparse
import cgi
import cgitb; cgitb.enable() # for troubleshooting

import os
import jinja2

from collections import OrderedDict
from decimal import Decimal

from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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
            if heading.lower() in args.addcols or heading.lower() in [h.lower() for h in default_headings]:
                headings[heading] = possible_headings[heading]
    else:
        for heading in default_headings:
            headings[heading] = possible_headings[heading]
    return headings

#time.sleep(20)
engine = create_engine('mysql://blreams@localhost/track_port')
Base = declarative_base(engine)
metadata = MetaData()
finance_quotes = Table('finance_quote', metadata, autoload=True, autoload_with=engine)

def load_session():
    """
    """
    metadata = Base.metadata
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

class FinanceQuotes(Base):
    """
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

def render(tpl_path, context):
    path, filename = os.path.split(tpl_path)
    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')).get_template(filename).render(context)

###############################################################################
# classes related to TransactionReport
###############################################################################
class FinanceQuote(object):
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
    def __init__(self):
        self._data = {}
        fqq = session.query(FinanceQuotes).all()
        for fq in fqq:
            self._data[fq.symbol] = FinanceQuote(fq)

    def get_by_symbol(self, symbol):
        return self._data[symbol]

class Transaction(object):
    def __init__(self, trl_obj):
        self.fieldlist = [
                'symbol', 'fileportname', 'sector', 'position', 'descriptor', 'shares', 'open_price',
                'open_date', 'closed', 'close_price', 'close_date', 'expiration', 'strike',
                              ]
        for field in self.fieldlist:
            self.__setattr__(field, trl_obj.__getattribute__(field))

    def apply_quote(self, fq_obj):
        for field in fq_obj.fieldlist:
            if field not in self.fieldlist:
                self.__setattr__(field, fq_obj.__getattribute__(field))
        self.fieldlist.extend(fq_obj.fieldlist[1:])

class TransactionList(object):
    def __init__(self, fileportname):
        self.fileportname = fileportname
        self.combined_positions = {'longs': {}, 'shorts': {}, 'options': {}, 'cash': {}, 'closed': {}}

    def query_positions(self, quotes):
        self.open_positions = []
        tlq = session.query(TransactionLists).filter_by(fileportname=self.fileportname, closed=False, position='long').all()
        for t in tlq:
            self.open_positions.append(Transaction(t))
            self.open_positions[-1].apply_quote(quotes.get_by_symbol(t.symbol))

    def query_cash(self):
        self.cash_positions = []
        tlq = session.query(TransactionLists).filter_by(fileportname=self.fileportname, position='cash').all()
        for t in tlq:
            self.cash_positions.append(Transaction(t))

    def query_closed(self):
        self.closed_positions = []
        tlq = session.query(TransactionLists).filter_by(fileportname=self.fileportname, closed=True).all()
        for t in tlq:
            self.closed_positions.append(Transaction(t))

    def combine_positions(self):
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
            position.gen_report_line(quotes.get_by_symbol(t.symbol))
            self.combined_positions[positiontype][t.symbol] = position
            self.cash -= t.open_price * t.shares
            self.openvalue += position.report['MktVal'][1]

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

class Position(object):
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

    def add_transaction(self, transaction):
        self.shares += transaction.shares
        self.basis += transaction.shares * transaction.open_price
        self.open_price = self.basis / self.shares
        if not self.open_date:
            self.open_date = transaction.open_date
        elif self.open_date > transaction.open_date:
            self.open_date = transaction.open_date
        self.transactions.append(transaction)

    def gen_report_line(self, quote):
        datefmt = '%Y-%m-%d'
        ex_div = '' if not quote.ex_div else quote.ex_div.strftime(datefmt)
        report = OrderedDict()
        report['Shrs'] = ('{:.0f}', self.shares)
        report['Purch'] = ('{:.2f}', self.open_price)
        report['Symb'] = ('{}', self.symbol)
        report['Last'] = ('{:.2f}', quote.last)
        report['Chg'] = ('{:+.2f}', quote.net)
        report['Day%'] = ('{:+.2f}%', quote.p_change)
        report['Day'] = ('{:+.2f}', self.shares * quote.net)
        report['MktVal'] = ('{:+.2f}', self.shares * quote.last)
        report['Gain'] = ('{:+.2f}', (self.shares * quote.last) - self.basis)
        report['Gain%'] = ('{:+.1f}%', ((self.shares * quote.last) - self.basis) * Decimal(100.0) / abs(self.basis))
        report['Basis'] = ('{:.2f}', self.basis)
        report['Port%'] = ('{:+.1f}%', 0.1 * 100.0)
        #report['Low'] = ('{:.2f}', quote.low)
        #report['High'] = ('{:.2f}', quote.high)
        #report['HL%'] = ('{:.1f}%', Decimal(100.0) * ((quote.last - quote.low) / (quote.high - quote.low)))
        report['Days'] = ('{:d}', 1) #TODO
        report['PurDate'] = ('{:s}', self.open_date.strftime(datefmt))
        report['P/E'] = ('{:.2f}', quote.pe)
        report['Vol'] = ('{:d}', quote.volume)
        report['MkCap'] = ('{:d}', quote.cap)
        #report['Low52'] = ('{:.2f}', quote.low52)
        #report['High52'] = ('{:.2f}', quote.high52)
        #report['HL52%'] = ('{:.1f}%', Decimal(100.0) * ((quote.last - quote.low52) / (quote.high52 - quote.low52)))
        report['CAGR'] = ('{:.1f}%', Decimal(10.1))
        report['DIV'] = ('{:.2f}', quote.dividend)
        report['YLD'] = ('{:.2f}', quote.div_yield)
        report['ExDiv'] = ('{:s}', ex_div)

        #TODO Figure out how to show purchase that happened today

        self.report = report

class CashPosition(Position):
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
    def add_transaction(self, transaction):
        self.basis += transaction.shares * transaction.open_price
        self.mktval += transaction.shares * transaction.close_price
        self.transactions.append(transaction)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--simulate', action='store_true', default=False, help="Used from command line to force arguments")
    parser.add_argument('--fpns', action='append', default=[], help="Add fileportname for querying db")
    parser.add_argument('-a', '--addcols', action='append', default=[], help="Add columns to the default list")
    args = parser.parse_args()
    if not args.fpns:
        args.fpns = ['port:fluffgazer']
    return args

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

    #import pdb;pdb.set_trace()
    context = {
        'tldict': tldict,
        'lheadings': lheadings,
        }

    #import pdb;pdb.set_trace()
    result = render(r'ptr_layout.html', context)
    print "Content-type: text/html"
    print
    print result


if __name__ == '__main__':
    main()

