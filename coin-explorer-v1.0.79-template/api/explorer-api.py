#!/usr/bin/env python3
"""Local socket, strict allowlist, read-only VIVO RPC query gateway."""
import json, os, re, socketserver, subprocess, urllib.parse, time, statistics
from http.server import BaseHTTPRequestHandler
from pathlib import Path

SOCKET='/run/vivo-explorer/explorer.sock'
CLI='/root/.vivocore/vivo-cli'
DATA='/root/.vivocore'
HEX=re.compile(r'^[0-9a-fA-F]{64}$')
HISTORY=Path('/var/cache/vivo-explorer-mempool/history-public.json')
ADDRESS=re.compile(r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{26,64}$')

def rpc(*args):
    result=subprocess.run([CLI, '-datadir='+DATA, *map(str,args)], capture_output=True, text=True, timeout=15, check=False)
    if result.returncode:
        # Do not leak CLI diagnostic or any credentials to public clients.
        raise LookupError('Blockchain lookup unavailable or item not found')
    raw = result.stdout.strip()
    if args and args[0] == 'getblockhash':
        if HEX.fullmatch(raw): return raw.lower()
        raise LookupError('Invalid block hash response')
    try: return json.loads(raw)
    except json.JSONDecodeError: raise LookupError('Unexpected node response')

def abbreviated_tx(tx):
    from decimal import Decimal

    vins = tx.get('vin', [])
    vouts = tx.get('vout', [])

    result = {
        'txid': tx.get('txid'),
        'confirmations': tx.get('confirmations'),
        'blockhash': tx.get('blockhash'),
        'blocktime': tx.get('blocktime'),
        'version': tx.get('version'),
        'type': tx.get('type'),
        'size': tx.get('size'),
        'height': tx.get('height'),
        'instantlock': (
            True if tx.get('instantlock') is True else None
        ),
        'input_count': len(vins),
        'output_count': len(vouts),
        'vin': [
            {
                'txid': v.get('txid'),
                'vout': v.get('vout'),
                'sequence': v.get('sequence'),
            }
            for v in vins[:10]
            if isinstance(v, dict)
        ],
        'vout': [
            {
                'n': v.get('n'),
                'value': v.get('value'),
                'scriptPubKey': {
                    'address': (
                        v.get('scriptPubKey', {}).get('address')
                        if isinstance(v.get('scriptPubKey'), dict)
                        else None
                    ),
                    'type': (
                        v.get('scriptPubKey', {}).get('type')
                        if isinstance(v.get('scriptPubKey'), dict)
                        else None
                    ),
                },
            }
            for v in vouts[:20]
            if isinstance(v, dict)
        ],
        'fee_status': 'unavailable',
        'fee_vivo': None,
        'input_total_vivo': None,
        'output_total_vivo': None,
    }

    if (
        tx.get('type') != 0
        or not tx.get('blockhash')
        or not isinstance(tx.get('confirmations'), int)
        or tx['confirmations'] <= 0
    ):
        return result

    try:
        block = rpc('getblock', tx['blockhash'], 3)

        if (
            not isinstance(block, dict)
            or block.get('size', 0) > 2000000
            or not isinstance(block.get('tx'), list)
        ):
            return result

        matches = [
            item for item in block['tx']
            if item.get('txid') == tx.get('txid')
        ]
        if len(matches) != 1:
            return result

        confirmed = matches[0]
        ins = confirmed.get('vin', [])
        outs = confirmed.get('vout', [])

        if not ins or len(ins) > 10000:
            return result

        if any(
            not isinstance(v.get('prevout'), dict)
            or v['prevout'].get('value') is None
            for v in ins
        ):
            return result

        def to_sat(value):
            amount = Decimal(str(value)) * Decimal(100000000)
            whole = amount.to_integral_exact()
            if amount != whole:
                raise ValueError('Non-integral satoshi value')
            return int(whole)

        input_sat = sum(
            to_sat(v['prevout']['value']) for v in ins
        )
        output_sat = sum(
            to_sat(v['value']) for v in outs
        )
        fee_sat = input_sat - output_sat

        if fee_sat < 0:
            return result

        if confirmed.get('fee') is not None:
            if to_sat(confirmed['fee']) != fee_sat:
                return result

        def vivo(amount):
            return format(
                Decimal(amount)/Decimal(100000000), '.8f'
            )

        result['fee_status'] = 'verified'
        result['fee_vivo'] = vivo(fee_sat)
        result['input_total_vivo'] = vivo(input_sat)
        result['output_total_vivo'] = vivo(output_sat)

    except Exception:
        # No guessed fees. Preserve existing search behavior.
        pass

    return result


# R74_FEE_GUARD
# Limit expensive confirmed transaction fee lookups.
# This is not a global HTTP request rate limiter.
import threading as _r74_threading
import time as _r74_time

_r74_fee_slots = _r74_threading.BoundedSemaphore(2)
_r74_cache_lock = _r74_threading.Lock()
_r74_fee_cache = {}
_r74_cache_ttl = 60.0
_r74_cache_max = 128

_r74_original_abbreviated_tx = abbreviated_tx


def _r74_summary_without_fee(tx):
    """Return existing sanitized transaction fields without fee RPC."""
    safe = dict(tx)
    safe['confirmations'] = 0
    result = _r74_original_abbreviated_tx(safe)
    result['confirmations'] = tx.get('confirmations')
    return result


def abbreviated_tx(tx):
    """Bound expensive fee work and cache verified results only."""
    if not isinstance(tx, dict):
        return _r74_original_abbreviated_tx(tx)

    if (
        tx.get('type') != 0
        or not tx.get('blockhash')
        or not isinstance(tx.get('confirmations'), int)
        or tx['confirmations'] <= 0
    ):
        return _r74_original_abbreviated_tx(tx)

    txid = tx.get('txid')
    blockhash = tx.get('blockhash')

    if not (
        isinstance(txid, str) and len(txid) == 64
        and isinstance(blockhash, str)
        and len(blockhash) == 64
    ):
        return _r74_summary_without_fee(tx)

    key = (txid, blockhash)
    now = _r74_time.monotonic()

    with _r74_cache_lock:
        entry = _r74_fee_cache.get(key)

        if entry is not None and entry[0] > now:
            cached = entry[1].copy()
        else:
            cached = None
            if entry is not None:
                _r74_fee_cache.pop(key, None)

    if cached is not None:
        result = _r74_summary_without_fee(tx)
        result.update(cached)
        return result

    # Never allow unbounded concurrent getblock verbosity-3
    # operations. Return safely without a verified fee when full.
    if not _r74_fee_slots.acquire(blocking=False):
        return _r74_summary_without_fee(tx)

    try:
        result = _r74_original_abbreviated_tx(tx)

        if result.get('fee_status') == 'verified':
            fields = (
                'fee_status',
                'fee_vivo',
                'input_total_vivo',
                'output_total_vivo',
            )
            verified = {
                field: result.get(field)
                for field in fields
            }

            with _r74_cache_lock:
                # Bounded, process-local, monotonic TTL cache.
                now = _r74_time.monotonic()

                expired = [
                    k for k, v in _r74_fee_cache.items()
                    if v[0] <= now
                ]
                for k in expired:
                    _r74_fee_cache.pop(k, None)

                if len(_r74_fee_cache) >= _r74_cache_max:
                    oldest = next(iter(_r74_fee_cache))
                    _r74_fee_cache.pop(oldest, None)

                _r74_fee_cache[key] = (
                    now + _r74_cache_ttl,
                    verified
                )

        return result

    finally:
        _r74_fee_slots.release()


# R11 public, bounded, read-only network views.
# Never expose local DKG member IPs, operator keys, or raw diagnostics.
QUORUM_TYPES = ('llmq_vivo_chainlocks','llmq_vivo_instantsend',
                'llmq_vivo_platform','llmq_vivo_mnhf')

def public_mn_list():
    raw=rpc('masternodelist','json')
    if not isinstance(raw,dict): raise LookupError('Unexpected masternode response')
    entries=[]
    total=len(raw)
    for protx, item in list(raw.items())[:250]:
        if not isinstance(item,dict): continue
        # Only explicitly recognized public fields. No operator secrets or IPs.
        entries.append({
          'protx':str(protx)[:72],
          'status':str(item.get('status',item.get('state','Unknown')))[:60],
          'type':str(item.get('type',item.get('mnType','Unknown')))[:40],
          'lastpaidblock':item.get('lastpaidblock',item.get('lastPaidBlock')),
          'lastpaidtime':item.get('lastpaidtime',item.get('lastPaidTime')),
          'payee':str(item.get('payee',item.get('payoutAddress','')))[:96]
        })
    return {'total':total,'shown':len(entries),'nodes':entries,
            'truncated':total>len(entries),'at':int(time.time()),
            'note':'Current node view, not a historical masternode index.'}

def public_quorum_list():
    raw=rpc('quorum','listextended')
    if not isinstance(raw,dict): raise LookupError('Unexpected quorum response')
    out={}
    for kind in QUORUM_TYPES:
        items=raw.get(kind,[])
        arr=[]
        if isinstance(items,list):
            for group in items[:60]:
                if isinstance(group,str):
                    arr.append({'hash':group,'creationHeight':None,'numValidMembers':None,'healthRatio':None})
                elif isinstance(group,dict):
                    # Some builds nest quorum hash -> metadata in each list element.
                    for h,v in list(group.items())[:5]:
                        if not isinstance(v,dict): continue
                        arr.append({'hash':str(h)[:70],
                          'creationHeight':v.get('creationHeight'),
                          'numValidMembers':v.get('numValidMembers'),
                          'healthRatio':v.get('healthRatio'),
                          'minedBlockHash':v.get('minedBlockHash')})
        out[kind]={'count':len(items) if isinstance(items,list) else None,
                   'records':arr[:100]}
    return {'types':out,'at':int(time.time()),
       'note':'On-chain records; presence does not demonstrate healthy signing.'}

def summarize_dkg(obj):
    # Only aggregate public telemetry; raw quorum dkgstatus contains node-local
    # details and should never be forwarded unfiltered.
    out={'reported':False,'sessions':[], 'at':int(time.time()),
         'scope':'Local node observation; not a network-wide verdict'}
    if not isinstance(obj,dict): return out
    out['reported']=True
    def collect(v,depth=0):
        if depth>4 or len(out['sessions'])>=24: return
        if isinstance(v,list):
            for x in v[:24]: collect(x,depth+1)
        elif isinstance(v,dict):
            # Only known aggregate fields; no member identifiers.
            allowed=('llmqType','quorumType','phase','status','sessionStatus',
                     'receivedContributions','receivedComplaints',
                     'receivedJustifications','receivedPrematureCommitments',
                     'receivedFinalCommitments')
            record={k:v[k] for k in allowed if k in v and
                    (isinstance(v[k],(int,float,bool)) or
                     isinstance(v[k],str) and len(v[k])<70)}
            if record: out['sessions'].append(record)
            for k,x in list(v.items())[:35]:
                if isinstance(x,(list,dict)): collect(x,depth+1)
    collect(obj)
    return out

def public_mempool():
    """Bounded snapshot; no wallet or broadcast RPC methods."""
    info=rpc('getmempoolinfo')
    if not isinstance(info,dict):
        raise LookupError('Mempool summary unavailable')
    # Avoid large verbose mempool output. Only fetch transaction ids here.
    ids=rpc('getrawmempool')
    if not isinstance(ids,list):
        raise LookupError('Mempool transaction listing unavailable')
    if len(ids)>100000:
        raise LookupError('Mempool list exceeds safety limit')
    selected=[txid for txid in ids[:50] if isinstance(txid,str) and HEX.fullmatch(txid)]
    # Limit detail lookups to 20 RPC calls per request, ordered by node listing.
    entries=[]
    for txid in selected[:20]:
        entry={'txid':txid,'fee':None,'vsize':None,'time':None,'ancestorcount':None,'age_seconds':None,'fee_rate_vb':None,'status':'pending','instantlock_status':'not_verified'}
        try:
            detail=rpc('getmempoolentry',txid)
            if isinstance(detail,dict):
                fees=detail.get('fees',{})
                if isinstance(fees,dict):
                    v=fees.get('base')
                else:
                    v=detail.get('fee')
                if isinstance(v,(int,float)) and not isinstance(v,bool):
                    entry['fee']=v
                for key in ('vsize','time','ancestorcount'):
                    n=detail.get(key)
                    if isinstance(n,int) and not isinstance(n,bool) and n>=0:
                        entry[key]=n
        except (LookupError,subprocess.TimeoutExpired):
            # A transaction may leave the mempool while data is collected.
            pass
        if entry['time'] is not None:
            entry['age_seconds']=max(0,int(time.time())-entry['time'])
        if entry['fee'] is not None and entry['vsize']:
            entry['fee_rate_vb']=round(entry['fee']*100000000/entry['vsize'],3)
        entries.append(entry)
    for txid in selected[20:]:
        entries.append({'txid':txid,'fee':None,'vsize':None,'time':None,
          'ancestorcount':None,'age_seconds':None,'fee_rate_vb':None,
          'status':'pending','instantlock_status':'not_verified'})
    safe_info={}
    for key in ('size','bytes','usage','maxmempool','mempoolminfee','minrelaytxfee','unbroadcastcount'):
        val=info.get(key)
        if isinstance(val,(int,float)) and not isinstance(val,bool):
            safe_info[key]=val
    rates=[x['fee_rate_vb'] for x in entries if x.get('fee_rate_vb') is not None]
    fee_stats={'sampled':len(rates),'min_sat_vb':min(rates) if rates else None,
        'max_sat_vb':max(rates) if rates else None,
        'avg_sat_vb':round(statistics.mean(rates),3) if rates else None,
        'bins':{'under_1':sum(v<1 for v in rates),
                '1_to_5':sum(1<=v<5 for v in rates),
                '5_to_20':sum(5<=v<20 for v in rates),
                '20_plus':sum(v>=20 for v in rates)}}
    return {'fee_statistics':fee_stats,'summary':safe_info,'transactions':entries,'shown':len(entries),
            'total_in_rpc_list':len(ids),'at':int(time.time()),
            'note':'Local node mempool snapshot. Pending transactions may be evicted, replaced, or mined. First-seen time is node-local.'}

def mempool_history():
    # The root-owned collector publishes only a bounded, sanitized report.
    try:
        if not HISTORY.is_file() or HISTORY.stat().st_size>250000:
            raise LookupError('History snapshot unavailable')
        with HISTORY.open('r',encoding='utf8') as stream:
            report=json.load(stream)
        if not isinstance(report,dict) or report.get('schema')!=1:
            raise LookupError('Invalid history report')
        return report
    except (OSError,ValueError,TypeError):
        raise LookupError('History snapshot unavailable')

# R44: bounded featured-block report, with no arbitrary block-scan RPC exposure.
FEATURED_HEIGHT=2197198
FEATURED_HASH='00000037661aaa1c2c4659a645d97398bb0accbba30cc54c716dc97c2251fbb0'
FEATURED_OBSERVED_FEES_SATS=922196

def featured_block_report():
    bh=rpc('getblockhash',FEATURED_HEIGHT)
    if bh.lower()!=FEATURED_HASH:
        raise LookupError('Featured block no longer matches active chain')
    b=rpc('getblock',bh,2)
    if not isinstance(b,dict) or not isinstance(b.get('tx'),list):
        raise LookupError('Block transaction data unavailable')
    txs=b['tx']
    types={}
    large=[]
    normal=0
    for tx in txs:
        if not isinstance(tx,dict):
            raise LookupError('Invalid block transaction')
        typ=tx.get('type')
        types[str(typ)]=types.get(str(typ),0)+1
        if typ==0:
            normal+=1
        size=tx.get('size')
        if typ==0 and isinstance(size,int) and size>=50000:
            large.append({'txid':tx.get('txid'),'size':size})
    # Pre-confirmation fee records exist only for these 11 verified TXIDs.
    # Do not present this as a generic on-chain fee calculation.
    known={'05f678987098614d5582e1670463325f5f402f1878b8316339f4d702e99affa1',
      'b057855210682ebe198799f320304cb457db0c32128bb1a5bcd274b9dd8f7087',
      'a2536cf8ac4e0a78c9c4b511347a3d1dc8c64a9df6c2f5e3baac8558c66d8a53',
      '40adb4fbaf619849ecaa7477910c294009b92443ef3be6a60a9f3991564d368e',
      'a4e3be466c415b628229d09ed76a713758502c12d712f744abdb767e92e240d9',
      '0bdf4937555746851566b333b0b0abe13782cb440ff3c6058a7488fe40d4a0db',
      '302d562d409fca4766820f5293f93425aba0b93cb4b2a9c14f14c63d1181499e',
      'e92d92ab2faaedbacd32ea632a129ee9e15cd3708354858f8016ada7b6012c8d',
      '22f0008ccd1fc51141e8ca76609cca3ce1b2f13e3cb5a8c5b0fa46230b4f5d00',
      '52a3c4b6a29b29cdffe1df0e35268fd8b281af2d19454e42c5b869d8e6f5da9d',
      '74e669d418574f2abc6af2120ed53d8de6847d4812d723da75c4aba950523047'}
    identified={str(t.get('txid','')).lower() for t in large}
    verified=identified==known and len(large)==11 and normal==11
    fees=(f'{FEATURED_OBSERVED_FEES_SATS/100000000:.8f}' if verified else None)
    return {'height':FEATURED_HEIGHT,'hash':bh,'confirmations':b.get('confirmations'),
      'time':b.get('time'),'size':b.get('size'),'tx_count':len(txs),
      'large_count':len(large),'large_bytes':sum(x['size'] for x in large),
      'types':types,'large_transactions':large[:20],
      'observed_fee_total_vivo':fees,
      'fee_method':'Sum of previously recorded mempool base fees for 11 confirmed ordinary transactions; not a general block fee RPC result.',
      'at':int(time.time())}

# R50: fee totals from an independent, bounded root-run cache; never perform
# prevout lookups from an unauthenticated public request.
FEE_CACHE=Path('/var/cache/vivo-explorer-fees/recent.json')

def read_fee_cache():
    try:
        st=FEE_CACHE.stat()
        if st.st_size>30000 or st.st_size<20 or time.time()-st.st_mtime>600:
            return {}
        with FEE_CACHE.open('r',encoding='utf8') as f:
            d=json.load(f)
        if not isinstance(d,dict) or d.get('schema_version')!=2:
            return {}
        if not isinstance(d.get('generated_at_unix'),int) or abs(time.time()-d['generated_at_unix'])>600:
            return {}
        rows=d.get('blocks')
        if not isinstance(rows,list) or len(rows)>6:
            return {}
        return {r['hash']:r for r in rows if isinstance(r,dict) and
                isinstance(r.get('hash'),str) and HEX.fullmatch(r['hash']) and
                isinstance(r.get('height'),int)}
    except (OSError,ValueError,TypeError,KeyError):
        return {}

# R45: bounded, read-only live scan of latest six blocks.
# No prevout fetching or inferred fees; no full historical scan.
def recent_block_activity():
    tip=rpc('getblockcount')
    rows=[]
    fee_cache=read_fee_cache()
    for height in range(tip, max(-1, tip-6), -1):
        bh=rpc('getblockhash',height)
        block=rpc('getblock',bh,2)
        txs=block.get('tx',[])
        if not isinstance(txs,list):
            raise LookupError('Block transaction list unavailable')
        normal_count=0
        large_count=0
        large_bytes=0
        qc_count=0
        for tx in txs:
            if not isinstance(tx,dict):
                raise LookupError('Invalid block transaction entry')
            typ=tx.get('type')
            if typ==0:
                normal_count+=1
                size=tx.get('size')
                if isinstance(size,int) and size>=50000:
                    large_count+=1
                    large_bytes+=size
            elif typ==6:
                qc_count+=1
        row={'height':height,'hash':bh,'time':block.get('time'),
            'confirmations':block.get('confirmations'),'size':block.get('size'),
            'tx_count':len(txs),'ordinary_count':normal_count,
            'large_count':large_count,'large_bytes':large_bytes,
            'quorum_commitment_count':qc_count,
            'fee_status':'unavailable','total_fees_vivo':None,
            'coinbase_outputs_total_vivo':None}
        cached=fee_cache.get(bh)
        if (isinstance(cached,dict) and cached.get('height')==height and
            cached.get('fee_status')=='verified' and
            cached.get('tx_count')==len(txs) and
            cached.get('ordinary_count')==normal_count and
            cached.get('large_count')==large_count and
            cached.get('quorum_commitment_count')==qc_count and
            isinstance(cached.get('total_fees_sats'),int) and
            cached['total_fees_sats']>=0 and
            isinstance(cached.get('total_fees_vivo'),str) and
            re.fullmatch(r'\d+\.\d{8}',cached['total_fees_vivo']) and
            isinstance(cached.get('coinbase_outputs_total_vivo'),str) and
            re.fullmatch(r'\d+\.\d{8}',cached['coinbase_outputs_total_vivo'])):
            row['fee_status']='verified'
            row['total_fees_vivo']=cached['total_fees_vivo']
            row['coinbase_outputs_total_vivo']=cached['coinbase_outputs_total_vivo']
        rows.append(row)
    return {'tip':tip,'blocks':rows,'at':int(time.time()),
       'large_threshold_bytes':50000,
       'fee_status':'verified_or_unavailable',
       'fee_method':'Input prevout minus output sum; cached locally; only same-hash verified values shown',
       'note':'Latest six blocks; coinbase outputs are total payouts including masternode outputs, not exclusively miner revenue.'}

def handle(path, query):
    if path=='/block-activity':
        return recent_block_activity()
    if path=='/featured-block':
        return featured_block_report()
    if path=='/status':
        d=rpc('getblockchaininfo'); n=rpc('getnetworkinfo')
        return {'height':d.get('blocks'),'headers':d.get('headers'), 'ibd':d.get('initialblockdownload'), 'peers':n.get('connections'), 'version':n.get('subversion'), 'at':int(time.time()), 'addressindex':'disabled'}
    if path=='/recent':
        count=min(max(int(query.get('count',['10'])[0]),1),20)
        height=rpc('getblockcount'); blocks=[]
        for h in range(height,height-count,-1):
            if h<0: break
            b=rpc('getblock',rpc('getblockhash',h),1)
            blocks.append({'height':b.get('height'),'hash':b.get('hash'),'time':b.get('time'),'txcount':len(b.get('tx',[])), 'confirmations':b.get('confirmations')})
        return {'blocks':blocks,'at':int(time.time()),'tip':height}
    if path=='/search':
        value=query.get('q',[''])[0].strip()
        if len(value)>75: raise ValueError('Invalid search input')
        if re.fullmatch(r'\d{1,10}',value):
            h=int(value)
            if h>rpc('getblockcount'): raise LookupError('Block height exceeds chain tip')
            block=rpc('getblock',rpc('getblockhash',h),1)
            return {'type':'block','block':block}
        if HEX.fullmatch(value):
            try:
                block=rpc('getblock',value,1)
                return {'type':'block','block':block}
            except LookupError: pass
            tx=rpc('getrawtransaction',value,'true')
            return {'type':'transaction','tx':abbreviated_tx(tx)}
        if ADDRESS.fullmatch(value):
            # Address index is not enabled. Do not claim arbitrary address balances.
            return {'type':'address','address':value,'available':False,
                    'reason':'Address history is not enabled on this node. No balance is displayed.'}
        raise ValueError('Enter a block height, 64-character hash, or VIVO address')
    if path=='/mempool-history':
        return mempool_history()
    if path=='/mempool':
        return public_mempool()
    if path=='/masternodes':
        return public_mn_list()
    if path=='/quorum-list':
        return public_quorum_list()
    if path=='/dkg-health':
        return summarize_dkg(rpc('quorum','dkgstatus'))
    if path=='/quorum-detail':
        kind=query.get('type',[''])[0]
        h=query.get('hash',[''])[0]
        if kind not in QUORUM_TYPES or not HEX.fullmatch(h):
            raise ValueError('Invalid quorum request')
        raw=rpc('quorum','info',kind,h)
        if not isinstance(raw,dict): raise LookupError('Unexpected quorum response')
        # No member addresses or raw secrets. Field availability varies by build.
        fields=('quorumHash','quorumType','minedBlockHash','creationHeight',
                'numValidMembers','healthRatio','quorumPublicKey',
                'isValid','quorumIndex','members')
        data={}
        for k in fields:
            if k=='members':
                value=raw.get(k)
                if isinstance(value,list):
                    data['memberCount']=len(value)
                    data['validMembers']=sum(1 for x in value if
                        isinstance(x,dict) and x.get('valid') is True)
            elif k in raw and isinstance(raw[k],(str,int,float,bool)):
                data[k]=raw[k]
        return {'type':kind,'hash':h,'details':data,'at':int(time.time())}
    if path=='/quorums':
        data=rpc('quorum','list')
        return {'quorums':{k:len(v) if isinstance(v,list) else None for k,v in data.items()},'at':int(time.time())}
    raise ValueError('Unsupported request')

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url=urllib.parse.urlsplit(self.path)
        try:
            params=urllib.parse.parse_qs(url.query, keep_blank_values=True, max_num_fields=5)
            if len(self.path)>200: raise ValueError('Request too large')
            data=handle(url.path,params)
            status=200
        except (ValueError,OverflowError):
            status,data=400,{'error':'Invalid request'}
        except (LookupError, subprocess.TimeoutExpired):
            status,data=404,{'error':'No matching record or node unavailable'}
        except Exception:
            status,data=503,{'error':'Service temporarily unavailable'}
        body=json.dumps(data,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self,fmt,*args): pass

import threading as _r77_threading

class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True
    request_queue_size=12

    # R77: bound active request-handler threads.
    # This is a concurrency limit, not a per-client rate limit.
    _r77_http_slots = _r77_threading.BoundedSemaphore(8)

    def process_request(self, request, client_address):
        if not self._r77_http_slots.acquire(blocking=False):
            body = b'{"error":"Service busy; retry later"}'
            response = (
                b'HTTP/1.0 503 Service Unavailable\r\n'
                b'Content-Type: application/json; charset=utf-8\r\n'
                b'Cache-Control: no-store\r\n'
                b'Connection: close\r\n'
                + b'Content-Length: '
                + str(len(body)).encode()
                + b'\r\n\r\n'
                + body
            )

            try:
                request.sendall(response)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return

        try:
            super().process_request(request, client_address)
        except BaseException:
            self._r77_http_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(
                request, client_address
            )
        finally:
            self._r77_http_slots.release()

if __name__=='__main__':
    path=Path(SOCKET)
    if path.exists(): path.unlink()
    with Server(SOCKET,Handler) as server:
        os.chmod(SOCKET,0o660)
        os.chown(SOCKET,0,__import__('grp').getgrnam('www-data').gr_gid)
        server.serve_forever()
