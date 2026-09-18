"""Opt-in, bounded local GPU checks. No public participants or network protocol.
Uses only a hash-verified prepared corpus. Does not evaluate the final-test split.
"""
from __future__ import annotations
import argparse, gc, hashlib, json, os, platform, subprocess, sys, time
from dataclasses import asdict
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import torch
from .config import ModelConfig
from .data import TokenStream, write_json, digest_file
from .engine import Engine, TrainConfig
from . import snapshot


def setup():
    if not torch.cuda.is_available(): raise RuntimeError('CUDA unavailable; no CPU substitute')
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.cuda.set_per_process_memory_fraction(.70)


def sensor():
    r=subprocess.run(['nvidia-smi','--query-gpu=name,temperature.gpu,power.draw,memory.used,utilization.gpu',
                      '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,check=True)
    row=r.stdout.strip().splitlines()[0].split(', ')
    if len(row)!=5:raise RuntimeError('Unexpected GPU telemetry')
    result=dict(zip(['name','temperature_c','power_w','used_memory_mib','utilization_percent'],row))
    if float(result['temperature_c'])>=82:raise RuntimeError('GPU temperature stop threshold reached')
    return result


def guard(start,stop):
    if time.monotonic()-start>840: raise TimeoutError('14-minute internal GPU cap reached')
    if stop.exists(): raise RuntimeError('Owner stop file present')


def metadata():
    p=torch.cuda.get_device_properties(0)
    return {'torch':str(torch.__version__),'cuda_runtime':torch.version.cuda,'python':platform.python_version(),
            'gpu':p.name,'gpu_total_bytes':p.total_memory,'attention':'MATH SDPA control',
            'deterministic_algorithms':True,'tf32':False,'precision':'FP16 autocast, FP32 parameters, dynamic GradScaler',
            'process_memory_fraction_cap':.70}


def run_calibration(a):
    setup();start=time.monotonic();a.output.mkdir(parents=True,exist_ok=False)
    guard(start,a.stop_file);before_sensor=sensor()
    stream=TokenStream(a.data,'train',a.manifest);dev=TokenStream(a.data,'dev',a.manifest)
    tc=TrainConfig(method='single',workers=1,microbatch=2,accumulation=4,precision='fp16')
    e=Engine(ModelConfig(),tc,stream,'cuda');before=e.evaluate(dev,16)
    warm=[]
    for _ in range(20):guard(start,a.stop_file);warm.append(e.step())
    torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();t=time.perf_counter();losses=[];sensors=[]
    for i in range(100):
        guard(start,a.stop_file);losses.append(e.step())
        if (i+1)%20==0:sensors.append(sensor());print('MEASURED_LOCAL_STEPS',i+1,flush=True)
    torch.cuda.synchronize();seconds=time.perf_counter()-t
    allocated=torch.cuda.max_memory_allocated();reserved=torch.cuda.max_memory_reserved()
    after=e.evaluate(dev,16);checkpoint=a.output/'calibrated.safetensors';sha=e.save(checkpoint)
    report={'schema':1,'scope':'One physical RTX 5070; one local learner; real TinyStories train/dev; NOT G1 quality screen, RTX2060 compatibility, WAN or distributed speedup.',
            'environment':metadata(),'model_parameters':e.mc.parameter_count(),'training_config':asdict(tc),
            'manifest_sha256':a.manifest,'warmup_optimizer_steps':20,'measured_optimizer_steps':100,
            'targets_per_local_step':e.targets,'measured_target_tokens':100*e.targets,'measured_seconds':seconds,
            'measured_target_tokens_per_second':100*e.targets/seconds,'peak_cuda_allocated_bytes':allocated,
            'peak_cuda_reserved_bytes':reserved,'dev_probe_windows':16,'dev_nll_before':before,'dev_nll_after':after,
            'total_processed_targets':e.tokens,'final_train_loss':losses[-1],'all_measured_losses_finite':True,
            'grad_scaler':e.scalers[0].state_dict(),'start_sensor':before_sensor,'periodic_sensors':sensors,
            'checkpoint':{'file':checkpoint.name,'bytes':checkpoint.stat().st_size,'sha256':sha},
            'wall_seconds_including_validation_and_checkpoint':time.monotonic()-start,
            'notes':['Time includes local data gathering and GPU transfer, not checkpoint/evaluation.',
                     'Math attention chosen for a reproducible control, not the fastest available kernel.',
                     'Only GPU allocated/reserved memory measured; not total system memory or energy.',
                     '100 timed steps are not an end-to-end language quality or speedup claim.']}
    write_json(a.output/'CALIBRATION.json',report);print(json.dumps(report,indent=2),flush=True)


def compare(a,b,path='root'):
    if isinstance(a,torch.Tensor):
        if not isinstance(b,torch.Tensor) or a.dtype!=b.dtype or a.shape!=b.shape or not torch.equal(a,b):
            return [path]
        return []
    if isinstance(a,dict):
        if not isinstance(b,dict) or a.keys()!=b.keys():return [path+'.keys']
        errors=[]
        for k in a:errors+=compare(a[k],b[k],path+'.'+str(k))
        return errors
    if isinstance(a,(list,tuple)):
        if type(a)!=type(b) or len(a)!=len(b):return [path+'.length']
        errors=[]
        for i,(x,y) in enumerate(zip(a,b)):errors+=compare(x,y,path+'.'+str(i))
        return errors
    return [] if type(a)==type(b) and a==b else [path]


def run_continue(a):
    setup();start=time.monotonic();request=json.loads(a.request.read_text())
    stream=TokenStream(Path(request['data']),'train',request['manifest'])
    e=Engine(ModelConfig(),TrainConfig(**request['config']),stream,'cuda')
    e.load(a.request.parent/'mid.safetensors',request['snapshot_sha256'])
    losses=[]
    for _ in range(2):guard(start,a.stop_file);losses.append(e.step())
    sha=e.save(a.request.parent/'resumed.safetensors')
    write_json(a.request.parent/'child.json',{'losses':losses,'sha256':sha,'pid':os.getpid()})


def run_resume(a):
    setup();start=time.monotonic();a.output.mkdir(parents=True,exist_ok=False)
    sensor();stream=TokenStream(a.data,'train',a.manifest)
    tc=TrainConfig(method='diloco',workers=4,local_steps=8,microbatch=2,accumulation=4,precision='fp16')
    e=Engine(ModelConfig(),tc,stream,'cuda')
    for i in range(7):guard(start,a.stop_file);e.step();print('RESUME_PREP_STEP',i+1,flush=True)
    before=e.save(a.output/'mid.safetensors')
    expected_losses=[e.step(),e.step()]
    sha_expected=e.save(a.output/'expected.safetensors')
    info={'data':str(a.data),'manifest':a.manifest,'config':asdict(tc),'snapshot_sha256':before}
    write_json(a.output/'request-private.json',info)
    del e;gc.collect();torch.cuda.empty_cache()
    args=[sys.executable,'-m','commons_lab.gpu_calibration','--mode','continue',
          '--request',str(a.output/'request-private.json'),'--stop-file',str(a.stop_file)]
    subprocess.run(args,check=True,timeout=max(1,840-(time.monotonic()-start)))
    child=json.loads((a.output/'child.json').read_text())
    expected=snapshot.load(a.output/'expected.safetensors',sha_expected)
    resumed=snapshot.load(a.output/'resumed.safetensors',child['sha256'])
    errors=compare(expected,resumed);same_losses=expected_losses==child['losses']
    report={'schema':1,'scope':'Fresh-process local CUDA FP16 recovery, exact 22M model, four sequential logical learners, checkpoint inside H8 round then cross outer update; NOT separate computers or a hard power-loss test.',
            'environment':metadata(),'model_parameters':ModelConfig().parameter_count(),'training_config':asdict(tc),
            'manifest_sha256':a.manifest,'checkpoint_after_global_step':7,'continued_global_steps':2,
            'expected_losses':expected_losses,'resumed_losses':child['losses'],'losses_bitwise_equal':same_losses,
            'full_state_bitwise_equal':not errors,'mismatched_fields':errors[:20],
            'end_global_step':resumed['global_step'],'end_outer_updates':resumed['outer_updates'],
            'end_token_count':resumed['tokens'],'data_ledger_sha256':resumed['ledger'],
            'parent_pid':os.getpid(),'child_pid':child['pid'],'wall_seconds':time.monotonic()-start,
            'compared':['server and learner parameters','all inner Adam states','outer anchor and momentum',
                        'AMP scalers','data cursor and token counts','accepted outer position','Python and CPU/CUDA RNG']}
    write_json(a.output/'GPU_RESUME.json',report);print(json.dumps(report,indent=2),flush=True)
    if errors or not same_losses:raise RuntimeError('CUDA resume differs; do not advance quality experiment')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['calibration','resume','continue'],required=True)
    p.add_argument('--data',type=Path);p.add_argument('--manifest');p.add_argument('--output',type=Path)
    p.add_argument('--request',type=Path);p.add_argument('--stop-file',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='continue':
        if not a.request:p.error('--request required')
        run_continue(a)
    else:
        if not a.data or not a.output or not a.manifest or len(a.manifest)!=64:p.error('Explicit corpus, hash and fresh output required')
        (run_calibration if a.mode=='calibration' else run_resume)(a)
if __name__=='__main__':main()
