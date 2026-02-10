
import plotly.express as px
import pandas as pd
import json

df = pd.DataFrame({'x': [1, 2, 3], 'y': [1, 3, 2], 'name': ['A', 'A', 'A']})
fig = px.line(df, x='x', y='y', color='name')

json_str = fig.to_json()
json_obj = json.loads(json_str)

print("Keys:", json_obj.keys())
print("Data type:", type(json_obj['data']))
print("Data length:", len(json_obj['data']))
