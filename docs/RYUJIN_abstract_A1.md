# RYUJIN -- DICE Abstract (A1 Template Mapping)

**DARPA BAA HR001126S0010 -- Decentralized Artificial Intelligence through
Controlled Emergence (DICE)**
**Working draft for the A1 Abstract Template. TA1 & TA2. UNCLASSIFIED.**
**7-page maximum (cover sheet, ToC, bibliography excluded). 12-pt, 1" margins.**

> NOTE: This markdown is the content source. Final submission must be pasted
> into the official `A1_-_DICE_Abstract_Template.docx`, formatted to 12-pt with
> 1" margins, blue instructional text deleted, exported to PDF, and uploaded via
> BAAT. Fields in [BRACKETS] require your confirmation before submission.
> The cover-sheet table below maps onto the template's COVER SHEET page (excluded
> from the 7-page count). Figure 1 must be inserted manually in Word from
> `docs/sim_images/ryujin_worstcase_filmstrip.png` (a Markdown image embed does
> not transfer on copy-paste); size it to 8-10 pt captioning per the template.

---

## COVER SHEET

| Field | Value |
|---|---|
| Abstract Title | RYUJIN: A Doctrine-Bound, Self-Organizing, Adversary-Resilient Architecture for Heterogeneous Multi-Agent Autonomy |
| Technical Area | [X] TA1 & TA2   [ ] TA3 |
| Proposer Organization | SEAN BRADLEY INC. (DBA Victory Technology Partners) |
| Technical POC | Sean Bradley<br /><sean@victorytechpartners.com> <br />(213) 925-8598<br />8605 Santa Monica Blvd., #25450, Los Angeles, CA 90069-4109 |
| Administrative POC | Sean Bradley -- <sean@victorytechpartners.com> -- (213) 925-8598 |
| Other Team Members | [University sub-PI for formal analysis -- TBD; see Capabilities/Management] |
| Award Instrument Requested | [X] OT for Research (10 U.S.C. 4021) |
| Estimated Total Cost (Base + Options) | ~$5.75M over 36 months (bottom-up; see Cost and Schedule). No award ceiling is stated in the BAA. |
| Estimated Period of Performance | 36 months: Phase 1 (9 mo) + Phase 2 (15 mo) + Phase 3 (12 mo) |
| Other solicitations this concept was submitted to | None |
| SAM.gov UEI | EGD7LQKP4RM6 |

---

## 1. Goals and Impact

RYUJIN delivers the **local adaptor** DICE requires: a per-agent module that
makes a collective of heterogeneous AI agents coordinate without a central
orchestrator (TA1) while each agent remains role-coherent and mission-aligned
under adversarial pressure (TA2). The central problem DICE names -- emergence
that is powerful but uncontrolled -- is exactly the failure mode we have already
characterized empirically in long-horizon AI execution: **silent
plan-prescription divergence**, in which individually reasonable local decisions
compound into systematic drift away from mission intent. RYUJIN's thesis is that
controlled emergence is achieved by **architecturally separating an inviolable
doctrine layer from an adaptive coordination layer**, and coupling them through
a single measurable quantity.

The motivating context is the one DICE names: contested, adversarial operations
in which an agentic collective must execute long-horizon missions without a
central orchestrator. DARPA's own examples span a battle unit (e.g., a platform
composed of navigation, perception, and control agents), command and control of
a swarm of agentic systems, disaster response, and scientific discovery. In
every case a centralized orchestrator is a single bone whose removal collapses
the skeleton; RYUJIN has no such bone, because coordination is leaderless and
doctrine is replicated at every node, so the collective degrades gracefully
rather than catastrophically.

**What is new.** Most self-organizing multi-agent systems let coordination and
behavior co-evolve freely, which is precisely why they accumulate entropy and
lose coherence over long missions. RYUJIN inverts this. A per-agent **mission
constitution** -- cryptographically signed, content-addressed, quorum-verified,
and append-only after installation -- cannot be renegotiated by any peer message
or local inference step. Coordination then operates **freely within the legal
space the constitution defines**, while a validator gate makes doctrine-violating
collective states impossible by construction. Silent drift is
detected by a conservation-and-debt-ledger mechanism and is never smoothed over;
the same drift signal drives both human escalation and autonomous Byzantine
reputation/slashing.

