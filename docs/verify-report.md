# Forecast Duel independent verification

Reviewed on 2026-10-21 by GPT/Codex, independently of the Z.ai builder and Claude fixer. This is a local artifact review, not a live-service availability check.

## Result

| Check | Severity | Finding |
| --- | --- | --- |
| 1. Lookahead by price date | ok | Current input paths stop at made_on; all 210 stored naive forecasts match the raw CSV close on made_on. |
| 2. Scoring | bug | Independent totals match the published leaderboard, but cached CSV loading changes one flat naive direction and rebuilds 37.50% instead of 36.88%. |
| 3. Holiday date alignment | bug | Forecast targets include closed weekdays; scoring silently substitutes the next five available bars. |
| 4. JavaScript edge cases | ok | 48 Node render combinations passed with live n=0, null actual, and empty past[]. |
| 5. Hourly fallback | risk | A stale morning-only hourly feed can become a final daily close after the completion cutoff, including at 00:30 UTC. |

No model inference was rerun. Kronos currently receives 150 bars. This review does not establish why the previous 512-bar forecasts drifted.

All commands below ran from `/Users/andreirazvanalexandru/Radar Builds/forecast-duel`. Python probes used the existing environment with `--no-sync`, disabled bytecode, and put uv/test/output files under `/private/tmp`. No network price requests were made.

## Existing tests

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/private/tmp/forecast-duel-verify-uv uv run --no-sync pytest -q -p no:cacheprovider --basetemp=/private/tmp/forecast-duel-verify-pytest
```

Output:

```text
.....                                                                    [100%]
5 passed in 0.36s
```

These five tests pass but do not cover the two reproduced bugs below.

## 1. Lookahead leakage

Severity: **ok** for the current price-date boundary.

In `duel/__main__.py:46`, naive uses `loc[:made_on]`. Both model paths apply the same date cutoff before selecting the last 150 Kronos bars or up to 1024 Timestral closes at lines 93 and 95. Forecast target dates are future dates; they do not provide future prices.

The following probe replaced inference with a capture object. For every stored model forecast, it compared inputs selected from the full cached history against inputs selected after physically removing all rows after made_on. All 420 model inputs were identical, and Kronos input indexes never exceeded made_on.

Evidence:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/private/tmp/forecast-duel-verify-uv uv run --no-sync python -B -c 'import csv,json
from pathlib import Path
from collections import Counter
from duel.__main__ import run_one
from duel.fetch import load_cached
rows=[json.loads(x) for x in Path("data/forecasts.jsonl").read_text().splitlines() if x.strip()]
prices={p.stem:load_cached(p.stem) for p in Path("data/prices").glob("*.csv")}
assert all(df.index.is_monotonic_increasing and df.index.is_unique for df in prices.values())
bad=[]
for r in rows:
    if r["model"]=="naive":
        df=prices[r["ticker"]]
        d=df.loc[:r["made_on"]]
        close=float(d["close"].iloc[-1])
        if d.index[-1].strftime("%Y-%m-%d")!=r["made_on"] or r["values"]!=[close]*5: bad.append((r["ticker"],r["made_on"]))
print("naive rows checked:",sum(r["model"]=="naive" for r in rows),"mismatches:",bad)
class Capture:
    def forecast(self,x,*args):
        self.x=x.copy() if hasattr(x,"copy") else list(x)
        self.args=args
        return [0.0]*5 if args else ([0.0]*5,None,None)
checked=Counter(); lens={}
for r in rows:
    if r["model"]=="naive": continue
    name,ticker,D=r["model"],r["ticker"],r["made_on"]
    kind="crypto" if ticker=="BTC-USD" else "stock"
    a,b=Capture(),Capture()
    run_one(a,name,prices,D,ticker,kind)
    truncated={ticker:prices[ticker].loc[:D]}
    run_one(b,name,truncated,D,ticker,kind)
    if name=="kronos":
        assert a.x.equals(b.x) and all(d.strftime("%Y-%m-%d")<=D for d in a.x.index)
    else: assert a.x==b.x
    assert a.args==b.args
    checked[name]+=1
    lens.setdefault(name,set()).add(len(a.x))
print("full cache versus future-removed inputs identical:",dict(checked))
print("input window lengths:",{k:sorted(v) for k,v in lens.items()})
print("sorted unique price indexes:",len(prices))
print("record fields:",sorted(rows[0]))
'
```

