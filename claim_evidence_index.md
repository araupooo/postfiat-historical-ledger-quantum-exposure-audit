# Claim-to-evidence index

Every headline claim in this pack, mapped to the repo file, field, and
line that holds it. Line numbers refer to the files as published in
this repository. Pinned tree: postfiatd main commit
`0085a1ff885d6a446369cf73a4430f75af22be55`. Harness:
`harness.py` 1.0.0. Sample: 500 consecutive validated ledgers,
8020940–8021439, fetched 2026-11-13T19:34:17Z from the public
read-only endpoint `https://rpc.testnet.postfiat.org/`.

## Measured claims (from running the harness)

| # | Claim | Evidence |
|---|-------|----------|
| M-01 | Sample is 500 consecutive validated ledgers, 8020940–8021439, fetched 2026-11-13T19:34:17Z; server build 1.0.9, network_id 2025, complete_ledgers 7950054–8021439 | `results/summary.json`, `fetch_date_utc` line 21, `sample` block lines 71–80, `server_info` lines 83–88; `results/summary.txt`, lines 5–6 and 8; `results/sample_ledger_data.json` (vendored raw sample, 497 ledgers) |
| M-02 | 142 transactions total: 119 Payment, 14 NFTokenMint, 9 NFTokenBurn; all 142 `tesSUCCESS` | `results/summary.json`, `transactions.by_type` lines 117–121 and `by_result` lines 114–116, `total` line 127; `results/summary.txt`, lines 11 and 14–15; `results/transactions.csv`, 143 lines (header + 142 rows) |
| M-03 | 31 distinct transacting accounts; 0 multi-signature signer accounts | `results/summary.json`, `distinct_accounts` line 122 and `distinct_multi_signer_accounts` line 123; `results/summary.txt`, lines 12–13 |
| M-04 | 142 signatures total, all single-signed, all Ed25519, all 64 bytes; 0 secp256k1 in the sample | `results/summary.json`, `signatures` block lines 89–112 (`by_key_type` lines 90–95: ed25519 142, secp256k1 0; `ed25519_signature_bytes` lines 97–102: count 142, min/max/mean 64); `results/summary.txt`, lines 17–20; `results/transactions.csv`, every data row has `key_type` ed25519 and `signature_bytes` 64 |
| M-05 | 493 consecutive parent-hash links checked, 0 breaks — the sampled hash chain is intact | `results/summary.json`, `chain_linkage` lines 2–6; `results/summary.txt`, line 9; `docs/index.html`, line 50 |
| M-06 | Entry census (first page of ledger 8021439): 256 entries, 5 distinct types, 0 carrying a public key; 240 AccountRoot, 7 LedgerHashes, 4 NFTokenPage, 3 NFTokenOffer, 2 DirectoryNode | `results/summary.json`, `entry_census` lines 8–20 and `sample.entry_census_returned` line 75; `results/entry_type_census.csv`, 6 lines (header + 5 rows); `results/summary.txt`, lines 23–24 |
| M-07 | 3 of 500 ledger fetches failed after 4 attempts each (ledgers 8020957, 8021042, 8021222); 497 fetched | `results/fetch_log.json`, lines 128–129 (8020957 IncompleteRead), 723–724 (8021042 RemoteDisconnected), 1983–1984 (8021222 IncompleteRead); `results/summary.json`, `ledgers_fetched` line 78 and `ledgers_missing` line 79 |
| M-08 | Mean 0.2857 transactions per ledger; 83 ledgers with transactions, 414 empty | `results/summary.json`, `mean_tx_per_ledger` line 126, `ledgers_with_transactions` line 125, `ledgers_empty` line 124; `results/summary.txt`, line 11 |
| M-09 | Mean ledger close interval 3.04 s; sample spans 1,508 s of close time (847912152 to 847913660) | `results/ledger_sample.csv`, line 2 (first ledger close_time 847912152) and line 498 (last ledger close_time 847913660); `mitigation_design.md`, lines 197–199 (cost table) |
| M-10 | Classical signature bytes in the sample total 9,088 (142 × 64 B) | `results/summary.json`, `classical_signature_bytes_total` line 96; `results/summary.txt`, line 21 |
| M-11 | The harness ran against the pinned tree: `tree_head_commit` equals the pinned commit | `results/summary.json`, `tree_check` lines 130–133 (`tree_head_commit` `0085a1ff...`, `tree_head_matches_pinned` `true`) |
| M-12 | The public node retains 71,386 ledgers (7950054–8021439), about 2.5 days at the measured close interval | `results/summary.json`, `complete_ledgers` line 85 (7950054–8021439; 8021439 − 7950054 + 1 = 71,386); `mitigation_design.md`, lines 197–202 (cost table) and lines 124–125 |

## Source-derived claims (from the pinned tree and primary sources)

