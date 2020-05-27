#!/usr/bin/env python3
import sys
import os
import argparse
import six
from decimal import Decimal

def finviz_lookup():
    import finviz
    results = finviz.get_stock(arguments.symbol)
    last = results['Price']
    close = results['Prev Close']
    dayhigh = 0.00
    daylow = 0.00
    yearlow, yearhigh = results['52W Range'].split(' - ')
    volume = results['Volume'].replace(',', '')
    pe = results['P/E']
    if pe == '-':
        pe = 0.0
    net = "{}".format(Decimal(last) - Decimal(close))
    p_change = "{:.6f}".format(((Decimal(last) / Decimal(close)) - 1) * 100)
    bid = 0.00
    ask = 0.00
    line = [close, last, dayhigh, daylow, yearlow, yearhigh, volume, pe, net, p_change, bid, ask,]
    if arguments.verbose or arguments.debug:
        print("close,last,dayhigh,daylow,yearlow,yearhigh,volume,pe,net,p_change,bid,ask")
    return " ".join(["{}".format(item) for item in line])

def parse_arguments(args):
    global arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', default=False, help="Run in debug mode")
    parser.add_argument('--version', action='store_true', default=False, help="Show version")
    parser.add_argument('--verbose', action='store_true', default=False, help="Run in verbose mode")
    parser.add_argument('--service', choices=('finviz',), default='finviz', help="Specify service to use")
    parser.add_argument('--symbol', help="Specify ticker to lookup")
    parser.add_argument('--call', action='store_true', default=False, help="Return list of values")

    arguments = parser.parse_args(args)

def main(args=''):
    global arguments
    if not args:
        args = ['--help']
    if isinstance(args, six.string_types):
        args = args.split()
    parse_arguments(args)
    func = globals()["{}_lookup".format(arguments.service)]
    legacy = False
    try:
        retval = func()
    except:
        if arguments.verbose:
            print("get_a_quote.py failed, trying legacy get_a_quote")
        legacy = True
    if legacy:
        import subprocess
        cmd = ['get_a_quote', '--symbol', arguments.symbol]
        pipe = subprocess.run(cmd, stdout=subprocess.PIPE)
        #print(pipe.stdout.decode().strip())
        retval = pipe.stdout.decode().strip()

    if arguments.call:
        return retval
    else:
        print(retval)

if __name__ == '__main__':
    main(args=sys.argv[1:])


