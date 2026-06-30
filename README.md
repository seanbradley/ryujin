# RYUJIN

A doctrine-bound, self-organizing counter-swarm architecture - a pre-abstract
working repository for a DARPA DICE (Decentralized AI through Controlled
Emergence) TA1 + TA2 proposal.

## What this is

RYUJIN proposes a per-agent **local adaptor** that couples:

- **TA1** - leaderless, stigmergic coordination with Byzantine-resilient context
  fusion (CrossMax / Krum / FLTrust), reputation, and slashing; and
- **TA2** - an inviolable per-agent mission constitution, inference-time role
  control, drift detection, and a conservation/debt ledger,

joined by a single measurable quantity, the **coherence horizon**, which the TA2
controller publishes and the TA1 planner uses to bound distributed planning
depth. The adaptor is replicated identically at every node. There is no central
orchestrator.

The name is a single light hook: Ryujin is the sea sovereign whose disciplined
servants break the coherence of the adversary's cheap, dense, leaderless
"jellyfish" drone swarm. All components are named in plain operational English.

## Layout

| Path | Contents |
|---|---|
| `RYUJIN.md` | The full solution document: architecture, diagrams, algorithm, attack/mitigation analysis, schedule, risks, references |
| `docs/` | Supporting drafts (abstract, gap-and-teaming memo, technical white paper) |
| `poc/` | Proof-of-concept simulation scaffold (pending) |

## Status

Pre-abstract. Not for submission in its current form.
