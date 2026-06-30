# DICE Abstract Draft -- Project LODESTAR (TA1 + TA2)

> STATUS: Working draft. NOT submission-ready. Before submission, transcribe
> into the official **A1 - DICE Abstract Template** (download from the DICE
> program page). Per BAA Sec. 5.2, "information not explicitly requested in
> Attachment A1 will not be reviewed." Field order below approximates a typical
> DARPA abstract and MUST be re-mapped to A1's exact headings.
>
> BAA: HR001126S0010 (Decentralized AI through Controlled Emergence, DICE)
> Abstract due: 2026-06-30 14:00 ET via DARPA BAA Tool (BAAT) ONLY.
> Technical Area: TA1 + TA2 (must be proposed together; TA3 is excluded).
> Classification of this abstract: Unclassified (required for TA1/TA2).

---

## 1. Administrative

- **Proposed Title:** LODESTAR -- Bounded Stigmergic Coordination under Invariant
  Doctrine for Controlled Emergence
- **Technical Area(s):** TA1 (Self-organization via Peer-to-Peer Coordination
  and Distributed Consensus) and TA2 (Role Coherence and Local Inference Control)
- **Lead Organization / POC:** [TBD -- see B_gap_and_teaming memo]
- **Award Instrument sought:** OT for Research Agreement (10 U.S.C. 4021)
  [rationale: lightest-weight vehicle for fundamental research; avoids CMMC L2]

## 2. Innovative Claims

LODESTAR is built on one disruptive thesis: **emergence is only safe when
reinforcement operates strictly beneath a hard layer of inviolable invariants.**
Most self-organizing MAS let coordination and behavior co-evolve freely, which
is why they accumulate entropy and drift (cf. ClawBots, Moltbook). LODESTAR
inverts this: a per-agent **doctrine layer** (a machine-checkable OPORD
"constitution") is architecturally incapable of being renegotiated by any local
optimization, while a **stigmergic coordination layer** adapts continuously
*within* the legal space the doctrine permits.

Three specific claims:

1. **(TA2) Contract-bounded inference control eliminates silent role drift.**
   We treat role/mission alignment as a *conservation law with infeasibility
   surfacing*, not as a soft prompt. An agent that cannot satisfy its role
   contract under current context must *surface infeasibility and abstain or
   escalate*, never emit a plausible-but-off-role action. This converts role
   coherence from a best-effort property into a mechanically enforced invariant,
   measurable as the variance/total-error decoherence ratio the BAA specifies.

2. **(TA1) Bounded stigmergy gives O(n)-tractable, leaderless coordination that
   cannot violate doctrine by construction.** Pheromone-style reinforcement
   biases task/role allocation toward empirically successful motifs, but a
   heuristic-validator gate rejects any emergent assignment that breaks an
   invariant. There is no central orchestrator and no elected leader holding a
   replicated log; coordination state is local and append-only.

3. **(TA1<->TA2 coupling) The controller's coherence horizon is a first-class
   coordination invariant.** TA2 exposes a statistical guarantee on role-coherence
   length (in inference steps); TA1 uses that bound directly to set distributed
   planning depth and replanning cadence. This is the exact bidirectional
   dependency the BAA mandates, made explicit and measurable.

## 3. Technical Approach

### TA2 -- Contract-Bounded Inference Control (local adaptor)

- **Doctrine/Constitution layer:** mission + role invariants compiled into a
  per-agent, machine-checkable contract. For open-weight agents, enforced via
  **activation steering toward a role vector** (with subspace/PCA projection for
  tractable control). For black-box agents, enforced via **context/memory
  engineering + mechanism-design incentives** over the agentic scaffold.
- **Role-drift / mission-misalignment detector:** continuous monitor derived
  from our prior empirical work on "silent plan-prescription divergence" -- a
  documented, instrumented failure mode in which helpful models drift off-role
  through locally reasonable steps. Detector output is the decoherence metric.
- **Conservation + debt ledger:** planned obligation = delivered + owed;
  shortfalls are surfaced, never smoothed. This is the anti-sycophancy enforcer.