**Impact if successful.** A decentralized collective that (a) scales to the
program's 100K-agent / 1M-interaction target with O(n) interaction complexity,
(b) recovers locally from agent loss or compromise without global replanning,
(c) keeps heterogeneous agents doctrinally aligned across 10K-step horizons
under adversarial load, and (d) surfaces infeasibility to a human operator
rather than failing silently. Beyond defense, the same control kernel transfers
to clinical-compliance and multi-agent enterprise systems, where silent
under-delivery against contractual obligations is the dominant failure mode.

## 2. Technical Approach

RYUJIN is a replicated per-agent adaptor with two coupled layers over a
crash-fault-tolerant compute substrate.

**TA2 -- Local inference control (doctrine).** Each agent carries the mission
constitution: signed, content-addressed, quorum-installed role and mission
invariants. Enforcement is mechanical, not prompt-based. For open-weight models,
a role vector is enforced at inference time via **activation steering**; for
black-box models, control is applied through context/memory engineering and
mechanism design. A **role-drift detector** computes a decoherence metric
(variance over total error) and a **conservation/debt ledger** tracks
planned-vs-delivered obligations, surfacing infeasibility and escalating to the
human responsibility boundary instead of accommodating decline.

**TA1 -- Coordination and resilient fusion.** Task allocation is a **leaderless
auction**: agents bid on and decompose tasks over a peer-to-peer bus with no
central scheduler. **Roles are not statically assigned; they are dynamically
allocated by the auction each cycle and re-allocated around distrusted or lost
agents, bounded by the signed constitution -- so the collective self-organizes
into mission-effective teams (allocating roles) without a central planner, yet
no agent can ever assume a role the doctrine forbids.** Selection is biased by two complementary signals -- reactive
steering on the live state of nearby agents (fast local deconfliction) and a
**shared, recency-weighted success signal** that nudges agents toward task
patterns that have recently worked (a lightweight, leave-a-trail form of
indirect coordination adapted from swarm robotics; Reynolds 1986, Dorigo 1992).
Both signals are gated so only constitution-legal actions are ever considered.
Peer claims are combined by **robust context fusion** (CrossMax /
Krum / trimmed-mean) with **FLTrust-style directional anchoring** that judges
inputs by their direction relative to the doctrine baseline rather than by
distance from peers -- defeating poisoned and adversarial inputs even when
honest agents are non-IID. **Momentum-weighted reputation with slashing** and
per-node resource quotas isolate Byzantine, rogue, and kamikaze nodes; a Ben-Or
randomized step breaks leaderless deadlocks.

**The TA1<->TA2 coupling (our distinguishing claim).** The TA2 controller
publishes a **coherence horizon** -- a statistical guarantee of how many
inference steps an agent remains role-coherent under current adversarial load.
TA1 sets its distributed planning depth and replanning cadence to that horizon.
The loop is explicit, bidirectional, and measurable; no competing architecture
in scope formalizes it.

**Attack surfaces, named explicitly (risk register).** We name our own
crown-jewel vulnerabilities rather than hide them; each has a concrete
mitigation and a residual we do not overclaim.

1. *Mission-constitution propagation* -- a poisoned constitution makes every
   honest node faithfully enforce the wrong rules. Mitigations: signing with
   monotonic sequence numbers, content-addressed identity, quorum-gated
   installation (n-f attestation), append-only post-install semantics, periodic
   constitutional self-check, and FLTrust semantic anchoring against the
   operator baseline to catch adversarially crafted but validly signed doctrine.
2. *Trusted-anchor capture* -- the FLTrust root of trust is itself a high-value
   target; a static anchor goes stale on a moving target while a fast one is
   capturable. Primary mitigation is an *exogenous, attested* anchor (a
   human-in-the-loop designation -- a forward observer or a lasing aircrew -- or
   a high-assurance organic sensor declared authoritative by doctrine), with a
   rate-limited consensus fallback bounded against the signed baseline and
   periodic re-attestation, used only when no exogenous truth is available.
