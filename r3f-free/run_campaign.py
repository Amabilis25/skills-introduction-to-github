from __future__ import annotations
import base64, gzip, hashlib, json, os, random, subprocess, time
from pathlib import Path

import torch
from huggingface_hub import HfApi, snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'neutralized_requests.jsonl'
PART_GLOB = 'neutralized_requests.part*.b64'
EXPECTED_DATA_SHA256 = '42cc5082864fb38913e104c52e2d1ee510d4b7c175f9cf32b483b369c7a8c0bf'
OUT = ROOT / 'out'
MODEL_ID = os.environ.get('R3F_MODEL_ID', 'Qwen/Qwen2.5-0.5B-Instruct')
RANDOMIZATION_SEED = 53031
BLIND_SEED = 88421
MAX_NEW_TOKENS = 900


def sha_text(s: str) -> str:
    return 'sha256:' + hashlib.sha256(s.encode('utf-8')).hexdigest()

def sha_obj(x) -> str:
    payload=json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(payload).hexdigest()

def data_bytes() -> bytes:
    if DATA.exists():
        raw = DATA.read_bytes()
    else:
        parts = sorted(ROOT.glob(PART_GLOB))
        if not parts:
            raise FileNotFoundError('R3F_FREE_DATA_PARTS_MISSING')
        payload = ''.join(part.read_text(encoding='ascii').strip() for part in parts)
        raw = gzip.decompress(base64.b64decode(payload, validate=True))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_DATA_SHA256:
        raise SystemExit(f'DATASET_DIGEST_MISMATCH:{digest}')
    return raw

def read_cases():
    return [json.loads(x) for x in data_bytes().decode('utf-8').splitlines() if x.strip()]

def git_sha():
    try:
        return subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    except Exception:
        return os.environ.get('GITHUB_SHA','UNKNOWN')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases=read_cases()
    if len(cases) != 18:
        raise SystemExit(f'EXPECTED_18_CASES_GOT_{len(cases)}')

    info=HfApi().model_info(MODEL_ID)
    model_sha=str(info.sha)
    if not model_sha or model_sha.lower() in {'none','unknown'}:
        raise SystemExit('CONCRETE_MODEL_REVISION_REQUIRED')
    model_dir=snapshot_download(repo_id=MODEL_ID, revision=model_sha)
    tokenizer=AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True, torch_dtype=torch.float32)
    model.eval()
    torch.set_num_threads(max(1, os.cpu_count() or 2))
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id=tokenizer.eos_token_id

    params={
        'temperature':0.0,
        'do_sample':False,
        'max_new_tokens':MAX_NEW_TOKENS,
        'use_cache':True,
    }
    identity={
        'provider':'huggingface-local-github-actions-cpu',
        'model':MODEL_ID,
        'revision':model_sha,
        'decoding_profile':sha_obj(params),
    }
    rng=random.Random(RANDOMIZATION_SEED)
    records=[]
    conditions=['NONE','SELECTIVE','ORACLE_FORMS']
    for case in cases:
        order=list(conditions); rng.shuffle(order)
        invariant={
            'prompt':case['prompt'],
            'external_context':case.get('external_context',''),
            'generation_parameters':params,
        }
        inv_sha=sha_obj(invariant)
        for condition in order:
            system=case['arms'][condition]['system']
            user=case['prompt']
            ext=case.get('external_context','')
            if ext:
                user = user + '\n\nContexte externe fourni:\n' + ext
            messages=[{'role':'system','content':system},{'role':'user','content':user}]
            rendered=tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs=tokenizer(rendered, return_tensors='pt')
            started=time.perf_counter()
            with torch.inference_mode():
                out=model.generate(
                    **inputs,
                    do_sample=False,
                    max_new_tokens=MAX_NEW_TOKENS,
                    use_cache=True,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            elapsed_ms=int((time.perf_counter()-started)*1000)
            new_tokens=out[0, inputs['input_ids'].shape[1]:]
            text=tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            if not text:
                raise RuntimeError(f'EMPTY_MODEL_OUTPUT:{case["case_id"]}:{condition}')
            response_id=hashlib.sha256((case['case_id']+'|'+condition+'|'+sha_text(text)).encode()).hexdigest()[:24]
            records.append({
                'response_id':response_id,
                'case_id':case['case_id'],
                'condition':condition,
                'task_family':case['task_family'],
                'system_sha256':sha_text(system),
                'user_sha256':sha_text(case['prompt']),
                'external_context_sha256':sha_text(case.get('external_context','')),
                'invariant_request_sha256':inv_sha,
                'generation_parameters_sha256':sha_obj(params),
                'model_identity':identity,
                'output_text':text,
                'output_sha256':sha_text(text),
                'latency_ms':elapsed_ms,
                'input_tokens':int(inputs['input_ids'].shape[1]),
                'output_tokens':int(new_tokens.shape[0]),
                'status':'PASS',
            })

    by_case={}
    for r in records: by_case.setdefault(r['case_id'],[]).append(r)
    if len(records) != 54 or set(by_case) != {c['case_id'] for c in cases}:
        raise SystemExit('PAIRING_COUNT_FAILED')
    identity_digests={sha_obj(r['model_identity']) for r in records}
    if len(identity_digests) != 1:
        raise SystemExit('SAME_MODEL_INVARIANT_FAILED')
    for cid, rs in by_case.items():
        if {r['condition'] for r in rs} != set(conditions):
            raise SystemExit(f'ARM_SET_FAILED:{cid}')
        if len({r['invariant_request_sha256'] for r in rs}) != 1:
            raise SystemExit(f'INVARIANT_REQUEST_FAILED:{cid}')
        if len({r['generation_parameters_sha256'] for r in rs}) != 1:
            raise SystemExit(f'GENERATION_PARAMETERS_FAILED:{cid}')

    case_map={c['case_id']:c for c in cases}
    blind_rng=random.Random(BLIND_SEED)
    shuffled=list(records); blind_rng.shuffle(shuffled)
    mapping={}; blind=[]
    for idx,r in enumerate(shuffled,1):
        blind_id=f'R3F-BLIND-{idx:03d}'
        mapping[blind_id]={'response_id':r['response_id'],'case_id':r['case_id'],'condition':r['condition']}
        c=case_map[r['case_id']]
        blind.append({
            'blind_id':blind_id,
            'case_id':r['case_id'],
            'prompt':c['prompt'],
            'external_context':c.get('external_context',''),
            'task_family':c['task_family'],
            'criteria':c['criteria'],
            'output_text':r['output_text'],
        })

    (OUT/'runs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in records),encoding='utf-8')
    (OUT/'blind_bundle.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in blind),encoding='utf-8')
    (OUT/'blind_mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    receipt={
        'status':'GENERATION_COMPLETE_BLIND_SCORING_REQUIRED',
        'protocol':'R3F-FREE-NEUTRALIZED/1',
        'git_commit':git_sha(),
        'model_identity':identity,
        'model_identity_sha256':next(iter(identity_digests)),
        'dataset_sha256':'sha256:'+hashlib.sha256(data_bytes()).hexdigest(),
        'generation_parameters':params,
        'records':len(records),
        'cases':len(cases),
        'same_model_invariant':'PASS',
        'pairing_invariant':'PASS',
        'monetary_compute_requirement':'NONE_GITHUB_PUBLIC_STANDARD_RUNNER',
    }
    (OUT/'generation_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True))

if __name__=='__main__':
    main()