```text
naive rows checked: 210 mismatches: [('ENI.MI', '2026-10-07'), ('ENI.MI', '2026-10-14'), ('ENEL.MI', '2026-10-20'), ('STLAM.MI', '2026-09-24'), ('STLAM.MI', '2026-10-01'), ('STLAM.MI', '2026-10-14'), ('STLAM.MI', '2026-10-16'), ('STLAM.MI', '2026-10-19')]
full cache versus future-removed inputs identical: {'kronos': 210, 'timestral': 210}
input window lengths: {'kronos': [150], 'timestral': [618, 619, 620, 621, 622, 623, 624, 625, 626, 627, 628, 629, 630, 631, 632, 633, 634, 635, 636, 637, 638, 900, 901, 902, 903, 904, 905, 906, 907, 908, 909, 910, 911, 912, 913, 914, 915, 916, 917, 918, 919, 920]}
sorted unique price indexes: 10
record fields: ['dates', 'live', 'made_on', 'model', 'q10', 'q90', 'ticker', 'values']
```

The eight exact-equality mismatches above are pandas CSV parsing differences, at most 3.55e-15 in absolute price. A second probe verified all 1050 naive values within 1e-12. More decisively, the independent standard-library CSV parser in check 2 found **zero** mismatches across all 210 naive rows, without a tolerance. That parsing distinction matters for sign comparisons, as check 2 demonstrates.

Limits: stored forecast records contain no input-date manifest or input hash. These results establish the current code's cutoff and consistency of stored naive records; they cannot prove which historical inputs an earlier binary actually consumed. Yahoo adjusted historical data are fetched today rather than archived as known on each warm-up date, so this is not a point-in-time backtest audit.

Suggested fix: No date-cutoff correction needed; persist input end date, input hash, and code revision with future forecast records to make historical provenance auditable.

## 2. Scoring correctness

Severity: **bug** in cached-reload direction scoring; published MAPE and warm-up counts are correct.

The independent calculation below reads raw CSV prices with Python's csv module, selects the first five later bars, computes mean absolute percentage error, compares endpoint signs with zero counted as up, and compares MAPE with the stored naive forecast using strict less-than. It checks all 480 mature records, then selects one random mature record per model with seed 20261021.

There are no per-record stored MAPE, direction_hit, or beats_naive fields in forecasts.jsonl. The stored per-record values are predictions; scores are computed in report.py and only aggregated in site/data.json. For naive, beats_naive is not defined, so its aggregate is null.

| Random scored record | Independent MAPE % | direction_hit | beats_naive |
| --- | ---: | --- | --- |
| ENEL.MI, 2026-10-12, kronos | 1.1981722428625636 | true | true |
| ENI.MI, 2026-10-06, timestral | 3.833129999289917 | false | false |
| BTC-USD, 2026-10-13, naive | 1.6829841209283964 | false | null |

The same sample records passed the production score functions. Production per-record _metrics returned the same booleans and MAPEs within floating-point precision.

Evidence:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/private/tmp/forecast-duel-verify-uv uv run --no-sync python -B -c 'import csv,json,random,math
from pathlib import Path
from collections import defaultdict
from duel.score import mape,direction_hit
from duel import report
rows=[json.loads(s) for s in Path("data/forecasts.jsonl").read_text().splitlines() if s.strip()]
site=json.loads(Path("site/data.json").read_text())
prices={}
for p in Path("data/prices").glob("*.csv"):
    with p.open() as f:
        rd=csv.DictReader(f); dates=[]; closes=[]
        for r in rd: dates.append(r[rd.fieldnames[0]]); closes.append(float(r["close"]))
    prices[p.stem]=(dates,closes,dict(zip(dates,closes)))
