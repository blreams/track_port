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
    @classmethod
    def setUpClass(cls):
        port_edit.arguments = Namespace(
                test=True,
                fileportname='port:fluffgazer', 
                action='show_transactions',
                )
        port_edit.parse_arguments()
        port_edit.process_arguments()
        cls.soup = BeautifulSoup(port_edit.main(), 'html.parser')

    def test_show_transactions(self):
        assert self.soup.title.string == 'port_edit.py'

