import argparse, csv, datetime as dt, pathlib, re, sys, time
from collections import Counter, defaultdict
try:
    import serial
except ImportError:
    serial = None
HEADER_RE_V65 = re.compile(r"^V6\.5,SID=(\d{5}),MID=([0-4]),(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$")
HEADER_RE_LEGACY = re.compile(r"^V6\.[0-4],MODE=(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$")
RAW_RE = re.compile(r"^CH([12]),RAW,128,([0-9A-F]{4}(?:,[0-9A-F]{4}){127})$")
MODE_TO_IDX = {"FULL": 0, "PCUT": 1, "NCUT": 2, "EXTR": 3, "FCYC": 4}
EXPECTED_MODES = set(range(5))
def parse_header(line):
    m = HEADER_RE_V65.match(line)
    if m:
        return {"protocol":"V65_RAW","sample_id":int(m.group(1)),"mode_idx":int(m.group(2)),"mode":m.group(3),"sensor_power":int(m.group(4)),"txn":m.group(5)}, None
    m = HEADER_RE_LEGACY.match(line)
    if m:
        mode=m.group(1); return {"protocol":"V60_RAW","sample_id":None,"mode_idx":MODE_TO_IDX[mode],"mode":mode,"sensor_power":int(m.group(2)),"txn":m.group(3)}, None
    return None, f"bad header: {line!r}"
def parse_frame(lines):
    if len(lines)!=3: return None, f"expected 3 lines, got {len(lines)}"
    header,err=parse_header(lines[0])
    if err: return None,err
    ch1=RAW_RE.match(lines[1]); ch2=RAW_RE.match(lines[2])
    if not ch1 or ch1.group(1)!="1": return None, f"bad CH1 line: {lines[1]!r}"
    if not ch2 or ch2.group(1)!="2": return None, f"bad CH2 line: {lines[2]!r}"
    if header["mode_idx"] != MODE_TO_IDX[header["mode"]]: return None, f"MID/mode mismatch: MID={header['mode_idx']} mode={header['mode']}"
    header["ch1"]=[int(x,16) for x in ch1.group(2).split(',')]; header["ch2"]=[int(x,16) for x in ch2.group(2).split(',')]
    return header,None
def assign_legacy_sample_ids(frames):
    for i,f in enumerate(frames):
        if f["sample_id"] is None: f["sample_id"]=i//5
def validate_samples(frames):
    by=defaultdict(list)
    for f in frames: by[f["sample_id"]].append(f)
    rows=[]; errs=[]
    for sid in sorted(by):
        fs=by[sid]; mids=[f["mode_idx"] for f in fs]; missing=sorted(EXPECTED_MODES-set(mids)); dup=sorted(m for m in EXPECTED_MODES if mids.count(m)>1); order_ok=(mids==[0,1,2,3,4]); valid=(not missing and not dup and order_ok and len(fs)==5)
        rows.append({"sample_id":sid,"valid":int(valid),"order_ok":int(order_ok),"frame_count":len(fs),"missing_mode_idx":"|".join(map(str,missing)),"duplicate_mode_idx":"|".join(map(str,dup)),"modes":"|".join(f["mode"] for f in fs),"txns":"|".join(f["txn"] for f in fs)})
        if not valid: errs.append(f"sample {sid}: frame_count={len(fs)} mids={mids} missing={missing} dup={dup}")
    return rows,errs
def write_csv(path, frames):
    assign_legacy_sample_ids(frames)
    with path.open('w',newline='',encoding='ascii') as f:
        w=csv.writer(f); ch1=[f"CH1_{i:03d}" for i in range(128)]; ch2=[f"CH2_{i:03d}" for i in range(128)]
        w.writerow(["pc_time_iso","type","sample_id","mode_idx","txn","mode","spwr"]+ch1+ch2)
        for fr in frames: w.writerow([fr["_ts"],fr["protocol"],fr["sample_id"],fr["mode_idx"],fr["txn"],fr["mode"],fr["sensor_power"]]+[f"{v:04X}" for v in fr["ch1"]]+[f"{v:04X}" for v in fr["ch2"]])
def write_metadata(path, frames):
    rows,errs=validate_samples(frames)
    if rows:
        with path.open('w',newline='',encoding='ascii') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return errs