3. *Gossip interception / injection / jamming* -- the network is assumed
   hostile. Every peer message is signed and content-addressed, so interception
   yields no integrity advantage and a relay cannot forge or alter it; BFT
   quorum plus robust fusion defeat injection by a minority; message volume is
   policed by per-node quotas (a flooding/Sybil control, distinct from trust).
   The residual is traffic analysis and jamming -- an availability risk
   mitigated by emission control, frequency agility, and store-and-forward
   gossip, not a solved problem.
4. *Enclave / substrate boundary* -- Ray never crosses a trust boundary; an
   enclave speaks the same signed RYUJIN protocol to the field as any other
   peer, so its edge is defended identically and nothing it says is trusted
   without signatures and quorum. Loss of an enclave is an availability event
   (mitigated by replication and graceful degradation), not an integrity hole.
5. *Decoherence-induced compute exhaustion* -- an adversary who forces
   decoherence upward can drive recalibration toward numerical and temporal
   limits (ill-conditioned fusion; recompute latency exceeding the rate of world
   change). Mitigations: conditioning guards and saturating arithmetic, a hard
   floor on the coherence horizon with fallback to a cached last-good doctrinal
   action, rate-limited recalibration, and the debt-ledger tripwire that hands
   control to the human before the loop destabilizes.

**Preliminary evidence (single-host model).** A standard-library localhost model
of the coordination/control layer already runs the above mechanics -- robust
FLTrust fusion, leaderless auction, doctrine-anchored recoverable reputation, a
conservation ledger that re-broadcasts (never drops) unmet orders, and graceful
degradation after node loss. Across a 200-trial Monte Carlo sweep over randomized
fault timing and adversary fraction (0-2 of 6 nodes compromised), the
decentralized adaptor sustained coordination -- median completion 0.98 and median
post-loss coherence 0.81 -- isolated every adversary and wrongly benched no honest
agent in any trial, while the centralized baseline collapsed to zero coherence on
orchestrator loss (median completion 0.61). Transient order backlog under the
compound shock (insider + node loss) is surfaced to the operator and then burned
down as coherence recovers -- conserved, not hidden. The model also exposes the
trust-posture tradeoff explicitly: a zero-trust start contains an insider
immediately (0 vs ~2 cycles) at the cost of a short, bounded self-attestation
bootstrap (~10 agent-cycles). It is a mechanism illustration, not calibrated
performance, and exists to de-risk the Phase 1 build.

![RYUJIN single-host model -- persistent-insider scenario](sim_images/ryujin_worstcase_filmstrip.png)

*Figure 1. Single-host mechanism illustration (standard-library Python; not
calibrated performance). Persistent-insider scenario, four matched cycles. **Top
row -- the legacy centralized approach:** the spoofed fix (red X) is never
identified, so the single averaged estimate is dragged off the true target and,
once the lone orchestrator is lost, coordination collapses entirely. **Second row
-- RYUJIN on the same cycles:** the same spoofed fix is down-weighted by robust
FLTrust fusion and ringed in red once its trust falls below the distrust floor and
it is slashed from the fused estimate, so the defended track holds on truth and the
team keeps coordinating after node loss. **Third row:** roles are dynamically
auction-allocated each cycle and re-routed around the distrusted (red) and offline
agents, which the doctrine excludes. **Bottom row:** the coherence horizon contracts
under attack and recovers (left); the conserved order backlog spikes under the
shock, is surfaced to the operator, and then burns down to zero rather than being
hidden (center); and only the adversary ends distrusted -- shown against the
recoverable-reputation hysteresis band (distrust floor 0.30, reinstate ceiling
0.70). An animated version, a three-row RYUJIN-vs-baseline comparison figure, the
recoverable-trust ("repentant adversary") scenario, and an innocent-vs-zero-trust
posture comparison are in the public repository linked below.*

**Code and online demonstration.** The single-host model, the Monte Carlo
sweep, and both animations (persistent-insider and recoverable-trust) are
available at [REPO: https://github.com/<org>/ryujin -- confirm URL before
submission] (standard-library Python; matplotlib only for the optional
visualization; license: [confirm -- e.g., MIT or Apache-2.0]).