- **Agility preservation:** the contract bounds *outcomes*, not *methods*; the
  agent retains full freedom to generate diverse courses of action inside the
  legal space, so cognitive agility (measured via mission-success rate and
  course-of-action diversity) is preserved rather than crushed.

### TA1 -- Bounded Stigmergic Coordination + Resilient Consensus

- **Coordination:** distributed, auction/pheromone-biased task decomposition;
  agents bid on mission fragments within their skills and rebroadcast the
  remainder; failed agents' tasks are locally re-auctioned without global replan.
- **Hard-constraint validator:** every candidate allocation passes a doctrine
  filter before commit; illegal coordination states are impossible by
  construction (the STIGMA invariant pattern).
- **Resilient context fusion / reputation:** Byzantine-fault-tolerant
  aggregation (PBFT/HotStuff-class, NOT leader-based RAFT) plus a distributed,
  Sybil-resistant reputation layer to detect, discount, and isolate
  compromised/rogue/colluding agents -- agnostic to whether failure is benign,
  Byzantine, or self-generated instrumental drift.
- **Provenance:** per-agent append-only, tamper-evident interaction ledger for
  attribution and forensic root-cause (transparency layer).

### Interface

- Two adaptor interface modes per the BAA: an **activation-accessible** mode for
  open-weight agents and a **scaffold-only** mode (memory, tool-use constraints,
  stateful role) for black-box agents. We will converge to the program's
  standardized adaptor interface early.

## 4. Why this is not incremental (originality gate, Sec. 5.3 Step 1)

Current SOTA MAS (LangGraph/CrewAI/AutoGen-style) are centrally orchestrated --
the exact baseline DICE Phase 1 evaluates against. LODESTAR is leaderless and
doctrine-bounded. The novel scientific contribution is the **formal separation
of an inviolable invariant layer from an adaptive reinforcement layer**, with a
proven mechanism (conservation + infeasibility surfacing) for preventing the
drift that destroys long-horizon coherence in every prior self-evolving
collective. No consumer product is proposed or referenced.

## 5. Deliverables and Schedule (maps to BAA Sec. 2.6 / 2.7)

| Phase | Months | LODESTAR deliverable |
|---|---|---|
| P1 Decentralization | 1-9 | Adaptor v0 (doctrine layer + bounded-stigmergy coordination); by M8, in the TA3 environment, demonstrate advantage over the orchestrated baseline on **adaptability (time-to-recover) and resilience** at 500 agents / 5K interactions (NOT raw small-scale task quality) |
| P2 Adversarial Robustness | 10-23 | BFT consensus + reputation; role coherence to 1K adversarial steps; 5K agents / 50K interactions; survive M23 down-select |
| P3 Scaling | 24-35 | O(n) interaction complexity; 10K-step coherence; 100K agents / 1M interactions; agents-creating-agents |

Standard deliverables: algorithms + implementations + courseware; quarterly
reports; PI-meeting slides; biweekly DARPA syncs. Open-source with Government
Purpose Rights per Sec. 2.8.

NOTE (scoping): The M8 comparison is a Phase-1 milestone, NOT an abstract
precondition. The official benchmark runs in the TA3 simulation environment,
which does not exist until TA3's first release (Month 3); no pre-award
demonstration against the official baseline is possible or expected. The
abstract must instead argue *when/why/how* decentralization wins (BAA Sec. 2.4)
on the adaptability/resilience/scaling-slope axes, and may cite a small,
self-built proof-of-concept (single-box, 10-50 agents) as supporting evidence.

## 6. Team and Management

See `B_gap_and_teaming.md`. LODESTAR requires a teaming arrangement: control-
theory/doctrine kernel (originator) + a research partner with depth in
distributed consensus / mechanistic interpretability + activation steering.

## 7. Rough Cost Posture

[TBD with teaming partner. OT for Research keeps cost-share and CMMC burden
minimal; Cost Realism is the lowest-weighted Step-2 criterion but must be
defensible per labor hours/task.]
