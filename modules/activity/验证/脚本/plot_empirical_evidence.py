"""All-cow empirical evidence figure from the fixed module's raw-packet replay."""
from pathlib import Path
from decimal import Decimal
import csv
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

HERE=Path(__file__).resolve().parents[2]
OUT=HERE/'验证/结果'
FIGURES=HERE/'说明/图表'
FIGURES.mkdir(parents=True,exist_ok=True)
source=OUT/'逐包特征与决策.csv'
data=pd.read_csv(source,dtype={'cow_id':str})
per=pd.read_csv(OUT/'逐牛_活动证据.csv',dtype={'cow_id':str}).set_index('cow_id')
summary=json.loads((OUT/'validation_summary.json').read_text(encoding='utf-8'))
labels={}
with (HERE.parent/'温度数据集/CSV数据/产犊标注.csv').open(encoding='utf-8-sig',newline='') as handle:
    for row in csv.DictReader(handle):
        if row['cohort']=='normal_calving':
            labels[(row['cow_id'],row['label'])]=int(Decimal(row['start_ms']))
cows=sorted(data.cow_id.unique())
assert len(cows)==10 and len(data)==500 and per.early_hit.sum()==8
for name,digest in summary['code_sha256'].items():
    assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest

plt.rcParams.update({'font.family':'sans-serif',
    'font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
    'font.size':12,'axes.unicode_minus':False,'axes.spines.top':False,
    'axes.spines.right':False,'axes.linewidth':.9,'svg.fonttype':'none','pdf.fonttype':42})
BLUE='#0F4D92'; GOLD='#C28C2C'; RED='#B64342'; GREY='#92999F'; DARK='#243444'
fig=plt.figure(figsize=(15.7,10.5),facecolor='white')
grid=fig.add_gridspec(10,2,left=.088,right=.96,top=.805,bottom=.18,
                      width_ratios=[2.65,1.05],wspace=.20,hspace=.22)
axes=[]; drawn=[]
for i,cow in enumerate(cows):
    ax=fig.add_subplot(grid[i,0]);axes.append(ax)
    g=data[data.cow_id==cow].sort_values('evaluated_at_ms').copy()
    t0=labels[(cow,'犊牛完全娩出')];hoof=labels[(cow,'露蹄')]
    g['hours']=(g.evaluated_at_ms-t0)/3600000
    g=g[(g.hours>=-12)&(g.hours<0)]
    hoof_h=(hoof-t0)/3600000
    ax.axvspan(-6,hoof_h,color='#EAF2F8',zorder=0)
    ax.axhline(1,color='#CBD2D9',lw=.7,zorder=0)
    ax.axhline(1.5,color=GOLD,lw=1.0,ls=(0,(4,3)),zorder=1)
    ax.axvline(hoof_h,color=RED,lw=1.15,ls=(0,(2,2)),zorder=3)
    x=g.hours.to_numpy();y=g.activity_ratio.to_numpy()
    # Break missing values and long packet gaps. No synthetic observations are added.
    xx=[];yy=[]
    for j in range(len(x)):
        if j and x[j]-x[j-1]>1.6:
            xx.append(np.nan);yy.append(np.nan)
        xx.append(x[j]);yy.append(y[j])
    ax.plot(xx,yy,'o-',color=BLUE,lw=1.5,ms=3.4,zorder=4)
    missing=~np.isfinite(y)
    ax.scatter(x[missing],np.full(missing.sum(),.23),transform=ax.get_xaxis_transform(),
               marker='x',s=24,lw=1.1,color=GREY,zorder=5)
    first=g[(g.hours>=-6)&(g.evaluated_at_ms<hoof)&g.new_activity_evidence].head(1)
    if len(first):
        ax.scatter(first.hours,first.activity_ratio,marker='*',s=150,color=GOLD,
                   edgecolor='white',linewidth=.65,zorder=6)
        expected=per.loc[cow,'first_early_lead_hoof_hours']
        actual=(hoof-int(first.evaluated_at_ms.iloc[0]))/3600000
        assert abs(expected-actual)<1e-9
    assert bool(len(first))==bool(per.loc[cow,'early_hit'])
    assert not (g.activity_ratio.dropna()>5).any(), 'common y-scale would clip an observation'
    ax.set_ylim(0,5);ax.set_yticks([1,3]);ax.tick_params(axis='y',length=2,labelsize=9,colors='#63717C')
    ax.set_xlim(-12,.12);ax.set_xticks([-12,-9,-6,-3,0]);ax.tick_params(axis='x',length=3,labelsize=11)
    ax.spines['left'].set_color('#CBD2D9');ax.spines['bottom'].set_color('#CBD2D9')
    if i<9:
        ax.tick_params(axis='x',bottom=False,labelbottom=False);ax.spines['bottom'].set_visible(False)
    else:
        ax.set_xlabel('距犊牛完全娩出的小时数（按数据可用时刻）',labelpad=9,fontsize=12)
    ax.text(-.071,.5,cow,transform=ax.transAxes,va='center',ha='right',fontsize=12,fontweight='bold',color=DARK)
    drawn.append({'cow_id':cow,'displayed_updates':len(g),'displayed_valid_ratios':int(np.isfinite(y).sum()),
                  'first_early_lead_hoof_minutes':float(per.loc[cow,'first_early_lead_hoof_hours']*60)
                  if per.loc[cow,'early_hit'] else None})

