#!/usr/bin/env python3
"""Build docs/index.html from the harness outputs.

Reads results/summary.json, record_inventory.csv and
results/record_class_counts.csv; writes docs/index.html. Deterministic:
no timestamps are generated here (the fetch date comes from
summary.json, which is fixed for a given vendored sample).
Python 3.8+ standard library only.
"""

import csv
import html
import json
import os

PACK_DIR = os.path.dirname(os.path.abspath(__file__))


def esc(value):
    return html.escape(str(value))


def main():
    with open(os.path.join(PACK_DIR, "results", "summary.json"),
              encoding="utf-8") as fh:
        s = json.load(fh)
    with open(os.path.join(PACK_DIR, "record_inventory.csv"),
              encoding="utf-8") as fh:
        inventory = list(csv.DictReader(fh))
    with open(os.path.join(PACK_DIR, "results", "record_class_counts.csv"),
              encoding="utf-8") as fh:
        classes = list(csv.DictReader(fh))

    tx = s["transactions"]
    sig = s["signatures"]
    chain = s["chain_linkage"]
    census = s["entry_census"]
    sample = s["sample"]
    server = s["server_info"]

    inv_rows = "\n".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
        "<td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(r["class_id"]), esc(r["record_class"]),
            esc(r["where_recorded"]), esc(r["signing_scheme"]),
            esc(r["key_type"]), esc(r["public_key_bytes"]),
            esc(r["signature_bytes"]), esc(r["sampled_count"]))
        for r in inventory)

    class_rows = "\n".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(r["record_class"]), esc(r["sampled_count"]),
            esc(r["unit"]), esc(r["forgeable_by_quantum_adversary"]))
        for r in classes)

    entry_rows = "\n".join(
        "<tr><td>%s</td><td>%s</td></tr>" % (
            esc(k), esc(v))
        for k, v in sorted(census["by_type"].items()))

    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Historical Ledger Quantum-Exposure Audit</title>
