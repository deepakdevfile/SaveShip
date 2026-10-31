import pandas as pd
import numpy as np
import re

pd.set_option('display.width',250)
pd.set_option('display.max_columns',50)
pd.set_option('display.max_rows',200)

df=pd.read_pickle('clean.pkl')

def t(s,name=None):
    x=df.groupby(s,observed=True).rto.agg(['count','mean']).round(3)
    print('\n',name or '')
    print(x)

# names
print(df.customer_name.str.split().str.len().value_counts())
odd=df[~df.customer_name.str.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$')]
print(len(odd))
print(odd.customer_name.value_counts().head(40))
print(odd.rto.mean())

# address junk
junk=df.address.str.lower().str.strip().isin(['.','xyz','home','near station','call me','na','test','asdf','abc','-','x','...'])
t(junk,'junk addr')
print(df[~junk & (df.addr_len<20)].address.value_counts().head(30))

# address types
def atype(a):
    if re.match(r'^(B-\d+|House No\.|\d+/\d+)',a): 
        return 'structured'
    if re.search(r'ke paas|ke saamne|ke peeche|krke|se left',a,re.I): 
        return 'landmark_hinglish'
    return 'other'

df['atype']=df.address.map(atype); t(df.atype,'atype')
print(df[df.atype=='other'].address.value_counts().head(25))
print(df[df.atype=='landmark_hinglish'].address.sample(8,random_state=1).tolist())

# phone patterns
print(df[df.phone.str.len()!=10].phone.head(10).tolist())
df['phone_ok']=df.phone.str.match(r'^[6-9]\d{9}$')
t(df.phone_ok,'phone_ok')
df['phone_rep']=df.phone.map(df.phone.value_counts())>1
t(df.phone_rep,'phone repeated')
print(df.phone.value_counts().head(5))

# phone sequential/repeated digits
df['phone_weird']=df.phone.str.extract(r'(\d)\1{5,}|1234567|0123456789')
t(df.phone_weird)

# order value 0
# city/state missing, pincode vs city
print(df[df.city.isna()][['city','state','pincode','rto']])
df['pin_prefix']=df.pincode.astype('Int64').astype(str).str[:3]

# pincode matches state? first digit
print(df.groupby('state').pin_prefix.agg(lambda s:s.str[0].value_counts().to_dict()))

# tiering
metros=['Delhi','Mumbai','Bengaluru','Hyderabad','Pune','Chennai','Kolkata']
df['tier']=np.where(df.city.isin(metros),'metro',np.where(df.city.isin(['Jaipur','Lucknow','Indore','Patna','Guwahati']),'tier2','tier3'))
t(df.tier,'tier')

# first-time x meta x tier
df['first']=df.customer_prior_orders==0
t([df['first'],df.utm_source=='meta_ads'],'first x meta')
t([df['first'],df.tier],'first x tier')
t([df.atype,df.tier],'atype x tier')

# combined good address + metro
t([df.atype!='other', df.addr_len>15],'x')

# value x tier
df['hv']=df.order_value>1500; t([df.hv,df.tier],'hv x tier')
t([df.hv,df['first']],'hv x first')

# prior RTO
t([df.customer_prior_rto,df['first']],'prior rto x first')

# prior orders & rto together
t([df.customer_prior_orders>0, df.customer_prior_rto>0],'repeat x rtoflag')

# order value zero
print(df[df.order_value==0][['order_id','rto']])

# items
print(df['items'].str.split('|').explode().value_counts())
df['item1']=df['items'].str.split('|').str[0]

# per item rto
ex=df.assign(item=df['items'].str.split('|')).explode('item')
print(ex.groupby('item').rto.agg(['count','mean']).round(3))

# value/num_items consistency
print((df.order_value/df.num_items).describe())

# hour
df['night']=df.hour.between(0,5); t(df.night,'night')
t(df.dow,'dow')
df.to_pickle('clean2.pkl')