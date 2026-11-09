<?php
declare(strict_types=1);
function e(mixed $v): string { return htmlspecialchars((string)$v, ENT_QUOTES|ENT_SUBSTITUTE, 'UTF-8'); }
function api(string $path, array $query=[]): ?array {
    $ch=curl_init('http://localhost'.$path.($query?'?'.http_build_query($query):''));
    if ($ch===false) return null;
    curl_setopt_array($ch,[CURLOPT_UNIX_SOCKET_PATH=>'/run/vivo-explorer/explorer.sock',CURLOPT_RETURNTRANSFER=>true,CURLOPT_TIMEOUT=>20,CURLOPT_CONNECTTIMEOUT=>2]);
    $body=curl_exec($ch); $code=curl_getinfo($ch,CURLINFO_HTTP_CODE); curl_close($ch);
    if (!is_string($body)||$code!==200) return null;
    $data=json_decode($body,true); return is_array($data)?$data:null;
}
$q=trim((string)($_GET['q']??'')); $searchTooLong=strlen($q)>75; if($searchTooLong) $q='';
$result=$q!==''?api('/search',['q'=>$q]):null;
$status=api('/status');
$recent=api('/recent',['count'=>10]);
$quorums=api('/quorums');
$view=(string)($_GET['view']??'');
if (!in_array($view,['masternodes','quorums','dkg','mempool','block-report','block-activity'],true)) $view='';
$mn=$view==='masternodes'?api('/masternodes'):null;
$ql=$view==='quorums'?api('/quorum-list'):null;
$dkg=$view==='dkg'?api('/dkg-health'):null;
$mempool=$view==='mempool'?api('/mempool'):null;
$memhist=$view==='mempool'?api('/mempool-history'):null;
$featured=$view==='block-report'?api('/featured-block'):null;
$activity=$view==='block-activity'?api('/block-activity'):null;
$qtype=(string)($_GET['type']??'');
$qhash=(string)($_GET['hash']??'');
$qdetail=($view==='quorums' && preg_match('/^[0-9a-fA-F]{64}$/D',$qhash) && in_array($qtype,['llmq_vivo_chainlocks','llmq_vivo_instantsend','llmq_vivo_platform','llmq_vivo_mnhf'],true))?api('/quorum-detail',['type'=>$qtype,'hash'=>$qhash]):null;