def make_test_frame():
    vals1=','.join(f"{i&0xffff:04X}" for i in range(128)); vals2=','.join(f"{(i+0x100)&0xffff:04X}" for i in range(128)); out=[]
    for sid in range(2):
        for mid,mode in enumerate(["FULL","PCUT","NCUT","EXTR","FCYC"]): out.append([f"V6.5,SID={sid:05d},MID={mid},{mode},SPWR=1,TXN={sid*5+mid:02X}",f"CH1,RAW,128,{vals1}",f"CH2,RAW,128,{vals2}"])
    return out
def run_self_test():
    frames=[]
    for lines in make_test_frame():
        fr,err=parse_frame(lines)
        if err: raise SystemExit(err)
        fr["_ts"]="2026-01-01T00:00:00"; frames.append(fr)
    rows,errs=validate_samples(frames)
    if errs or len(rows)!=2 or any(r["valid"]!=1 for r in rows): raise SystemExit(f"sample validation failed: {errs} rows={rows}")
    print("SELFTEST PASS: V6.5 header parse + sample completeness validation"); return 0
def main():
    ap=argparse.ArgumentParser(description="Capture V6.5 cycle-aware ASCII UART frames."); ap.add_argument('--port',default='COM5'); ap.add_argument('--baud',type=int,default=921600); ap.add_argument('--frames',type=int,default=None); ap.add_argument('--samples',type=int,default=None,help='Complete 5-mode samples to capture; maps to frames=samples*5'); ap.add_argument('--timeout',type=float,default=120.0); ap.add_argument('--out-dir',default='logs'); ap.add_argument('--sensor',default=None); ap.add_argument('--condition',default=None); ap.add_argument('--test',action='store_true'); args=ap.parse_args()
    if args.test: return run_self_test()
    if serial is None: raise SystemExit('pyserial is required for capture: pip install pyserial')
    if args.samples is not None: args.frames=args.samples*5
    if args.frames is None: args.frames=200
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True); stem=f"v65{'_'+args.sensor if args.sensor else ''}{'_'+args.condition if args.condition else ''}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"; csv_path=out/f"{stem}.csv"; meta_path=out/f"{stem}_samples.csv"
    print(f"Sensor: {args.sensor or 'N/A'}  Condition: {args.condition or 'N/A'}  Target: {args.frames} frames  Timeout: {args.timeout}s")
    ser=serial.Serial(args.port,args.baud,timeout=0.01)
    try: ser.set_buffer_size(rx_size=256*1024)
    except AttributeError: pass
    frames=[]; errors=[]; deadline=time.time()+args.timeout; pending=[]; buf=b''; recv_bytes=0; t0=time.time()
    try:
        while len(frames)<args.frames and time.time()<deadline:
            chunk=ser.read(ser.in_waiting or 65536)
            if not chunk: continue
            buf+=chunk; recv_bytes+=len(chunk)
            if len(buf)>256*1024: buf=buf[-65536:]
            while b'\n' in buf:
                line_bytes,buf=buf.split(b'\n',1); line=line_bytes.decode('ascii',errors='replace').strip()
                if not line: continue
                if line.startswith('V6.'): pending=[line]
                elif pending:
                    pending.append(line)
                    if len(pending)==3:
                        fr,err=parse_frame(pending)
                        if err: errors.append(err)
                        else:
                            fr['_ts']=dt.datetime.now().isoformat(); frames.append(fr)
                            if len(frames)>=args.frames: buf=b''; break
                        pending=[]
            n=len(frames)
            if n>0 and n%50==0:
                elapsed=time.time()-t0; rate=n/elapsed if elapsed>0 else 0; eta=(args.frames-n)/rate if rate>0 else 0; print(f"  {n}/{args.frames} frames  {recv_bytes/1024:.0f} KB  {rate:.0f} fps  ETA {eta:.0f}s")
    finally: ser.close()
    elapsed=time.time()-t0; counts=Counter(f['mode'] for f in frames); mode_str='  '.join(f"{m}={counts.get(m,0)}" for m in ['FULL','PCUT','NCUT','EXTR','FCYC'])
    write_csv(csv_path,frames); sample_errors=write_metadata(meta_path,frames)
    print(f"\nDONE  {len(frames)} frames in {elapsed:.1f}s  {len(frames)/elapsed if elapsed else 0:.0f} fps  {mode_str}  parse_errors={len(errors)} sample_errors={len(sample_errors)}"); print(f"CSV: {csv_path}"); print(f"Sample metadata: {meta_path}")
    for e in (errors[:3]+sample_errors[:3]): print(f"    {e}")
    return 0 if frames and not sample_errors else 1
if __name__=='__main__': sys.exit(main())
