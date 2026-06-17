import argparse, pathlib, re, sys
import numpy as np
import pandas as pd
MODES=["FULL","PCUT","NCUT","EXTR","FCYC"]; MODE_TO_IDX={m:i for i,m in enumerate(MODES)}
CH1=[f"CH1_{i:03d}" for i in range(128)]; CH2=[f"CH2_{i:03d}" for i in range(128)]
def h2s(v):
    x=int(str(v),16); return x-0x10000 if x>=0x8000 else x
def tags(path):
    m=re.search(r"v6[05]_(B2-\d+)_(NTNP|NTHP|HTNP|HTHP)_",path.name); return (m.group(1),m.group(2)) if m else (None,None)
def convert(csv_path,out_dir):
    out_dir.mkdir(parents=True,exist_ok=True); df=pd.read_csv(csv_path,dtype=str); sensor,condition=tags(csv_path)
    if 'sample_id' not in df.columns: df['sample_id']=np.arange(len(df))//5
    if 'mode_idx' not in df.columns: df['mode_idx']=df['mode'].map(MODE_TO_IDX)
    samples=[]; meta=[]
    for sid,g in df.groupby('sample_id',sort=True):
        arr=np.zeros((5,2,128),dtype=np.int16); present=set()
        for _,r in g.iterrows():
            mid=int(r['mode_idx']); mode=r['mode']
            if mid<0 or mid>4 or MODE_TO_IDX.get(mode)!=mid: continue
            arr[mid,0,:]=[h2s(r[c]) for c in CH1]; arr[mid,1,:]=[h2s(r[c]) for c in CH2]; present.add(mid)
        missing=sorted(set(range(5))-present); valid=(len(g)==5 and not missing); samples.append(arr)
        meta.append({'sample_id':int(sid),'source_csv':csv_path.name,'sensor_id':sensor or '', 'condition':condition or '', 'valid':int(valid),'frame_count':int(len(g)),'missing_mode_idx':'|'.join(map(str,missing))})
    X=np.stack(samples,axis=0) if samples else np.zeros((0,5,2,128),dtype=np.int16); stem=csv_path.stem
    npz=out_dir/f"{stem}_X_cycles.npz"; meta_path=out_dir/f"{stem}_metadata_cycles.csv"
    np.savez_compressed(npz,X=X,mode_names=np.array(MODES),channel_names=np.array(['CH1','CH2']),sample_id=np.array([m['sample_id'] for m in meta],dtype=np.int32),sensor_id=np.array([m['sensor_id'] for m in meta]),condition=np.array([m['condition'] for m in meta]),valid=np.array([m['valid'] for m in meta],dtype=np.int8))
    pd.DataFrame(meta).to_csv(meta_path,index=False); print(f"Wrote {npz} shape={X.shape}"); print(f"Wrote {meta_path}"); return 0 if all(m['valid'] for m in meta) else 1
def main():
    ap=argparse.ArgumentParser(description='Convert V6.5 cycle-aware CSV into analysis-ready X_cycles.npz'); ap.add_argument('csv',type=pathlib.Path); ap.add_argument('--out-dir',type=pathlib.Path,default=None); a=ap.parse_args(); return convert(a.csv,a.out_dir or (a.csv.parent/'processed'))
if __name__=='__main__': sys.exit(main())
