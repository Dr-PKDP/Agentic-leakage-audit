"""P6 release entry point: offline replay by default; fitting requires explicit options."""
import argparse, hashlib, json, sys
from pathlib import Path
BASE=Path(__file__).resolve().parent/'repro/p6'
sys.path.insert(0,str(BASE))
import analysis

def verify():
    root=Path(__file__).resolve().parent
    manifest=json.loads((root/'RELEASE_MANIFEST.json').read_text())
    for f in manifest['files']:
        p=root/f['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:raise SystemExit('Release integrity failed: '+f['path'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=BASE/'_generated');p.add_argument('--check-inputs',action='store_true');p.add_argument('--demo',type=Path);p.add_argument('--dpq',type=Path);p.add_argument('--allow-fit',action='store_true');a=p.parse_args()
    verify()
    if a.allow_fit:
        if not a.demo or not a.dpq:p.error('--allow-fit requires --demo and --dpq')
        from reference_portable import refit
        refit(BASE,a.demo,a.dpq,a.out);return
    if a.check_inputs:
        if not a.demo or not a.dpq:p.error('--check-inputs requires --demo and --dpq')
        from reference_portable import check_inputs
        print(json.dumps(check_inputs(BASE,a.demo,a.dpq),indent=2));return
    if a.out.exists():raise SystemExit('Output exists; select a new --out directory. No overwrite.')
    a.out.mkdir(parents=True)
    result={'principal':analysis.principal(BASE,a.out),'earlier_pilot':analysis.pilot(BASE,a.out),'reference':analysis.reference_metadata(BASE,a.out),'new_model_calls':0,'new_participant_fits':0}
    analysis.write(a.out/'summary.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