bykey={(r["made_on"],r["ticker"],r["model"]):r for r in rows}
independent={}; totals=defaultdict(list)
for r in rows:
    dates,closes,close_of=prices[r["ticker"]]
    pairs=[(d,c) for d,c in zip(dates,closes) if d>r["made_on"]][:5]
    if len(pairs)!=5:continue
    actual=[c for d,c in pairs]; lc=close_of[r["made_on"]]; pred=r["values"]
    err=sum(abs(p-a)/abs(a) for p,a in zip(pred,actual))/5*100
    hit=(pred[-1]>=lc)==(actual[-1]>=lc)
    n=bykey[(r["made_on"],r["ticker"],"naive")]["values"]
    naive_err=sum(abs(p-a)/abs(a) for p,a in zip(n,actual))/5*100
    beats=None if r["model"]=="naive" else err<naive_err
    assert math.isclose(err,mape(pred,actual),rel_tol=1e-12,abs_tol=1e-12)
    assert hit==direction_hit(pred,actual,lc)
    val={"mape_pct":err,"direction_hit":hit,"beats_naive":beats,"actual_dates":[d for d,c in pairs],"actual":actual,"last_close":lc}
    independent[(r["made_on"],r["ticker"],r["model"])]=val
    totals[("live" if r["live"] else "warmup",r["model"])].append(val)
rng=random.Random(20261021)
for model in site["models"]:
    candidates=sorted(k for k in independent if k[2]==model)
    key=rng.choice(candidates)
    print("random_sample",key,json.dumps(independent[key],sort_keys=True))
for split in ["live","warmup"]:
    for model in site["models"]:
        vs=totals[(split,model)]; n=len(vs); b=[v["beats_naive"] for v in vs if v["beats_naive"] is not None]
        block={"n":n,"mape_pct":round(sum(v["mape_pct"] for v in vs)/n,2) if n else None,"direction_hit_pct":round(sum(v["direction_hit"] for v in vs)/n*100,2) if n else None,"beats_naive_pct":round(sum(b)/len(b)*100,2) if b else None}
        stored=site["leaderboard"][split][model]
        print(split,model,"recomputed",json.dumps(block,sort_keys=True),"stored",json.dumps(stored,sort_keys=True),"equal",block==stored)