right=fig.add_subplot(grid[:,1])
right.set_xlim(0,255);right.set_ylim(0,1)
right.set_yticks([]);right.spines['left'].set_visible(False)
right.spines['bottom'].set_color('#CBD2D9')
right.set_xticks([0,60,120,180,240]);right.tick_params(axis='x',labelsize=11)
right.grid(axis='x',color='#E5EAF0',lw=.8,zorder=0)
right.set_xlabel('首次新提示提前露蹄 / 分钟',labelpad=9,fontsize=12)
pos=right.get_position()
for ax,cow in zip(axes,cows):
    center=(ax.get_position().y0+ax.get_position().y1)/2
    y=(center-pos.y0)/pos.height
    if per.loc[cow,'early_hit']:
        lead=float(per.loc[cow,'first_early_lead_hoof_hours']*60)
        right.barh(y,lead,height=.044,color=BLUE,alpha=.91,zorder=3)
        label=f'{lead:.0f}'
        right.text(lead+4,y,label,va='center',color=DARK,fontweight='bold',fontsize=12,zorder=4)
    else:
        right.text(4,y,'未提示｜有效参考仅约1.9 h',va='center',color='#697681',fontsize=10.6)

fig.text(.042,.96,'活动量实测：10头牛中8头在露蹄前出现新提示',fontsize=23,fontweight='bold',color=DARK)
fig.text(.042,.917,'判据 R = 最近1小时平均活动 ÷ 自身动态基线；R ≥ 1.5 提供活动升高证据',fontsize=15,color=DARK)
fig.text(.96,.958,'原始数据逐包回放\n10头牛 · 500包 · 8831万帧',ha='right',va='top',fontsize=10.5,color='#697681')
fig.text(.088,.831,'A  全部牛只的相对活动曲线（统一纵轴 R：0–5）',fontsize=13,fontweight='bold',color=DARK)
fig.text(right.get_position().x0,.831,'B  首次提示的实际提前量',fontsize=13,fontweight='bold',color=DARK)
legend=[Line2D([0],[0],color=BLUE,marker='o',lw=1.5,ms=4,label='实际更新点'),
        Line2D([0],[0],color=GOLD,ls='--',lw=1,label='1.5倍门槛'),
        Line2D([0],[0],color=GOLD,marker='*',lw=0,ms=11,label='目标窗内首次新提示'),
        Line2D([0],[0],color=RED,ls=':',lw=1.2,label='露蹄'),
        Line2D([0],[0],color=GREY,marker='x',lw=0,ms=6,label='基线/覆盖不足（非零活动）')]
fig.legend(handles=legend,loc='upper left',bbox_to_anchor=(.08,.895),ncol=5,
           frameon=False,fontsize=10.5,columnspacing=1.5,handlelength=2)
fig.text(.088,.09,'蓝色阴影：完全娩出前6小时至露蹄前。时间采用文件更新时间代理；连线只辅助阅读，长缺口断开。',fontsize=10.5,color='#596874')
fig.text(.088,.055,'较早时段仍有18次提示 / 217.77有效观测小时（约1.98次 / 24小时）；8/10是本批回放结果，不是独立预测准确率。',
         fontsize=11,color=DARK)
png=FIGURES/'活动量规律_全部牛实测证据.png'
pdf=FIGURES/'活动量规律_全部牛实测证据.pdf'
fig.savefig(png,dpi=300,facecolor='white')
fig.savefig(pdf,facecolor='white')
plt.close(fig)
metadata={'input_csv_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'figure_cows':drawn,'algorithm_unchanged':True,'display_hours':[-12,0],
          'target_window':'[delivery-6h,hoof)','ratio_threshold':1.5,
          'moderate_evidence':summary['moderate_evidence'],
          'notes':'all 10 cows shown; exact packet arrivals, no smoothing or invented points; same development cohort'}
(FIGURES/'活动量实测图_数据核对.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
print(png)
print('all-cow event times and y-axis bounds checked; output PDF also saved')