<style>
body{font-family:system-ui,sans-serif;max-width:960px;margin:2em auto;padding:0 1em;color:#111}
table{border-collapse:collapse;margin:1em 0;width:100%%}
th,td{border:1px solid #999;padding:4px 8px;text-align:left;vertical-align:top}
th{background:#eee}
code{background:#f4f4f4;padding:0 2px}
h1{font-size:1.5em}h2{font-size:1.2em;margin-top:1.5em}
.warn{background:#fff3cd;border:1px solid #d8b400;padding:8px 12px}
</style>
</head>
<body>
<h1>Historical Ledger Quantum-Exposure Audit</h1>
<p>Pinned tree: postfiatd main <code>0085a1ff885d6a446369cf73a4430f75af22be55</code>.
Harness: <code>harness.py 1.0.0</code>. Full pack: <code>README.md</code>;
claim-to-evidence index: <code>claim_evidence_index.md</code>.</p>

<h2>Headline finding</h2>
<p>The ledger's permanently recorded history contains <strong>one</strong>
signature-bearing record class in meaningful quantity:
<strong>transactions</strong>. Validations, proposals, manifests and
payment-channel claims are <strong>not recorded in ledgers at all</strong>
&mdash; they are ephemeral. A future quantum adversary cannot harvest
them from history. What history does record, permanently and publicly,
is every transaction signature ever validated, with its public key.
Forging a key lets an adversary submit <em>new</em> transactions as the
account; it cannot rewrite validated history, which sits under the
SHA-512Half hash chain.</p>

<h2>Measured sample</h2>
<ul>
<li>Sample: %(ledgers_requested)s consecutive validated ledgers,
%(ledger_start)s to %(ledger_end)s; %(ledgers_fetched)s fetched,
%(ledgers_missing)s failed (see <code>results/fetch_log.json</code>).</li>
<li>Fetch date (UTC): %(fetch_date)s. Endpoint:
<code>%(endpoint)s</code>. Server: build %(build)s, network_id
%(network_id)s, complete_ledgers %(complete)s.</li>
<li>Transactions: <strong>%(tx_total)s</strong> in %(ledgers_with_tx)s
ledgers with transactions (%(ledgers_empty)s empty); mean %(mean_tx)s
per ledger; <strong>%(accounts)s distinct accounts</strong>.</li>
<li>Types: %(tx_types)s. Results: %(tx_results)s.</li>
<li>Signatures: <strong>%(sig_total)s total</strong>
(%(sig_single)s single-signed, %(sig_multi)s multi-signed);
by key type: %(key_types)s. Ed25519 signatures: %(ed_count)s, all
64 bytes. Classical signature bytes total: %(sig_bytes)s.</li>
<li>Chain linkage: %(links)s consecutive parent-hash links checked,
<strong>%(breaks)s breaks</strong>.</li>
<li>Entry census (first %(census_returned)s entries of ledger
%(census_ledger)s; server capped the page at 256): %(census_entries)s
entries, %(census_types)s distinct types, %(census_keys)s carrying a
public key.</li>
</ul>

<h2>Record-class inventory</h2>
<table>
<tr><th>ID</th><th>Record class</th><th>Where recorded</th><th>Scheme</th>
<th>Key type</th><th>Pubkey (B)</th><th>Signature (B)</th><th>Sampled</th></tr>
%(inv_rows)s
</table>
<p>Full evidence (file:line citations) in <code>record_inventory.md</code>
and <code>record_inventory.csv</code>.</p>

<h2>Forgeable surface (sampled counts)</h2>
<table>
<tr><th>Record class</th><th>Sampled</th><th>Unit</th>
<th>Forgeable by a quantum adversary</th></tr>
%(class_rows)s
</table>

<h2>Entry census (sampled state page)</h2>
<table>
<tr><th>LedgerEntryType</th><th>Count in census page</th></tr>
%(entry_rows)s
</table>

<h2>Mitigation verdict</h2>
<p>Full re-signing of historical transactions is <strong>not
feasible</strong>: the private keys are held by users and mostly
unavailable, and re-signing would cost ~7.58 GB of ML-DSA-65 signatures
for the extrapolated full history while leaving the classical signatures
in place. The recommended substitute is <strong>post-quantum
checkpoints</strong>: one ML-DSA-65 signature (3,309 B) over each
1,000th ledger hash &mdash; about 26.5 MB for the whole history &mdash;
plus key rotation and the live ML-DSA migration for new records.
See <code>mitigation_design.md</code> for the phased plan, costs and
open questions.</p>

<div class="warn"><strong>Limits.</strong> This is a <em>sample</em> of
recent history, not the full history (see <code>assumptions.md</code>).
Zero counts for validations, manifests, proposals and payment-channel
claims are structural &mdash; those records are not in ledgers &mdash;
not measurements of absence. The ledger was not compiled or executed.
Reproduction: <code>bash run_all.sh</code> regenerates every derived
output offline from the vendored sample; see
<code>REPRODUCTION.md</code> and the raw run log in
<code>results/run_log.txt</code>.</div>
</body>
</html>
""" % {
        "ledgers_requested": sample["ledgers_requested"],
        "ledger_start": sample["ledger_start"],
        "ledger_end": sample["ledger_end"],
        "ledgers_fetched": sample["ledgers_fetched"],
        "ledgers_missing": sample["ledgers_missing"],
        "fetch_date": esc(s["fetch_date_utc"]),
        "endpoint": esc(s["endpoint"]),
        "build": esc(server.get("build_version", "")),
        "network_id": esc(server.get("network_id", "")),
        "complete": esc(server.get("complete_ledgers", "")),
        "tx_total": tx["total"],
        "ledgers_with_tx": tx["ledgers_with_transactions"],
        "ledgers_empty": tx["ledgers_empty"],
        "mean_tx": tx["mean_tx_per_ledger"],
        "accounts": tx["distinct_accounts"],
        "tx_types": esc(json.dumps(tx["by_type"], sort_keys=True)),
        "tx_results": esc(json.dumps(tx["by_result"], sort_keys=True)),
        "sig_total": sig["total_signatures"],
        "sig_single": sig["single_signed"],
        "sig_multi": sig["multi_signed_signatures"],
        "key_types": esc(json.dumps(sig["by_key_type"], sort_keys=True)),
        "ed_count": sig["ed25519_signature_bytes"]["count"],
        "sig_bytes": sig["classical_signature_bytes_total"],
        "links": chain["consecutive_parent_hash_links_checked"],
        "breaks": chain["break_count"],
        "census_returned": sample["entry_census_returned"],
        "census_ledger": sample["entry_census_ledger"],
        "census_entries": census["entries_in_page"],
        "census_types": census["distinct_entry_types_in_page"],
        "census_keys": census["entries_carrying_public_key"],
        "inv_rows": inv_rows,
        "class_rows": class_rows,
        "entry_rows": entry_rows,
    }

    out_dir = os.path.join(PACK_DIR, "docs")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    print("build_derived.py: OK (docs/index.html)")


if __name__ == "__main__":
    main()
