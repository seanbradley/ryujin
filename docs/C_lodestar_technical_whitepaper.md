# LODESTAR: Contract-Bounded Inference Control and Bounded Stigmergic

# Coordination for Controlled Emergence

> Technical white paper extracting the Duchaine System / STYG-ENGINE control
> kernel into a formal DICE TA1+TA2 local-adaptor specification.
> Companion to the abstract draft (A) and teaming memo (B).
> All claims here are research hypotheses, not validated results.

## 0. One-paragraph summary

LODESTAR is a per-agent **local adaptor** with two layers. A **doctrine layer**
(TA2) holds inviolable role/mission invariants and enforces them at inference
time, surfacing infeasibility instead of drifting. A **coordination layer** (TA1)
performs leaderless, stigmergy-biased task allocation and Byzantine-resilient
context fusion, but every coordination action is gated by the doctrine layer so
illegal collective states are impossible by construction. The two layers are
coupled through a single shared quantity: the **coherence horizon**.

---

## 1. The core principle: invariants over emergence

The Duchaine System's central result is that *adaptive systems operating over
long horizons drift unless conservation is mechanically enforced.* LODESTAR
generalizes this from a single fitness agent to a heterogeneous collective:

- **Invariant layer (rigid):** what an agent / collective must never do.
- **Adaptive layer (flexible):** how it accomplishes the mission within bounds.

This maps directly onto DICE's stated TA2 tension (mission/role alignment vs.
cognitive agility) and onto the program's "controlled emergence" goal: emergence
is permitted, but only in the null space of the invariants.

## 2. TA2 -- Contract-Bounded Inference Control

### 2.1 The OPORD constitution (machine-checkable doctrine)

Each agent receives a role contract `C_role` and mission invariants `C_mission`,
expressed as predicates over the agent's state, outputs, and tool calls. These
are compiled, not prompted. Analogous to Duchaine heuristics H1-H11: a candidate
action that violates any predicate is rejected before emission.

### 2.2 Enforcement -- two interface modes

- **Open-weight agents (activation-accessible):** compute a **role vector** as
  the activation difference (in-role minus out-of-role) for matched prompts;
  project to principal components for tractable control; steer activations
  toward the role subspace each inference step. Drift = falling angle/decreasing
  projection onto the role subspace.
- **Black-box agents (scaffold-only):** enforce `C_role`/`C_mission` through
  memory shaping, context pruning, tool-use gating, and mechanism-design
  incentives (reward in-role behavior, tax deviation) over the agentic scaffold.
  Use intermediate reasoning tokens for observability, with explicit
  trust-discounting of those tokens.

### 2.3 Role-drift detector (the measurable contribution)

Implements the BAA's decoherence metric directly:

    decoherence = Var / TotalError,   TotalError = Bias^2 + Var

plus a role-subspace alignment score for open-weight agents. The detector is the
generalization of our "silent plan-prescription divergence" instrument: it
catches locally-reasonable, cumulatively-off-role behavior before it compounds.

### 2.4 Conservation + debt ledger (anti-sycophancy enforcer)

Mission obligations obey a conservation identity:

    Obligation_planned = Delivered + Owed   (per agent, per role)

A shortfall is recorded as `Owed` and surfaced; it is never silently dropped.
When no in-role action can satisfy the contract under current context, the agent
**abstains or escalates** (the BAA explicitly accepts abstention as a sufficient
TA2 response; non-abstaining coherence is the stretch goal).

### 2.5 Agility preservation

Because the contract bounds outcomes (`Delivered >= Minimum`) and not methods,
the agent's course-of-action generator is unconstrained inside the legal space.
Agility is measured by (a) mission-success rate under high-agility scenarios and
(b) diversity of generated courses of action.

### 2.6 Exposed invariant: the coherence horizon

TA2 publishes a statistical guarantee `H_coh` = expected number of inference
steps role coherence is maintained (with/without adversarial context). This is
the single value TA1 consumes.

## 3. TA1 -- Bounded Stigmergic Coordination + Resilient Consensus

### 3.1 Coordination (leaderless, no orchestrator)

Auction/pheromone-biased distributed task decomposition:

1. Mission propagates peer-to-peer.
2. Each agent forwards, bids on a fragment within its skills, or volunteers.
3. A pheromone vector over task->role motifs biases bids toward historically
   successful allocations (the STYG reinforcement, lifted to the collective).
4. Consensus selects the preferred decomposition; a failed agent's task is
   re-auctioned locally without global replan.

### 3.2 Hard-constraint validator (the STIGMA pattern)

Every candidate allocation is checked against doctrine before commit. Illegal
collective states (role conflicts, mission-invariant violations) are rejected and
the sequence is mutated -- exactly the STYG heuristic-validator loop, applied to
coordination rather than nutrition zones. Reinforcement can bias but never break.

### 3.3 Resilient fusion / reputation (Byzantine, NOT RAFT)

- BFT-class aggregation (PBFT / HotStuff lineage) for context fusion under
  conflicting/deceptive inputs. Explicitly avoid leader-elected log replication
  (RAFT, Mongo replica sets): a single primary reintroduces the orchestrator
  bottleneck and is only crash-fault-tolerant, not Byzantine-tolerant.
