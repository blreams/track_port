#!/usr/bin/env python

from sqlalchemy import *

mengine = create_engine('mysql://blreams@localhost/track_port')
sengine = create_engine('sqlite:///track_port.db')

def copy_table(src_engine, src_table_name, dst_engine):
    # Initial setup
    src_metadata = MetaData()
    src_table = Table(src_table_name, src_metadata, autoload=True, autoload_with=src_engine)
    dst_metadata = MetaData(dst_engine)
    dst_table = Table(src_table_name, dst_metadata)

    # setup dst table with columns
    dst_columns = []
    for column in src_table.columns:
        column.table = None
        if str(column.type).startswith('TINYINT'):
            column.type = INTEGER()
        dst_table.append_column(column)

    # Remove existing dst_table if it exists and create new empty one
    if dst_engine.dialect.has_table(dst_engine.connect(), src_table_name):
        dst_table.drop(dst_engine)
    dst_table.create()

    # Copy the data over
    rows = src_engine.execute(src_table.select()).fetchall()
    with dst_engine.begin() as con:
        for row in rows:
            con.execute(dst_table.insert().values(**row))
    
def main():
    tables = ('finance_quote', 'port_param', 'transaction_list')
    for table in tables:
        print "Copying {} from mysql to sqlite3.".format(table)
        copy_table(mengine, table, sengine)
        

if __name__ == '__main__':
    main()

#scolumns = []
#for column in mfinance_quotes.columns:
#    column.table = None
#    if str(column.type).startswith('TINYINT'):
#        column.type = INTEGER()
#    sfinance_quotes.append_column(column)
#
#if sengine.dialect.has_table(sengine.connect(), 'finance_quote'):
#    sfinance_quotes.drop(sengine)
#sfinance_quotes.create()
#rows = mengine.execute(mfinance_quotes.select()).fetchall()
#with sengine.begin() as con:
#    for row in rows:
#        con.execute(sfinance_quotes.insert().values(**row))
#
#scolumns = []
#for column in mport_params.columns:
#    column.table = None
#    if str(column.type).startswith('TINYINT'):
#        column.type = INTEGER()
#    sport_params.append_column(column)
#
#if sengine.dialect.has_table(sengine.connect(), 'port_param'):
#    sport_params.drop(sengine)
#sport_params.create()
#rows = mengine.execute(mport_params.select()).fetchall()
#with sengine.begin() as con:
#    for row in rows:
#        con.execute(sport_params.insert().values(**row))