**Leveraged components (engineering substrate, not the contribution).** Compute
and orchestration ride on **Ray** (stateful actors, scheduling, object store;
crash-fault-tolerant only -- Byzantine defense lives above it in TA1). Ray runs
**only inside a trusted compute domain** (a VPC or air-gapped enclave) and never
spans the untrusted network between agents; cross-agent trust is carried
entirely by the signed TA1 protocol above it, so the decentralization guarantee
does not depend on the substrate.
Heterogeneous model serving uses an **OGX/vLLM** stack to present a uniform
interface across different foundation models and to support fully self-hosted,
air-gapped deployment for contested or enclave operation; activation-steering
control reaches beneath the serving API to the vLLM layer where activation
access lives. An optional DAG-BFT log (Bullshark/Mysticeti-class) is available
only where a use-case requires total ordering; it is not the contribution, and
framing RYUJIN as "a blockchain for agents" would be a category error.

**Compute capability.** RYUJIN is engineered so that scale is a function of
*logical* agents, not *physical* model replicas, which keeps the compute
footprint tractable. Heterogeneous agents share a small set of base-model
weights served through a vLLM/OGX layer with paged-attention and continuous
batching; per-agent identity is carried in lightweight context and an
activation-steering role vector that adds negligible marginal cost over a shared
forward pass. Because the mission constitution gates most candidate actions and
the coordination layer is event-driven, the large majority of agents are idle or
short-prompt at any instant, so many logical agents multiplex onto each GPU.
Coordination itself (the task auction, robust fusion, reputation) is
CPU/network-bound and rides the Ray substrate, not the GPUs. Concretely: Phase 1
at 500 agents / 5K interactions is feasible on a single multi-GPU node; Phase 2
at 5K agents / 50K interactions on a modest cluster; Phase 3 at 100K agents / 1M
interactions via agent multiplexing plus a discrete-event simulation harness for
the long tail of gated/idle agents, with elastic burst capacity for peak
inference. [CONFIRM what is in hand vs. procured under the award -- e.g., current
access to N x [GPU type, memory, interconnect] for Phase 1, with cloud and/or
national-compute (NAIRR, DoD HPC) capacity budgeted in the cost volume for later
phases.]

## 3. Capabilities / Management Plan

**Principal Investigator:** Sean Bradley (SEAN BRADLEY INC. / Victory Technology
Partners). Twenty-five years architecting distributed, cloud-native, and AI/ML
systems in zero-error-tolerance, heavily regulated domains -- exactly the
fault-tolerance, security, and interoperability discipline a contested
multi-agent system demands. Directly relevant record: architected large-scale
healthcare-interoperability and data-portability systems (FHIR/HL7, PHI/PII)
under HIPAA and federal mandates, including critical security-vulnerability
remediation, at ClearCare; currently a technical specialist on a Los Angeles
County Department of Public Health modernization team building high-volume,
cross-agency data-transfer pipelines (county/state/CDC); and hands-on GPU/ML
engineering (CUDA, RAPIDS, TensorFlow on NVIDIA DGX-class hardware) on a
cross-disciplinary AI/IoT R&D accelerator at Anadarko. As founder of a long-running
engineering consultancy and a former start-up CTO (raised a $2M Series A, scaled
engineering 4x), the PI can both build the kernel and run the program and its
subaward. Prior work most germane to this effort: the **Duchaine System**, an
operational long-horizon AI control architecture that empirically characterized
silent plan-prescription divergence and demonstrated conservation-law
enforcement, anti-sycophancy, and infeasibility surfacing -- the direct
intellectual antecedents of RYUJIN's TA2 doctrine layer. The PI is also a former
U.S. Army Airborne Ranger (Special Operations; held a Secret-level clearance;
Gulf War veteran), so the mission-constitution / OPORD framing that anchors the
TA2 doctrine layer is first-hand, not borrowed.

**Teaming (highly encouraged at abstract stage, not yet finalized).** We intend
to add a sub-awardee providing formal-methods and distributed-systems depth --
specifically [PhD, graph theory / distributed consensus] -- to own the formal
analysis of the coordination protocol and the Byzantine-resilience proofs. A
university CS/Math department (e.g., [target institution]) is the intended
academic sub. This pairs first-hand operational doctrine experience (PI) with
peer-reviewed theoretical rigor (sub).

