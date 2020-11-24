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

import jinja2
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
else:
    engine = create_engine('sqlite:///track_port.db')
    logpath = os.path.abspath(os.path.join(thisdir, 'port_edit.log'))
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
    def __init__(self, transaction_list_row):
        self.transaction_list_row = transaction_list_row

    def commit(self):
        logger = logging.getLogger(__name__ + '.' + 'Transaction.commit')
        if not arguments.skip_commit:
            logger.info("Committing")
            session.commit()


#############################################################################
# Function definitions
#############################################################################
def get_portnames():
    logger = logging.getLogger(__name__ + '.' + 'get_portnames')
    query = session.query(TransactionLists).all()
    portnames = set([row.fileportname for row in query])
    return portnames

def handle_cgi_args(cgi_fields):
    logger = logging.getLogger(__name__ + '.' + 'handle_cgi_args')
    known_keys = ('action', 'fileportname')

    cgi_args = {'cgi': True}
    for argkey in cgi_fields.keys():
        if argkey.startswith('-'):
            cgi_args['cgi'] = False
        if argkey.lstrip('-') in known_keys:
            cgi_args[argkey.lstrip('-')] = cgi_fields[argkey].value

    return cgi_args

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
    parser.add_argument('--simulate', action='store_true', default=False, help="Used from command line to force arguments")
    parser.add_argument('--skip_commit', action='store_true', default=False, help="Skip commit to databases")
    # The following arguments are mimicking what can be passed via cgi
    action_choices = ('show_transactions',)
    fileportname_choices = get_portnames()
    parser.add_argument('--action', choices=action_choices, default=action_choices[0], help="Edit action")
    parser.add_argument('--fileportname', choices=fileportname_choices, default=None, help="The fileportname being edited")
    try:
        arguments = parser.parse_args()
    except:
        pass
    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")

def process_arguments():
    global arguments
    logger = logging.getLogger(__name__ + '.' + 'process_arguments')
    logger.debug("Arguments:")
    for arg, val in arguments.__dict__.items():
        logger.debug(f"{arg}={val}")


#############################################################################
# Main
#############################################################################
def main():
    logger = logging.getLogger(__name__)

    cgi_fields = cgi.FieldStorage()
    logger.debug(f"cgi_fields={cgi_fields}")
    cgi_args = handle_cgi_args(cgi_fields)
    logger.debug(f"cgi_args={cgi_args}")
    if cgi_args['cgi']:
        arguments.cgi = True
        arguments.fileportname = cgi_args['fileportname']
        arguments.action = cgi_args['action']

    context = {
            }

    result = render(r'port_edit_layout.html', context)
    if hasattr(arguments, 'cgi') and arguments.cgi:
        print("Content-type: text/html\n\n")
    print(result)


if __name__ == '__main__':
    configure_logging()
    parse_arguments()
    process_arguments()
    main()

