# -*- coding: utf-8 -*-
"""
Created on Sat Jun 24 15:56:36 2023

@author: Patrick
"""
import pandas as pd

START = '2010-01-01'
END = '2017-12-31'

DATA_STORE = 'assets.h5'
DATA = ['engineered_features', 'sp500/fred', 'sp500/stocks']
DATA.append('quandl/wiki/prices')
DATA.append('us_equities/stocks')

with pd.HDFStore(DATA_STORE) as store:
    for d in DATA:
        print('---------------')
        print(d)
        print('---------------')
        metadata = store[d]
        print(metadata)
        print(metadata.columns)
        print('---------------')
        print('')
    
    