**Organization and roles.** PI/prime (SEAN BRADLEY INC.): architecture, TA2
doctrine/control, integration, and program management. Sub-PI: TA1 formal
coordination guarantees and robust-fusion analysis. Risk is managed by phasing
the highest-uncertainty work (activation-steering transfer, BFT throughput at
scale) into clearly bounded milestones with black-box fallback paths.

## 4. Cost and Schedule

**Schedule (aligned to the DICE three-phase structure):**

- **Phase 1 (9 months) -- Decentralization.** Adaptor interface spec; mission-
  constitution module; bounded stigmergic auction v0; CrossMax fusion; drift
  detector + debt ledger; self-evaluation vs. a centralized baseline. Target:
  500 agents / 5K interactions.
- **Phase 2 (15 months) -- Adversarial robustness.** BFT context fusion +
  reputation/slashing; 1K-step adversarial coherence; activation steering for
  open-weight models; scale to 5K agents / 50K interactions; team-vs-team eval.
- **Phase 3 (12 months) -- Scaling.** O(n) interaction complexity; 10K-step
  adversarial coherence; 100K agents / 1M interactions; final leaderboard and
  team-vs-team.

**Cost (bottom-up estimate):** ~$5.75M over 36 months (Base + Options), with
**compute itemized separately** per the template. The estimate is built from a
lean prime team (PI + 1-2 research engineers) plus one academic subaward, not
from a target number.

| Phase | Prime (labor, indirect, ODC, fee), ex-compute | Compute (cloud, itemized) | Phase total |
|---|---|---|---|
| Phase 1 (9 mo) | $0.99M | $0.04M | $1.03M |
| Phase 2 (15 mo) | $2.14M | $0.25M | $2.39M |
| Phase 3 (12 mo) | $1.78M | $0.55M | $2.33M |
| **Total** | **$4.91M** | **$0.84M** | **$5.75M** |

Key assumptions (detailed in the cost volume): direct salaries PI $240K, senior
engineer $200K, second engineer $180K (Phase 2+); fringe 30%, overhead 25% of
labor+fringe, G&A 12%, fee 8% on prime cost (no fee on the subaward); academic
subaward ~$400K/yr fully loaded (postdoc + students + university F&A); compute
rented, not purchased, at ~$2.50/H100-GPU-hr (specialty cloud; AWS on-demand
runs ~50-60% higher), with Phase 3 scale held down by agent multiplexing over
shared base weights plus a discrete-event harness for the idle/gated long tail.
Compute is the dominant cost risk: if evaluation forces more live inference than
multiplexing assumes, Phase 3 compute could rise 2-3x. **OT for Research** is
requested partly to keep indirect-rate and CMMC overhead proportionate to a
small business.

## 5. Publications (up to 10, 2016+; team-member names highlighted)

1. **Bradley, S.** The Duchaine System: constraint-satisfaction and
   conservation-law enforcement for long-horizon AI execution (2026). [link]
2. [Add up to nine additional relevant references; where the sub-PI is added,
   highlight their peer-reviewed distributed-systems / graph-theory papers here.]

## 6. Bibliography (does not count against page limit)

Reynolds (1986) Boids; Grasse (1959), Dorigo (1992) stigmergy/ACO; Castro (1999)
PBFT; Yin et al. (2019) HotStuff; Spiegelman et al. (2022) Bullshark; Mysten Labs
(2023) Mysticeti; Blanchard et al. (2017) Krum/Bulyan; Cao et al. (2020) FLTrust;
Ben-Or (1983) randomized consensus; Zou et al. (2023), Turner et al. (2023)
activation steering; Moritz et al. (RISELab) Ray; Tomasev et al. (2025)
distributional AGI safety; Simon (1956) bounded rationality. [Format full
citations with links in the final document.]

---

## Open items before submission (your inputs)

1. [ ] UEI string -> cover sheet
2. [ ] Technical/Admin POC contact block
3. [ ] Confirm award instrument (recommended: OT for Research)
4. [ ] Confirm/replace all cost figures and the compute plan
5. [ ] Compute-capability paragraph (what hardware is in hand vs. to be procured)
6. [ ] PI bio specifics; intended sub-PI and university to name
7. [ ] Publications list (finalize; add sub-PI papers once partner is confirmed)
8. [ ] BAAT account created for upload
