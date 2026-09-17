"""Validate a study plan without executing it. Null data hashes BLOCK a run."""
import argparse, json, re
from pathlib import Path
from .config import ModelConfig

def validate(plan):
    if plan.get('model_parameters')!=ModelConfig().parameter_count():raise ValueError('Wrong model dimensions')
    expected=plan['learners']*plan['targets_per_local_step']
    if plan['targets_per_global_step']!=expected:raise ValueError('Global token accounting mismatch')
    local=plan['context']*plan['microbatch_sequences']*plan['local_accumulation_steps']
    if plan['targets_per_local_step']!=local:raise ValueError('Local token accounting mismatch')
    for key in ('screen_target_tokens','confirmation_target_tokens'):
        value=plan[key]
        if type(value) is not int or value<=0 or value%expected:raise ValueError('Partial global step in budget')
        for h in (8,32):
            if value//expected%h:raise ValueError('Partial exchange round in budget')
    if plan['budgets']['public_training'] or plan['budgets']['store_publication']:
        raise ValueError('Out of scope for this research iteration')
    missing=[k for k in ('tokenizer_sha256','prepared_manifest_sha256')
             if not re.fullmatch('[0-9a-f]{64}',str(plan['dataset'].get(k,'')))]
    if not plan['dataset'].get('prerequisites_complete'):missing.append('reviewed_data_preparation')
    return {'plan_valid':True,'G1_execution_ready':not missing,'blocking_prerequisites':missing,
            'screen_global_steps':plan['screen_target_tokens']//expected,
            'confirmation_global_steps':plan['confirmation_target_tokens']//expected,
            'scope':'validation only; this function cannot launch training'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config',type=Path);p.add_argument('--require-ready',action='store_true');a=p.parse_args()
    result=validate(json.loads(a.config.read_text()));print(json.dumps(result,indent=2))
    if a.require_ready and not result['G1_execution_ready']:raise SystemExit(2)
if __name__=='__main__':main()
