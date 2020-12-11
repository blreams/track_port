#!/usr/bin/env python3

import sys
import os
import time as _time
import logging
import logging.handlers
import argparse
import cgi
#import cgitb; cgitb.enable(display=0, logdir='/home/blreams') # for troubleshooting
from decimal import Decimal, getcontext
from datetime import datetime, date, time, timedelta
import dateparser
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
    logpath = os.path.abspath(os.path.join(thisdir, '..', 'logs', 'port_edit.log'))
    stdin_file = os.path.abspath(os.path.join(thisdir, '..', 'logs', 'post_args.stdin'))
else:
    logpath = os.path.abspath(os.path.join(thisdir, 'port_edit.log'))
    stdin_file = os.path.abspath(os.path.join(thisdir, 'post_args.stdin'))

#############################################################################
# Additional globals
#############################################################################
arguments = argparse.Namespace # defined in parse_arguments
logger = None # defined in configure_logging
Base = None # defined in setup_database
session = None # defined in setup_database
TransactionLists = None # defined in setup_database

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
    if logger is not None:
        return
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
    logging_configured = True

#############################################################################
# Database Setup
#############################################################################
def setup_database():
    global Base
    global session
    global TransactionLists

    logger = logging.getLogger(__name__ + '.' + 'setup_database')
    if arguments.database:
        database_path = os.path.abspath(arguments.database)
        logger.warning(f"using a non-standard database {database_path}")
    else:
        database_path = os.path.join(thisdir, 'track_port.db')

    if host and host in ('skx-linux',):
        #engine = create_engine('mysql://blreams@localhost/track_port')
        engine = create_engine('sqlite:////home/blreams/bin/track_port.db')
    else:
        engine = create_engine(f"sqlite:///{database_path}")

    Base = declarative_base(engine)
    metadata = Base.metadata
    Session = sessionmaker(bind=engine)
    session = Session()

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

        # For each ttype, execute calculated fields
        # Initial cash transaction
        if tlr.position == 'cash' and tlr.descriptor == 'initial':
            self.ttype = 'initial'
            self.amount = tlr.open_price
            if tlr.open_date is not None:
                self.days = (datetime.now().date() - tlr.open_date).days
            else:
                self.days = 0

        # Intermediate cash transaction
        if tlr.position == 'cash' and tlr.descriptor == 'intermediate':
            self.ttype = 'intermediate'
            self.amount = tlr.open_price
            if tlr.open_date is not None:
                self.days = (datetime.now().date() - tlr.open_date).days
            else:
                self.days = 0

        # Open long stock
        if tlr.position == 'long' and tlr.descriptor == 'stock' and not tlr.closed:
            self.ttype = 'open_stock'
            self.basis = tlr.shares * tlr.open_price
            self.close = 0
            self.gain = 0
            self.days = (datetime.now().date() - tlr.open_date).days

        # Open long option
        if tlr.position == 'long' and tlr.descriptor in ('call', 'put',) and not tlr.closed:
            self.ttype = f"open_{tlr.descriptor}"
            self.basis = tlr.shares * tlr.open_price
            self.close = 0
            self.gain = 0
            self.days = (datetime.now().date() - tlr.open_date).days

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


class ShowTransactionsForm(object):
    default_decimal_format = '.4f'

    def __init__(self, transactions):
        self.transactions = transactions
        self.table = []
        self.initialize()

    def initialize(self):
        self.headers = {
                'transaction_id': None,
                'ttype': None,
                'symbol': None,
                'sector': None,
                'position': None,
                'descriptor': None,
                'shares': self.default_decimal_format,
                'open_price': self.default_decimal_format,
                'open_date': None,
                'basis': self.default_decimal_format,
                'closed': None,
                'close_price': self.default_decimal_format,
                'close_date': None,
                'close': self.default_decimal_format,
                'gain': self.default_decimal_format,
                'days': None,
                'expiration': None,
                'strike': self.default_decimal_format,
                }
        for transaction in self.transactions:
            self.add_row(transaction)

    def add_row(self, transaction):
        row = {}
        for header, fmt in self.headers.items():
            if hasattr(transaction, header):
                if fmt is None:
                    row[header] = getattr(transaction, header)
                else:
                    row[header] = f"{getattr(transaction, header):{fmt}}"
                if header == 'transaction_id':
                    form = Form()
                    form.add_input(FormInput(name='action', value='edit_transaction', itype='hidden', first=True))
                    form.add_input(FormInput(name='transaction_id', value=transaction.id, itype='hidden'))
            else:
                row[header] = ''

        self.table.append((row, form))

