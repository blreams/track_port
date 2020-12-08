import sys
import os
import importlib
import unittest
from datetime import datetime
import dateparser
from argparse import Namespace
from decimal import Decimal
from bs4 import BeautifulSoup
from shutil import copyfile

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

def elapsed_days(date1, date2=datetime.now().date()):
    return str((date2 - dateparser.parse(date1).date()).days)

#############################################################################
# Test the helper functions
#############################################################################
class TestFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        port_edit.initialize()

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

#############################################################################
# Test show_transactions URLs
#############################################################################
class TestUrlShowTransactions(unittest.TestCase):
    def startup(self, argv):
        sys.argv = argv
        port_edit.initialize()
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

#############################################################################
# Test edit_transaction GET URLs
#############################################################################
class TestUrlEditTransactionGet(unittest.TestCase):
    def startup(self, argv):
        sys.argv = argv
        port_edit.initialize()
        self.soup = BeautifulSoup(port_edit.main(), 'html.parser')

    def test_edit_transaction_ttype_initial(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=1213',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected = {
                'transaction_id': '1213',
                'ttype': 'initial',
                'fileportname': 'port:fluffgazer',
                'sector': '',
                'position': 'cash',
                'descriptor': 'initial',
                'open_price': '108406.4679',
                'open_date': 'None',
                'days': '0',
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_ttype_intermediate(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=1241',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected_open_date = '2011-01-14'
        expected = {
                'transaction_id': '1241',
                'ttype': 'intermediate',
                'fileportname': 'port:fluffgazer',
                'symbol': 'BOOM',
                'sector': 'dividend',
                'position': 'cash',
                'descriptor': 'intermediate',
                'open_price': '20.0000',
                'open_date': expected_open_date,
                'days': elapsed_days(expected_open_date),
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_ttype_open_stock(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=12460',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected_open_date = '2013-03-07'
        expected = {
                'transaction_id': '12460',
                'ttype': 'open_stock',
                'fileportname': 'port:fluffgazer',
                'symbol': 'MA',
                'sector': 'mfp',
                'position': 'long',
                'descriptor': 'stock',
                'shares': '120.0000',
                'open_price': '52.7000',
                'open_date': expected_open_date,
                'basis': '6324.0000',
                'closed': '0',
                'close_price': '0.0000',
                'close_date': 'None',
                'close': '0.0000',
                'gain': '0.0000',
                'days': elapsed_days(expected_open_date),
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_ttype_closed_stock(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=271',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
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
                'gain': '1317.1000',
                'days': '451',
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_ttype_closed_call(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=8166',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected = {
                'transaction_id': '8166',
                'ttype': 'closed_call',
                'fileportname': 'port:fluffgazer',
                'symbol': 'GES',
                'sector': 'mfo',
                'position': 'long',
                'descriptor': 'call',
                'shares': '-200.0000',
                'open_price': '2.1423',
                'open_date': '2013-09-03',
                'basis': '-428.4600',
                'closed': '1',
                'close_price': '0.0000',
                'close_date': '2014-01-17',
                'close': '-0.0000',
                'gain': '428.4600',
                'days': '136',
                'expiration': '2014-01-18',
                'strike': '30.8000',
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_ttype_closed_put(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=8213',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected = {
                'transaction_id': '8213',
                'ttype': 'closed_put',
                'fileportname': 'port:fluffgazer',
                'symbol': 'SPY',
                'sector': 'mfp',
                'position': 'long',
                'descriptor': 'put',
                'shares': '200.0000',
                'open_price': '2.7177',
                'open_date': '2013-10-15',
                'basis': '543.5400',
                'closed': '1',
                'close_price': '0.0000',
                'close_date': '2013-11-15',
                'close': '0.0000',
                'gain': '-543.5400',
                'days': '31',
                'expiration': '2013-11-16',
                'strike': '170.0000',
                }
        self.assertDictEqual(actual, expected)

#############################################################################
# Test edit_transaction POST URLs
#############################################################################
class TestUrlEditTransactionPost(unittest.TestCase):
    test_db_name = 'test_track_port.db'

    @classmethod
    def setUpClass(cls):
        """These tests require a test version of the database since they will
        be modifying the database.
        """
        # start by copying the database to a new file.
        cls.test_db_name = 'test_track_port.db'
        src_db = os.path.join('..', 'scgi-bin', 'track_port.db')
        dst_db = os.path.join('.', cls.test_db_name)
        copyfile(src_db, dst_db)
        pass

    def startup(self, argv):
        self.maxDiff = None
        sys.argv = argv
        sys.argv.append(f"--database={self.test_db_name}")
        port_edit.initialize()
        self.soup = BeautifulSoup(port_edit.main(), 'html.parser')

    def test_edit_transaction_post_ttype_initial(self):
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                '--transaction_id=1213',
                '--post_args=post_args_edit_transaction_initial.txt',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected_open_date = '2000-12-31'
        expected = {
                'transaction_id': '1213',
                'ttype': 'initial',
                'fileportname': 'port:fluffgazer',
                'sector': 'This is my portfolio',
                'position': 'cash',
                'descriptor': 'initial',
                'open_price': '200000.0000',
                'open_date': expected_open_date,
                'days': elapsed_days(expected_open_date),
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_post_ttype_intermediate(self):
        transaction_id = 11272
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                f'--transaction_id={transaction_id}',
                '--post_args=post_args_edit_transaction_intermediate.txt',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected_open_date = '2017-03-15'
        expected = {
                'transaction_id': f'{transaction_id}',
                'ttype': 'intermediate',
                'fileportname': 'port:fluffgazer',
                'symbol': 'JNJ',
                'sector': 'Editing a VLCM dividend',
                'position': 'cash',
                'descriptor': 'intermediate',
                'open_price': '200.0000',
                'open_date': expected_open_date,
                'days': elapsed_days(expected_open_date),
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_post_ttype_open_stock(self):
        transaction_id = 11130
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                f'--transaction_id={transaction_id}',
                '--post_args=post_args_edit_transaction_open_stock.txt',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected_open_date = '2016-11-04'
        expected = {
                'transaction_id': f'{transaction_id}',
                'ttype': 'open_stock',
                'fileportname': 'port:fluffgazer',
                'symbol': 'AMZN',
                'sector': 'Keep AMZN forever',
                'position': 'long',
                'descriptor': 'stock',
                'shares': '31.0000',
                'open_price': '700.0000',
                'open_date': expected_open_date,
                'basis': '21700.0000',
                'closed': '0',
                'close_price': '0.0000',
                'close_date': 'None',
                'close': '0.0000',
                'gain': '0.0000',
                'days': elapsed_days(expected_open_date),
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_post_ttype_closed_stock(self):
        transaction_id = 271
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                f'--transaction_id={transaction_id}',
                '--post_args=post_args_edit_transaction_closed_stock.txt',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected = {
                'transaction_id': f'{transaction_id}',
                'ttype': 'closed_stock',
                'fileportname': 'port:fluffgazer',
                'symbol': 'BWLD',
                'sector': 'New Services',
                'position': 'long',
                'descriptor': 'stock',
                'shares': '150.0000',
                'open_price': '26.2900',
                'open_date': '2010-04-21',
                'basis': '3943.5000',
                'closed': '1',
                'close_price': '72.6320',
                'close_date': '2011-09-15',
                'close': '10894.8000',
                'gain': '6951.3000',
                'days': '512',
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_post_ttype_closed_call(self):
        transaction_id = 10380
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                f'--transaction_id={transaction_id}',
                '--post_args=post_args_edit_transaction_closed_call.txt',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected = {
                'transaction_id': f'{transaction_id}',
                'ttype': 'closed_call',
                'fileportname': 'port:fluffgazer',
                'symbol': 'AAL',
                'sector': 'Changing closed call',
                'position': 'long',
                'descriptor': 'call',
                'shares': '-200.0000',
                'open_price': '0.6925',
                'open_date': '2015-03-13',
                'basis': '-138.5000',
                'closed': '1',
                'close_price': '4.4000',
                'close_date': '2015-03-20',
                'close': '-880.0000',
                'gain': '-741.5000',
                'days': '7',
                'expiration': '2015-04-10',
                'strike': '53.0000',
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_post_ttype_closed_put(self):
        transaction_id = 10500
        argv = [
                'port_edit.py',
                '--test',
                '--action=edit_transaction',
                f'--transaction_id={transaction_id}',
                '--post_args=post_args_edit_transaction_closed_put.txt',
                ]
        self.startup(argv)
        inputs = self.soup.find("table").find_all("input")
        actual = dict(zip([i.get('name') for i in inputs], [i.get('value') for i in inputs]))
        expected = {
                'transaction_id': f'{transaction_id}',
                'ttype': 'closed_put',
                'fileportname': 'port:fluffgazer',
                'symbol': 'SPY',
                'sector': 'Changing closed put',
                'position': 'long',
                'descriptor': 'put',
                'shares': '400.0000',
                'open_price': '3.0000',
                'open_date': '2014-12-01',
                'basis': '1200.0000',
                'closed': '1',
                'close_price': '13.8569',
                'close_date': '2016-01-12',
                'close': '5542.7600',
                'gain': '4342.7600',
                'days': '407',
                'expiration': '2016-03-19',
                'strike': '200.0000',
                }
        self.assertDictEqual(actual, expected)

    def test_edit_transaction_xxxx_post_including_closed(self):
        pass
