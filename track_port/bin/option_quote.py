import argparse
import re
import stockretriever as sr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', "--debug", help="print debug output", action="store_true")
    parser.add_argument('-s', "--symbollist", metavar='N', nargs='+', help="list of symbols to lookup")
    args = parser.parse_args()
    symbols = [re.match('([^\d]+)', sym).groups()[0] for sym in args.symbollist]
    expirations = [re.match('([^\d]+)(\d\d\d\d)', sym).groups()[1] for sym in args.symbollist]
    symbolexpirations = set((sym,'20'+exp[0:2]+'-'+exp[2:]) for sym, exp in zip(symbols, expirations))
    symbolexpirations = [(sym,'20'+exp[0:2]+'-'+exp[2:]) for sym, exp in zip(symbols, expirations)]

    optioninfo = sr.get_multi_options_info(symbolexp=symbolexpirations)

    optionlist = []
    if isinstance(optioninfo, list):
        for d in optioninfo:
            optionlist.extend(d['option'])
    else:
        optionlist.extend(optioninfo['option'])

    optiondict = {}
    for option in optionlist:
        optiondict[option['symbol']] = option

    if args.debug:
        for optionsymbol in sorted(optiondict.keys()):
            print("%s %s %s %s %s %s %s %s %s %s" % (
                    optiondict[optionsymbol]['symbol'],
                    optiondict[optionsymbol]['type'],
                    optiondict[optionsymbol]['strikePrice'],
                    optiondict[optionsymbol]['lastPrice'],
                    optiondict[optionsymbol]['change'],
                    optiondict[optionsymbol]['changeDir'],
                    optiondict[optionsymbol]['bid'],
                    optiondict[optionsymbol]['ask'],
                    optiondict[optionsymbol]['vol'],
                    optiondict[optionsymbol]['openInt'],
                    ))

    for option in args.symbollist:
        print("%s %s %s %s %s %s %s %s %s %s" % (
                optiondict[option]['symbol'],
                optiondict[option]['type'],
                optiondict[option]['strikePrice'],
                optiondict[option]['lastPrice'],
                optiondict[option]['change'],
                optiondict[option]['changeDir'],
                optiondict[option]['bid'],
                optiondict[option]['ask'],
                optiondict[option]['vol'],
                optiondict[option]['openInt'],
                ))


if __name__ == '__main__':
    main()