| # | Claim | Evidence |
|---|-------|----------|
| S-01 | Validations are secp256k1-only by construction, and are kept only in memory — they are not recorded in any ledger | Pinned tree: `include/xrpl/protocol/STValidation.h`, lines 249–250 (signing gate) and 201–209 (deserialization gate); `src/libxrpl/protocol/STValidation.cpp`, lines 72–73 (`sfSigningPubKey`/`sfSignature` REQUIRED) and 123–146 (`isValid()`); `src/xrpld/consensus/Validations.h`, line 306 (`current_` in-memory map) and lines 315–323 (aged in-memory maps). Cited in `record_inventory.md`, lines 127–153; `record_inventory.csv`, line 7 (R-06) |
| S-02 | Single-signed transactions are verified by `checkSingleSign` over `txSign`-prefixed data; key type is dispatched from the 33-byte serialized key (`0xED` = Ed25519, `0x02`/`0x03` = secp256k1) | Pinned tree: `src/libxrpl/protocol/STTx.cpp`, lines 452 (`checkSingleSign`), 415 (`singleSignHelper`), 188–199 (`getSigningData`/`getSigningHash`); `include/xrpl/protocol/HashPrefix.h`, line 72 (`txSign`); `src/libxrpl/protocol/PublicKey.cpp`, lines 224–236 (`publicKeyType`). Cited in `record_inventory.md`, lines 22–61; `record_inventory.csv`, line 2 (R-01) |
| S-03 | Multi-signed transactions carry a `Signers` array of Account + SigningPubKey + TxnSignature, verified over `txMultiSign`-prefixed data; a transaction cannot be both single- and multi-signed | Pinned tree: `src/libxrpl/protocol/STTx.cpp`, lines 581 (`checkMultiSign`) and 420–425 (single + multi forbidden); `src/libxrpl/protocol/Sign.cpp`, lines 96–107 (`buildMultiSigningData`); `include/xrpl/protocol/HashPrefix.h`, line 75 (`txMultiSign`); `src/libxrpl/protocol/InnerObjectFormats.cpp`, lines 39–45 (`sfSigner`). Cited in `record_inventory.md`, lines 62–81; `record_inventory.csv`, line 3 (R-02) |
| S-04 | A manifest is verified by two signatures (ephemeral + master) under the `MAN` prefix; sequence `0xFFFFFFFF` is a permanent revocation of the master key | Pinned tree: `src/xrpld/app/misc/detail/Manifest.cpp`, lines 196–213 (`verify()`), 236–240 (`revoked()`), 62–81 (format); `include/xrpl/protocol/HashPrefix.h`, line 84 (`manifest`). Cited in `record_inventory.md`, lines 167–189; `record_inventory.csv`, line 9 (R-08) |
| S-05 | The ledger hash is SHA-512Half over the `ledgerMaster` prefix plus sequence, drops, parent/transaction/account hashes and close times; the header carries no signature | Pinned tree: `src/xrpld/app/ledger/Ledger.cpp`, lines 54–71 (`calculateLedgerHash`); `include/xrpl/protocol/HashPrefix.h`, line 69 (`ledgerMaster`); `src/libxrpl/protocol/LedgerHeader.cpp`, lines 28–41 (`addRaw`). Cited in `record_inventory.md`, lines 190–207; `record_inventory.csv`, line 10 (R-09) |
| S-06 | The tree defines 30 ledger entry types; no entry carries a signature field; the only public-key field in any entry is `ltPAYCHAN sfPublicKey` | Pinned tree: `include/xrpl/protocol/detail/ledger_entries.macro`, lines 45–559 (30 entry types) and line 375 (`ltPAYCHAN sfPublicKey`); `src/libxrpl/protocol/LedgerFormats.cpp`, lines 32–36 (common fields are only `LedgerEntryType` + `Flags`). Cited in `record_inventory.md`, lines 208–233; `record_inventory.csv`, line 11 (R-10) |
| S-07 | An account address is RIPEMD-160(SHA-256(public key)), so a never-transacting account's public key is hidden behind a 160-bit hash | Pinned tree: `src/libxrpl/protocol/AccountID.cpp`, lines 168 (`calcAccountID`) and 145–146 (comment: "SHA256 followed by RIPEMD160 for account IDs"). Cited in `record_inventory.md`, lines 52–61 and 234–252 |
| S-08 | A payment-channel claim is an off-ledger signed message (`CLM\0` + channel + amount), verified at redemption against the channel's public key | Pinned tree: `src/xrpld/app/tx/detail/PayChan.cpp`, lines 469–486 (claim verification) and 103–108 (CLM message format); `include/xrpl/protocol/HashPrefix.h`, line 87 (`paymentChannelClaim`). Cited in `record_inventory.md`, lines 109–126; `record_inventory.csv`, line 6 (R-05) |
| S-09 | ML-DSA sizes are FIPS 204 Table 2: ML-DSA-44 1,312 B pk / 2,420 B sig; ML-DSA-65 1,952 B / 3,309 B; ML-DSA-87 2,592 B / 4,627 B | NIST FIPS 204, Tables 1–2; documented in `sources.md`, "Standards"; used in `mitigation_design.md`, lines 63–64 and 208–212 |
| S-10 | Validation quorum is 67% in postfiatd (45 of 66 validators) vs 80% upstream | Pinned tree: `src/xrpld/app/misc/detail/ValidatorList.cpp`, lines 1898–1900 (67% quorum comment, "Original XRPL uses 80%"); 45 = ceil(66 × 0.67). Amendment threshold 67/100 is `include/xrpl/protocol/SystemParameters.h`, line 85. Cited in `record_inventory.md`, lines 150–151; `mitigation_design.md`, lines 154–155 |
| S-11 | Consensus proposals are capped at 72-byte signatures and verified via `verifyDigest` over the `PRP`-prefixed signing hash | Pinned tree: `src/xrpld/app/consensus/RCLCxPeerPos.cpp`, lines 37–44 (72-byte cap) and 48–51 (`checkSign`); `include/xrpl/protocol/HashPrefix.h`, line 81 (`proposal`). Cited in `record_inventory.md`, lines 154–166; `record_inventory.csv`, line 8 (R-07) |
| S-12 | Cross-chain attestations carry a public key and a signature inside the transaction; `sfSignatureReward` is an amount, not a signature | Pinned tree: `src/libxrpl/protocol/InnerObjectFormats.cpp`, lines 84–110 (attestation collection element); `src/libxrpl/protocol/XChainAttestations.cpp`, line 111; `include/xrpl/protocol/detail/sfields.macro`, line 284 (`sfSignatureReward`, type `AMOUNT`). Cited in `record_inventory.md`, lines 95–108 and 225–233; `record_inventory.csv`, lines 5 and 11 (R-04, R-10) |
| S-13 | Batch transactions are verified per batch signer (`checkBatchSign` → single/multi) over `batch`-prefixed data | Pinned tree: `src/libxrpl/protocol/STTx.cpp`, lines 300 (`checkBatchSign`), 314 (`sfBatchSigners`), 463 (`checkBatchSingleSign`), 555 (`checkBatchMultiSign`); `include/xrpl/protocol/HashPrefix.h`, line 93 (`batch`). Cited in `record_inventory.md`, lines 82–94; `record_inventory.csv`, line 4 (R-03) |