function timeLabel(mixed $t): string { return is_numeric($t)?gmdate('Y-m-d H:i:s',(int)$t).' UTC':'—'; }
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VIVO Blockchain Explorer</title><style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif}*{box-sizing:border-box}body{margin:0;background:#0c1424;color:#e9f2ff;line-height:1.5}header,main,footer{max-width:1140px;margin:auto;padding:20px}header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;border-bottom:1px solid #33445d}a{color:#71c9ff;text-decoration:none}a:hover{text-decoration:underline}.brand{font-size:1.35rem;font-weight:750}.links{display:flex;flex-wrap:wrap;gap:18px}.hero{margin:24px 0}.muted{color:#a9bdd5}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:12px}.card{background:#14243b;border:1px solid #2d4361;border-radius:12px;padding:18px;margin:16px 0}.number{font-size:1.5rem;font-weight:bold}.search{display:flex;gap:10px;flex-wrap:wrap}.search input{flex:1;min-width:230px;padding:14px;background:#0b1729;border:1px solid #54708c;border-radius:8px;color:white;font-size:1rem}.search button{background:#278ad2;border:0;border-radius:8px;padding:13px 22px;color:white;font-weight:bold;cursor:pointer}table{border-collapse:collapse;width:100%}th,td{padding:11px;text-align:left;border-bottom:1px solid #30425b}th{color:#a9bdd5}td.hash{overflow-wrap:anywhere;font-family:monospace;font-size:.83rem}.tablewrap{overflow-x:auto}code{overflow-wrap:anywhere}h1,h2{margin-top:.2rem}.notice{border-left:3px solid #e1b761;padding:10px 15px;background:#302a20}.good{color:#6bddb2}.bad{color:#ffb98c}footer{color:#a9bdd5;font-size:.87rem}
</style></head><body>
<header><div class="brand">▣ VIVO Blockchain Explorer</div><nav class="links"><a href="/">Web Wallet</a><a href="/blockchain-in-motion/">Blockchain in Motion</a><a href="#blocks">Blocks</a><a href="?view=masternodes">Masternodes</a><a href="?view=quorums">Quorums</a><a href="?view=dkg">DKG Health</a><a href="?view=mempool">Mempool</a><a href="?view=block-report">Mined Large TX</a><a href="?view=block-activity">Block Activity</a></nav></header>
<main><section class="hero"><h1>Explore the VIVO blockchain</h1><p class="muted">Search by block height, block hash, transaction hash or VIVO address.</p><form class="search" method="get"><input name="q" aria-label="Blockchain search" maxlength="75" placeholder="Block height, hash, transaction ID or address" value="<?=e($q)?>" required><button type="submit">Search</button></form></section>
<div class="cards"><div class="card"><div class="muted">Node Height</div><div class="number"><?=e($status['height']??'Unavailable')?></div></div><div class="card"><div class="muted">Node Version</div><div class="number"><?=e($status['version']??'Unavailable')?></div></div><div class="card"><div class="muted">Peers</div><div class="number"><?=e($status['peers']??'Unavailable')?></div></div><div class="card"><div class="muted">Recent blocks indexed</div><div class="number"><?=e(count($recent['blocks']??[]))?></div></div></div>
<?php if ($q!=='' || $searchTooLong): ?><section class="card"><h2>Search result</h2>
<?php if($searchTooLong): ?><p class="bad">Search input is too long. Enter a block height, a 64-character hexadecimal hash, or a supported VIVO address.</p><?php elseif(!$result): ?><p class="bad">No matching blockchain record was found, or the search service is temporarily unavailable. Check your input and try again.</p>
<?php elseif(($result['type']??'')==='address'): ?><p>Address: <code><?=e($result['address']??'')?></code></p><div class="notice">Address history and balances are not currently enabled. This input matches address formatting only; ownership and validity have not been verified.</div>
<?php elseif(($result['type']??'')==='block'): $b=$result['block']; ?><p><b>Block:</b> <?=e($b['height']??'')?></p><p><b>Hash:</b> <code><?=e($b['hash']??'')?></code></p><p><b>Time:</b> <?=e(timeLabel($b['time']??null))?></p><p><b>Confirmations:</b> <?=e($b['confirmations']??'—')?></p><h3>Transactions</h3><div class="tablewrap"><table><tbody><?php foreach(array_slice($b['tx']??[],0,100) as $tx): ?><tr><td class="hash"><a href="?q=<?=e(urlencode((string)$tx))?>"><?=e($tx)?></a></td></tr><?php endforeach; ?></tbody></table></div><?php if(count($b['tx']??[])>100):?><p class="muted">Showing first 100 transactions.</p><?php endif; ?>
<?php elseif(($result['type']??'')==='transaction'): $t=$result['tx']; ?><p><b>Transaction ID:</b> <code><?=e($t['txid']??'')?></code></p><p><b>Block:</b> <?php if(!empty($t['blockhash'])):?><a href="?q=<?=e(urlencode((string)$t['blockhash']))?>"><?=e($t['blockhash'])?></a><?php else:?>Unconfirmed<?php endif;?></p><p><b>Confirmations:</b> <?=e($t['confirmations']??0)?></p><p><b>Inputs:</b> <?=e(($t['input_count']??count($t['vin']??[])))?> &nbsp; <b>Outputs:</b> <?=e(($t['output_count']??count($t['vout']??[])))?></p><p><b>Type:</b> <?=e($t['type']??'—')?> &nbsp;
<b>Size:</b> <?=e($t['size']??'—')?> bytes</p>
<p><b>Transaction fee:</b>
<?php if(($t['fee_status']??'')==='verified'): ?>
<?=e($t['fee_vivo'])?> VIVO
<small>(verified)</small>
<?php else: ?>Unavailable<?php endif; ?></p>
<p><b>Total inputs:</b>
<?=e($t['input_total_vivo']??'Unavailable')?>
<?php if(isset($t['input_total_vivo'])): ?> VIVO<?php endif; ?>
&nbsp; <b>Total outputs:</b>
<?=e($t['output_total_vivo']??'Unavailable')?>
<?php if(isset($t['output_total_vivo'])): ?> VIVO<?php endif; ?>
</p>
<p class="muted">Transaction input and output previews
are limited for performance. Counts include all entries.</p>
<h3>Outputs (up to 20)</h3><div class="tablewrap"><table><thead><tr><th>Index</th><th>Value (VIVO)</th><th>Address / type</th></tr></thead><tbody><?php foreach($t['vout']??[] as $v):?><tr><td><?=e($v['n']??'')?></td><td><?=e($v['value']??'')?></td><td><?=e($v['scriptPubKey']['address']??($v['scriptPubKey']['type']??'—'))?></td></tr><?php endforeach;?></tbody></table></div><?php endif; ?>
</section><?php endif; ?>
<section class="card" id="blocks"><h2>Latest Blocks</h2><p class="muted">Node tip: <?=e($recent['tip']??'Unavailable')?> · Updated: <?=e(timeLabel($recent['at']??null))?></p><div class="tablewrap"><table><thead><tr><th>Height</th><th>Block Hash</th><th>Transactions</th><th>Time</th></tr></thead><tbody><?php foreach(($recent['blocks']??[]) as $b):?><tr><td><a href="?q=<?=e($b['height']??'')?>"><?=e($b['height']??'')?></a></td><td class="hash"><a href="?q=<?=e(urlencode((string)($b['hash']??'')))?>"><?=e($b['hash']??'')?></a></td><td><?=e($b['txcount']??'')?></td><td><?=e(timeLabel($b['time']??null))?></td></tr><?php endforeach; ?></tbody></table></div></section>
<section class="card" id="quorums"><h2>On-chain Quorum Counts</h2><p class="muted">These are listed quorum records, not proof of healthy signing.</p><div class="cards"><?php foreach(($quorums['quorums']??[]) as $kind=>$count):?><div><div class="muted"><?=e($kind)?></div><div class="number"><?=e($count??'—')?></div></div><?php endforeach;?></div></section>
<div class="notice">Address indexing is disabled. Coin supply, rich list and complete address history will be added only after independent indexing validation. Search requests are read-only.</div>
<?php if($view==='block-activity'): ?>
<section class="card" id="block-activity"><h2>Recent Block Activity</h2>
<p class="muted">Read-only view of the latest six blocks on the active chain. A large ordinary transaction is 50,000 bytes or more. Quorum commitment counts do not prove healthy quorum formation.</p>
<?php if(!$activity):?><p class="bad">Recent block activity is temporarily unavailable.</p>
<?php else: ?>
<p class="muted">Node tip: <?=e($activity['tip']??'—')?> · Updated: <?=e(timeLabel($activity['at']??null))?> · Fees: verified from previous outputs when available; otherwise unavailable</p>
<div class="tablewrap"><table><thead><tr><th>Height</th><th>Block size</th><th>Total TX</th><th>Ordinary TX</th><th>Large TX ≥50 KB</th><th>Large TX bytes</th><th>Quorum commitments</th><th>TX fees (VIVO)</th><th>Coinbase outputs (VIVO)</th><th>Time (UTC)</th></tr></thead><tbody>
<?php foreach(($activity['blocks']??[]) as $b): ?><tr>
<td><a href="?q=<?=e($b['height']??'')?>"><?=e($b['height']??'—')?></a></td>
<td><?=e($b['size']??'—')?></td><td><?=e($b['tx_count']??'—')?></td><td><?=e($b['ordinary_count']??'—')?></td><td><?=e($b['large_count']??'—')?></td><td><?=e($b['large_bytes']??'—')?></td><td><?=e($b['quorum_commitment_count']??'—')?></td><td><?=e(($b['fee_status']??'')==='verified'?($b['total_fees_vivo']??'Unavailable'):'Unavailable')?></td><td><?=e(($b['fee_status']??'')==='verified'?($b['coinbase_outputs_total_vivo']??'Unavailable'):'Unavailable')?></td><td><?=e(timeLabel($b['time']??null))?></td>
</tr><?php endforeach;?></tbody></table></div>
<p class="muted">Coinbase outputs are the total block payouts, including masternode and other required payments—not solely the miner's earnings. Missing, stale or incomplete fee data is shown as unavailable.</p>
<p class="muted">Historical verified example: <a href="?view=block-report">Block #2,197,198 — 11 large transactions and recorded fees</a>.</p>
<?php endif;?></section>
<?php endif; ?>
<?php if($view==='block-report'): ?>
<section class="card" id="block-report"><h2>Large-transaction block — #2,197,198</h2>
<p class="muted">Historical case study: 11 large UTXO consolidation transactions mined by CENT Pool. This is not a live mempool view.</p>
<?php if(!$featured):?><p class="bad">Block verification unavailable or active chain differs from the reference block.</p>
<?php else: ?>
<p><b>Block:</b> <a href="?q=2197198">#<?=e($featured['height']??'')?></a> · <b>Confirmations:</b> <?=e($featured['confirmations']??'—')?> · <b>Size:</b> <?=e($featured['size']??'—')?> bytes</p>
<div class="cards"><div><div class="muted">Total transactions</div><div class="number"><?=e($featured['tx_count']??'—')?></div></div><div><div class="muted">Large ordinary transactions (≥50 KB)</div><div class="number"><?=e($featured['large_count']??'—')?></div></div><div><div class="muted">Large transaction bytes</div><div class="number"><?=e($featured['large_bytes']??'—')?></div></div><div><div class="muted">Observed fees from 11 transactions (VIVO)</div><div class="number"><?=e($featured['observed_fee_total_vivo']??'Unavailable')?></div></div></div>
<p class="muted"><?=e($featured['fee_method']??'')?> The observed fee total is displayed only when all 11 historically identified transactions match this active-chain block.</p>
<p><b>Block hash:</b> <code><?=e($featured['hash']??'')?></code></p>
<h3>Block transaction types</h3><p><?php foreach(($featured['types']??[]) as $t=>$c): ?>Type <?=e($t)?>: <?=e($c)?> &nbsp; <?php endforeach;?></p>
<h3>Large confirmed transactions</h3><div class="tablewrap"><table><thead><tr><th>Transaction ID</th><th>Bytes</th></tr></thead><tbody><?php foreach(($featured['large_transactions']??[]) as $t):?><tr><td class="hash"><a href="?q=<?=e(rawurlencode((string)($t['txid']??'')))?>"><?=e($t['txid']??'')?></a></td><td><?=e($t['size']??'')?></td></tr><?php endforeach;?></tbody></table></div>
<?php endif;?></section>
<?php endif; ?>
<?php if($view==='masternodes'): ?>
<section class="card" id="masternodes"><h2>Masternode Explorer</h2><p class="muted">Current deterministic masternode snapshot (not historical). The list is capped at 250 records.</p>
<?php if(!$mn):?><p class="bad">Masternode information is unavailable.</p><?php else: ?>
<p>Total: <?=e($mn['total']??'—')?> · Displayed: <?=e($mn['shown']??'—')?> <?php if(!empty($mn['truncated'])):?>· Partial listing<?php endif;?></p>
<div class="search" style="margin:12px 0"><input id="mnFilter" placeholder="Filter visible rows by ProTx, status or type" aria-label="Filter masternodes"></div>
<div class="tablewrap"><table id="mnTable"><thead><tr><th>ProTx</th><th>Type</th><th>Status</th><th>Last paid block</th><th>Payout address</th></tr></thead><tbody>
<?php foreach(($mn['nodes']??[]) as $n):?><tr><td class="hash"><?=e($n['protx']??'')?></td><td><?=e($n['type']??'')?></td><td><?=e($n['status']??'')?></td><td><?=e($n['lastpaidblock']??'—')?></td><td class="hash"><?=e($n['payee']??'')?></td></tr><?php endforeach;?></tbody></table></div>
<script>document.getElementById('mnFilter').addEventListener('input',function(){let q=this.value.toLowerCase();document.querySelectorAll('#mnTable tbody tr').forEach(tr=>tr.hidden=!tr.textContent.toLowerCase().includes(q));});</script>
<?php endif;?></section>
<?php elseif($view==='quorums'): ?>
<section class="card" id="quorumlist"><h2>Quorum Explorer</h2><p class="muted">On-chain quorum commitments, not evidence of active finality or successful InstantSend signing.</p>
<?php if(!$ql):?><p class="bad">Quorum information unavailable.</p><?php else:?>
<?php foreach(($ql['types']??[]) as $kind=>$group):?>
<h3><?=e($kind)?> · <?=e($group['count']??'—')?> listed</h3>
<div class="tablewrap"><table><thead><tr><th>Quorum hash</th><th>Creation height</th><th>Valid members</th><th>Health ratio</th></tr></thead><tbody>
<?php foreach(($group['records']??[]) as $rec):?><tr><td class="hash"><a href="?view=quorums&amp;type=<?=e(rawurlencode((string)$kind))?>&amp;hash=<?=e(rawurlencode((string)($rec['hash']??'')))?>"><?=e($rec['hash']??'')?></a></td><td><?=e($rec['creationHeight']??'—')?></td><td><?=e($rec['numValidMembers']??'—')?></td><td><?=e($rec['healthRatio']??'—')?></td></tr><?php endforeach;?></tbody></table></div>
<?php endforeach;?><?php endif;?>
<?php if($qdetail):?><div class="card"><h3>Quorum detail</h3><p class="hash"><?=e($qdetail['hash']??'')?></p><div class="tablewrap"><table><tbody><?php foreach(($qdetail['details']??[]) as $k=>$v):?><tr><th><?=e($k)?></th><td><?=e($v)?></td></tr><?php endforeach;?></tbody></table></div></div><?php endif;?></section>
<?php elseif($view==='mempool'): ?>
<section class="card" id="mempool"><h2>VIVO Mempool — Pending Transactions</h2>
<div class="notice">This is a local node snapshot of unconfirmed transactions, not a list of confirmed payments or proof of InstantSend locks. Entries can disappear when mined, replaced, or evicted. Times refer to first observation by this node.</div>
<?php if(!$mempool):?><p class="bad">Mempool data is currently unavailable.</p>
<?php else: $mi=$mempool['summary']??[]; ?>
<div class="cards"><div><div class="muted">Pending transactions</div><div class="number"><?=e($mi['size']??'—')?></div></div><div><div class="muted">Transaction bytes</div><div class="number"><?=e($mi['bytes']??'—')?></div></div><div><div class="muted">Memory usage (bytes)</div><div class="number"><?=e($mi['usage']??'—')?></div></div><div><div class="muted">Node minimum fee (VIVO/kB)</div><div class="number"><?=e($mi['mempoolminfee']??'—')?></div></div></div>
<div class="card"><h3>Fee analysis</h3><p class="muted">Fee rates are sampled from up to 20 detailed transactions; they are not representative of the full network mempool.</p>
<?php $fs=$mempool['fee_statistics']??[]; ?><div class="cards"><div><div class="muted">Sample size</div><div class="number"><?=e($fs['sampled']??0)?></div></div><div><div class="muted">Average (sat/vB)</div><div class="number"><?=e($fs['avg_sat_vb']??'—')?></div></div><div><div class="muted">Lowest (sat/vB)</div><div class="number"><?=e($fs['min_sat_vb']??'—')?></div></div><div><div class="muted">Highest (sat/vB)</div><div class="number"><?=e($fs['max_sat_vb']??'—')?></div></div></div>
<p class="muted">Fee-rate buckets (sampled only): <?php foreach(($fs['bins']??[]) as $label=>$count): ?> <?=e(str_replace('_',' ',(string)$label))?>: <?=e($count)?>; <?php endforeach; ?></p></div>
<p class="muted">Observed: <?=e(timeLabel($mempool['at']??null))?> · Showing <?=e($mempool['shown']??0)?> of <?=e($mempool['total_in_rpc_list']??0)?> local entries (maximum 50). First 20 include available metadata.</p>
<div class="tablewrap"><table><thead><tr><th>Transaction ID</th><th>Fee (VIVO)</th><th>Virtual size (vB)</th><th>First seen (UTC)</th><th>Age</th><th>Fee rate (sat/vB)</th><th>Status</th><th>InstantSend</th><th>Ancestors</th></tr></thead><tbody>
<?php foreach(($mempool['transactions']??[]) as $t):?><tr><td class="hash"><a href="?q=<?=e(rawurlencode((string)($t['txid']??'')))?>"><?=e($t['txid']??'')?></a></td><td><?=e($t['fee']??'—')?></td><td><?=e($t['vsize']??'—')?></td><td><?=isset($t['age_seconds'])?e(round(((int)$t['age_seconds'])/60,1).' min'):'—'?></td><td><?=e($t['fee_rate_vb']??'—')?></td><td>Pending</td><td>Not verified</td><td><?=e($t['ancestorcount']??'—')?></td></tr><?php endforeach;?></tbody></table></div>
<div class="card"><h3>Mempool history and confirmation tracking</h3><div class="notice">Five-minute node-local snapshots. Confirmed means a positive confirmation count was independently returned by VIVO Core. Disappeared transactions without such proof are marked unresolved, not confirmed. InstantSend locks are not verified by this release.</div>
<?php if(!$memhist):?><p class="muted">History collector has not published its first snapshot yet.</p><?php else: ?><p>Latest collection: <?=e($memhist['collected_at']??'—')?> · Snapshot count: <?=e(count($memhist['points']??[]))?></p><div class="tablewrap"><table><thead><tr><th>UTC</th><th>Pending</th><th>Memory bytes</th><th>Mempool bytes</th></tr></thead><tbody><?php foreach(array_slice(array_reverse($memhist['points']??[]),0,24) as $h):?><tr><td><?=e($h['at']??'')?></td><td><?=e($h['pending']??'—')?></td><td><?=e($h['usage']??'—')?></td><td><?=e($h['bytes']??'—')?></td></tr><?php endforeach;?></tbody></table></div><h3>Observed transaction outcomes</h3><div class="tablewrap"><table><thead><tr><th>Transaction</th><th>Observed outcome</th><th>Confirmations</th><th>Last checked UTC</th></tr></thead><tbody><?php foreach(($memhist['outcomes']??[]) as $o):?><tr><td class="hash"><a href="?q=<?=e(rawurlencode((string)($o['txid']??'')))?>"><?=e($o['txid']??'')?></a></td><td><?=e($o['status']??'')?></td><td><?=e($o['confirmations']??'—')?></td><td><?=e($o['checked_at']??'')?></td></tr><?php endforeach;?></tbody></table></div><?php endif; ?></div>
<?php if(empty($mempool['transactions'])):?><p class="good">No pending transactions visible from this node at this observation.</p><?php endif; ?>
<?php endif;?></section>
<?php elseif($view==='dkg'): ?>
<section class="card" id="dkg"><h2>DKG Health Monitor</h2><div class="notice">Local node observations only. DKG information does not prove the health of other masternodes. Member identifiers, operator keys and IP addresses are intentionally excluded.</div>
<?php if(!$dkg):?><p class="bad">DKG status is unavailable from this node.</p><?php else:?>
<p>Aggregate session records: <?=e(count($dkg['sessions']??[]))?> · Observed <?=e(timeLabel($dkg['at']??null))?></p>
<div class="tablewrap"><table><thead><tr><th>Type / phase</th><th>Contributions</th><th>Complaints</th><th>Premature commitments</th></tr></thead><tbody>
<?php foreach(($dkg['sessions']??[]) as $d):?><tr><td><?=e($d['llmqType']??($d['quorumType']??'—'))?> / <?=e($d['phase']??($d['status']??'—'))?></td><td><?=e($d['receivedContributions']??'—')?></td><td><?=e($d['receivedComplaints']??'—')?></td><td><?=e($d['receivedPrematureCommitments']??'—')?></td></tr><?php endforeach;?></tbody></table></div>
<p class="muted">Missing contributions, remote dial failures and historical signing failures require a separate, verified monitoring feed. They are not inferred from absent quorum records.</p>
<?php endif;?></section>
<?php endif;?>
</main><footer>VIVO Explorer v1.0.79 · Independent public blockchain viewer · No wallet login required</footer></body></html>
