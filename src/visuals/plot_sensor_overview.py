"""Plot supplied observed sensor readings without filling or smoothing."""
from pathlib import Path
import hashlib,json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
root=Path(__file__).resolve().parents[1]
source=root/'notebooks/data/google_drive_full_raw.csv'
out=root/'docs/assets/sensor_overview'
out.mkdir(parents=True,exist_ok=True)
d=pd.read_csv(source,index_col='datetime',parse_dates=True).loc[:'2026-04-23 23:59'].sort_index()
assert d.index.is_unique
specs=[('70coda1inf','A1 influent COD','mg/L','Influent quality','#2266aa'),('70doa1aerobic','A1 aerobic dissolved oxygen','mg-O2/L','Aerobic conditions','#008477'),('70mlssa2aerobic','A2 aerobic MLSS','mg/L','Biomass concentration','#8a63a8'),('70flowa1methdosing','A1 methanol dosing flow','m3/hour','Chemical dosing','#b96a1b'),('70flowa1aerobic','A1 aeration flow','m3/min','Aeration','#b44965'),('70nh4_neffammonia','Effluent NH4-N','mg-N/L','Effluent quality','#3d7491'),('70no3_neffnitrate','Effluent NO3-N','mg-N/L','Constant recorded signal','#59704b')]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':13,'axes.titlesize':17,'axes.labelsize':12,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.facecolor':'white'})
def panel(ax,spec):
 tag,name,unit,group,color=spec
 s=d[tag].dropna()
 ax.scatter(s.index,s,s=1.3,color=color,linewidths=0,alpha=.8,rasterized=True)
 ax.set_title(name,loc='left',fontweight='bold',pad=25)
 missing = int(d[tag].isna().sum())
 ax.text(0,1.025,f'{group} | Nulls: {missing:,} ({missing / len(d):.1%})',transform=ax.transAxes,color='#596777',fontsize=11)
 ax.set_ylabel(unit)
 ax.set_xlim(d.index.min(),d.index.max())
 ax.xaxis.set_major_locator(md.DayLocator(interval=7))
 ax.xaxis.set_major_formatter(md.DateFormatter('%d %b'))
 ax.yaxis.set_major_locator(MaxNLocator(4))
 ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}' if unit=='mg/L' else '{x:,.1f}'))
 ax.tick_params(axis='both',labelsize=11)
 ax.grid(axis='y',color='#e5e9ee',linewidth=.7)
 ax.set_axisbelow(True)
 for side in ['left','bottom']: ax.spines[side].set_color('#c7cfd8')
 if s.nunique()==1: ax.set_ylim(s.iloc[0]-.5,s.iloc[0]+.5)
 else: ax.margins(y=.1)
def save(fig,name):
 for ext in ['png','svg']: fig.savefig(out/(name+'.'+ext),dpi=200)
 plt.close(fig)
fig,axes=plt.subplots(3,2,figsize=(16,9))
fig.subplots_adjust(left=.07,right=.98,top=.83,bottom=.09,hspace=.9,wspace=.23)
fig.text(.05,.95,'Sensor readings over time',fontsize=26,fontweight='bold',color='#172c43')
fig.text(.05,.903,f'24 March-23 April 2026 | All 30 channels: {int(d.isna().sum().sum()):,} nulls ({d.isna().sum().sum()/d.size:.1%})',fontsize=15,color='#536375')
for ax,spec in zip(axes.flat,specs): panel(ax,spec)
fig.text(.05,.025,'Observed CSV values only. No local filling, smoothing or outlier removal. Separate y-axis scales; timestamps as supplied.',fontsize=10,color='#536375')
save(fig,'six_sensor_overview')
for spec in specs:
 fig,ax=plt.subplots(figsize=(16,9))
 fig.subplots_adjust(left=.10,right=.96,top=.78,bottom=.15)
 panel(ax,spec)
 fig.text(.10,.93,'Sensor readings over time',fontsize=25,fontweight='bold',color='#172c43')
 fig.text(.10,.875,'24 March-23 April 2026 | Observed values before local gap filling',fontsize=15,color='#536375')
 ax.set_xlabel('Observation date (2026)',labelpad=13)
 fig.text(.10,.045,'No local filling, smoothing or outlier removal. Missing measurements are not plotted. Units follow the workbook.',fontsize=11,color='#536375')
 save(fig,spec[0])
stats=[]
for tag,name,unit,group,color in specs:
 s=d[tag]
 stats.append(dict(tag=tag,sensor=name,group=group,unit=unit,rows=len(s),observed=int(s.count()),missing=int(s.isna().sum()),unique=int(s.nunique()),minimum=s.min(),maximum=s.max()))
pd.DataFrame(stats).to_csv(out/'sensor_summary.csv',index=False)
meta=dict(source=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),start=str(d.index.min()),end=str(d.index.max()),rows=len(d),channels=len(d.columns),observed_readings=int(d.notna().sum().sum()),method='All nonmissing readings plotted as points without filling, aggregation, clipping or smoothing.',caveat='Observed refers to supplied CSV; upstream cleaning is not independently verified.')
(out/'provenance.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta,indent=2))
