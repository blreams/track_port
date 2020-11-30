import sys
import os
import importlib
import unittest
from argparse import Namespace
from decimal import Decimal
from bs4 import BeautifulSoup

port_edit = importlib.import_module('scgi-bin.port_edit')

def decimal_equal(num1, num2):
    dec1 = Decimal(num1)
    dec2 = Decimal(num2)
    err = abs(dec1 - dec2)
    if err < 0.00001:
        return True
    else:
        print(f"error diff = {err}")
        return False

class TestFunctions:
    def test_get_portnames(self):
        portnames = port_edit.get_portnames()
        assert 'port:fluffgazer' in portnames

    def test_get_transactions(self):
        port_edit.arguments = Namespace(fileportname='port:fluffgazer')
        transactions = port_edit.get_transactions()
        assert len(transactions) >= 1218
        transaction_ids = [transaction.id for transaction in transactions]
        assert 271 in transaction_ids
        transactions = port_edit.get_transactions(ttype='initial')
        assert len(transactions) == 1
        assert decimal_equal(transactions[0].open_price, 108406.4679)

    def test_get_transaction(self):
        transaction_id = 271
        transaction = port_edit.get_transaction(transaction_id)
        assert transaction.symbol == 'BWLD'

class TestUrlShowTransactions(unittest.TestCase):
    configure_logging_called = False
    def startup(self, argv):
        sys.argv = argv
        port_edit.configure_logging()
        port_edit.parse_arguments()
        port_edit.process_arguments()
        self.soup = BeautifulSoup(port_edit.main(), 'html.parser')

    def test_show_transactions(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=show_transactions',
                '--fileportname=port:fluffgazer',
                ]
        self.startup(argv)
        inputs = self.soup.find("td").find_all("input")
        values = [i.get('value') for i in inputs]
        self.assertEqual(values, ['edit_transaction', '254', 'Edit'])

    def test_show_transactions_closed_put(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=show_transactions',
                '--fileportname=port:fluffgazer',
                '--ttype=closed_put',
                ]
        self.startup(argv)
        inputs = self.soup.find("td").find_all("input")
        values = [i.get('value') for i in inputs]
        self.assertEqual(values, ['edit_transaction', '7779', 'Edit'])

    def test_edit_transaction_271(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=271',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        names = [i.get('name') for i in inputs]
        values = [i.get('value') for i in inputs]
        expected = {
                'transaction_id': '271',
                'ttype': 'closed_stock',
                'fileportname': 'port:fluffgazer',
                'symbol': 'BWLD',
                'sector': 'Services',
                'position': 'long',
                'descriptor': 'stock',
                'shares': '50.0000',
                'open_price': '36.2900',
                'open_date': '2010-05-21',
                'basis': '1814.5000',
                'closed': '1',
                'close_price': '62.6320',
                'close_date': '2011-08-15',
                'close': '3131.6000',
                'days': '451',
                }
        self.assertListEqual(names, list(expected.keys()))
        self.assertListEqual(values, list(expected.values()))

