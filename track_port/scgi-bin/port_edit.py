#!/usr/bin/env python3

import sys
import os
import time as _time
import logging
import logging.handlers
import argparse
import cgi
#import cgitb; cgitb.enable(display=0, logdir='/home/blreams') # for troubleshooting
from decimal import Decimal
from datetime import datetime, date, time, timedelta
from collections import defaultdict

import jinja2
import jinja2.ext
from sqlalchemy import create_engine, Table, MetaData, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#############################################################################
# This stuff needs to be done as globals
#############################################################################
thisdir = os.path.dirname(__file__)
try:
    host = os.uname()[1]
except:
    host = None

if host and host in ('skx-linux',):
    #engine = create_engine('mysql://blreams@localhost/track_port')
    engine = create_engine('sqlite:////home/blreams/bin/track_port.db')
    logpath = os.path.abspath(os.path.join(thisdir, '..', 'logs', 'port_edit.log'))
    stdin_file = os.path.abspath(os.path.join(thisdir, '..', 'logs', 'post_args.stdin'))
else:
    engine = create_engine('sqlite:///track_port.db')
    logpath = os.path.abspath(os.path.join(thisdir, 'port_edit.log'))
    stdin_file = os.path.abspath(os.path.join(thisdir, 'post_args.stdin'))
Base = declarative_base(engine)
metadata = Base.metadata
Session = sessionmaker(bind=engine)
session = Session()

#############################################################################
# Additional globals
#############################################################################
arguments = argparse.Namespace
logger = None

#############################################################################
# tablesorter stuff
#############################################################################
tclasses = ['main']
tclasses = set(tclasses)
schemes = ['garnet', 'green', 'purple', 'blue', 'ice', 'gray']
schemes = set(schemes)
tsconfig = {
    'main': {
        'debug': 'true',
        'cssChildRow': '"tablesorter-childRow"',
        'cssInfoBlock': '"tablesorter-no-sort"',
        'sortInitialOrder': '"desc"',
        'sortList': '[[1,0]]',
        'widgets': '["zebra"]',
        'widgetOptions': '{zebra: ["odd", "even"],}',
        #'headers': '{' + ','.join(headersvals) + '}',
    },
}

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
    fileHandler = logging.handlers.RotatingFileHandler(filename=logpath, maxBytes=100000000, backupCount=10)
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
class TransactionLists(Base):
    __tablename__ = 'transaction_list'
    __table_args__ = {'autoload': True}


#############################################################################
# Other classes
#############################################################################
class Transaction(object):

    earliest_date = datetime.now().date()
    column_order = (
            'id',
            'ttype',
            'symbol',
            'sector',
            'position',
            'descriptor',
            'shares',
            'open_price',
            'open_date',
            'basis',
            'closed',
            'close_price',
            'close_date',
            'close',
            'gain',
            'days',
            'expiration',
            'strike',
            )

    def __init__(self, transaction_list_row):
        self.transaction_list_row = transaction_list_row
        self.initialize()

    def __repr__(self):
        return f"Transaction:ttype={self.ttype},symbol={self.symbol},position={self.position},descriptor={self.descriptor},shares={self.shares},earliest={self.earliest_date}"

    def initialize(self):
        tlr = self.transaction_list_row
        if tlr.open_date is not None and tlr.open_date < self.earliest_date:
            Transaction.earliest_date = tlr.open_date
        self.ttype = 'unknown'
        for key in tlr.__table__.columns.keys():
            setattr(self, key, getattr(tlr, key))
        self.transaction_id = tlr.id

        # Initial cash transaction
        if tlr.position == 'cash' and tlr.descriptor == 'initial':
            self.ttype = 'initial'
            self.amount = tlr.open_price

        # Intermediate cash transaction
        if tlr.position == 'cash' and tlr.descriptor == 'intermediate':
            self.ttype = 'intermediate'
            self.amount = tlr.open_price

        # Open long stock
        if tlr.position == 'long' and tlr.descriptor == 'stock' and tlr.shares > 0.0 and not tlr.closed:
            self.ttype = 'open_long'
            self.basis = tlr.shares * tlr.open_price

        # Open short stock
        if tlr.position == 'long' and tlr.descriptor == 'stock' and tlr.shares < 0.0 and not tlr.closed:
            self.ttype = 'open_short'
            self.basis = tlr.shares * tlr.open_price

        # Open long option
        if tlr.position == 'long' and tlr.descriptor in ('call', 'put',) and tlr.shares > 0.0 and not tlr.closed:
            self.ttype = f"open_{tlr.descriptor}"
            self.basis = tlr.shares * tlr.open_price

        # Open short option
        if tlr.position == 'long' and tlr.descriptor in ('call', 'put',) and tlr.shares < 0.0 and not tlr.closed:
            self.ttype = f"open_{tlr.descriptor}"
            self.basis = tlr.shares * tlr.open_price

        # Close stock
        if tlr.position == 'long' and tlr.descriptor == 'stock' and tlr.closed:
            self.ttype = 'closed_stock'
            self.basis = tlr.shares * tlr.open_price
            self.close = tlr.shares * tlr.close_price
            self.gain = self.close - self.basis
            self.days = (tlr.close_date - tlr.open_date).days

        # Close option
        if tlr.position == 'long' and tlr.descriptor in ('call', 'put',) and tlr.closed:
            self.ttype = f"closed_{tlr.descriptor}"
            self.basis = tlr.shares * tlr.open_price
            self.close = tlr.shares * tlr.close_price
            self.gain = self.close - self.basis
            self.days = (tlr.close_date - tlr.open_date).days


