import pandas as pd
import numpy as np
import re

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.metrics import roc_auc_score

pd.set_option('display.width',250)
pd.set_option('display.max_rows',100)
df=pd.read_pickle('clean2.pkl')

def acls(a):
    s=a.strip().lower()
    if s in ('.','xyz','home','near station','call me','na','-','x'): 
        return 'junk'
    if s in [c.lower() for c in df.city.dropna().unique()]: 
        return 'cityonly'
    if re.match(r'^(b-\d+|house no\.|\d+/\d+|flat \d+)',s): 
        return 'structured'
    if 'ghar ka naam' in s: 
        return 'ghar_ka_naam'
    if 'ph krke aana' in s: 
        return 'phkrke'
    if 'gali no' in s: 
        return 'gali'
    if 'peeche wala ghar' in s: 
        return 'peeche'
    if 'chowk se left' in s: 
        return 'chowk'
    return 'other'

df['acls']=df.address.map(acls)
print(df.groupby('acls').rto.agg(['count','mean']).round(3))
print(df[df.acls=='other'].address.head(10).tolist())

df['namejunk']=~df.customer_name.str.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$')
print(df.groupby('namejunk').rto.agg(['count','mean']))
print(pd.crosstab(df.namejunk, df.acls=='junk'))

df['phone_bad']=~df.phone.str.match(r'^[6-9]\d{9}$')
print(df.groupby('phone_bad').rto.agg(['count','mean']))
print(df[df.phone_bad].phone.str.len().value_counts())

# tier3 cities
print(df.groupby(['tier','city']).rto.agg(['count','mean']).round(3))

# model
def X(d,cols):
     return pd.get_dummies(d[cols],drop_first=False).astype(float)

d=df.copy()
d['logv']=np.log1p(d.order_value.clip(lower=100))
d['hv']=(d.order_value>1500).astype(int)
d['meta']=(d.utm_source=='meta_ads').astype(int)
d['first']=d['first'].astype(int)

d['rep_rto']=d.customer_prior_rto
d['rto2']=(d.customer_prior_rto>=2).astype(int)
d['repeat_clean']=((d.customer_prior_orders>0)&(d.customer_prior_rto==0)).astype(int)

d['fri']=(d.dow=='Friday').astype(int)

sets={
 'base':['city','acls','namejunk','phone_bad','rep_rto','first','hv','meta'],
 'tier':['tier','acls','namejunk','phone_bad','rep_rto','first','hv','meta'],
 'city+fri':['city','acls','namejunk','phone_bad','rep_rto','first','hv','meta','fri'],
 'city+courier':['city','acls','namejunk','phone_bad','rep_rto','first','hv','meta','courier'],
 'city+prior':['city','acls','namejunk','phone_bad','rep_rto','repeat_clean','first','hv','meta','logv'],
}

y=d.rto.values
for k,c in sets.items():
    Xm=X(d,c)
    aucs=[]
    for seed in range(3):
        p=cross_val_predict(LogisticRegression(C=0.5,max_iter=2000),Xm,y,cv=StratifiedKFold(5,shuffle=True,random_state=seed),method='predict_proba')[:,1]
        aucs.append(roc_auc_score(y,p))
    print(k,round(np.mean(aucs),4))