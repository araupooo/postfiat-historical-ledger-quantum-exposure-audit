# Historical Ledger Quantum-Exposure Audit

What a future quantum adversary could do with the ledger's permanently
recorded history: which signature-bearing records the history actually
contains, how many of each exist in a measured sample of public ledger
data, what forging each class would let an adversary claim, and what
stays safe.

**Canonical results page: `docs/index.html`.**

## Headline finding

The ledger's permanently recorded history contains **one**
signature-bearing record class in meaningful quantity: **transactions**.
Validations, proposals, manifests and payment-channel claims are **not
recorded in ledgers at all** — they are ephemeral messages that exist
only while gossiped or held in memory. A future quantum adversary cannot
harvest them from history. What history does record, permanently and
publicly, is every transaction signature ever validated, with its
public key. Forging a key lets an adversary submit *new* transactions
as the account; it cannot rewrite validated history, which sits under
the SHA-512Half hash chain.

## Headline numbers (from `results/summary.json`)

- Sample: 500 consecutive validated ledgers, 8020940 to 8021439,
  fetched 2026-11-13T19:34:17Z from the public read-only endpoint
  `https://rpc.testnet.postfiat.org/`; 497 fetched, 3 failed
  (server closed the connection; 4 attempts each — see
  `results/fetch_log.json`).
- Transactions: **142 total** in 83 ledgers with transactions (414
  empty ledgers); mean 0.2857 per ledger; **31 distinct accounts**;
  119 Payment, 14 NFTokenMint, 9 NFTokenBurn; all `tesSUCCESS`.
- Signatures: **142 total, all single-signed, all Ed25519, all 64
  bytes**; 0 multi-signed, 0 secp256k1 in this sample (a sample
  property — both schemes are supported by the code). Classical
  signature bytes total: 9,088.
- Chain linkage: **493 consecutive parent-hash links checked, 0
  breaks** — the sampled hash chain is intact.
- Entry census (first page of ledger 8021439; server returned 256
  entries for a requested limit of 400): 240 AccountRoot,
  7 LedgerHashes, 4 NFTokenPage, 3 NFTokenOffer, 2 DirectoryNode;
  **0 entries carrying a public key**.
- Record classes inventoried: 10 (see `record_inventory.md`), with
  file:line evidence from the pinned tree for each.

## Mitigation verdict

Full re-signing of historical transactions is **not feasible**: the
private keys are held by users and mostly unavailable, and re-signing
would cost ~7.58 GB of ML-DSA-65 signatures for the extrapolated full
history while leaving the classical signatures in place. The
recommended substitute is **post-quantum checkpoints**: one ML-DSA-65
signature (3,309 B) over each 1,000th ledger hash — about 26.5 MB for
the whole history — plus key rotation and the live ML-DSA migration
for new records. See `mitigation_design.md`.

## Scanned tree

- Repository: postfiatd
- Commit: `0085a1ff885d6a446369cf73a4430f75af22be55`
  ("Merge pull request #50 from postfiatorg/hotfix/upstream-hardening-1.0.9")
- The harness records the tree's `HEAD` commit in
  `results/summary.json` (`tree_check`), so a wrong tree is
  detectable. The tree used at authoring time was a detached checkout
  at `0085a1ff`.

## Companion packs (same pinned tree)

- Crypto inventory (production signatures Ed25519 + secp256k1/ECDSA,
  0 post-quantum mentions in the tree):
  https://github.com/araupooo/postfiat-ledger-crypto-inventory-quantum-exposure-audit
- Validator key lifecycle (N=66 validators live, quorum 45/66 under
  the 67% rule, two-tier keys, manifest sequence and revocation) and
  consensus-signature migration (37 consensus-path call sites,
  ML-DSA-65 sizes, 5-phase migration, no rollback after activation):
  companion packs built on the same pinned tree. The facts used here
  are cited with file:line evidence in `record_inventory.md` and
  `sources.md`, not re-derived; no repository URL is claimed for them
  here.

## Reproduce

Requirements: Python 3.8+ (standard library only), a checkout of the
pinned tree, `git` (only to record the tree commit), `sha256sum`.

```sh
# 1. Regenerate every derived output offline from the vendored sample
#    (no network access):
./run_all.sh

# 2. Verify the digest manifest:
./verify_digests.sh --check

# 3. Re-fetch a fresh live sample instead (public read-only endpoint,
#    no credentials) — overwrites results/sample_ledger_data.json and
#    all derived outputs with a new sample:
python3 harness.py --live
./run_all.sh
```

`run_all.sh` runs `harness.py` in offline mode (regenerates
`results/summary.json`, `results/*.csv`, `results/summary.txt` from
the vendored `results/sample_ledger_data.json`), then
`build_derived.py` (regenerates `docs/index.html`), then
`verify_digests.sh` (rebuilds `SHA256SUMS`). The offline path is
deterministic: a fresh copy of the pack regenerates byte-identical
derived outputs. See `REPRODUCTION.md` for the fresh-environment
reproduction record and `results/run_log.txt` for the raw console log
of that run. Tool versions used at authoring time: Python 3.12.3,
git 2.43.0, GNU coreutils `sha256sum` (Ubuntu).

## Pack contents

| File | What it is |
|---|---|
| `docs/index.html` | Canonical results page |
| `harness.py` | Sampling harness (live fetch + offline regeneration) |
| `results/sample_ledger_data.json` | Vendored raw sample (497 ledgers + entry census page) |
| `results/fetch_log.json` | Per-request fetch outcomes, including 3 failures |
| `results/summary.json`, `results/summary.txt` | Aggregate measured results |
| `results/ledger_sample.csv` | Per-ledger records (hash chain, tx counts) |
| `results/transactions.csv` | Per-transaction signature records |
| `results/entry_type_census.csv` | Entry-type counts on the sampled state page |
| `results/record_class_counts.csv` | Per-record-class forgeable surface |
| `record_inventory.csv`, `record_inventory.md` | Record-class inventory with file:line evidence |
| `mitigation_design.md` | Checkpointing / re-signing / historical-proof design, phased plan, costs |
| `sources.md` | Primary sources |
| `assumptions.md` | Assumptions and limits — read before citing numbers |
| `claim_evidence_index.md` | Every headline claim mapped to file, field and line |
| `run_all.sh`, `verify_digests.sh`, `SHA256SUMS` | Reproduction and integrity |
| `REPRODUCTION.md` | Fresh-environment reproduction record |
| `results/run_log.txt` | Raw console log of the fresh-environment `run_all.sh` run |

## Scope and limits (read before citing the numbers)

- **A sample, not the full history.** All counts describe 500 recent
  validated ledgers. The public node retains only ~71,386 ledgers
  (~2.5 days); no full-history source was available. Full-history
  figures in `mitigation_design.md` are labelled illustrative
  extrapolations.
- **Zero counts for ephemeral classes are structural.** Validations,
  manifests, proposals and payment-channel claims score 0 because
  they are not recorded in ledgers, not because none exist.
- **No build, no run.** A full build of the ledger is not feasible on
  the audit machine (no Conan, ~1 GB RAM available). Nothing in this
  pack claims the ledger was compiled or executed.
- **No live peer connections.** The harness uses only the public
  read-only JSON-RPC endpoint. Anything about live validations or
  manifests comes from reading the code and upstream documentation.
- See `assumptions.md` for the full list.