raw_mismatches=[(r["ticker"],r["made_on"]) for r in rows if r["model"]=="naive" and r["values"]!=[prices[r["ticker"]][2][r["made_on"]]]*5]
print("raw csv float naive mismatches",raw_mismatches)
print("per-record stored metrics fields",set(rows[0])&{"mape","mape_pct","direction_hit","beats_naive"})
'
```

```text
random_sample ('2026-10-12', 'ENEL.MI', 'kronos') {"actual": [9.006999969482422, 9.02299976348877, 9.095999717712402, 9.187000274658203, 9.01200008392334], "actual_dates": ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19"], "beats_naive": true, "direction_hit": true, "last_close": 8.918000221252441, "mape_pct": 1.1981722428625636}
random_sample ('2026-10-06', 'ENI.MI', 'timestral') {"actual": [24.235000610351562, 24.8799991607666, 25.209999084472656, 25.405000686645508, 25.670000076293945], "actual_dates": ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13"], "beats_naive": false, "direction_hit": false, "last_close": 24.135000228881836, "mape_pct": 3.833129999289917}
random_sample ('2026-10-13', 'BTC-USD', 'naive') {"actual": [81562.4921875, 82141.4609375, 81500.8046875, 81382.1484375, 82017.6015625], "actual_dates": ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"], "beats_naive": null, "direction_hit": false, "last_close": 83095.125, "mape_pct": 1.6829841209283964}
live kronos recomputed {"beats_naive_pct": null, "direction_hit_pct": null, "mape_pct": null, "n": 0} stored {"beats_naive_pct": null, "direction_hit_pct": null, "mape_pct": null, "n": 0} equal True
live timestral recomputed {"beats_naive_pct": null, "direction_hit_pct": null, "mape_pct": null, "n": 0} stored {"beats_naive_pct": null, "direction_hit_pct": null, "mape_pct": null, "n": 0} equal True
live naive recomputed {"beats_naive_pct": null, "direction_hit_pct": null, "mape_pct": null, "n": 0} stored {"beats_naive_pct": null, "direction_hit_pct": null, "mape_pct": null, "n": 0} equal True
warmup kronos recomputed {"beats_naive_pct": 31.25, "direction_hit_pct": 42.5, "mape_pct": 3.44, "n": 160} stored {"beats_naive_pct": 31.25, "direction_hit_pct": 42.5, "mape_pct": 3.44, "n": 160} equal True
warmup timestral recomputed {"beats_naive_pct": 43.12, "direction_hit_pct": 40.62, "mape_pct": 2.48, "n": 160} stored {"beats_naive_pct": 43.12, "direction_hit_pct": 40.62, "mape_pct": 2.48, "n": 160} equal True
warmup naive recomputed {"beats_naive_pct": null, "direction_hit_pct": 36.88, "mape_pct": 2.43, "n": 160} stored {"beats_naive_pct": null, "direction_hit_pct": 36.88, "mape_pct": 2.43, "n": 160} equal True
raw csv float naive mismatches []
per-record stored metrics fields set()
```

Warm-up n is **160 for each model**, as required. All published aggregate fields match the raw CSV recomputation, including MAPE Kronos 3.44%, Timestral 2.48%, naive 2.43%. Live n is zero for each model.

A production rebuild to a temporary output then exposed a reproducibility defect. `fetch.load_cached` uses pandas.read_csv without round-trip float parsing at `duel/fetch.py:62`. For the mature STLAM.MI naive forecast made on 2026-09-24, the stored flat prediction is 3.9635000228881836, but pandas reloads its baseline close as 3.963500022888184. The negative difference is about 4.44e-16. `score.direction_hit` at lines 15-17 treats this as a down prediction instead of a flat/up prediction. The actual endpoint is down, so one incorrect hit is added.

Consequently, rebuilding from the unchanged cached CSVs changes naive warm-up direction_hit_pct from **36.88 to 37.50**. Kronos and Timestral totals, all MAPE totals, and all counts remain unchanged. Only STLAM.MI scores differ among site asset objects.

Evidence:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/private/tmp/forecast-duel-verify-uv uv run --no-sync python -B -c 'import json,tempfile
from pathlib import Path
from duel import report
from duel.fetch import load_cached
from duel.store import load
site=json.loads(Path("site/data.json").read_text()); prices={a["ticker"]:load_cached(a["ticker"]) for a in site["assets"]}
with tempfile.TemporaryDirectory(prefix="forecast-duel-report-",dir="/private/tmp") as td:
    rebuilt=report.build(prices,out_path=Path(td)/"data.json")
for split in ["live","warmup"]:
    for m in site["models"]:
        print(split,m,"stored",site["leaderboard"][split][m],"rebuilt",rebuilt["leaderboard"][split][m])
        if split=="warmup":assert rebuilt["leaderboard"][split][m]["n"]==160
rows=load()
for ticker,df in prices.items():
    for r in rows:
        if r["ticker"]!=ticker or r["model"]!="naive":continue
        D=r["made_on"]; v=r["values"][-1]; lc=float(df.loc[D,"close"]); later=df.loc[D:]["close"].tolist()[1:6]
        if len(later)==5 and v<lc:
            print("naive flat parsed as down",ticker,D,"stored_pred",repr(v),"pandas_close",repr(lc),"actual_end",repr(later[-1]),"flat_hit",later[-1]>=lc,"production_hit",report.direction_hit(r["values"],later,lc))
for a,b in zip(site["assets"],rebuilt["assets"]):
    if a!=b:
        print("asset differing fields",a["ticker"],[k for k in a if a[k]!=b[k]])
print("repo cache file mtimes")
for p in sorted(Path(".pytest_cache").rglob("*")):
    if p.is_file():print(str(p),p.stat().st_mtime)
'
```

```text
live kronos stored {'n': 0, 'mape_pct': None, 'direction_hit_pct': None, 'beats_naive_pct': None} rebuilt {'n': 0, 'mape_pct': None, 'direction_hit_pct': None, 'beats_naive_pct': None}
live timestral stored {'n': 0, 'mape_pct': None, 'direction_hit_pct': None, 'beats_naive_pct': None} rebuilt {'n': 0, 'mape_pct': None, 'direction_hit_pct': None, 'beats_naive_pct': None}
live naive stored {'n': 0, 'mape_pct': None, 'direction_hit_pct': None, 'beats_naive_pct': None} rebuilt {'n': 0, 'mape_pct': None, 'direction_hit_pct': None, 'beats_naive_pct': None}
warmup kronos stored {'n': 160, 'mape_pct': 3.44, 'direction_hit_pct': 42.5, 'beats_naive_pct': 31.25} rebuilt {'n': 160, 'mape_pct': 3.44, 'direction_hit_pct': 42.5, 'beats_naive_pct': 31.25}
warmup timestral stored {'n': 160, 'mape_pct': 2.48, 'direction_hit_pct': 40.62, 'beats_naive_pct': 43.12} rebuilt {'n': 160, 'mape_pct': 2.48, 'direction_hit_pct': 40.62, 'beats_naive_pct': 43.12}
warmup naive stored {'n': 160, 'mape_pct': 2.43, 'direction_hit_pct': 36.88, 'beats_naive_pct': None} rebuilt {'n': 160, 'mape_pct': 2.43, 'direction_hit_pct': 37.5, 'beats_naive_pct': None}
naive flat parsed as down STLAM.MI 2026-09-24 stored_pred 3.9635000228881836 pandas_close 3.963500022888184 actual_end 3.84850001335144 flat_hit False production_hit True
asset differing fields STLAM.MI ['scores']
```

Suggested fix: Load cached prices with round-trip float parsing and compare moves with a defined near-zero tolerance so a serialized flat baseline remains flat.

## 3. Stock holiday date alignment

Severity: **bug**.

`target_dates` at `duel/__main__.py:17-25` checks weekdays only. It generates 25 December, 26 December, and 1 January as stock targets. There is no exchange calendar to handle Good Friday or other closed sessions either.

At scoring time, `report._actual_after` at lines 30-34 ignores stored target dates and takes closes at positions i+1 through i+5. With fewer than five later bars the row is temporarily skipped. Once five later bars exist it is scored, even when those dates differ from the forecast's dates. It is therefore silently misaligned, rather than stuck forever waiting for a holiday close.

The following in-memory fixture explicitly omits closed/gap dates. It is a synthetic price series, not an assertion of the full exchange calendar. The same command also supplies the check 5 hourly fixture. It invokes neither fetch() nor report.build() and performs no CSV writes.

Evidence:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/private/tmp/forecast-duel-verify-uv uv run --no-sync python -B -c 'import datetime as dt
import pandas as pd
from unittest.mock import patch
from duel.__main__ import target_dates
from duel.report import _actual_after,_metrics
from duel import fetch
D="2025-12-24"
dates=[D,"2025-12-29","2025-12-30","2026-01-02","2026-01-05","2026-01-06"]
closes=[100.,101.,102.,103.,104.,105.]
row={"made_on":D,"ticker":"ENI.MI","model":"naive","values":[100.]*5,"live":False,"dates":target_dates(D,"stock")}
print("stock targets",row["dates"])
print("Jan 1 targets",target_dates("2025-12-31","stock"))
print("synthetic actual session dates",dates[1:])
print("four later closes",_actual_after(dates[:5],closes[:5],D))
print("five later closes",_actual_after(dates,closes,D))
print("scores despite absent target holiday",_metrics([row],"ENI.MI",dates,closes,dict(zip(dates,closes)),False)["naive"])
base=pd.DataFrame({c:[100.]*12 for c in ["open","high","low","close","volume"]},index=pd.bdate_range(end="2026-10-20",periods=12))
hourly=pd.DataFrame({"Open":[110.],"High":[112.],"Low":[109.],"Close":[111.],"Volume":[10.]},index=pd.DatetimeIndex(["2026-10-21T08:00:00Z"]))
real_complete=fetch.is_complete
for now in [dt.datetime(2026,10,21,15,44,tzinfo=dt.timezone.utc),dt.datetime(2026,10,21,15,45,tzinfo=dt.timezone.utc),dt.datetime(2026,10,22,0,30,tzinfo=dt.timezone.utc)]:
    with patch.object(fetch.yf,"download",return_value=hourly.copy()),patch.object(fetch,"is_complete",side_effect=lambda d,k:real_complete(d,k,now)):
        out=fetch._fill_from_hourly("ENI.MI",base.copy())
        added=out.loc[out.index>base.index[-1]]
        print("hourly fallback",now.isoformat(),"accepted",added.index.strftime("%Y-%m-%d").tolist(),"close",added["close"].tolist())
print("synthetic feed supplies only a morning hour; network and CSV writes were not called")
'
```

```text
stock targets ['2025-12-25', '2025-12-26', '2025-12-29', '2025-12-30', '2025-12-31']
Jan 1 targets ['2026-01-01', '2026-01-02', '2026-01-05', '2026-01-06', '2026-01-07']
synthetic actual session dates ['2025-12-29', '2025-12-30', '2026-01-02', '2026-01-05', '2026-01-06']
four later closes None
five later closes [101.0, 102.0, 103.0, 104.0, 105.0]
scores despite absent target holiday ([2.8943126581816783], [True], [])
hourly fallback 2026-10-21T15:44:00+00:00 accepted [] close []
hourly fallback 2026-10-21T15:45:00+00:00 accepted ['2026-10-21'] close [111.0]
hourly fallback 2026-10-22T00:30:00+00:00 accepted ['2026-10-21'] close [111.0]
synthetic feed supplies only a morning hour; network and CSV writes were not called
```

The missing holiday targets are paired with actuals on 29 December, 30 December, 2 January, 5 January, and 6 January in this fixture. A nominal 25 December prediction is scored against the first later available close. Kronos also receives the incorrect future timestamps as model inputs, so merely relabeling the chart would not fully repair the issue.

Suggested fix: Use a Borsa Italiana session calendar for stock forecast targets and a shared, explicit date mapping for scoring; version or flag legacy forecasts whose target schedules differ.

## 4. JavaScript on zero or missing results

Severity: **ok** for the requested cases.

This was exercised with Node v26.9.0, not inferred solely from reading. The probe loads the actual app.js and data.json, exposes the existing renderAll closure in memory, and stubs DOM methods. For the original data and each mutated case, it runs both live/warmup modes, all three layouts, and past paths both hidden/shown. Ledger details are opened for the first asset and chart binding is exercised.

Evidence:

```sh
node -e 'const fs=require("fs"),vm=require("vm"),assert=require("assert");
const data=JSON.parse(fs.readFileSync("site/data.json","utf8"));
class E {
  constructor(dataset={}) {this.dataset=dataset;this.innerHTML="";this.textContent="";this.style={};}
  addEventListener(){} setAttribute(){} appendChild(){}
  querySelector(){return new E();}
  querySelectorAll(s){
    if(s===".cw" || s==="td.spark[data-i]") return data.assets.map((a,i)=>new E({i:String(i)}));
    if(s===".detail .cw") return [new E({i:"0"})];
    if(s==="tr.row") return data.assets.map(a=>new E({t:a.ticker}));
    return [];
  }
  getBoundingClientRect(){return {left:0,width:100};}
}
const ids=new Map();
const document={querySelector(s){if(!ids.has(s))ids.set(s,new E());return ids.get(s);},
  querySelectorAll(){return [];},createElement(){return new E();}};
const src=fs.readFileSync("site/app.js","utf8");
const exposed=src.replace(/\n\}\)\(\);\s*$/, '\''\nglobalThis.probe={renderAll,S,setD:x=>{D=x}};\n})();'\'');
const ctx={document,window:{addEventListener(){}},localStorage:{getItem(){return null;},setItem(){}},
  location:{search:"",href:"http://localhost/"},history:{replaceState(){}},
  fetch(){return new Promise(()=>{});},setTimeout,clearTimeout,URL,URLSearchParams,Intl,Date,console};