class EditTransactionForm(object):
    msg_no_change = 'You may not change this field'
    msg_calculated = 'Info-Only: field is calculated based on other fields'
    msg_asterisk = '*'
    msg_illegal_change = 'Illegal change'
    msg_modified = 'Modified'
    default_decimal_format = '.4f'

    def __init__(self, transaction):
        self.transaction = transaction
        self.initialize()

    def initialize(self):
        """
        initial        intermediate   open_stock     open_call      closed_stock   closed_call
                                                     open_put                      closed_put
        -------------- -------------- -------------- -------------- -------------- --------------
        transaction_id transaction_id transaction_id transaction_id transaction_id transaction_id
        ttype          ttype          ttype          ttype          ttype          ttype
        fileportname   fileportname   fileportname   fileportname   fileportname   fileportname
                       symbol         symbol         symbol         symbol         symbol
        *sector        *sector        *sector        *sector        *sector        *sector
        position       position       position       position       position       position
        descriptor     descriptor     descriptor     descriptor     descriptor     descriptor
                                      *shares        *shares        *shares        *shares
        *open_price    *open_price    *open_price    *open_price    *open_price    *open_price
        *open_date     *open_date     *open_date     *open_date     *open_date     *open_date
                                      **basis        **basis        **basis        **basis
                                      *closed        *closed        *closed        *closed
                                      *close_price   *close_price   *close_price   *close_price
                                      *close_date    *close_date    *close_date    *close_date
                                      **close        **close        **close        **close
                                      **gain         **gain         **gain         **gain
        **days         **days         **days         **days         **days         **days
                                                     expiration                    expiration
                                                     strike                        strike
        *  -- editable
        ** -- calculated
        """
        self.form = Form()
        self.form.add_input(FormInput(name='transaction_id', value=self.transaction.id, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input(FormInput(name='ttype', value=self.transaction.ttype, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input(FormInput(name='fileportname', value=self.transaction.fileportname, message=self.msg_asterisk, disabled='disabled'))
        if self.transaction.ttype not in ('initial',):
            self.form.add_input(FormInput(name='symbol', value=self.transaction.symbol, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input(FormInput(name='sector', value=self.transaction.sector, message='Free form text (limit 32 chars)', autofocus='autofocus', first=True))
        self.form.add_input(FormInput(name='position', value=self.transaction.position, message=self.msg_asterisk, disabled='disabled'))
        self.form.add_input(FormInput(name='descriptor', value=self.transaction.descriptor, message=self.msg_asterisk, disabled='disabled'))
        if self.transaction.ttype not in ('initial', 'intermediate'):
            self.form.add_input(FormInput(name='shares', value=self.transaction.shares, message='Number of shares (negative if short)', fmt=self.default_decimal_format))
        self.form.add_input(FormInput(name='open_price', value=self.transaction.open_price, message='Price per share at open', fmt=self.default_decimal_format))
        self.form.add_input(FormInput(name='open_date', value=self.transaction.open_date, message='Date transaction was opened'))
        if self.transaction.ttype not in ('initial', 'intermediate'):
            self.form.add_input(FormInput(name='basis', value=self.transaction.basis, message=self.msg_asterisk*2, disabled='disabled', fmt=self.default_decimal_format))
            self.form.add_input(FormInput(name='closed', value=self.transaction.closed, message='Indicates a "closed" transaction (set to 1)'))
            self.form.add_input(FormInput(name='close_price', value=self.transaction.close_price, message='Price per share at close', fmt=self.default_decimal_format))
            self.form.add_input(FormInput(name='close_date', value=self.transaction.close_date, message='Date transaction was closed'))
            self.form.add_input(FormInput(name='close', value=self.transaction.close, message=self.msg_asterisk*2, disabled='disabled', fmt=self.default_decimal_format))
            self.form.add_input(FormInput(name='gain', value=self.transaction.gain, message=self.msg_asterisk*2, disabled='disabled', fmt=self.default_decimal_format))
        self.form.add_input(FormInput(name='days', value=self.transaction.days, message=self.msg_asterisk*2, disabled='disabled'))
        if self.transaction.ttype.endswith(('_call', '_put')):
            self.form.add_input(FormInput(name='expiration', value=self.transaction.expiration, message='Expiration date (options-only)'))
            self.form.add_input(FormInput(name='strike', value=self.transaction.strike, message='Strike price (options-only)', fmt=self.default_decimal_format))

    def validate_text(self, input_name):
        form_input = getattr(self.form, input_name)
        if hasattr(arguments, input_name) and getattr(arguments, input_name) != getattr(self.transaction, input_name):
            setattr(form_input, 'message', self.msg_modified)
            setattr(form_input, 'changed', True)
            setattr(form_input, 'validated', True)
            setattr(form_input, 'validated_value', getattr(arguments, input_name)[:32])
            setattr(form_input, 'form_value', getattr(arguments, input_name)[:32])

    def validate_decimal(self, input_name):
        logger = logging.getLogger(__name__ + '.' + 'EditTransactionForm.validate_decimal')
        form_input = getattr(self.form, input_name)
        try:
            validated_value = Decimal(float(getattr(arguments, input_name)))
        except:
            logger.warning(f"validate failed on {getattr(arguments, input_name)}")
            setattr(form_input, 'validated', False)
        else:
            setattr(form_input, 'validated_value', validated_value)
            setattr(form_input, 'validated', True)
            if form_input.fmt:
                setattr(form_input, 'form_value', f"{validated_value:{form_input.fmt}}")
            else:
                setattr(form_input, 'form_value', f"{validated_value}")

        if abs(validated_value - getattr(self.transaction, input_name)) > Decimal(0.00001):
            setattr(form_input, 'message', self.msg_modified)
            setattr(form_input, 'changed', True)

    def validate_date(self, input_name):
        logger = logging.getLogger(__name__ + '.' + 'EditTransactionForm.validate_date')
        form_input = getattr(self.form, input_name)
        if getattr(arguments, input_name) == 'None':
            validated_value = None
            setattr(form_input, 'validated_value', validated_value)
            setattr(form_input, 'validated', True)
            setattr(form_input, 'form_value', validated_value)
        else:
            try:
                validated_value = dateparser.parse(getattr(arguments, input_name)).date()
            except:
                logger.warning(f"validate failed on {getattr(arguments, input_name)}")
                setattr(form_input, 'validated', False)
            else:
                setattr(form_input, 'validated_value', validated_value)
                setattr(form_input, 'validated', True)
                setattr(form_input, 'form_value', validated_value)

        if validated_value != getattr(self.transaction, input_name):
            setattr(form_input, 'message', self.msg_modified)
            setattr(form_input, 'changed', True)

    def validate_int_1_0(self, input_name):
        logger = logging.getLogger(__name__ + '.' + 'EditTransactionForm.validate_int_1_0')
        form_input = getattr(self.form, input_name)
        try:
            validated_value = int(getattr(arguments, input_name))
        except:
            logger.warning(f"validate failed on {getattr(arguments, input_name)}")
            setattr(form_input, 'validated', False)
        else:
            setattr(form_input, 'validated_value', validated_value)
            setattr(form_input, 'validated', True)
            setattr(form_input, 'form_value', validated_value)

        if validated_value != getattr(self.transaction, input_name):
            setattr(form_input, 'message', self.msg_modified)
            setattr(form_input, 'changed', True)

    def recalculate_basis(self):
        form_input = getattr(self.form, 'basis')
        self.form.basis.message = 'Recalculated'
        self.form.basis.validated_value = self.form.shares.validated_value * self.form.open_price.validated_value
        self.form.basis.form_value = f"{self.form.basis.validated_value:{form_input.fmt}}"

    def recalculate_close(self):
        form_input = getattr(self.form, 'close')
        if self.form.closed:
            self.form.close.message = 'Recalculated'
            self.form.close.validated_value = self.form.shares.validated_value * self.form.close_price.validated_value
            self.form.close.form_value = f"{self.form.close.validated_value:{form_input.fmt}}"

    def recalculate_gain(self):
        form_input = getattr(self.form, 'gain')
        if self.form.closed.validated_value:
            self.form.gain.message = 'Recalculated'
            self.form.gain.validated_value = self.form.shares.validated_value * (self.form.close_price.validated_value - self.form.open_price.validated_value)
            self.form.gain.form_value = f"{self.form.gain.validated_value:{form_input.fmt}}"
        else:
            self.form.gain.message = 'Recalculated'
            self.form.gain.validated_value = 0.0
            self.form.gain.form_value = f"{self.form.gain.validated_value:{form_input.fmt}}"

    def recalculate_days(self):
        form_input = getattr(self.form, 'days')
        if hasattr(self.form, 'closed') and self.form.closed and self.form.close_date.validated_value is not None:
           self.form.days.message = 'Recalculated'
           self.form.days.validated_value = (self.form.close_date.validated_value - self.form.open_date.validated_value).days
           self.form.days.form_value = f"{self.form.days.validated_value}"
        else:
           self.form.days.message = 'Recalculated'
           self.form.days.validated_value = (datetime.now().date() - self.form.open_date.validated_value).days
           self.form.days.form_value = f"{self.form.days.validated_value}"

    def validate_transaction(self):
        """Once all the individual forms values have been validated, then
        validate the entire transaction as a whole.
        """
        # Here are some ideas for checks to perform:
        #   - There should be no additional inputs beyond what is allowed by
        #     the transaction type.
        #   - The close_date and open_date should make sense.
        #   - If the closed field is 1, then you must have both close_price
        #     and close_date.
        #   - If the closed field is 0, then you must have neither close_price
        #     nor close_date.
        #   - If descriptor indicates this is an option, you must have both
        #     expiration and strike fields.
        pass

    def validate(self):
        logger = logging.getLogger(__name__ + '.' + 'EditTransactionForm.validate')
        validated = True
        changed = False

        for input_name in self.form.inputs:
            logger.debug(f"pre:{getattr(self.form, input_name)}")

        for input_name in self.form.inputs:
            form_input = getattr(self.form, input_name)
            if input_name in ('ttype', 'fileportname'):
                continue

            if input_name in ('transaction_id', 'symbol', 'position', 'descriptor'):
                setattr(form_input, 'changed', False)
                setattr(form_input, 'validated', True)
                setattr(form_input, 'validated_value', getattr(self.transaction, input_name))
                continue

            if not hasattr(arguments, input_name):
                continue

            if input_name in ('sector',):
                self.validate_text(input_name)

            elif input_name in ('shares', 'open_price', 'close_price', 'strike'):
                self.validate_decimal(input_name)

            elif input_name in ('open_date', 'close_date', 'expiration'):
                self.validate_date(input_name)

            elif input_name in ('closed',):
                self.validate_int_1_0(input_name)

            else:
                setattr(form_input, 'changed', False)
                setattr(form_input, 'validated', False)

            validated &= getattr(form_input, 'validated', True)
            changed |= getattr(form_input, 'changed', False)

        if hasattr(self.form, 'basis'):
            self.recalculate_basis()

        if hasattr(self.form, 'close'):
            self.recalculate_close()

        if hasattr(self.form, 'gain'):
            self.recalculate_gain()

        if hasattr(self.form, 'days'):
            self.recalculate_days()

        self.validate_transaction()

        for input_name in self.form.inputs:
            logger.debug(f"post:{getattr(self.form, input_name)}")

        return validated, changed


class Form(object):
    def __init__(self):
        self.inputs = []
        self.tabindex = 1

    def add_input(self, form_input):
        self.inputs.append(form_input.name)
        setattr(self, form_input.name, form_input)
        if not form_input.disabled:
            setattr(form_input, 'tabindex', self.tabindex)
            self.tabindex += 1

class FormInput(object):
    tabindex_count = 0
    def __init__(self, name, value, fmt='', message='', itype='text', disabled='', autofocus='', first=False):
        self.name = name
        self.value = value
        self.fmt = fmt
        self.message = message
        self.itype = itype
        self.disabled = disabled
        self.autofocus = autofocus
        self.first = first

        if not disabled:
            if first:
                self.tabindex_count = 0
            self.tabindex_count += 1
            self.tabindex = self.tabindex_count
        self.validated_value = value
        if fmt:
            self.form_value = f"{value:{fmt}}"
        else:
            self.form_value = f"{value}"

    def __repr__(self):
        base_repr = f"FormInput: name={self.name},value={self.value},form_value={self.form_value}"
        if hasattr(self, 'validated_value'):
            base_repr += f",validated_value={self.validated_value}"
        if hasattr(self, 'changed'):
            base_repr += f",changed={self.changed}"
        if hasattr(self, 'validated'):
            base_repr += f",validated={self.validated}"
        return base_repr

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
    path, filename = os.path.split(os.path.join(thisdir, template))
    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')).get_template(filename).render(context)

#############################################################################
# Argument processing
#############################################################################
def parse_arguments():
    global arguments
    global non_cgi_arguments
    logger = logging.getLogger(__name__ + '.' + 'parse_arguments')
    parser = argparse.ArgumentParser(
            prog="port_edit",
            description="This is how we edit transaction_list items in the database"
            )
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Show verbose messages")
    parser.add_argument('-d', '--debug', action='store_true', default=False, help="Run in debug mode")
    parser.add_argument('-t', '--test', action='store_true', default=False, help="Use this when testing")
    parser.add_argument('--database', default='', help="Specify a different sqlite database (relative if no starting '/')")
    # The following arguments are mimicking what can be passed via cgi
    parser.add_argument('--post_args', default=None, help="File containing post argument string (usually copied from log on server)")
    action_choices = ('show_transactions', "edit_transaction")
    parser.add_argument('--action', choices=action_choices, help="Edit action")
    parser.add_argument('--fileportname', default=None, help="The fileportname being edited")
    ttype_choices = ('initial', 'intermediate', 'open_stock', 'open_call', 'open_put', 'closed_stock', 'closed_call', 'closed_put')
    parser.add_argument('--ttype', choices=ttype_choices, default=None, help="The transaction type")
    parser.add_argument('--transaction_id', type=int, default=-1, help="id from transaction_list table")
    parser.add_argument('--validated_changed', default='', help="only passed when form inputs are changed/validated")

    # Need to filter pytest arguments
    if 'pytest' in sys.argv[0]:
        argv = [argv_item for argv_item in sys.argv if 'test_port_edit.py::' not in argv_item]
        sys.argv = argv

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

    non_cgi_arguments = ('verbose', 'debug', 'test')
    logger.debug(f"non_cgi_arguments={non_cgi_arguments} skipped when processing cgi arguments")

    if os.environ.get('REQUEST_METHOD') is None:
        # In order to mimic cgi arguments using command line arguments
        # we must set a few environment variables.
        if arguments.post_args is None:
            os.environ['REQUEST_METHOD'] = 'GET'
            query_string_parts = [f"{key}={value}" for key, value in arguments.__dict__.items() if value is not None and key not in non_cgi_arguments]
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

    # Removing environment variables, needed for unittest where module is imported
    os.environ.pop('REQUEST_METHOD', None)
    os.environ.pop('QUERY_STRING', None)
    os.environ.pop('CONTENT_LENGTH', None)


#############################################################################
# Initialize
#############################################################################
def initialize():
    configure_logging()
    parse_arguments()
    setup_database()
    process_arguments()

#############################################################################
# Main
#############################################################################
def main():
    logger = logging.getLogger(__name__)

    context = {
            'arguments': arguments,
            'tclasses': tclasses,
            'schemes': schemes,
            'tsconfig': tsconfig,
            'cgi': arguments.cgi,
            'column_order': Transaction.column_order,
            }

    if hasattr(arguments, 'action') and arguments.action == 'show_transactions':
        show_transactions_form = ShowTransactionsForm(get_transactions(ttype=arguments.ttype))
        context['form'] = show_transactions_form
        result = render('port_edit_show_transactions.html', context)
    elif hasattr(arguments, 'action') and arguments.action == 'edit_transaction':
        edit_transaction_form = EditTransactionForm(get_transaction(arguments.transaction_id))
        context['form'] = edit_transaction_form
        if arguments.request_method == 'GET':
            result = render(r'port_edit_edit_transaction.html', context)
        elif arguments.request_method == 'POST':
            context['validated'], context['changed'] = edit_transaction_form.validate()
        result = render(r'port_edit_edit_transaction.html', context)
    elif hasattr(arguments, 'action') and arguments.action == 'commit_transaction':
        result = render(r'port_edit_else.html', context)
    else:
        result = render(r'port_edit_else.html', context)

    if arguments.test:
        return result

    if hasattr(arguments, 'cgi') and arguments.cgi:
        print("Content-type: text/html\n\n")
    print(result)


if __name__ == '__main__':
    initialize()
    main()

