"""Risk model: a small, explainable logistic regression (maths, not an LLM).
Each feature's contribution can be turned into a plain-English reason."""
import joblib
import numpy as np 
import pandas as pd
import pathlib

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.metrics import roc_auc_score
from .features import build_X, FEATURES

OUT = pathlib.Path(__file__).resolve().parent.parent / "output"

def fit(df):
    m = LogisticRegression(C=0.7, max_iter=3000)
    m.fit(build_X(df), df["rto"])
    return m

def oof_predict(df, seed=7):
    X = build_X(df)
    return cross_val_predict(LogisticRegression(C=0.7, max_iter=3000), X, df["rto"],
                             cv=StratifiedKFold(5, shuffle=True, random_state=seed), method="predict_proba")[:, 1]

def predict(model, df):
    return model.predict_proba(build_X(df))[:, 1]

def contributions(model, X_row):
    """Return {feature: contribution to log-odds vs. an 'average clean' order}."""
    return dict(zip(FEATURES, model.coef_[0] * X_row[FEATURES].values))

def save(model): 
    OUT.mkdir(exist_ok=True)
    joblib.dump(model, OUT / "model.joblib")

def load(): 
    return joblib.load(OUT / "model.joblib")

if __name__ == "__main__":
    from .clean import load_orders
    from .features import add_checks
    df = add_checks(load_orders())
    p = oof_predict(df)
    print("5-fold AUC", round(roc_auc_score(df.rto, p), 3))
    tr = df[df.order_datetime < "2026-09-01"]
    te = df[df.order_datetime >= "2026-09-01"]
    m = fit(tr)
    pt = predict(m, te)
    print("Train Apr-Aug n=%d, test Sep n=%d, AUC %.3f" % (len(tr), len(te), roc_auc_score(te.rto, pt)))
    cal = pd.DataFrame({"p": p, "y": df.rto})
    cal["bin"] = pd.cut(cal.p, [0, .15, .25, .35, .5, .7, 1])
    print(cal.groupby("bin", observed=True).agg(n=("y", "size"), predicted=("p", "mean"), actual=("y", "mean")).round(3))
    for f, c in zip(FEATURES, fit(df).coef_[0]): 
        print(f"{f:16s} {c:+.2f}")
    save(fit(df))