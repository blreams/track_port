#!/usr/bin/env python

from datetime import datetime
from sqlalchemy import *

sqlite_db_name = f"track_port_{datetime.now().date().strftime('%Y-%m-%d')}.db"
mengine = create_engine('mysql://blreams@localhost/track_port')
sengine = create_engine(f"sqlite:///{sqlite_db_name}")

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
        if str(column.type).startswith('LONGTEXT'):
            column.type = TEXT()
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
    tables = (
            'auth_group',
            'auth_group_permissions',
            'auth_permission',
            'auth_user',
            'auth_user_groups',
            'auth_user_user_permissions',
            'color_scheme',
            'django_admin_log',
            'django_content_type',
            'django_migrations',
            'django_session',
            'finance_quote',
            #'hit_counter',   # This causes an error in sqlalchemy
            'market_holiday',
            'port_history',
            'port_param',
            'put_stats',
            'table_format',
            'ticker_symbols',
            'transaction_list',
            'transaction_report',
            )
    for table in tables:
        print("Copying {} from mysql to sqlite3.".format(table))
        copy_table(mengine, table, sengine)
        

if __name__ == '__main__':
    main()