class EditTransactionForm(object):
    msg_no_change = 'You may not change this field'
    msg_calculated = 'Info-Only: field is calculated based on other fields'
    msg_asterisk = '*'

    def __init__(self, transaction):
        self.transaction = transaction
        self.initialize()

    def initialize(self):
        self.form = Form()
        self.form.add_input('transaction_id', FormInput(value=self.transaction.id, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input('ttype', FormInput(value=self.transaction.ttype, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input('fileportname', FormInput(value=self.transaction.fileportname, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input('symbol', FormInput(value=self.transaction.symbol, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input('position', FormInput(value=self.transaction.position, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input('descriptor', FormInput(value=self.transaction.descriptor, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input('shares', FormInput(value=self.transaction.shares, message='Number of shares (negative if short)'))
        self.form.add_input('open_price', FormInput(value=self.transaction.open_price, message='Price per share at open'))
        self.form.add_input('open_date', FormInput(value=self.transaction.open_date, message='Date transaction was opened'))
        self.form.add_input('basis', FormInput(value=self.transaction.basis, message=self.msg_asterisk*2, disabled='disabled'))
        self.form.add_input('closed', FormInput(value=self.transaction.closed, message='Indicates a "closed" transaction (set to 1)'))
        self.form.add_input('close_price', FormInput(value=self.transaction.close_price, message='Price per share at close'))
        self.form.add_input('close_date', FormInput(value=self.transaction.close_date, message='Date transaction was closed'))
        self.form.add_input('close', FormInput(value=self.transaction.close, message=self.msg_asterisk*2, disabled='disabled'))
        self.form.add_input('days', FormInput(value=self.transaction.days, message=self.msg_asterisk*2, disabled='disabled'))
        self.form.add_input('expiration', FormInput(value=self.transaction.expiration, message='Expiration date (options-only)'))
        self.form.add_input('strike', FormInput(value=self.transaction.strike, message='Strike price (options-only)'))

    def validate(self):
        change = False
        if hasattr(arguments, 'transaction_id') and self.transaction.transaction_id != arguments.transaction_id:
            self.form.transaction_id.message = 'Illegal change'
        if hasattr(arguments, 'ttype') and self.transaction.ttype != arguments.ttype:
            self.form.ttype.message = 'Illegal change'
        if hasattr(arguments, 'fileportname') and self.transaction.fileportname != arguments.fileportname:
            self.form.fileportname.message = 'Illegal change'
        if hasattr(arguments, 'symbol') and self.transaction.symbol != arguments.symbol:
            self.form.symbol.message = 'Illegal change'
        if hasattr(arguments, 'position') and self.transaction.position != arguments.position:
            self.form.position.message = 'Illegal change'
        if hasattr(arguments, 'descriptor') and self.transaction.descriptor != arguments.descriptor:
            self.form.descriptor.message = 'Illegal change'
        if hasattr(arguments, 'sector') and self.transaction.sector != arguments.sector:
            self.form.sector.message = 'Modified'
            change = True
        if hasattr(arguments, 'shares') and self.transaction.shares != arguments.shares:
            self.form.shares.message = 'Modified'
            change = True
        if hasattr(arguments, 'open_price') and self.transaction.open_price != arguments.open_price:
            self.form.open_price.message = 'Modified'
            change = True
        if hasattr(arguments, 'open_date') and self.transaction.open_date != arguments.open_date:
            self.form.open_date.message = 'Modified'
            change = True
        if hasattr(arguments, 'closed') and self.transaction.closed != arguments.closed:
            self.form.closed.message = 'Modified'
            change = True
        if hasattr(arguments, 'close_price') and self.transaction.close_price != arguments.close_price:
            self.form.close_price.message = 'Modified'
            change = True
        if hasattr(arguments, 'close_date') and self.transaction.close_date != arguments.close_date:
            self.form.close_date.message = 'Modified'
            change = True
        if hasattr(arguments, 'expiration') and self.transaction.expiration != arguments.expiration:
            self.form.expiration.message = 'Modified'
            change = True
        if hasattr(arguments, 'strike') and self.transaction.strike != arguments.strike:
            self.form.strike.message = 'Modified'
            change = True
        if self.form.shares.message == 'Modified' or self.form.open_price.message == 'Modified':
            self.form.basis.message = 'Recalculated'
            change = True
        if self.form.shares.message == 'Modified' or self.form.close_price.message == 'Modified':
            self.form.close.message = 'Recalculated'
            change = True
        if self.form.open_date.message == 'Modified' or self.form.close_date.message == 'Modified':
            self.form.days.message = 'Recalculated'
            change = True
        self.validated = False

class Form(object):
    def __init__(self):
        self.inputs = []

    def add_input(self, input_name, form_input):
        self.inputs.append(input_name)
        setattr(self, input_name, form_input)

class FormInput(object):
    def __init__(self, value, message, itype='text', disabled=''):
        self.value = value
        self.message = message
        self.itype = itype
        self.disabled = disabled

#############################################################################
# Function definitions
#############################################################################
def get_portnames():
    logger = logging.getLogger(__name__ + '.' + 'get_portnames')
    query = session.query(TransactionLists).all()
    portnames = set([row.fileportname for row in query])
    return portnames

def get_transaction(transaction_id):
    logger = logging.getLogger(__name__ + '.' + 'get_transaction')
    query = session.query(TransactionLists).filter_by(id=transaction_id).one()
    return Transaction(query)

def get_transactions(ttype=None):
    logger = logging.getLogger(__name__ + '.' + 'get_transactions')
    query = session.query(TransactionLists).filter_by(fileportname=arguments.fileportname).all()
    transactions = []
    for row in query:
        transaction = Transaction(row)
        if ttype is None or transaction.ttype == ttype:
            transactions.append(transaction)
    return transactions

def render(template, context):
    """Helper function to render page using jinja2
    """
    path, filename = os.path.split(template)
    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')).get_template(filename).render(context)

#############################################################################
# Argument processing
#############################################################################
def parse_arguments():
    global arguments
    logger = logging.getLogger(__name__ + '.' + 'parse_arguments')
    parser = argparse.ArgumentParser(
            prog="port_edit",
            description="This is how we edit transaction_list items in the database"
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Run in debug mode")
    parser.add_argument('--skip_commit', action='store_true', default=False, help="Skip commit to databases")
    parser.add_argument('--post_args', default=None, help="File containing post argument string (usually copied from log on server)")
    # The following arguments are mimicking what can be passed via cgi
    action_choices = ('show_transactions', "edit_transaction")
    #parser.add_argument('--action', choices=action_choices, default=action_choices[0], help="Edit action")
    parser.add_argument('--action', choices=action_choices, help="Edit action")
    fileportname_choices = get_portnames()
    parser.add_argument('--fileportname', choices=fileportname_choices, help="The fileportname being edited")
    ttype_choices = ('initial', 'intermediate', 'open_long', 'open_short', 'open_call', 'open_put', 'closed_stock', 'closed_call', 'closed_put')
    parser.add_argument('--ttype', choices=ttype_choices, default=None, help="The transaction type")
    parser.add_argument('--transaction_id', type=int, default=-1, help="id from transaction_list table")
    try:
        arguments = parser.parse_args()
        logger.debug("Arguments:")
        for arg, val in arguments.__dict__.items():
            logger.debug(f"{arg}={val}")
    except:
        assert False, "Aborting in parse_arguments."

    if arguments.post_args is not None:
        assert os.path.isfile(arguments.post_args), f"Unable to open file {arguments.post_args}"

def process_arguments():
    global arguments
    logger = logging.getLogger(__name__ + '.' + 'process_arguments')
    stdin_save = sys.stdin

    if os.environ.get('REQUEST_METHOD') is None:
        # In order to mimic cgi arguments using command line arguments
        # we must set a few environment variables.
        if arguments.post_args is None:
            os.environ['REQUEST_METHOD'] = 'GET'
            query_string_parts = [f"{key}={value}" for key, value in arguments.__dict__.items() if value is not None and key not in ('verbose', 'debug', 'skip_commit')]
            query_string = '&'.join(query_string_parts)
            os.environ['QUERY_STRING'] = query_string
        else:
            os.environ['REQUEST_METHOD'] = 'POST'
            os.environ['CONTENT_LENGTH'] = str(os.stat(arguments.post_args).st_size)
            sys.stdin = open(arguments.post_args, 'r')


    logger.debug("ENV:")
    logger.debug(f"REQUEST_METHOD: {os.environ.get('REQUEST_METHOD')}")
    logger.debug(f"QUERY_STRING: {os.environ.get('QUERY_STRING')}")
    logger.debug(f"CONTENT_LENGTH: {os.environ.get('CONTENT_LENGTH')}")
    if os.environ.get('CONTENT_LENGTH'):
        logger.debug("sys.stdin.read():")
        stdin_contents = sys.stdin.read().strip()
        logger.debug(f"{stdin_contents}")
        with open(stdin_file, 'w') as f:
            f.write(stdin_contents)
        sys.stdin = open(stdin_file, 'r')

    arguments.request_method = os.environ.get('REQUEST_METHOD')
    logger.debug("CGI Arguments:")
    cgi_fields = cgi.FieldStorage()
    sys.stdin = stdin_save
    for cgi_key in cgi_fields.keys():
        logger.debug(f"{cgi_key}: <{cgi_fields.getlist(cgi_key)}>")

    cgi_args = {'cgi': None}
    for argkey in cgi_fields.keys():
        if argkey.startswith('-'):
            cgi_args['cgi'] = False
        cgi_args[argkey.lstrip('-')] = cgi_fields.getlist(argkey)[0]
    if cgi_args['cgi'] is None:
        cgi_args['cgi'] = True

    logger.debug("Arguments:")

    logger.debug(f"cgi_fields={cgi_fields}")
    logger.debug(f"cgi_args={cgi_args}")
    if cgi_args['cgi']:
        for key in cgi_args:
            setattr(arguments, key, cgi_args[key])
    else:
        arguments.cgi = False

    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")


#############################################################################
# Main
#############################################################################
def main():
    logger = logging.getLogger(__name__)

    transactions = get_transactions(ttype=arguments.ttype)
    context = {
            'arguments': arguments,
            'tclasses': tclasses,
            'schemes': schemes,
            'tsconfig': tsconfig,
            'cgi': arguments.cgi,
            'column_order': Transaction.column_order,
            'transactions': transactions,
            }

    if hasattr(arguments, 'action') and arguments.action == 'show_transactions':
        result = render(r'port_edit_show_transactions.html', context)
    elif hasattr(arguments, 'action') and arguments.action == 'edit_transaction':
        edit_transaction_form = EditTransactionForm(get_transaction(arguments.transaction_id))
        context['form'] = edit_transaction_form
        if arguments.request_method == 'GET':
            result = render(r'port_edit_edit_transaction.html', context)
        elif arguments.request_method == 'POST':
            context['validated'] = edit_transaction_form.validate()
        result = render(r'port_edit_edit_transaction.html', context)
    else:
        result = render(r'port_edit_else.html', context)

    if hasattr(arguments, 'cgi') and arguments.cgi:
        print("Content-type: text/html\n\n")
    print(result)


if __name__ == '__main__':
    configure_logging()
    parse_arguments()
    process_arguments()
    main()