## Design judgements (not measurements)

| # | Claim | Evidence |
|---|-------|----------|
| D-01 | Full re-signing of historical transactions is not feasible: the private keys are unavailable, and re-signing would not remove the classical signatures | `mitigation_design.md`, section 1, lines 27–57. This is a judgement from the measured sample and the key-ownership facts in S-02/S-07. |
| D-02 | Post-quantum checkpoints (one ML-DSA-65 signature per 1,000th ledger hash) are the recommended substitute: ~26.5 MB for the whole history, ~265 MB at every 100 ledgers | `mitigation_design.md`, section 2, lines 63–64 (options table) and Phase 2, lines 103–145; cost table lines 211–212. The 26.5 MB figure is exact arithmetic (8,021 × 3,309 B); the ledger count is the validated ledger at fetch time (M-01). |
| D-03 | No protocol rollback exists after the activation amendment enables; recovery is forward-only | `mitigation_design.md`, Phase 3, lines 146–168, and section 5, lines 227–243; the amendment mechanism has no disable path for enabled amendments (see the companion consensus migration pack). |

## What is NOT claimed (limits)

- No claim that validations, manifests, proposals or payment-channel
  claims do not exist — only that they are not recorded in ledgers
  and therefore cannot be counted from ledger data (A3 in
  `assumptions.md`).
- No claim about the full history: every count is a sample of 500
  recent ledgers (M-01; A1–A2). The 2.29M-transaction / 7.58 GB
  full-history figures are labelled illustrative extrapolations
  (`mitigation_design.md`, lines 214–225; A11).
- No claim that any secp256k1 transaction signature was measured —
  none occurred in the sample (M-04; A4, A8).
- No claim that the ledger was compiled or executed — it was not
  (A6).
- No claim about live peer-network behaviour — no peer connection was
  made (A7).
- No claim about when a cryptographically relevant quantum computer
  will exist (A9).
- No claim about credential signing: the `credential` hash prefix
  exists but no signing use was found (A10).

## Reproduction

Run `bash run_all.sh` from a fresh copy of this repository: it re-runs
the harness in offline mode from the vendored sample, rebuilds
`docs/index.html`, regenerates `SHA256SUMS`, and verifies digests.
Expected: exit 0, all derived outputs byte-identical to the shipped
files. See `REPRODUCTION.md` for the exact command and recorded
result, and `results/run_log.txt` for the raw console log of the
fresh-environment run. Verify digests at any time with
`bash verify_digests.sh --check`.