- Distributed, Sybil-resistant reputation; stake/penalty mechanism design;
  collusion detection via outcome-correlation and transaction-graph analysis
  (not just message logs) -- per the DeepMind distributional-safety catalog.
- Defense is **failure-agnostic**: same isolation path whether an agent is
  crashed, compromised, or has self-generated misaligned instrumental goals.

### 3.4 Provenance

Per-agent append-only, tamper-evident interaction ledger for attribution and
forensic root-cause. This is the transparency layer, not a coordination
mechanism -- it does not require global consensus to write locally.

## 4. The TA1<->TA2 coupling (the part most teams will under-specify)

    TA2 -> TA1:  H_coh (coherence horizon) bounds the distributed planning depth
                 and sets replanning cadence. Plan no deeper than agents can stay
                 coherent.
    TA1 -> TA2:  coordination requirements (required role set, interaction rate)
                 set the control targets H_coh must meet.

This closes the loop the BAA describes ("the distributed planning horizon in TA1
will depend on the TA2 guarantee on the length of role coherence; the TA2 control
target will be determined by the TA1 coordination requirements").

## 5. Scaling plan against program metrics

| Capability | P1 (M1-9) | P2 (M10-23) | P3 (M24-35) |
|---|---|---|---|
| Agents / interactions | 500 / 5K | 5K / 50K | 100K / 1M |
| Interaction complexity | O(n^2) | O(n log n) | O(n) |
| Role-coherence horizon | multi-step, benign | 1K steps, adversarial | 10K steps, adversarial |
| Consensus | crash-fault baseline | BFT + reputation | BFT at scale, sparse comms |
| Eval | vs orchestrated baseline | team vs team (down-select M23) | final leaderboard + playoff |

## 5b. Consensus-stack positioning (IMPORTANT scoping correction)

There are three distinct layers, often conflated. DICE needs the first two;
the third is the least central and is a framing trap.

| Layer | Job | Examples | LODESTAR use |
|---|---|---|---|
| Coordination | Who does which task; team formation | auctions, MARL, stigmergy | TA1 core |
| Robust aggregation / fusion | Fuse noisy/poisoned inputs robustly | Krum, Bulyan, CrossMax, trimmed-mean, FLTrust | TA1 context fusion |
| Agreement / total ordering | Agree on one ordered log | PBFT, HotStuff, Bullshark, Mysticeti | optional substrate only |

- **CrossMax is an aggregation RULE, not a consensus protocol.** It robustly
  fuses logits/predictions and is deterministic (hence replicable leaderlessly),
  but determinism is not Byzantine *agreement*. Use it for context fusion; pair
  it with an actual coordination/agreement mechanism. Do not oversell it.
- **Mysticeti / Narwhal / Bullshark provide total-ordered atomic broadcast (a
  ledger).** Total ordering is likely MORE than DICE needs, and a "blockchain
  for agents" framing reads as off-target to AI/control reviewers. Borrow the
  useful idea -- decouple data dissemination from ordering, stay leaderless --
  but cite it as an optional comms substrate, not the contribution.
- **FLTrust's clean-baseline-vector == the OPORD constitution.** The doctrine
  layer is the root-of-trust that lets fusion accept unusual-but-on-mission
  inputs and reject on-distribution-but-off-doctrine ones, by *direction* rather
  than distance -- robust even if >50% of nodes are compromised. This is a tight
  TA1<->TA2 weld.

### The Munchausen / responsibility-boundary anchor (resilience narrative)

Three ways to terminate a justification regress, mapped to this program:

- **Duchaine:** terminate at the human **responsibility boundary** (escalate on
  surfaced drift/infeasibility). This is the human-in-the-loop path.
- **Ben-Or:** terminate consensus deadlock with **shared randomness** (a common
  coin). Use this as the deadlock-breaker in leaderless coordination.
- **Resource floor (energy/tokens):** terminate with a budget cap. BUT
  energy-as-truth fails against a **kamikaze/griefing node** (liveness-over-
  safety; fatal for a collective). Therefore the real defense is **mechanism
  design**: per-node token quotas + staking/slashing + momentum reputation
  (maps to DICE reputation management + DeepMind stake-based trust).

Synthesis: **drift-surfacing is the single signal that feeds BOTH the autonomous
reputation/slashing layer AND the human escalation path.** One instrument, two
consumers -- the spine of the resilience story.

## 6. Key risks (and why none is fatal at abstract stage)

- **Activation-steering transfer across heterogeneous models** may be weaker
  than the Platonic-representation hypothesis predicts -> fall back to
  scaffold-only control; treat open-weight steering as upside.
- **BFT throughput at 100K agents** is hard -> rely on sparsity (O(n)) and
  hierarchical/local consensus domains; this is shared program risk.
- **Coherence-horizon guarantees** may be statistical, not worst-case ->
  acceptable; the BAA explicitly allows statistical guarantees.

## 7. Provenance note

The control kernel (rigid contracts / flexible execution, conservation,
infeasibility surfacing, anti-sycophancy, bounded stigmergy under inviolable
heuristics) originates in the author's prior N=1 optimization work. LODESTAR is a
clean-room generalization to heterogeneous multi-agent collectives; no consumer
application code is proposed as a DICE deliverable.
