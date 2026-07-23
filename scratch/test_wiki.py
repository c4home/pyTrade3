import requests
import pandas as pd

import io

headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
tables = pd.read_html(io.StringIO(response.text))
df = tables[0]
print(len(df['Symbol'].tolist()))
