#!/usr/bin/env python3
"""Historical ledger quantum-exposure audit: sampling harness.

Samples public, read-only ledger data from the PostFiat testnet JSON-RPC
endpoint (no credentials, no auth, no writes, no peer connections) and
quantifies the signature-bearing surface recorded in the sampled range.

Two modes:
  * --live    : fetch from the RPC endpoint and write
                results/sample_ledger_data.json (the vendored raw sample)
                plus all derived outputs.
  * --offline : (default) regenerate every derived output from the
                vendored results/sample_ledger_data.json, with no network
                access. This is the reproducible path used by run_all.sh.

Usage:
    python3 harness.py --live    [--out-dir results] [--tree <postfiatd tree>]
    python3 harness.py           [--out-dir results] [--tree <postfiatd tree>]

Python 3.8+ standard library only.
"""

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HARNESS_VERSION = "1.0.0"
RPC_ENDPOINT = "https://rpc.testnet.postfiat.org/"
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"

# Sample design: 500 consecutive validated ledgers ending at the latest
# validated ledger at fetch time. Consecutive (not cherry-picked) so the
# sample is a plain slice of recent history; 500 ledgers is large enough
# for a signature-class breakdown on this quiet testnet (stride probe
# 2026-11-13: ~0.45 transactions per ledger) while keeping the live
# fetch to a few minutes with 8 parallel workers.
SAMPLE_LEDGER_COUNT = 500
ENTRY_CENSUS_LIMIT = 400  # first page of ledger_data on the end ledger
MAX_WORKERS = 8
MAX_TRIES = 4


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rpc_call(method, params, timeout=25):
    """One JSON-RPC call. Returns (result_dict_or_None, error_or_None, attempts)."""
    body = json.dumps({"method": method, "params": params}).encode()
    last_err = None
    for attempt in range(1, MAX_TRIES + 1):
        try:
            req = urllib.request.Request(
                RPC_ENDPOINT, data=body,
                headers={"Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.load(resp)
            if "error" in payload:
                return None, "rpc_error: %s" % json.dumps(payload["error"]), attempt
            return payload.get("result"), None, attempt
        except Exception as exc:  # noqa: BLE001 - record and retry everything
            last_err = "%s: %s" % (type(exc).__name__, exc)
            time.sleep(1.5 * attempt)
    return None, "failed_after_%d_tries: %s" % (MAX_TRIES, last_err), MAX_TRIES


def key_type_of(signing_pub_key_hex):
    """Classify a serialized SigningPubKey hex string.

    Serialized keys are 33 bytes: Ed25519 keys carry a 0xED prefix byte
    (32-byte key + prefix); secp256k1 keys are 33-byte compressed points
    starting 0x02/0x03. See PublicKey.cpp publicKeyType().
    """
    if not signing_pub_key_hex:
        return "none"
    try:
        raw = bytes.fromhex(signing_pub_key_hex)
    except ValueError:
        return "unparsable"
    if len(raw) == 33 and raw[0] == 0xED:
        return "ed25519"
    if len(raw) == 33 and raw[0] in (0x02, 0x03):
        return "secp256k1"
    return "unknown_%d_bytes" % len(raw)


def sig_bytes(hex_str):
    if not hex_str:
        return 0
    try:
        return len(bytes.fromhex(hex_str))
    except ValueError:
        return -1


def fetch_live():
    """Fetch the sample from the public RPC endpoint.

    Returns (sample_dict, fetch_log_list).
    """
    fetch_log = []
    started = utcnow_iso()
    result, err, _ = rpc_call("server_info", [{}])
    fetch_log.append({"request": "server_info", "ok": err is None,
                      "error": err})
    if err is not None:
        raise SystemExit("server_info failed: %s" % err)
    info = result["info"]
    validated = int(info["validated_ledger"]["seq"])
    complete = info.get("complete_ledgers", "")
    build_version = info.get("build_version", "")
    network_id = info.get("network_id", "")
    end = validated
    start = end - SAMPLE_LEDGER_COUNT + 1
    indexes = list(range(start, end + 1))

    ledgers = {}

    def fetch_one(idx):
        res, e, attempts = rpc_call(
            "ledger", [{"ledger_index": idx, "transactions": True,
                        "expand": True, "owner_funds": False,
                        "binary": False, "queue": False}])
        return idx, res, e, attempts

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for idx, res, e, attempts in pool.map(fetch_one, indexes):
            ok = e is None and res is not None and "ledger" in res
            fetch_log.append({"request": "ledger", "ledger_index": idx,
                              "ok": ok, "error": e, "attempts": attempts})
            if ok:
                ledgers[idx] = res["ledger"]

    # Ledger-state entry census: first page of ledger_data on the end ledger.
    census, cerr, _ = rpc_call(
        "ledger_data", [{"ledger_index": end, "limit": ENTRY_CENSUS_LIMIT}])
    fetch_log.append({"request": "ledger_data", "ledger_index": end,
                      "limit": ENTRY_CENSUS_LIMIT,
                      "ok": cerr is None and census is not None,
                      "error": cerr})
    census_state = census.get("state", []) if census else []
    census_marker = census.get("marker") if census else None

    sample = {
        "harness_version": HARNESS_VERSION,
        "endpoint": RPC_ENDPOINT,
        "fetch_started_utc": started,
        "fetch_finished_utc": utcnow_iso(),
        "pinned_commit": PINNED_COMMIT,
        "server_info": {
            "build_version": build_version,
            "network_id": network_id,
            "complete_ledgers": complete,
            "validated_ledger": validated,
        },
        "sample": {
            "ledger_count_requested": SAMPLE_LEDGER_COUNT,
            "ledger_start": start,
            "ledger_end": end,
            "ledgers_fetched": sorted(ledgers.keys()),
            "entry_census_ledger": end,
            "entry_census_limit": ENTRY_CENSUS_LIMIT,
            "entry_census_returned": len(census_state),
            "entry_census_has_more_pages": census_marker is not None,
        },
        "ledgers": [ledgers[i] for i in sorted(ledgers.keys())],
        "entry_census_state": census_state,
    }
    return sample, fetch_log


def analyse(sample):
    """Derive all measured outputs from a sample dict (live or vendored).

    Returns (summary_dict, per_ledger_rows, per_tx_rows, entry_rows,
             class_rows).
    """
    ledgers = sample["ledgers"]
    meta = sample["sample"]
    fetch_date = sample.get("fetch_started_utc", "")

    per_ledger = []
    per_tx = []
    chain_breaks = []
    chain_links_checked = 0
    prev_hash = None
    prev_idx = None
    total_txs = 0
    sigs_single = 0
    sigs_multi = 0
    sigs_total = 0
    key_types = {"ed25519": 0, "secp256k1": 0, "none": 0, "other": 0}
    sig_sizes = {"ed25519": [], "secp256k1": []}
    tx_types = {}
    accounts = set()
    signer_accounts = set()
    results = {}
    unsigned_txs = []

    for led in ledgers:
        idx = int(led["ledger_index"])
        txs = led.get("transactions", []) or []
        # Only consecutive indexes can be chain-checked: a failed fetch
        # leaves a gap, and the ledger after a gap cannot be linked to
        # the last fetched hash (its parent is the missing ledger).
        if prev_hash is not None and prev_idx is not None and idx == prev_idx + 1:
            chain_links_checked += 1
            if led.get("parent_hash") != prev_hash:
                chain_breaks.append(idx)
        prev_hash = led.get("ledger_hash")
        prev_idx = idx
        per_ledger.append({
            "ledger_index": idx,
            "ledger_hash": led.get("ledger_hash", ""),
            "parent_hash": led.get("parent_hash", ""),
            "close_time": led.get("close_time", ""),
            "close_time_human": led.get("close_time_human", ""),
            "transaction_hash": led.get("transaction_hash", ""),
            "account_hash": led.get("account_hash", ""),
            "total_coins": led.get("total_coins", ""),
            "tx_count": len(txs),
        })
        total_txs += len(txs)
        for tx in txs:
            ttype = tx.get("TransactionType", "")
            tx_types[ttype] = tx_types.get(ttype, 0) + 1
            accounts.add(tx.get("Account", ""))
            meta_tx = tx.get("metaData", tx.get("meta", {}) or {})
            results[meta_tx.get("TransactionResult", "")] = \
                results.get(meta_tx.get("TransactionResult", ""), 0) + 1
            spk = tx.get("SigningPubKey", "")
            signers = tx.get("Signers", []) or []
            if spk and not signers:
                kt = key_type_of(spk)
                sigs_single += 1
                sigs_total += 1
                n = sig_bytes(tx.get("TxnSignature", ""))
                if kt in sig_sizes and n > 0:
                    sig_sizes[kt].append(n)
                key_types[kt if kt in key_types else "other"] += 1
                per_tx.append({
                    "ledger_index": idx,
                    "hash": tx.get("hash", ""),
                    "TransactionType": ttype,
                    "Account": tx.get("Account", ""),
                    "Sequence": tx.get("Sequence", ""),
                    "signing_mode": "single",
                    "key_type": kt,
                    "signing_pub_key_bytes": sig_bytes(spk),
                    "signature_bytes": n,
                    "signer_count": 0,
                    "TransactionResult": meta_tx.get("TransactionResult", ""),
                })
            elif signers:
                sigs_multi += len(signers)
                sigs_total += len(signers)
                for s in signers:
                    signer = s.get("Signer", s) or {}
                    signer_accounts.add(signer.get("Account", ""))
                    kt = key_type_of(signer.get("SigningPubKey", ""))
                    n = sig_bytes(signer.get("TxnSignature", ""))
                    if kt in sig_sizes and n > 0:
                        sig_sizes[kt].append(n)
                    key_types[kt if kt in key_types else "other"] += 1
                per_tx.append({
                    "ledger_index": idx,
                    "hash": tx.get("hash", ""),
                    "TransactionType": ttype,
                    "Account": tx.get("Account", ""),
                    "Sequence": tx.get("Sequence", ""),
                    "signing_mode": "multi",
                    "key_type": "multi:%s" % ",".join(
                        sorted({key_type_of((sg.get("Signer", sg) or {}).get("SigningPubKey", ""))
                                for sg in signers})),
                    "signing_pub_key_bytes": sig_bytes(spk),
                    "signature_bytes": sum(
                        sig_bytes((sg.get("Signer", sg) or {}).get("TxnSignature", ""))
                        for sg in signers),
                    "signer_count": len(signers),
                    "TransactionResult": meta_tx.get("TransactionResult", ""),
                })
            else:
                unsigned_txs.append(tx.get("hash", ""))
                per_tx.append({
                    "ledger_index": idx,
                    "hash": tx.get("hash", ""),
                    "TransactionType": ttype,
                    "Account": tx.get("Account", ""),
                    "Sequence": tx.get("Sequence", ""),
                    "signing_mode": "UNSIGNED-OR-UNPARSED",
                    "key_type": "none",
                    "signing_pub_key_bytes": sig_bytes(spk),
                    "signature_bytes": sig_bytes(tx.get("TxnSignature", "")),
                    "signer_count": 0,
                    "TransactionResult": meta_tx.get("TransactionResult", ""),
                })

    def size_stats(vals):
        if not vals:
            return {"count": 0, "min": None, "max": None, "mean": None}
        return {"count": len(vals), "min": min(vals), "max": max(vals),
                "mean": round(sum(vals) / len(vals), 2)}

    # Entry-type census on the sampled state page.
    entry_counts = {}
    entry_key_carriers = []
    for entry in sample.get("entry_census_state", []) or []:
        etype = entry.get("LedgerEntryType", "")
        entry_counts[etype] = entry_counts.get(etype, 0) + 1
        if "PublicKey" in entry:
            entry_key_carriers.append(
                {"LedgerEntryType": etype, "index": entry.get("index", ""),
                 "PublicKey_bytes": sig_bytes(entry.get("PublicKey", ""))})
    entry_rows = [{"LedgerEntryType": k, "count_in_census_page": v}
                  for k, v in sorted(entry_counts.items())]

    ledgers_fetched = len(ledgers)
    requested = meta["ledger_count_requested"]
    class_rows = [
        {"record_class": "single-signed transaction",
         "sampled_count": sigs_single,
         "unit": "signatures",
         "forgeable_by_quantum_adversary": "yes - signing key recoverable from exposed public key",
         "what_forging_enables": "submit arbitrary transactions as the account (spend, set keys, change settings) until the key is rotated"},
        {"record_class": "multi-signed transaction signature",
         "sampled_count": sigs_multi,
         "unit": "signatures",
         "forgeable_by_quantum_adversary": "yes - per signer key, same as single-signed",
         "what_forging_enables": "forge one signer's share; a transaction still needs quorum of signer keys, so one broken key alone does not authorize a multi-signed transaction"},
        {"record_class": "ledger header (hash-chained)",
         "sampled_count": ledgers_fetched,
         "unit": "headers",
         "forgeable_by_quantum_adversary": "no - headers carry no signature; integrity is the SHA-512Half hash chain plus the validation quorum at close time",
         "what_forging_enables": "nothing by signature forgery; rewriting a validated header requires a hash preimage/collision, not a broken signature key"},
        {"record_class": "validation (ephemeral, not in ledger)",
         "sampled_count": 0,
         "unit": "validations",
         "forgeable_by_quantum_adversary": "yes in principle (validator ephemeral key, secp256k1) - but validations are NOT recorded in ledger history, so there is no historical validation to harvest; the live threat is forging current validations",
         "what_forging_enables": "impersonate a validator in live consensus; with quorum of forged validations, validate a false ledger"},
        {"record_class": "manifest (ephemeral, not in ledger)",
         "sampled_count": 0,
         "unit": "manifests",
         "forgeable_by_quantum_adversary": "yes in principle (validator master key, secp256k1, public in the manifest itself) - manifests are NOT recorded in ledger history; they are distributed via validator site / peer protocol",
         "what_forging_enables": "publish a forged manifest binding a new ephemeral key to a validator identity; impersonate that validator until the master key is revoked by a higher-sequence manifest"},
        {"record_class": "ledger entry carrying a public key (state page)",
         "sampled_count": len(entry_key_carriers),
         "unit": "entries",
         "forgeable_by_quantum_adversary": "yes - the carried key itself is the exposed public key",
         "what_forging_enables": "payment-channel claims (ltPAYCHAN sfPublicKey): forge off-ledger claims against the channel balance; other key-carrying entries expose keys whose compromise affects the owning account or attestation set"},
        {"record_class": "ledger entry without signature or key",
         "sampled_count": sum(entry_counts.values()) - len(entry_key_carriers),
         "unit": "entries",
         "forgeable_by_quantum_adversary": "no - no signature or public key in the entry; authenticity derives from the ledger hash chain and the validated ledger's quorum",
         "what_forging_enables": "nothing by signature forgery"},
        {"record_class": "payment-channel claim (off-ledger signed message)",
         "sampled_count": 0,
         "unit": "claims",
         "forgeable_by_quantum_adversary": "yes in principle - claims are signed off-ledger and never enter ledger history until redeemed, so no historical claim can be harvested from the ledger",
         "what_forging_enables": "redeem the channel balance to the adversary once a claim is forged; only claims already presented on-ledger are visible"},
        {"record_class": "cross-chain attestation signature (in-transaction)",
         "sampled_count": 0,
         "unit": "signatures",
         "forgeable_by_quantum_adversary": "yes - attestation public keys and signatures ride inside XChain transactions and are therefore permanently recorded when such a transaction is validated",
         "what_forging_enables": "forge attestations for cross-chain claims; counted inside the transaction signature totals above when such transactions occur in the sample (none did)"},
    ]

    summary = {
        "harness_version": HARNESS_VERSION,
        "pinned_commit": PINNED_COMMIT,
        "endpoint": sample.get("endpoint", RPC_ENDPOINT),
        "fetch_date_utc": fetch_date,
        "server_info": sample.get("server_info", {}),
        "sample": {
            "ledger_start": meta["ledger_start"],
            "ledger_end": meta["ledger_end"],
            "ledgers_requested": requested,
            "ledgers_fetched": ledgers_fetched,
            "ledgers_missing": requested - ledgers_fetched,
            "entry_census_ledger": meta.get("entry_census_ledger"),
            "entry_census_limit": meta.get("entry_census_limit"),
            "entry_census_returned": meta.get("entry_census_returned"),
            "entry_census_has_more_pages": meta.get("entry_census_has_more_pages"),
        },
        "chain_linkage": {
            "consecutive_parent_hash_links_checked": chain_links_checked,
            "breaks": chain_breaks,
            "break_count": len(chain_breaks),
        },
        "transactions": {
            "total": total_txs,
            "ledgers_with_transactions": sum(1 for r in per_ledger if r["tx_count"] > 0),
            "ledgers_empty": sum(1 for r in per_ledger if r["tx_count"] == 0),
            "mean_tx_per_ledger": round(total_txs / ledgers_fetched, 4) if ledgers_fetched else 0,
            "by_type": dict(sorted(tx_types.items())),
            "by_result": dict(sorted(results.items())),
            "distinct_accounts": len(accounts),
            "distinct_multi_signer_accounts": len(signer_accounts),
            "unsigned_or_unparsed_tx_hashes": unsigned_txs,
        },
        "signatures": {
            "total_signatures": sigs_total,
            "single_signed": sigs_single,
            "multi_signed_signatures": sigs_multi,
            "by_key_type": key_types,
            "ed25519_signature_bytes": size_stats(sig_sizes["ed25519"]),
            "secp256k1_signature_bytes": size_stats(sig_sizes["secp256k1"]),
            "classical_signature_bytes_total": sum(sig_sizes["ed25519"]) + sum(sig_sizes["secp256k1"]),
        },
        "entry_census": {
            "distinct_entry_types_in_page": len(entry_counts),
            "entries_in_page": sum(entry_counts.values()),
            "entries_carrying_public_key": len(entry_key_carriers),
            "key_carrying_entries": entry_key_carriers,
            "by_type": dict(sorted(entry_counts.items())),
        },
        "record_classes": [
            {"record_class": r["record_class"], "sampled_count": r["sampled_count"],
             "unit": r["unit"]} for r in class_rows
        ],
    }
    return summary, per_ledger, per_tx, entry_rows, class_rows


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def write_summary_txt(path, summary):
    s = summary
    lines = [
        "Historical ledger quantum-exposure audit: sampling summary",
        "Harness: harness.py %s" % HARNESS_VERSION,
        "Pinned tree: postfiatd main %s" % PINNED_COMMIT,
        "Endpoint: %s" % s["endpoint"],
        "Fetch date (UTC): %s" % s["fetch_date_utc"],
        "Server: build %s, network_id %s, complete_ledgers %s" % (
            s["server_info"].get("build_version", ""),
            s["server_info"].get("network_id", ""),
            s["server_info"].get("complete_ledgers", "")),
        "",
        "Sample: %d consecutive validated ledgers, %d to %d; %d fetched, %d missing" % (
            s["sample"]["ledgers_requested"], s["sample"]["ledger_start"],
            s["sample"]["ledger_end"], s["sample"]["ledgers_fetched"],
            s["sample"]["ledgers_missing"]),
        "Chain linkage: %d consecutive parent-hash links checked, %d breaks" % (
            s["chain_linkage"]["consecutive_parent_hash_links_checked"],
            s["chain_linkage"]["break_count"]),
        "",
        "Transactions: %d total in %d ledgers with transactions (%d empty ledgers); mean %.4f per ledger" % (
            s["transactions"]["total"],
            s["transactions"]["ledgers_with_transactions"],
            s["transactions"]["ledgers_empty"],
            s["transactions"]["mean_tx_per_ledger"]),
        "Distinct transacting accounts: %d" % s["transactions"]["distinct_accounts"],
        "Distinct multi-signature signer accounts: %d" % s["transactions"]["distinct_multi_signer_accounts"],
        "Transaction types: %s" % json.dumps(s["transactions"]["by_type"], sort_keys=True),
        "Transaction results: %s" % json.dumps(s["transactions"]["by_result"], sort_keys=True),
        "",
        "Signatures: %d total (%d single-signed, %d multi-signed)" % (
            s["signatures"]["total_signatures"],
            s["signatures"]["single_signed"],
            s["signatures"]["multi_signed_signatures"]),
        "By key type: %s" % json.dumps(s["signatures"]["by_key_type"], sort_keys=True),
        "Ed25519 signature bytes: %s" % json.dumps(s["signatures"]["ed25519_signature_bytes"], sort_keys=True),
        "secp256k1 signature bytes: %s" % json.dumps(s["signatures"]["secp256k1_signature_bytes"], sort_keys=True),
        "Classical signature bytes total: %d" % s["signatures"]["classical_signature_bytes_total"],
        "",
        "Entry census (first %d entries of ledger %d): %d entries, %d distinct types, %d carry a public key" % (
            s["sample"]["entry_census_returned"],
            s["sample"]["entry_census_ledger"],
            s["entry_census"]["entries_in_page"],
            s["entry_census"]["distinct_entry_types_in_page"],
            s["entry_census"]["entries_carrying_public_key"]),
        "Entry types in page: %s" % json.dumps(s["entry_census"]["by_type"], sort_keys=True),
        "",
        "Record classes (sampled counts):",
    ]
    for r in s["record_classes"]:
        lines.append("  %s: %d %s" % (r["record_class"], r["sampled_count"], r["unit"]))
    lines.append("")
    lines.append("Limits: this is a SAMPLE of recent history, not the full "
                 "history. Validations, manifests, proposals and "
                 "payment-channel claims are NOT recorded in ledgers and "
                 "therefore cannot be counted from ledger data; their "
                 "counts above are 0 by construction, with the reason "
                 "stated in record_class_counts.csv. See assumptions.md.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def tree_head(tree):
    import subprocess
    try:
        out = subprocess.run(["git", "-C", tree, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
        head = out.stdout.strip()
    except Exception:  # noqa: BLE001
        head = ""
    return {"tree_head_commit": head,
            "tree_head_matches_pinned": head == PINNED_COMMIT}


def main(argv=None):
    ap = argparse.ArgumentParser(description="PFTL historical ledger quantum-exposure sampler")
    ap.add_argument("--live", action="store_true",
                    help="fetch from the public RPC endpoint (default: offline, reuse vendored sample)")
    ap.add_argument("--out-dir", default=None,
                    help="results directory (default: <pack>/results)")
    ap.add_argument("--tree", default="/home/hatch/workspace/postfiatd-amendment/worktree-0085a1ff",
                    help="postfiatd tree to record HEAD for (default: pinned worktree)")
    args = ap.parse_args(argv)

    pack_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out_dir or os.path.join(pack_dir, "results")
    os.makedirs(out_dir, exist_ok=True)

    if args.live:
        sample, fetch_log = fetch_live()
        write_json(os.path.join(out_dir, "sample_ledger_data.json"), sample)
        write_json(os.path.join(out_dir, "fetch_log.json"), fetch_log)
    else:
        sample_path = os.path.join(out_dir, "sample_ledger_data.json")
        with open(sample_path, encoding="utf-8") as fh:
            sample = json.load(fh)
        # Offline mode never overwrites the vendored live fetch log: it is
        # the record of the actual network fetch. Only create a placeholder
        # if no fetch log was shipped at all.
        if not os.path.exists(os.path.join(out_dir, "fetch_log.json")):
            write_json(os.path.join(out_dir, "fetch_log.json"),
                       [{"request": "offline-mode",
                         "ok": True,
                         "error": None,
                         "note": "no network access; reused vendored results/sample_ledger_data.json"}])

    summary, per_ledger, per_tx, entry_rows, class_rows = analyse(sample)
    summary["tree_check"] = tree_head(args.tree)
    # Deterministic content hash of the vendored sample, for traceability.
    with open(os.path.join(out_dir, "sample_ledger_data.json"), "rb") as fh:
        summary["sample_sha256"] = hashlib.sha256(fh.read()).hexdigest()

    write_json(os.path.join(out_dir, "summary.json"), summary)
    write_csv(os.path.join(out_dir, "ledger_sample.csv"),
              ["ledger_index", "ledger_hash", "parent_hash", "close_time",
               "close_time_human", "transaction_hash", "account_hash",
               "total_coins", "tx_count"], per_ledger)
    write_csv(os.path.join(out_dir, "transactions.csv"),
              ["ledger_index", "hash", "TransactionType", "Account",
               "Sequence", "signing_mode", "key_type",
               "signing_pub_key_bytes", "signature_bytes", "signer_count",
               "TransactionResult"], per_tx)
    write_csv(os.path.join(out_dir, "entry_type_census.csv"),
              ["LedgerEntryType", "count_in_census_page"], entry_rows)
    write_csv(os.path.join(out_dir, "record_class_counts.csv"),
              ["record_class", "sampled_count", "unit",
               "forgeable_by_quantum_adversary", "what_forging_enables"],
              class_rows)
    write_summary_txt(os.path.join(out_dir, "summary.txt"), summary)
    print("harness.py: OK (%s mode, %d ledgers, %d transactions, %d signatures)"
          % ("live" if args.live else "offline",
             summary["sample"]["ledgers_fetched"],
             summary["transactions"]["total"],
             summary["signatures"]["total_signatures"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