vm.runInNewContext(exposed,ctx,{filename:"site/app.js"});
assert(ctx.probe);
let count=0;
for(const scenario of ["original","live-n0","null-actual","empty-past"]) {
  const d=structuredClone(data);
  if(scenario==="live-n0") {
    for(const b of [d.leaderboard.live,...d.assets.map(a=>a.scores.live)])
      for(const m of d.models) b[m]={n:0,mape_pct:null,direction_hit_pct:null,beats_naive_pct:null};
  }
  if(scenario==="null-actual") d.assets.forEach(a=>a.past.forEach(p=>p.actual=null));
  if(scenario==="empty-past") d.assets.forEach(a=>a.past=[]);
  ctx.probe.setD(d);
  let n=0;
  for(const mode of ["live","warmup"]) for(const variant of ["board","stage","ledger"]) for(const showPast of [false,true]) {
    Object.assign(ctx.probe.S,{mode,variant,showPast,open:d.assets[0].ticker,pick:d.assets[0].ticker});
    ctx.probe.renderAll(); n++; count++;
    if(mode==="live" && scenario==="live-n0") assert.equal(ids.get("#headline").textContent,"");
  }
  console.log(scenario+": "+n+" renderAll combinations passed");
}
console.log("node "+process.version+"; total "+count+"; actual references "+(/\bactual\b/.test(src)));
'
```

```text
original: 12 renderAll combinations passed
live-n0: 12 renderAll combinations passed
null-actual: 12 renderAll combinations passed
empty-past: 12 renderAll combinations passed
node v26.9.0; total 48; actual references false
```

The zero-n guards are in `site/app.js:67-109`; `past || []` and its loops are at lines 129-170. The script never reads the actual field, so a null actual cannot cause an exception through that field. Empty past[] is safe in the board, stage, and expanded ledger paths.

Limits: this is a JavaScript execution check with DOM stubs, not a browser layout or visual audit. It retains the populated history and latest objects from real data.json; it does not claim support for every possible missing-field schema.

Suggested fix: None required for these three cases.

## 5. Hourly fallback and partial closes

Severity: **risk**, reproduced with a synthetic stale feed, not observed as a proven error in existing cached prices.

The check 3 command supplies only one morning hourly candle for a date missing from the daily frame. `_fill_from_hourly` at `duel/fetch.py:24-37` removes intraday timestamps, aggregates close as last, and asks only whether the calendar date is complete. It never checks that the last returned hourly candle covers the end of the session. `fetch()` subsequently writes the resulting daily row to CSV at line 57.

Observed in the in-memory test above:

```text
hourly fallback 2026-10-21T15:44:00+00:00 accepted [] close []
hourly fallback 2026-10-21T15:45:00+00:00 accepted ['2026-10-21'] close [111.0]
hourly fallback 2026-10-22T00:30:00+00:00 accepted ['2026-10-21'] close [111.0]
```

On this summer-time date, 15:45 UTC is 17:45 Rome. Manual runs before 17:45 Rome exclude the current session. From 17:45 Rome onward, or at any later time for an earlier date, a missing daily row can accept a stale/partial hourly aggregate if Yahoo supplies one.

The nightly workflow is explicitly `30 0 * * *` in `.github/workflows/nightly.yml:7`. That time is after the prior Milan session. A healthy, fully refreshed hourly feed should have the closing data then; the test proves that a stale morning-only response is still accepted at that exact cron time. It does not prove a fixed 17:45-to-18:00 market-completion window or an actual vendor feed incident.

A bad fallback row can later enter the five actual closes used for scoring, or become made_on's close used for new forecasts. Scores are recomputed, not persisted in JSONL. Later fresh daily/hourly data can correct price-based scores, but idempotent append keys prevent automatic replacement of forecasts already made from an incorrect close. The hourly fallback is stock-only; crypto uses its UTC day completion rule.

Suggested fix: Validate the final hourly timestamp against the exchange session's closing interval and defer stale fallback dates; retain price-source/provisional provenance for later correction.

## Scope and repository verification

No pipeline run, model-weight download, code edit, data edit, commit, or push was performed. Only this report was intentionally written inside the repository. Read-only report builds wrote temporary data.json files under /private/tmp.

Scope exception: a delegated test command omitted `-p no:cacheprovider` and refreshed the ignored `.pytest_cache/v/cache/nodeids` file at 09:47:26 local time. This was contrary to the no-other-files instruction. Its original contents were not captured, so byte-for-byte equality of that ignored cache cannot be certified. No further cache-writing pytest commands ran. Git status was clean before the report, and tracked code, data, and site contents remained unchanged.

Final verification command:

```sh
git status --short --untracked-files=all
git diff --exit-code
git diff --cached --exit-code
```

Expected and checked final status:

```text
?? docs/verify-report.md
```

Both tracked diff commands exit zero. This satisfies the Git-status criterion; the ignored-cache exception above limits a stricter claim that no other filesystem entry was touched.

