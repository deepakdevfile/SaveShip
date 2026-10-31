import pandas as pd, numpy as np, re

pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 50)
pd.set_option('display.max_rows', 200)

df = pd.read_csv('orders_sample.csv', dtype={'phone':str})
df = df.drop_duplicates()

df['status'] = df.final_status.str.strip().str.upper()
df = df[df.status.isin(['DELIVERED', 'RTO'])].copy()
df['rto'] = (df.status=='RTO').astype(int)

df['dt'] = pd.to_datetime(df.order_datetime)
df['hour'] = df.dt.dt.hour
df['dow'] = df.dt.dt.day_name()
df['month'] = df.dt.dt.to_period('M')

print(len(df), df.rto.mean())

def g(c,bins=None):
    if bins is None:
        s = df[c]
    else:
        s = pd.cut(df[c], bins)
    t = df.groupby(s, observed=True).rto.agg(['count', 'mean']).round(3)
    print('\n', c)
    print(t)

for c in ['utm_source','courier','state','city','customer_prior_orders','customer_prior_rto','num_items','month','dow']: g(c)

g('order_value',[-1,300,500,700,1000,1500,2000,3000])
g('hour',[-1,5,9,12,17,21,24])

df['pin3']=df.pincode.astype('Int64').astype(str).str[:3]
df['first']=(df.customer_prior_orders==0)
g('first')

df['phone_len']=df.phone.str.len()
g('phone_len')

df['addr_len']=df.address.str.len()
g('addr_len',[0,3,8,15,30,50,100])

df['has_pin']=df.pincode.notna()
g('has_pin')

df['addr_hinglish']=df.address.str.contains('ke paas|ke saamne|ke peeche|krke|se left',case=False)
g('addr_hinglish')

df['addr_struct']=df.address.str.match(r'^(B-\d+|House No\.|\d+/\d+)')
g('addr_struct')

pc=df.groupby('pincode').rto.agg(['count','mean']).sort_values('count',ascending=False)
print(pc.head(10))
print((pc['count']>=5).sum(), pc.shape)

df.to_pickle('clean.pkl')