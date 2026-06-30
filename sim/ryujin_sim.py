"""
RYUJIN localhost simulation -- didactic, single-file demo (v3).

Purpose
-------
Make the DICE TA1/TA2 proposal concrete by running its mechanics on recognizable
real-world objects: a small mixed force of PLATFORMS (drones / sensors / compute
nodes), each carrying EQUIPMENT (camera / radio / processor), tracking a moving
TARGET and executing ORDERS (scout / relay / analyze). Lines tagged `# [RW]`
state which fielded component is being INSTANTIATED, CONSTRUCTED, or ALTERED.

HOW TO RUN
----------
    python sim/ryujin_sim.py            # one verbose scripted run (DEFAULT)
    python sim/ryujin_sim.py --quiet    # scripted run, summary only (no per-cycle log)
    python sim/ryujin_sim.py --sweep    # 200-trial Monte Carlo over randomized faults
    python sim/ryujin_sim.py --sweep --trials=500
    python sim/ryujin_sim.py --viz      # live matplotlib animation of one run
    python sim/ryujin_sim.py --viz --delay=0.3   # animation speed (seconds per cycle)
    python sim/ryujin_sim.py --heal     # adversary repents mid-run and recovers trust
    python sim/ryujin_sim.py --viz --heal        # watch a node heal, live
    python sim/ryujin_sim.py --zero-trust        # start at the distrust floor (earn standing)
    python sim/ryujin_sim.py --viz --zero-trust  # watch the bootstrap cost, live
    python sim/ryujin_sim.py --trust-tradeoff    # innocent vs zero-trust, side-by-side sweep
    python sim/ryujin_sim.py --viz-compare       # live side-by-side: centralized vs RYUJIN

Asset export (for the abstract figure and the repo README), all PDF/Markdown safe:
    python sim/ryujin_sim.py --filmstrip docs/sim_images/ryujin.png   # static figure
    python sim/ryujin_sim.py --compare  docs/sim_images/compare.png   # 3-row head-to-head
    python sim/ryujin_sim.py --save-gif  docs/sim_images/ryujin.gif   # animated GIF
    python sim/ryujin_sim.py --save-frames docs/sim_images/frames     # one PNG/cycle
    python sim/ryujin_sim.py --save-gif-compare docs/sim_images/compare.gif  # side-by-side GIF
    python sim/ryujin_sim.py --save-frames-compare docs/sim_images/cmp_frames # one PNG/cycle
    (append --heal to any of the above to export the recovery scenario instead)

The --save-gif-compare / --viz-compare animations show the OLD centralized
approach (naive average, LEFT) next to RYUJIN (robust fusion, RIGHT) on the same
cycles. Both panels ingest the IDENTICAL reports; only the fusion RULE differs, so
the contrast is not privileged information. (The trusted anchor is intentionally
NOT drawn in the spatial panels -- it lands on the fused star and would invite a
skimming reviewer to misread it as "the trick"; its anti-capture role is shown in
the --compare figure's "anchor vs truth" error line instead.)

The --compare figure stacks three rows -- RYUJIN, the centralized baseline, and
the supporting EMA signals (fusion weights, success signal, anchor error) -- as
a single proposal/oral slide. The --filmstrip adds a full-width dynamic
role-allocation heatmap showing roles are auction-assigned and doctrine-bound.

The scripted run is verbose by default, so there is no --verbose flag; use
--quiet to suppress the per-cycle trace. --heal can be added to any scripted or
--viz run to make the adversary stop spoofing partway through, so you can watch
recoverable-trust hysteresis bring it back above the reinstate ceiling. Only
--viz needs a third-party package (matplotlib); every other mode is stdlib-only.

TRUST POSTURE: by default peers start fully trusted (innocent-until-proven-guilty)
and must misbehave to be slashed. --zero-trust starts every peer at the distrust
floor (earn-your-standing): peers carry no fusion weight and throttled task
throughput until they agree with the defended track. --trust-tradeoff runs the
same randomized trial matrix under both postures and prints the cost/benefit
(detection latency vs early throughput and honest benchings).

UNITS: every tunable constant below states its unit in an inline comment -- a
probability in [0,1], a count of orders, a number of cycles, or "map-units"
(the abstract distance units of the 2-D target track; think kilometers).

No GPU, no LLM, no network, no Ray. Platforms are MOCK (rule-based) on purpose:
the demo exercises the COORDINATION + CONTROL layer -- the in-scope, novel
contribution -- not model inference. Ray would later replace the in-process
loop as the CFT substrate INSIDE a trusted enclave, with no change to the logic.

IMPORTANT: the numeric constants below are ILLUSTRATIVE teaching dials chosen to
produce one legible run. They are NOT empirical and NOT calibrated from data or
literature. The fault schedule (compromise cycle, loss cycle) is SCRIPTED, so a
single run demonstrates the MECHANISM, not average-case performance. Real use
would calibrate constants from platform/sensor specs and run a Monte Carlo sweep
over seeds, fault timing, and adversary fraction.

Scenario (per cycle): fuse a target track from noisy platform reports (TA1 robust
fusion + FLTrust directional anchoring), allocate skill-typed orders via a
leaderless auction biased by a shared success signal (TA1 coordination) gated by
the mission constitution (TA2 doctrine), and track issued-vs-completed orders to
surface drift (TA2 monitoring/escalation). Injected faults: a COMPROMISED
platform (poisons its reports + sabotages orders) and a PLATFORM LOSS mid-run. A
CENTRALIZED baseline (the legacy single-orchestrator architecture) runs on the
same reports to contrast robustness and resilience.
"""

import hashlib
import hmac
import math
import random
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

Vec = Tuple[float, float]

# ----------------------------------------------------------------------------
# Illustrative constants (seeded; deterministic). See the docstring caveat:
# these are TEACHING DIALS, not empirical values. Every line states its UNIT.
# "map-units" = the abstract distance units of the 2-D target track (think km).
# ----------------------------------------------------------------------------
SEED = 42  # unit: none (RNG seed); stands in for an uncontrolled real world
CYCLES = 14  # unit: cycles (OODA decision loops), not wall-clock time
SENSOR_NOISE = 0.40  # unit: map-units, 1-sigma Gaussian fix error vs true target
TASK_SUCCESS_BASE = 0.92  # unit: probability [0,1] a tasked platform succeeds
DISTRUST_FLOOR = 0.30  # unit: trust score [0,1]; below this, influence revoked
RETRUST_CEILING = 0.70  # unit: trust score [0,1]; a slashed platform must EARN
# back this much trust before rejoining fusion -- deliberately well above the
# 0.30 floor so a previously hostile node serves a real "probation" (several
# cycles of honest behavior) rather than flipping back in the instant it ticks
# above the floor. Raising this hardens the posture against repeat offenders;
# lowering it favors availability / fast false-positive recovery.
TRUST_GAIN = 0.40  # unit: EMA weight [0,1] per cycle (trust reaction speed)
SIGNAL_GAIN = 0.30  # unit: EMA weight [0,1] per cycle (success-signal speed)
ANCHOR_GAIN = 0.25  # unit: EMA weight [0,1] per cycle (anchor tracking speed)
MAX_ORDERS_PER_PLATFORM = 2  # unit: orders per platform per cycle (doctrine cap)
MAX_HORIZON_CYCLES = 10  # unit: cycles (longest planning lookahead sanctioned)
COMPROMISE_CYCLE = 3  # unit: cycle index at which one platform is compromised
LOSS_CYCLE = 7  # unit: cycle index at which a platform is lost off-net
REPENT_CYCLE = 10  # unit: cycle index; with --heal, adversary stops spoofing here
BACKLOG_ESCALATION = 2  # unit: orders. Operator-review line: ~one tasking cycle's worth
# of deferred (NOT failed -- deferred) work. Conserved work that briefly crosses this
# under a shock and then clears is the intended "surface, then burn down" behavior; a
# backlog pinned above it would be the real drift signal worth a human's attention.
NEW_ORDERS_PER_CYCLE = 4  # unit: orders per cycle (incoming tasking tempo). Set BELOW
# the force's sustained throughput so it runs with capacity margin: nominal backlog
# stays near zero, a shock (compromise + loss) makes it spike and surface to the
# operator, then it BURNS DOWN as coherence recovers -- a degrade/surface/recover
# arc, not a permanently saturated force.

# Initial trust posture. Default 1.0 = "innocent until proven guilty": peers start
# fully trusted and must MISbehave to be slashed. ZERO_TRUST_START models the
# opposite ("guilty until proven innocent"): peers start at the distrust floor and
# must EARN standing before they get fusion weight or full task throughput. The
# --zero-trust flag and the --trust-tradeoff comparison expose the cost/benefit.
INITIAL_TRUST = 1.0  # unit: trust score [0,1] every platform starts with
ZERO_TRUST_START = 0.0  # unit: trust score [0,1]; zero-trust start point. Below the
# floor, so peers begin SLASHED and must climb above the reinstate ceiling (by
# agreeing with the doctrine-anchored track) before they earn fusion weight or task
# throughput -- i.e. they attest their way in. That bootstrap is the cost we expose.
TARGET_HOME: Vec = (2.0, 1.0)  # unit: map-units (x, y) ground-truth start position

# [RW] the doctrine's capability matrix: which equipment each order type requires.
EQUIPMENT_FOR_ORDER = {"scout": "camera", "relay": "radio", "analyze": "processor"}
ORDER_TYPES = list(EQUIPMENT_FOR_ORDER.keys())


# ----------------------------------------------------------------------------
# Tiny 2-D vector helpers (kept stdlib-only on purpose).
# [RW] A "vector" here stands in for a real target TRACK -- a position fix
# (x, y); extendable to (x, y, t) or (x, y, vx, vy) for a maneuvering target.
# ----------------------------------------------------------------------------
def vadd(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def vsub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1])


def vscale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s)


def vlen(a: Vec) -> float:
    return math.hypot(a[0], a[1])


def vdist(a: Vec, b: Vec) -> float:
    return vlen(vsub(a, b))


def vdot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def vcos(a: Vec, b: Vec) -> float:
    # [RW] directional agreement between two tracks: the basis of FLTrust.
    la, lb = vlen(a), vlen(b)
    if la == 0.0 or lb == 0.0:
        return 0.0
    return vdot(a, b) / (la * lb)


def vunit(a: Vec) -> Vec:
    n = vlen(a)
    return (0.0, 0.0) if n == 0 else (a[0] / n, a[1] / n)


# ----------------------------------------------------------------------------
# An order: one unit of mission work.
# [RW] CONSTRUCTED each cycle as a tasking to be executed by some platform.
# Carries its own re-broadcast / decomposition state.
# ----------------------------------------------------------------------------
@dataclass
class Order:
    otype: str  # [RW] the kind of order, hence the equipment it requires
    attempts: int = 0  # [RW] times re-broadcast after finding no legal platform
    decomposed: bool = False  # [RW] split into a simpler order after staying stuck


# ----------------------------------------------------------------------------
# TA2 DOCTRINE: the Mission Constitution.
# [RW] CONSTRUCTED ONCE by the operator, replicated to every platform, and never
# mutable by any peer message thereafter (append-only doctrine). Signed (HMAC),
# content-addressed (SHA-256).
# ----------------------------------------------------------------------------
@dataclass
class MissionConstitution:
    mission_id: str  # [RW] content identity of this specific order set
    trusted_prior: Vec  # [RW] operator's trusted track prior (FLTrust root of trust)
    max_orders_per_platform: int  # [RW] doctrine load cap invariant
    equipment_for_order: Dict[str, str]  # [RW] required equipment per order type
    _secret: bytes = b"operator-signing-key"  # [RW] stand-in for operator keypair

    def _canonical(self) -> bytes:
        parts = [
            self.mission_id,
            f"{self.trusted_prior[0]:.4f},{self.trusted_prior[1]:.4f}",
            str(self.max_orders_per_platform),
            ";".join(f"{k}:{v}" for k, v in sorted(self.equipment_for_order.items())),
        ]
        return "|".join(parts).encode("utf-8")

    @property
    def content_hash(self) -> str:
        # [RW] content-addressed identity: any tampering changes the hash.
        return hashlib.sha256(self._canonical()).hexdigest()[:12]

    @property
    def signature(self) -> str:
        # [RW] cryptographic attestation that the operator authored this doctrine.
        return hmac.new(self._secret, self._canonical(), hashlib.sha256).hexdigest()[
            :12
        ]

    def verify(self, sig: str) -> bool:
        # [RW] each platform checks the signature before installing doctrine.
        return hmac.compare_digest(sig, self.signature)

    def validate_order(self, platform: "Platform", order: Order) -> bool:
        """Doctrine validator gate: an illegal order is impossible."""
        # [RW] no platform may be tasked outside the order set...
        if order.otype not in self.equipment_for_order:
            return False
        # [RW] ...nor without the required equipment...
        if self.equipment_for_order[order.otype] not in platform.equipment:
            return False
        # [RW] ...nor past the doctrine load cap. Any of these = an illegal order.
        if platform.assigned >= self.max_orders_per_platform:
            return False
        return True


# ----------------------------------------------------------------------------
# A platform: one heterogeneous member of the force.
# [RW] A drone / sensor / compute node. Holds only LOCAL state and runs the
# identical local adaptor. There is no shared mutable global state.
# ----------------------------------------------------------------------------
@dataclass
class Platform:
    pid: str  # [RW] platform identity (a signed peer identity in the real system)
    equipment: Set[str]  # [RW] gear it carries (camera / radio / processor)
    honest: bool = True  # [RW] true integrity (UNKNOWN to the rest of the force)
    trust: float = 1.0  # [RW] locally maintained trust score for this peer
    assigned: int = 0  # [RW] orders committed this cycle (ALTERED per cycle)
    online: bool = True  # [RW] still on-net and operational
    distrusted: bool = False  # [RW] influence revoked after trust fell below floor

    def report_track(
        self, target: Vec, trusted_prior: Vec, rng: random.Random, compromised: bool
    ) -> Vec:
        """Local sensing. A compromised platform spoofs against the trusted prior."""
        # [RW] a compromised platform reports a fabricated track aimed against the
        # operator's trusted prior (a spoofed target / poisoned feed).
        if not self.honest and compromised:
            spoof = vscale(trusted_prior, -3.0)
            return vadd(spoof, (rng.gauss(0, 0.3), rng.gauss(0, 0.3)))
        # [RW] an honest platform reports its true-but-noisy sensor fix.
        return vadd(target, (rng.gauss(0, SENSOR_NOISE), rng.gauss(0, SENSOR_NOISE)))


# ----------------------------------------------------------------------------
# TA1 ROBUST FUSION: FLTrust-style directional anchoring + trust weights.
#   weight_i = relu(cos(report_i, trusted_prior)) * trust_i
# [RW] ALTERS many local target fixes into ONE defended track. The anchor TRACKS
# the world slowly, so platforms are judged by direction-vs-doctrine, not
# agreement-with-majority, and the anchor cannot be captured by a transient
# spoofing burst. (The anchor is itself a high-value attack surface -- see the
# proposal risk register, same class as constitution propagation.)
# ----------------------------------------------------------------------------
def fuse_track(
    reports: List[Tuple["Platform", Vec]], trusted_prior: Vec
) -> Tuple[Vec, Dict[str, float]]:
    weights: Dict[str, float] = {}
    num: Vec = (0.0, 0.0)
    den = 0.0
    for plat, fix in reports:
        # [RW] trust this fix in proportion to how well its DIRECTION agrees with
        # the operator's trusted prior, scaled by the platform's standing. A fix
        # pointing against the prior earns ~zero weight (relu clamps it).
        w = max(0.0, vcos(fix, trusted_prior)) * max(0.0, plat.trust)
        weights[plat.pid] = w
        num = vadd(num, vscale(fix, w))
        den += w
    if den <= 1e-9:
        # [RW] degenerate case: no trusted fix -> plain average rather than freeze.
        fixes = [f for _, f in reports]
        if not fixes:
            return trusted_prior, weights
        cx = sum(v[0] for v in fixes) / len(fixes)
        cy = sum(v[1] for v in fixes) / len(fixes)
        return (cx, cy), weights
    # [RW] the defended target track the force will act on.
    return vscale(num, 1.0 / den), weights


def average_track(reports: List[Tuple["Platform", Vec]]) -> Vec:
    """Centralized baseline fusion: no robustness, no anchoring."""
    # [RW] the legacy orchestrator simply averages every fix -- so a single
    # spoofed report drags the whole track off-target.
    if not reports:
        return (0.0, 0.0)
    cx = sum(f[0] for _, f in reports) / len(reports)
    cy = sum(f[1] for _, f in reports) / len(reports)
    return (cx, cy)


# ----------------------------------------------------------------------------
# TA1 LEADERLESS AUCTION.
# [RW] CONSTRUCTS the order->platform assignment with NO central allocator: each
# platform self-computes a bid; lowest bid wins; the doctrine gate vetoes any
# illegal order; a shared success signal biases bids toward order types that
# have recently paid off (a learned tactic preference, NOT a location).
# ----------------------------------------------------------------------------
def assign_orders(
    orders: List[Order],
    platforms: List["Platform"],
    const: MissionConstitution,
    tactic_success: Dict[str, float],
    rng: random.Random,
) -> List[Tuple[Order, Optional["Platform"]]]:
    assignments: List[Tuple[Order, Optional[Platform]]] = []
    for order in orders:
        # [RW] only platforms that are on-net, trusted, and doctrine-legal for
        # this order may bid. The validator gate makes an illegal order impossible.
        eligible = [
            p
            for p in platforms
            if p.online and not p.distrusted and const.validate_order(p, order)
        ]
        if not eligible:
            # [RW] no legal platform this cycle -> re-broadcast (and later decompose).
            assignments.append((order, None))
            continue

        def cost(p: "Platform") -> float:
            # [RW] a platform's self-computed bid: stronger standing and a proven
            # tactic lower the cost; current workload raises it (load balances
            # itself). Lowest bid wins -- emergent allocation, no leader.
            return (
                1.0
                - 0.5 * p.trust
                - 0.4 * tactic_success.get(order.otype, 0.0)
                + 0.6 * p.assigned
                + rng.uniform(0, 0.05)
            )

        winner = min(eligible, key=cost)
        winner.assigned += 1  # [RW] the winner commits capacity to this order
        assignments.append((order, winner))
    return assignments


# ----------------------------------------------------------------------------
# The force. step() runs one full operational cycle.
# [RW] INSTANTIATES the running RYUJIN force: installed doctrine, deployed
# platforms, the shared success signal, the trusted track, and the order ledger.
# ----------------------------------------------------------------------------
class RyujinForce:
    def __init__(
        self, const: MissionConstitution, platforms: List[Platform], rng: random.Random
    ):
        self.const = const  # [RW] the installed mission doctrine
        self.platforms = platforms  # [RW] the deployed force
        self.rng = rng
        # [RW] shared success signal: which ORDER TYPES (tactics) recently paid off.
        # Note: indexed by tactic, NOT by location -- it survives target turnover.
        self.tactic_success: Dict[str, float] = {t: 0.0 for t in ORDER_TYPES}
        # [RW] operator's trusted track; tracks reality slowly (anti-capture).
        self.trusted_track: Vec = TARGET_HOME
        self.orders_issued = 0  # [RW] cumulative orders accepted (the ledger)
        self.orders_completed = 0  # [RW] cumulative orders actually fulfilled
        # [RW] last cycle's coherence horizon (unit: cycles); seeds the TA1<->TA2
        # loop. Starts at the max because cycle 1 has no prior stress assessment.
        self.last_horizon = MAX_HORIZON_CYCLES

    def online_platforms(self) -> List[Platform]:
        return [p for p in self.platforms if p.online]

    def step(
        self, target: Vec, queue: List[Order], compromised: bool
    ) -> Tuple[Dict, List[Order]]:
        const = self.const
        # [RW] start of an operational cycle: clear each platform's committed load.
        for p in self.platforms:
            p.assigned = 0

        # 1) Local sensing: every on-net platform reports its target fix.
        reports = [
            (p, p.report_track(target, const.trusted_prior, self.rng, compromised))
            for p in self.online_platforms()
        ]

        # 2) TA1 robust fusion uses only non-distrusted platforms.
        trusted_reports = [(p, f) for (p, f) in reports if not p.distrusted]
        fused_track, weights = fuse_track(trusted_reports, self.trusted_track)

        # [RW] the trusted track drifts slowly toward the defended consensus: fast
        # enough to follow a moving target, slow enough that a brief spoofing burst
        # cannot capture it. (This rate is the core anti-capture knob.)
        self.trusted_track = vadd(
            vscale(self.trusted_track, 1 - ANCHOR_GAIN),
            vscale(fused_track, ANCHOR_GAIN),
        )

        # 3) Trust update for ALL online platforms (so distrusted can HEAL), with
        #    hysteresis: distrust low, reinstate high. NOTE: trust depends only on
        #    DIRECTIONAL AGREEMENT, never on message volume (a "chatty" honest
        #    platform is not penalized; flooding is handled by quotas elsewhere).
        for plat, fix in reports:
            agree = max(0.0, vcos(fix, fused_track))
            plat.trust = TRUST_GAIN * agree + (1 - TRUST_GAIN) * plat.trust
            if plat.trust < DISTRUST_FLOOR:
                plat.distrusted = True
            elif plat.trust > RETRUST_CEILING:
                plat.distrusted = False

        # 4) CLOSED TA1<->TA2 LOOP: last cycle's coherence horizon caps planning
        # depth. [RW] high horizon (calm, coherent) -> commit near full capacity;
        # low horizon (stressed) -> commit only the most urgent orders and re-plan
        # next cycle. THIS is the single coupling quantity actually bounding
        # coordination -- not merely measured and reported.
        n_online = max(1, len(self.online_platforms()))
        capacity = MAX_ORDERS_PER_PLATFORM * n_online  # unit: orders the force can take
        commit_budget = max(
            1, round(capacity * self.last_horizon / MAX_HORIZON_CYCLES)
        )  # unit: orders sanctioned for commitment this cycle
        to_auction = queue[:commit_budget]
        planning_deferred = queue[commit_budget:]  # postponed by PLAN, not infeasible

        # 5) TA1 leaderless auction over the sanctioned slice, gated by TA2 doctrine.
        assignments = assign_orders(
            to_auction, self.online_platforms(), const, self.tactic_success, self.rng
        )
        # [RW] record which platform won which ORDER TYPE this cycle: this is the
        # dynamic ROLE ALLOCATION. It shifts every cycle and re-routes around
        # distrusted / lost platforms -- emergent, not centrally dictated.
        assignment_log = [
            (order.otype, plat.pid if plat is not None else None)
            for order, plat in assignments
        ]

        # 6) Execution + order ledger; unfilled orders are re-broadcast / decomposed.
        completed_this = 0
        carryover: List[Order] = []
        for order, plat in assignments:
            if plat is None:
                # [RW] unfillable this cycle: re-broadcast, and once chronically
                # stuck, decompose into a simpler order more platforms can take.
                order.attempts += 1
                if order.attempts >= 2:
                    order.decomposed = True
                carryover.append(order)
                continue
            # [RW] attempt execution; success probability reflects fit + standing.
            equipped = const.equipment_for_order[order.otype] in plat.equipment
            p = (
                TASK_SUCCESS_BASE
                * (1.0 if equipped else 0.0)
                * max(0.0, min(1.0, plat.trust))
            )
            if order.decomposed:
                p = min(0.98, p * 1.2)  # [RW] a simpler order is easier to complete
            if (not plat.honest) and compromised:
                p *= 0.1  # [RW] a compromised platform sabotages its own orders
            if self.rng.random() < p:
                completed_this += 1
                self.orders_completed += 1
                # [RW] reinforce the shared success signal for this TACTIC (order type).
                self.tactic_success[order.otype] = (
                    SIGNAL_GAIN + (1 - SIGNAL_GAIN) * self.tactic_success[order.otype]
                )
            else:
                # [RW] decay the success signal when this tactic underperforms.
                self.tactic_success[order.otype] = (
                    1 - SIGNAL_GAIN
                ) * self.tactic_success[order.otype]
                # [RW] CONSERVATION: a failed attempt is not lost work. It is
                # re-broadcast (and, once chronically stuck, decomposed) so the
                # ledger only clears on an ACTUAL completion. This is why backlog
                # can both spike under stress AND burn down once spare capacity
                # returns -- nothing silently vanishes.
                order.attempts += 1
                if order.attempts >= 2:
                    order.decomposed = True
                carryover.append(order)

        # [RW] orders postponed by the planning cap rejoin the queue next cycle.
        carryover.extend(planning_deferred)

        # 7) TA1<->TA2 coupling: coherence + coherence horizon (computed AFTER the
        # cycle and stored in self.last_horizon to gate NEXT cycle's planning).
        # [RW] dispersion of the surviving reports (the decoherence signal) and the
        # gap between the defended track and reality together set the coherence
        # horizon: under stress the controller SHORTENS how far ahead the force is
        # allowed to plan (re-sync often instead of committing a long sequence).
        residuals = [vdist(f, fused_track) for _, f in trusted_reports]
        track_error = vdist(fused_track, target)
        mean_res = sum(residuals) / len(residuals) if residuals else 0.0
        var_res = (
            sum((r - mean_res) ** 2 for r in residuals) / len(residuals)
            if residuals
            else 0.0
        )
        decoherence = var_res / (mean_res**2 + 1e-6)
        coherence = 1.0 / (1.0 + track_error)
        horizon = max(
            1, int(round(MAX_HORIZON_CYCLES / (1.0 + decoherence + track_error)))
        )  # unit: cycles
        # [RW] close the loop: this horizon caps NEXT cycle's planning depth.
        self.last_horizon = horizon

        # [RW] conservation ledger: orders issued minus completed. A growing
        # backlog is surfaced drift, never silently absorbed.
        backlog = self.orders_issued - self.orders_completed
        metrics = {
            "track_error": track_error,  # unit: map-units (fused vs truth)
            "coherence": coherence,  # unit: [0,1] (1 = perfect)
            "horizon": horizon,  # unit: cycles (planning depth granted)
            "commit_budget": commit_budget,  # unit: orders sanctioned this cycle
            "completed": completed_this,  # unit: orders completed this cycle
            "orders": len(queue),  # unit: orders queued this cycle
            "planning_deferred": len(planning_deferred),  # unit: orders postponed
            "backlog": backlog,  # unit: orders (issued minus completed)
            "distrusted": [p.pid for p in self.platforms if p.distrusted],
            "online": len(self.online_platforms()),  # unit: platforms on-net
            "weights": weights,  # FLTrust fusion weights, by platform id
            "tactic_success": dict(self.tactic_success),  # success-signal EMA by tactic
            "assignments": assignment_log,  # dynamic role allocation this cycle
            "decomposed": sum(1 for o in carryover if o.decomposed),
            # --- fields below are for visualization only ---
            "fused_track": fused_track,  # unit: map-units (x, y)
            "trusted_track": self.trusted_track,  # unit: map-units (x, y)
            "fixes": [(p.pid, f, p.honest) for (p, f) in reports],
        }
        return metrics, carryover


class CentralizedBaseline:
    """Legacy single-orchestrator architecture (an SOP/design, not an enemy)."""

    def __init__(self, platforms: List[Platform]):
        # [RW] the legacy/centralized approach: ONE orchestrator fuses everything
        # and allocates everything. It is an ARCHITECTURE we measure against --
        # not a combatant. Its single point of failure is the whole point.
        self.platforms = platforms
        self.orchestrator_online = True
        self.orders_completed = 0

    def step(
        self, target: Vec, orders: List[Order], reports: List[Tuple[Platform, Vec]]
    ) -> Dict:
        if not self.orchestrator_online:
            # [RW] orchestrator lost -> no fusion, no allocation: total collapse.
            return {
                "down": True,
                "track_error": float("inf"),
                "coherence": 0.0,
                "completed": 0,
                "orders": len(orders),
            }
        fused = average_track(reports)
        track_error = vdist(fused, target)
        completed = 0
        pool = [p for p in self.platforms if p.online]
        for order in orders:
            # [RW] central allocation: first capable platform is tasked, no bidding.
            takers = [
                p for p in pool if EQUIPMENT_FOR_ORDER[order.otype] in p.equipment
            ]
            if takers and takers[0].honest:
                completed += 1
                self.orders_completed += 1
        return {
            "down": False,
            "track_error": track_error,
            "coherence": 1.0 / (1.0 + track_error),
            "completed": completed,
            "orders": len(orders),
        }


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------
def build_platforms(
    adversary_ids: Optional[Set[str]] = None, initial_trust: float = INITIAL_TRUST
) -> List[Platform]:
    # [RW] CONSTRUCT a small heterogeneous force. Names describe what each thing
    # IS. By default "compute_node" is the platform that will be compromised.
    # initial_trust sets the starting posture (1.0 = innocent-until-proven-guilty;
    # ZERO_TRUST_START = guilty-until-proven-innocent / earn-your-standing).
    advs = {"compute_node"} if adversary_ids is None else adversary_ids
    roster = [
        ("scout_drone", {"camera"}),
        ("scout_relay_drone", {"camera", "radio"}),
        ("relay_drone", {"radio"}),
        ("compute_node", {"processor"}),
        ("scout_compute_drone", {"camera", "processor"}),
        ("relay_compute_node", {"radio", "processor"}),
    ]
    # [RW] a peer starting below the distrust floor begins SLASHED (it must earn
    # standing before it gets fusion weight or task throughput) -- the zero-trust
    # bootstrap. A peer starting at/above the floor begins admitted (innocent start).
    return [
        Platform(
            pid,
            eq,
            honest=(pid not in advs),
            trust=initial_trust,
            distrusted=(initial_trust < DISTRUST_FLOOR),
        )
        for pid, eq in roster
    ]


def simulate(
    seed: int = SEED,
    compromise_cycle: int = COMPROMISE_CYCLE,
    loss_cycle: int = LOSS_CYCLE,
    adversary_ids: Optional[Set[str]] = None,
    verbose: bool = False,
    on_cycle=None,
    repent_cycle: Optional[int] = None,
    initial_trust: float = INITIAL_TRUST,
) -> Dict:
    """Run one scenario; print a trace if verbose; return summary metrics.

    on_cycle, if given, is called once per cycle with a state dict (used by the
    --viz animation); it has no effect on the simulation itself.

    repent_cycle, if set, is the cycle at which the adversary STOPS spoofing and
    sabotaging. From then on it reports honestly, so recoverable-trust hysteresis
    should heal it back above the reinstate ceiling -- the "watch a node recover"
    demo (enabled by the --heal flag).
    """
    rng = random.Random(seed)
    # [RW] the operator AUTHORS and SIGNS the mission doctrine ONCE here; it is
    # then replicated to every platform and is immutable for the mission.
    const = MissionConstitution(
        mission_id="RYUJIN-DEMO-001",
        trusted_prior=vunit((1.0, 0.5)),
        max_orders_per_platform=MAX_ORDERS_PER_PLATFORM,
        equipment_for_order=EQUIPMENT_FOR_ORDER,
    )

    if verbose:
        print("=" * 74)
        print("RYUJIN localhost simulation (v3)")
        print(f"  mission        : {const.mission_id}")
        print(f"  constitution   : hash={const.content_hash}  sig={const.signature}")
        print(f"  signature ok?  : {const.verify(const.signature)}")
        print(
            f"  invariant      : <= {const.max_orders_per_platform} orders/platform; "
            f"order->equipment {const.equipment_for_order}"
        )
        print(
            f"  compromise at cycle {compromise_cycle}; "
            f"platform loss at cycle {loss_cycle}"
            + (f"; adversary repents at cycle {repent_cycle}" if repent_cycle else "")
        )
        print("=" * 74)

    # [RW] stand up two forces from identical rosters: RYUJIN (decentralized,
    # doctrine-bound) and the centralized baseline it is measured against.
    ryu_platforms = build_platforms(adversary_ids, initial_trust)
    base_platforms = build_platforms(adversary_ids, initial_trust)
    adversary_set = {p.pid for p in ryu_platforms if not p.honest}
    ryu = RyujinForce(const, ryu_platforms, rng)
    base = CentralizedBaseline(base_platforms)

    target: Vec = TARGET_HOME
    carryover: List[Order] = []
    log: List[Tuple[Dict, Dict]] = []

    for c in range(1, CYCLES + 1):
        # [RW] the target moves (mean-reverting walk keeps the run legible).
        target = vadd(
            vadd(vscale(target, 0.88), vscale(TARGET_HOME, 0.12)),
            (rng.gauss(0, 0.18), rng.gauss(0, 0.18)),
        )
        # [RW] a compromise begins at compromise_cycle and persists -- UNLESS a
        # repent_cycle is set, after which the adversary behaves honestly again
        # and recoverable trust is allowed to heal it.
        compromised = (c >= compromise_cycle) and (
            repent_cycle is None or c < repent_cycle
        )

        # [RW] new taskings arrive; added to the order ledger and pooled with
        # anything re-broadcast from prior cycles.
        fresh = [Order(rng.choice(ORDER_TYPES)) for _ in range(NEW_ORDERS_PER_CYCLE)]
        ryu.orders_issued += len(fresh)
        queue = carryover + fresh

        events: List[str] = []
        if c == compromise_cycle and adversary_set:
            events.append(
                "COMPROMISE: "
                + ", ".join(sorted(adversary_set))
                + " spoof reports + sabotage orders"
            )
        if c == loss_cycle:
            # [RW] a platform is lost mid-mission (downed / jammed off-net). We
            # remove the STRONGEST honest one -- the worst case -- from both forces.
            # For the centralized baseline the lost node is also its orchestrator,
            # so the whole baseline goes dark.
            victim_pid = "-"
            for platforms in (ryu_platforms, base_platforms):
                honest_online = [p for p in platforms if p.online and p.honest]
                if not honest_online:
                    continue
                victim = max(honest_online, key=lambda p: p.trust)
                victim.online = False
                victim_pid = victim.pid
            events.append(
                f"PLATFORM LOSS: removed strongest honest platform ({victim_pid})"
            )
            base.orchestrator_online = False
            events.append("CENTRAL ORCHESTRATOR DOWN (single point of failure)")
        if repent_cycle is not None and c == repent_cycle and adversary_set:
            events.append(
                "REPENT: "
                + ", ".join(sorted(adversary_set))
                + " stopped spoofing -- recoverable trust should now heal it"
            )

        # [RW] identical reports feed both forces, for a fair contrast.
        reports = [
            (p, p.report_track(target, const.trusted_prior, rng, compromised))
            for p in base.platforms
            if p.online
        ]

        # [RW] advance both forces one operational cycle.
        m, carryover = ryu.step(target, queue, compromised)
        b = base.step(target, fresh, reports)
        log.append((m, b))

        if on_cycle is not None:
            # [RW] baseline naive-average track + the SAME fixes it fused, so the
            # comparison figure can show the spoof dragging the centralized
            # estimate off-target (before the orchestrator goes dark).
            base_fixes = [(p.pid, f, p.honest) for (p, f) in reports]
            base_fused = None if b.get("down") else average_track(reports)
            on_cycle(
                {
                    "cycle": c,
                    "cycles": CYCLES,
                    "target": target,
                    "metrics": m,
                    "events": events,
                    "base_down": b.get("down", False),
                    "base": {
                        "down": b.get("down", False),
                        "track_error": b.get("track_error"),
                        "coherence": b.get("coherence", 0.0),
                        "completed": b.get("completed", 0),
                        "orders": b.get("orders", 0),
                        "fused": base_fused,
                        "fixes": base_fixes,
                    },
                    "adversary_set": adversary_set,
                    "platforms": [
                        {
                            "pid": p.pid,
                            "trust": p.trust,
                            "online": p.online,
                            "distrusted": p.distrusted,
                            "honest": p.honest,
                        }
                        for p in ryu_platforms
                    ],
                }
            )

        if verbose:
            be = "DOWN" if b.get("down") else f"{b['track_error']:.2f}"
            bd = "--" if b.get("down") else f"{b['completed']}/{b['orders']}"
            print(f"\nCycle {c:2d} | target=({target[0]:.2f},{target[1]:.2f})")
            for e in events:
                print(f"   ** {e}")
            print(
                f"   RYUJIN  : track_err={m['track_error']:.2f}  "
                f"coher={m['coherence']:.2f}  horizon={m['horizon']}  "
                f"done={m['completed']}/{m['orders']}  backlog={m['backlog']}  "
                f"online={m['online']}  distrusted={m['distrusted'] or '-'}"
                + (f"  decomp={m['decomposed']}" if m["decomposed"] else "")
            )
            print(f"   CENTRAL : track_err={be}  done={bd}")
            for adv in sorted(adversary_set):
                if compromised and adv in m["weights"]:
                    print(
                        f"   (FLTrust weight on compromised {adv} = "
                        f"{m['weights'][adv]:.3f})"
                    )
            if m["backlog"] >= BACKLOG_ESCALATION:
                print(
                    f"   !! OPERATOR ESCALATION: order backlog {m['backlog']} >= "
                    f"{BACKLOG_ESCALATION} -- surfacing drift to human boundary"
                )

    # ---- Summary -----------------------------------------------------------
    pre = [(m, b) for i, (m, b) in enumerate(log) if i + 1 < loss_cycle]
    post = [(m, b) for i, (m, b) in enumerate(log) if i + 1 >= loss_cycle]

    def avg(rows, key, side):
        vals = [(m if side == "r" else b).get(key) for m, b in rows]
        vals = [v for v in vals if isinstance(v, (int, float)) and v != float("inf")]
        return sum(vals) / len(vals) if vals else float("nan")

    final_distrusted = set(log[-1][0]["distrusted"])
    honest_wrongly = sorted(final_distrusted - adversary_set)
    adversaries_caught = (
        adversary_set.issubset(final_distrusted) if adversary_set else True
    )
    # [RW] detection latency: cycles from the compromise until EVERY adversary is
    # slashed. Smaller is faster containment. NaN if there is no adversary or it
    # was never fully caught. This is the headline benefit a zero-trust start buys.
    detect_latency = float("nan")
    if adversary_set:
        for i, (m, _b) in enumerate(log):
            if adversary_set.issubset(set(m["distrusted"])):
                detect_latency = max(0, (i + 1) - compromise_cycle)
                break
    # [RW] count cycle-instances where an honest, online platform was sidelined --
    # the availability cost a zero-trust start pays (false-positive benchings).
    honest_bench_instances = 0
    for m, _b in log:
        for pid in m["distrusted"]:
            if pid not in adversary_set:
                honest_bench_instances += 1
    summary = {
        "ryu_completion": ryu.orders_completed / (ryu.orders_issued or 1),
        "base_completion": base.orders_completed / (ryu.orders_issued or 1),
        "ryu_coh_pre": avg(pre, "coherence", "r"),
        "ryu_coh_post": avg(post, "coherence", "r"),
        "base_coh_pre": avg(pre, "coherence", "b"),
        "base_coh_post": avg(post, "coherence", "b"),
        "ryu_final_coh": log[-1][0]["coherence"],
        "honest_wrongly_distrusted": len(honest_wrongly),
        "adversaries_caught": adversaries_caught,
        "detect_latency": detect_latency,
        "honest_bench_instances": honest_bench_instances,
    }

    if verbose:
        loss_coh = log[loss_cycle - 1][0]["coherence"]
        print("\n" + "=" * 74)
        print("SUMMARY (one scripted run -- mechanism illustration, not evidence)")
        print("-" * 74)
        print(f"{'metric':34s}{'RYUJIN':>12s}{'CENTRALIZED':>20s}")
        print(
            f"{'mean track error (pre-loss)':34s}"
            f"{avg(pre,'track_error','r'):>12.2f}{avg(pre,'track_error','b'):>20.2f}"
        )
        print(
            f"{'mean coherence (pre-loss)':34s}"
            f"{summary['ryu_coh_pre']:>12.2f}{summary['base_coh_pre']:>20.2f}"
        )
        print(
            f"{'mean coherence (post-loss)':34s}"
            f"{summary['ryu_coh_post']:>12.2f}{summary['base_coh_post']:>20.2f}"
        )
        print(
            f"{'overall completion rate':34s}"
            f"{summary['ryu_completion']:>12.2f}{summary['base_completion']:>20.2f}"
        )
        print("-" * 74)
        print(
            f"RYUJIN post-loss recovery: coherence {loss_coh:.2f} (loss cycle) "
            f"-> {summary['ryu_final_coh']:.2f} (final)"
        )
        note = (
            "(adversary repented -- recoverable trust healed it back in)"
            if repent_cycle is not None
            else "(expect only the adversary; honest platforms heal)"
        )
        print(f"Final distrusted set: {sorted(final_distrusted) or '-'}  {note}")
        if honest_wrongly:
            print(f"   WARNING: honest platforms wrongly distrusted: {honest_wrongly}")
        print("-" * 74)
        print("FLTrust zeroes the compromised platform's weight; doctrine-anchored,")
        print("recoverable trust isolates ONLY the adversary; unfilled orders are")
        print("re-broadcast and decomposed; and after the platform loss RYUJIN keeps")
        print(
            "coordinating while the centralized orchestrator stays at zero coherence."
        )
        print("=" * 74)

    return summary


def _pct(vals: List[float], q: float) -> float:
    # Nearest-rank percentile (stdlib-only; q in [0, 1]).
    if not vals:
        return float("nan")
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[i]


def _sweep_rows(trials: int, initial_trust: float = INITIAL_TRUST) -> List[Dict]:
    """Run `trials` randomized scenarios and return their per-trial summaries.

    Timing (compromise/loss cycles) and adversary identities are randomized per
    trial off a fixed seed, so the same trial matrix is reused across trust
    postures -- making the innocent-vs-zero-trust comparison apples-to-apples.
    """
    rng = random.Random(SEED)
    roster_ids = [p.pid for p in build_platforms()]
    rows: List[Dict] = []
    for t in range(trials):
        comp = rng.randint(2, CYCLES - 2)  # compromise can begin almost anytime
        loss = rng.randint(comp + 1, CYCLES)  # loss always after the compromise
        n_adv = rng.randint(0, 2)  # 0, 1, or 2 of 6 platforms compromised
        advs = set(rng.sample(roster_ids, n_adv)) if n_adv else set()
        rows.append(
            simulate(
                SEED + 1 + t,
                comp,
                loss,
                advs,
                verbose=False,
                initial_trust=initial_trust,
            )
        )
    return rows


def run_sweep(trials: int = 200) -> None:
    """Monte Carlo over randomized seed, fault timing, and adversary fraction.

    This is the honest answer to "your scripted run looks lucky": timing and
    adversary identities are randomized each trial, so the table below brackets
    average-case behavior instead of one hand-picked scenario.
    """
    rows = _sweep_rows(trials)

    print("=" * 74)
    print(f"RYUJIN Monte Carlo sweep -- {trials} randomized trials")
    print("  randomized per trial: seed, compromise cycle, loss cycle,")
    print("  adversary count (0-2 of 6) and identities")
    print("=" * 74)
    print(f"{'metric':32s}{'p10':>9s}{'p50':>9s}{'p90':>9s}{'mean':>9s}")
    table = [
        ("RYUJIN completion rate", "ryu_completion"),
        ("CENTRAL completion rate", "base_completion"),
        ("RYUJIN coherence (post-loss)", "ryu_coh_post"),
        ("CENTRAL coherence (post-loss)", "base_coh_post"),
        ("RYUJIN final coherence", "ryu_final_coh"),
    ]
    for label, key in table:
        vals = [
            r[key]
            for r in rows
            if isinstance(r[key], (int, float)) and r[key] == r[key]
        ]
        mean = sum(vals) / len(vals) if vals else float("nan")
        print(
            f"{label:32s}{_pct(vals,0.1):>9.2f}{_pct(vals,0.5):>9.2f}"
            f"{_pct(vals,0.9):>9.2f}{mean:>9.2f}"
        )
    print("-" * 74)
    clean = sum(1 for r in rows if r["honest_wrongly_distrusted"] == 0)
    caught = sum(1 for r in rows if r["adversaries_caught"])
    won = sum(1 for r in rows if r["ryu_completion"] >= r["base_completion"])
    print(f"trials with ZERO honest platforms wrongly distrusted : {clean}/{trials}")
    print(f"trials where all adversaries ended distrusted        : {caught}/{trials}")
    print(f"trials where RYUJIN completion >= centralized        : {won}/{trials}")
    print("=" * 74)


def _adv_rows(rows: List[Dict]) -> List[Dict]:
    # only trials that actually had an adversary (latency is undefined otherwise)
    return [r for r in rows if r["detect_latency"] == r["detect_latency"]]


def run_trust_tradeoff(trials: int = 200) -> None:
    """Quantify the trust-posture tradeoff: innocent-start vs zero-trust-start.

    Runs the SAME randomized trial matrix under both postures and prints a
    side-by-side. The point is to make the tradeoff explicit and citable rather
    than asserted: a zero-trust start should contain adversaries at least as
    fast, at the cost of early throughput and some honest benchings while the
    force bootstraps its own standing.

        innocent-until-proven-guilty (start 1.0): peers begin fully trusted.
        zero-trust / earn-your-standing (start at the floor): peers begin with
            no fusion weight and must agree with the defended track to gain it.
    """
    innocent = _sweep_rows(trials, INITIAL_TRUST)
    zerotr = _sweep_rows(trials, ZERO_TRUST_START)

    def stat(rows: List[Dict], key: str, q: float = 0.5) -> float:
        vals = [
            r[key]
            for r in rows
            if isinstance(r[key], (int, float)) and r[key] == r[key]
        ]
        return _pct(vals, q)

    def mean(rows: List[Dict], key: str) -> float:
        vals = [
            r[key]
            for r in rows
            if isinstance(r[key], (int, float)) and r[key] == r[key]
        ]
        return sum(vals) / len(vals) if vals else float("nan")

    inn_adv = _adv_rows(innocent)
    zt_adv = _adv_rows(zerotr)

    print("=" * 74)
    print(f"RYUJIN trust-posture tradeoff -- {trials} randomized trials, both postures")
    print(
        f"  posture A: innocent-until-proven-guilty (start trust {INITIAL_TRUST:.2f})"
    )
    print(
        f"  posture B: zero-trust / earn-standing   (start trust {ZERO_TRUST_START:.2f})"
    )
    print("=" * 74)
    print(f"{'metric':40s}{'innocent':>16s}{'zero-trust':>16s}")
    print("-" * 74)
    print(
        f"{'adversary detect latency (p50 cycles)':40s}"
        f"{stat(inn_adv,'detect_latency'):>16.2f}{stat(zt_adv,'detect_latency'):>16.2f}"
    )
    print(
        f"{'adversary detect latency (mean cycles)':40s}"
        f"{mean(inn_adv,'detect_latency'):>16.2f}{mean(zt_adv,'detect_latency'):>16.2f}"
    )
    print(
        f"{'honest benchings (mean cycle-instances)':40s}"
        f"{mean(innocent,'honest_bench_instances'):>16.2f}"
        f"{mean(zerotr,'honest_bench_instances'):>16.2f}"
    )
    print(
        f"{'overall completion rate (mean)':40s}"
        f"{mean(innocent,'ryu_completion'):>16.2f}{mean(zerotr,'ryu_completion'):>16.2f}"
    )
    print(
        f"{'final coherence (mean)':40s}"
        f"{mean(innocent,'ryu_final_coh'):>16.2f}{mean(zerotr,'ryu_final_coh'):>16.2f}"
    )
    inn_caught = sum(1 for r in inn_adv if r["adversaries_caught"])
    zt_caught = sum(1 for r in zt_adv if r["adversaries_caught"])
    print(
        f"{'adversaries fully caught':40s}"
        f"{inn_caught:>13d}/{len(inn_adv):<2d}{zt_caught:>13d}/{len(zt_adv):<2d}"
    )
    print("-" * 74)
    print("Read: zero-trust trades early throughput (and some honest benchings while")
    print("the force earns its own standing) for faster, stricter adversary")
    print("containment. The architecture supports BOTH; the abstract demonstrates the")
    print("balanced innocent-start posture and cites this sweep for the alternative.")
    print("=" * 74)


# ----------------------------------------------------------------------------
# Visualization + asset export (matplotlib; the ONLY non-stdlib dependency).
# Shared drawing lives in _paint_panels so the live view, the per-cycle frame
# export, the GIF, and the static abstract "filmstrip" all stay in sync.
# ----------------------------------------------------------------------------
def _map_legend():
    # [RW] explicit proxy handles so EVERY marker -- including the red spoof X --
    # is named in the legend (the fixes are scatter-plotted in a loop).
    from matplotlib.lines import Line2D  # type: ignore[import-not-found]

    def _h(marker, fc, label, ms=8, ec="k"):
        return Line2D(
            [0],
            [0],
            marker=marker,
            color="w",
            markerfacecolor=fc,
            markeredgecolor=ec,
            markersize=ms,
            label=label,
        )

    return [
        _h("o", "tab:green", "honest fix (one agent's estimate)"),
        _h("X", "tab:red", "spoofed fix (compromised agent)"),
        _h(
            "o",
            "none",
            "distrusted: slashed from fusion (RYUJIN only)",
            ms=12,
            ec="red",
        ),
        _h(
            "*",
            "tab:blue",
            "estimate star -- RYUJIN: ROBUST fused track | centralized: NAIVE average",
            ms=14,
        ),
        _h("o", "none", "ground truth (true target state)", ms=10),
    ]


def _trust_band(ax, legend: bool = False) -> None:
    """Shade the recoverable-reputation hysteresis band on a trust axis.

    The mechanism is hysteresis, so a single line undersells it. Below the
    DISTRUST_FLOOR a platform is slashed from fusion; it cannot rejoin until its
    trust climbs back above the (higher) RETRUST_CEILING. The shaded gap between
    them is the limbo band -- drawn explicitly because it IS the mechanism.
    Y-axis is a dimensionless trust score in [0,1] (an EMA of directional
    agreement), ticked every 0.1 so the two thresholds are easy to read off.
    """
    ax.axhspan(DISTRUST_FLOOR, RETRUST_CEILING, color="orange", alpha=0.12, zorder=0)
    ax.axhline(
        DISTRUST_FLOOR,
        color="r",
        ls="--",
        lw=0.8,
        label=f"distrust floor ({DISTRUST_FLOOR:.2f}) -> slashed",
    )
    ax.axhline(
        RETRUST_CEILING,
        color="tab:green",
        ls="--",
        lw=0.8,
        label=f"reinstate ceiling ({RETRUST_CEILING:.2f}) -> rejoins",
    )
    ax.set_yticks([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    if legend:
        ax.legend(loc="lower right", fontsize=6)


# Categorical colors for the dynamic role-allocation heatmap. Index order must
# match the codes produced by _role_grid(): 0 idle, 1 scout, 2 relay, 3 analyze,
# 4 multi (two order types in one cycle), 5 distrusted (slashed), 6 offline.
#
# COLOR FAMILY = STATE, not just role: every TRUSTED (honest, online) role gets a
# shade on a single white->dark-blue ramp (idle = palest, analyze = darkest), so
# the eye reads "all of these are trusted agents doing different jobs." This keeps
# the heatmap from re-using GREEN, which everywhere else in the figure (battlespace
# honest fix, trust bars, reinstate ceiling) means "trusted." The two non-trusted
# states keep the figure-wide signal colors: RED = distrusted/slashed (same red as
# the spoofed-fix X), GRAY = offline/lost. "multi" (an emergent auction outcome --
# one agent winning two order types in a cycle, not an agent attribute) is purple.
_ROLE_COLORS = [
    "#deebf7",  # 0 idle (trusted, won nothing this cycle) -- palest blue
    "#9ecae1",  # 1 scout    -- light blue   (trusted)
    "#4292c6",  # 2 relay    -- medium blue  (trusted)  [was green; green=trusted]
    "#08519c",  # 3 analyze  -- dark blue    (trusted)
    "#b07aa1",  # 4 multi (emergent: two order types in one cycle) -- purple
    "#d62728",  # 5 distrusted: SAME red as the spoofed-fix X / trust bar (slashed)
    "#cfcfcf",  # 6 offline (lost / off-net) -- gray
]
_ROLE_LABELS = [
    "idle",
    "scout",
    "relay",
    "analyze",
    "multi",
    "distrusted",
    "offline (lost)",
]


def _int_cycle_axis(ax, cycles: int) -> None:
    """Force integer cycle ticks (cycles are whole OODA loops, never fractional)."""
    ax.set_xticks(range(2, cycles + 1, 2))


def _role_grid(states: List[Dict], pids: List[str]):
    """Build a platforms x cycles grid of role codes for the heatmap.

    Code per (platform, cycle): 0 idle, 1 scout, 2 relay, 3 analyze, 4 multi
    (two distinct order types in one cycle), 5 distrusted (trust below floor, so
    doctrine sidelines it), 6 offline (lost / off-net). 5 and 6 are kept
    separate so the heatmap distinguishes "we stopped trusting it" from "it is
    simply gone." This visualizes that roles are ALLOCATED DYNAMICALLY by the
    auction and BOUNDED by doctrine -- a sidelined platform can win nothing.
    """
    type_code = {"scout": 1, "relay": 2, "analyze": 3}
    grid = [[0 for _ in states] for _ in pids]
    row_of = {pid: i for i, pid in enumerate(pids)}
    for col, s in enumerate(states):
        status = {p["pid"]: p for p in s["platforms"]}
        per_pid: Dict[str, set] = {pid: set() for pid in pids}
        for otype, pid in s["metrics"].get("assignments", []):
            if pid in per_pid:
                per_pid[pid].add(otype)
        for pid in pids:
            st = status.get(pid, {})
            if not st.get("online", True):
                grid[row_of[pid]][col] = 6  # offline / lost
            elif st.get("distrusted", False):
                grid[row_of[pid]][col] = 5  # distrusted (slashed by doctrine)
            elif not per_pid[pid]:
                grid[row_of[pid]][col] = 0  # eligible but idle this cycle
            elif len(per_pid[pid]) == 1:
                grid[row_of[pid]][col] = type_code[next(iter(per_pid[pid]))]
            else:
                grid[row_of[pid]][col] = 4  # two order types in one cycle
    return grid


def _draw_role_heatmap(ax, states: List[Dict]) -> None:
    """Render the dynamic role-allocation heatmap onto ax (uses matplotlib)."""
    from matplotlib.colors import (  # type: ignore[import-not-found]
        BoundaryNorm,
        ListedColormap,
    )
    from matplotlib.patches import Patch  # type: ignore[import-not-found]

    pids = [p["pid"] for p in states[0]["platforms"]]
    grid = _role_grid(states, pids)
    cmap = ListedColormap(_ROLE_COLORS)
    norm = BoundaryNorm(range(len(_ROLE_COLORS) + 1), cmap.N)
    ax.imshow(grid, aspect="auto", cmap=cmap, norm=norm, origin="upper")
    # Title sits highest; the legend is lifted into a single horizontal strip
    # ABOVE the heatmap (like the battlespace legend over the top row) instead of
    # crowding the right margin. `pad` reserves vertical room for both.
    ax.set_title(
        "Dynamic role allocation (auction-assigned each cycle, bounded by doctrine)",
        fontsize=9,
        pad=30,
    )
    ax.set_xlabel("cycle")
    ax.set_xticks(range(len(states)))
    ax.set_xticklabels([str(s["cycle"]) for s in states], fontsize=6)
    ax.set_yticks(range(len(pids)))
    ax.set_yticklabels(pids, fontsize=6)
    ax.set_xticks([x - 0.5 for x in range(1, len(states))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(pids))], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)
    handles = [
        Patch(facecolor=_ROLE_COLORS[i], edgecolor="0.6", label=_ROLE_LABELS[i])
        for i in range(len(_ROLE_LABELS))
    ]
    ax.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=len(_ROLE_LABELS),
        fontsize=6,
        frameon=True,
        columnspacing=1.1,
        handletextpad=0.4,
        borderpad=0.4,
    )


def _banner(state: Dict) -> str:
    b = f"cycle {state['cycle']}/{state['cycles']}"
    if state["events"]:
        b += "  |  " + "  ".join(state["events"])
    if state["base_down"]:
        b += "  |  CENTRAL BASELINE DOWN"
    return "RYUJIN -- live TA1/TA2 simulation\n" + b


def _compare_banner(state: Dict) -> str:
    """Short head-to-head suptitle (heading + cycle only). The verbose per-cycle
    events are drawn separately as a wrapped sub-line so a long event string can
    never run off the right edge of the figure."""
    return (
        "OLD centralized baseline  vs  RYUJIN"
        f"   --   cycle {state['cycle']}/{state['cycles']}"
    )


def _compare_events(state: Dict) -> str:
    """Concise, wrappable event sub-line for the compare animation."""
    parts = list(state["events"])
    if state["base_down"]:
        parts.append("centralized control lost")
    return "  |  ".join(parts)


def _empty_hist() -> Dict[str, List]:
    return {"truth": [], "cycle": [], "coh": [], "hz": [], "back": [], "done": []}


def _push_hist(hist: Dict[str, List], state: Dict) -> None:
    m = state["metrics"]
    hist["truth"].append(state["target"])
    hist["cycle"].append(state["cycle"])
    hist["coh"].append(m["coherence"])
    hist["hz"].append(m["horizon"])
    hist["back"].append(m["backlog"])
    hist["done"].append(m["completed"])


def _paint_panels(axes, hist, state, map_legend) -> None:
    """Paint the four standard panels onto the supplied axes (shared by the live
    animation and the saved frames). axes = (ax_map, ax_coh, ax_hz, ax_trust,
    ax_back); ax_hz is ax_coh's twin carrying the horizon line."""
    ax_map, ax_coh, ax_hz, ax_trust, ax_back = axes
    m = state["metrics"]
    cycles = state["cycles"]

    # --- battlespace map ---
    ax_map.clear()
    ax_map.set_title("Battlespace: fixes / fused track / truth", fontsize=9)
    ax_map.set_xlim(-3.5, 3.5)
    ax_map.set_ylim(-2.0, 2.5)
    ax_map.set_xlabel("map-units (x)")
    ax_map.set_ylabel("map-units (y)")
    if len(hist["truth"]) > 1:
        ax_map.plot(
            [p[0] for p in hist["truth"]],
            [p[1] for p in hist["truth"]],
            color="0.75",
            lw=1,
            zorder=1,
        )
    # [RW] platforms whose trust fell below DISTRUST_FLOOR this cycle: their
    # fix is RINGED to show it has been slashed (excluded from the fusion).
    distrusted_pids = {p["pid"] for p in state["platforms"] if p["distrusted"]}
    for pid, fix, honest in m["fixes"]:
        ax_map.scatter(
            fix[0],
            fix[1],
            c=("tab:green" if honest else "tab:red"),
            marker=("o" if honest else "X"),
            s=70,
            alpha=0.85,
            edgecolors="k",
            linewidths=0.4,
            zorder=3,
        )
        if pid in distrusted_pids:
            # [RW] red ring = trust slashed; this report no longer counts.
            ax_map.scatter(
                fix[0],
                fix[1],
                s=190,
                facecolors="none",
                edgecolors="red",
                linewidths=1.8,
                marker="o",
                zorder=7,
            )
    ax_map.scatter(
        *m["fused_track"], c="tab:blue", marker="*", s=280, edgecolors="k", zorder=5
    )
    # NOTE: the trusted anchor (trusted_track) is deliberately NOT plotted here.
    # In this spatial view it lands almost on top of the fused star (it is a slow
    # EMA of that very track), so it adds no spatial information -- but a marker
    # present in RYUJIN and absent in the centralized panel invites a skimming
    # reviewer to misread it as "the trick." The anchor's real job (anti-capture)
    # is shown where it cannot be misread: the "anchor vs truth" error line in the
    # --compare figure's supporting row.
    ax_map.scatter(
        *state["target"],
        facecolors="none",
        edgecolors="k",
        marker="o",
        s=150,
        linewidths=1.8,
        zorder=6,
    )
    ax_map.legend(handles=map_legend, loc="upper left", fontsize=6)
    ax_map.text(
        0.98,
        0.02,
        "ABSTRACT agreement-space, NOT a terrain map.\n"
        "Points are ESTIMATES of the target's state (fixes),\n"
        "not agent positions. Clustering = consensus, not swarming.",
        transform=ax_map.transAxes,
        ha="right",
        va="bottom",
        fontsize=6,
        color="0.35",
        bbox=dict(boxstyle="round", fc="white", ec="0.8", alpha=0.85),
    )

    # --- TA2 -> TA1 coupling ---
    ax_coh.clear()
    ax_hz.clear()
    ax_coh.set_title("TA2->TA1 coupling: coherence drives horizon", fontsize=9)
    ax_coh.set_xlim(1, cycles)
    ax_coh.set_ylim(0, 1.05)
    ax_coh.set_xlabel("cycle")
    ax_coh.set_ylabel("coherence [0,1]", color="tab:blue")
    ax_coh.plot(hist["cycle"], hist["coh"], "-o", color="tab:blue")
    _int_cycle_axis(ax_coh, cycles)
    ax_hz.set_ylim(0, MAX_HORIZON_CYCLES + 0.5)
    ax_hz.set_ylabel("horizon (cycles)", color="tab:orange")
    # [RW] horizon is an INTEGER count of cycles, so a step plot is more honest
    # than a smooth line; the dotted line marks the doctrine-sanctioned ceiling.
    ax_hz.plot(
        hist["cycle"],
        hist["hz"],
        drawstyle="steps-post",
        marker="s",
        color="tab:orange",
    )
    ax_hz.axhline(MAX_HORIZON_CYCLES, color="tab:orange", ls=":", lw=0.8)
    ax_hz.set_yticks(range(0, MAX_HORIZON_CYCLES + 1, 2))

    # --- per-platform trust ---
    ax_trust.clear()
    ax_trust.set_title("Per-platform trust (red=distrusted, grey=offline)", fontsize=9)
    snaps = state["platforms"]
    names = [p["pid"] for p in snaps]
    colors = [
        "0.6" if not p["online"] else ("tab:red" if p["distrusted"] else "tab:green")
        for p in snaps
    ]
    ax_trust.bar(range(len(names)), [p["trust"] for p in snaps], color=colors)
    _trust_band(ax_trust, legend=True)
    ax_trust.set_ylim(0, 1.05)
    ax_trust.set_ylabel("trust score [0,1] (dimensionless)")
    ax_trust.set_xticks(range(len(names)))
    ax_trust.set_xticklabels(names, rotation=30, ha="right", fontsize=6)

    # --- conservation ledger ---
    ax_back.clear()
    ax_back.set_title("Conservation ledger: deferred backlog & completions", fontsize=9)
    ax_back.set_xlim(1, cycles)
    ax_back.set_xlabel("cycle")
    ax_back.set_ylabel("orders")
    ax_back.bar(
        hist["cycle"],
        hist["done"],
        color="tab:green",
        alpha=0.4,
        label="completed/cycle",
    )
    ax_back.plot(
        hist["cycle"], hist["back"], "-o", color="tab:red", label="deferred backlog"
    )
    ax_back.axhline(
        BACKLOG_ESCALATION,
        color="r",
        ls="--",
        lw=0.8,
        label="operator-review threshold",
    )
    ax_back.legend(loc="upper left", fontsize=7)
    _int_cycle_axis(ax_back, cycles)


def run_viz(
    delay: float = 0.6,
    repent_cycle: Optional[int] = None,
    initial_trust: float = INITIAL_TRUST,
) -> None:
    """Live matplotlib animation of one scripted run.

    Renders four panels per cycle: the battlespace (platform fixes, fused track,
    ground truth), the TA2->TA1 coupling (coherence + horizon), per-platform
    trust, and the conservation ledger (backlog + completions).
    matplotlib is the ONLY non-stdlib dependency, imported lazily here so the
    other run modes stay dependency-free.

    delay -- unit: seconds of wall-clock pause per cycle (animation speed).
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        print("Visualization needs matplotlib.  Install with:  pip install matplotlib")
        print("Then re-run:  python sim/ryujin_sim.py --viz")
        return

    plt.ion()
    fig, ((ax_map, ax_coh), (ax_trust, ax_back)) = plt.subplots(2, 2, figsize=(13, 8))
    ax_hz = ax_coh.twinx()  # one twin for the horizon line; reused every frame
    map_legend = _map_legend()
    hist = _empty_hist()

    def on_cycle(state: Dict) -> None:
        _push_hist(hist, state)
        _paint_panels(
            (ax_map, ax_coh, ax_hz, ax_trust, ax_back), hist, state, map_legend
        )
        fig.suptitle(_banner(state), fontweight="bold", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        plt.pause(max(0.01, delay))

    simulate(
        verbose=False,
        on_cycle=on_cycle,
        repent_cycle=repent_cycle,
        initial_trust=initial_trust,
    )
    print("Visualization complete. Close the window to exit.")
    plt.ioff()
    plt.show()


def _collect_states(repent_cycle: Optional[int] = None) -> List[Dict]:
    """Run one scenario and capture every per-cycle state dict (for asset export).
    Each state is freshly built by simulate(), so storing references is safe."""
    states: List[Dict] = []
    simulate(verbose=False, on_cycle=states.append, repent_cycle=repent_cycle)
    return states


def export_animation(
    repent_cycle: Optional[int] = None,
    frames_dir: Optional[str] = None,
    gif_path: Optional[str] = None,
    duration_ms: int = 700,
) -> None:
    """Render each cycle's four-panel figure to PNG and (optionally) stitch a GIF.

    frames_dir -- keep the per-cycle PNGs here (created if absent). If None and a
                  GIF is requested, a temporary directory is used then removed.
    gif_path   -- if set, assemble the frames into an animated GIF (needs Pillow,
                  which matplotlib already depends on).
    """
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")  # headless: write files, open no window
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        print("Export needs matplotlib.  Install with:  pip install matplotlib")
        return

    import os
    import tempfile

    states = _collect_states(repent_cycle)
    map_legend = _map_legend()

    own_tmp = False
    if frames_dir is None:
        frames_dir = tempfile.mkdtemp(prefix="ryujin_frames_")
        own_tmp = True
    os.makedirs(frames_dir, exist_ok=True)

    paths: List[str] = []
    for i, state in enumerate(states):
        fig, ((ax_map, ax_coh), (ax_trust, ax_back)) = plt.subplots(
            2, 2, figsize=(13, 8)
        )
        ax_hz = ax_coh.twinx()
        hist = _empty_hist()
        for s in states[: i + 1]:
            _push_hist(hist, s)
        _paint_panels(
            (ax_map, ax_coh, ax_hz, ax_trust, ax_back), hist, state, map_legend
        )
        fig.suptitle(_banner(state), fontweight="bold", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        p = os.path.join(frames_dir, f"frame_{state['cycle']:02d}.png")
        fig.savefig(p, dpi=110)
        plt.close(fig)
        paths.append(p)

    if gif_path:
        try:
            from PIL import Image  # type: ignore[import-not-found]
        except Exception:
            print("GIF assembly needs Pillow.  Install with:  pip install pillow")
        else:
            imgs = [Image.open(p) for p in paths]
            durations = [duration_ms] * len(imgs)
            if durations:
                durations[-1] = duration_ms * 3  # hold the final frame
            imgs[0].save(
                gif_path,
                save_all=True,
                append_images=imgs[1:],
                duration=durations,
                loop=0,
            )
            print(f"Wrote GIF: {gif_path}  ({len(imgs)} frames)")

    if not own_tmp:
        print(f"Wrote {len(paths)} frames to: {frames_dir}")
    else:
        import shutil

        shutil.rmtree(frames_dir, ignore_errors=True)


def _compare_legend_handles():
    """Legend for the side-by-side animation. The blue star is DELIBERATELY named
    twice over (one entry, explicit both-ways) and the purple anchor is flagged as
    RYUJIN-only AND endogenous, so a reviewer cannot read the contrast as 'RYUJIN
    just gets a human truth feed the baseline lacks.'"""
    from matplotlib.lines import Line2D  # type: ignore[import-not-found]

    def _h(marker, fc, label, ms=8, ec="k"):
        return Line2D(
            [0],
            [0],
            marker=marker,
            color="w",
            markerfacecolor=fc,
            markeredgecolor=ec,
            markersize=ms,
            label=label,
        )

    return [
        _h("o", "tab:green", "honest fix (one agent's estimate)"),
        _h("X", "tab:red", "spoofed fix (compromised agent)"),
        _h("o", "none", "distrusted / slashed (RYUJIN only)", ms=12, ec="red"),
        _h(
            "*",
            "tab:blue",
            "estimate star -- LEFT: naive average (dragged) | RIGHT: robust fused (pinned)",
            ms=14,
        ),
        _h("o", "none", "ground truth (true target state)", ms=10),
    ]


_COMPARE_CAPTION = (
    "Both forces ingest the IDENTICAL reports each cycle; only the fusion rule "
    "differs -- RYUJIN uses robust trust / direction weighting, the baseline a "
    "naive average. No live human correction is applied in either panel."
)


def _paint_compare(fig, gs, state: Dict) -> None:
    """Draw one cycle's two battlespace panels (centralized LEFT, RYUJIN RIGHT)
    onto an existing figure/gridspec, with fixed role titles (the per-cycle tag
    lives in the suptitle, so each panel keeps a stable, comparable heading)."""
    ax_cen = fig.add_subplot(gs[0, 0])
    _draw_mini_centralized(ax_cen, state)
    ax_cen.set_title("OLD centralized -- naive average of all reports", fontsize=10)

    ax_ryu = fig.add_subplot(gs[0, 1])
    _draw_mini(ax_ryu, state)
    ax_ryu.set_title(
        "RYUJIN -- robust fusion (trust / direction weighted)", fontsize=10
    )


def run_viz_compare(
    delay: float = 0.9,
    repent_cycle: Optional[int] = None,
    initial_trust: float = INITIAL_TRUST,
) -> None:
    """LIVE side-by-side battlespace: watch the centralized estimate get dragged
    off-target (and finally blink out when the lone orchestrator dies) next to
    RYUJIN holding the track, ringing the spoofer, and coordinating through a
    real loss. Needs matplotlib with an interactive backend."""
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        print("Visualization needs matplotlib.  Install with:  pip install matplotlib")
        return

    plt.ion()
    fig = plt.figure(figsize=(12, 6.8))
    handles = _compare_legend_handles()

    def on_cycle(state: Dict) -> None:
        fig.clear()
        gs = fig.add_gridspec(
            1, 2, left=0.04, right=0.98, top=0.84, bottom=0.30, wspace=0.08
        )
        _paint_compare(fig, gs, state)
        fig.suptitle(_compare_banner(state), fontweight="bold", fontsize=12)
        _ev = _compare_events(state)
        if _ev:
            fig.text(
                0.5,
                0.90,
                _ev,
                ha="center",
                va="top",
                fontsize=8.5,
                color="0.25",
                wrap=True,
            )
        fig.legend(
            handles=handles,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.105),
            ncol=2,
            fontsize=8,
            frameon=True,
        )
        fig.text(
            0.5,
            0.015,
            _COMPARE_CAPTION,
            ha="center",
            fontsize=7.5,
            style="italic",
            wrap=True,
        )
        plt.pause(max(0.01, delay))

    simulate(
        verbose=False,
        on_cycle=on_cycle,
        repent_cycle=repent_cycle,
        initial_trust=initial_trust,
    )
    print("Visualization complete. Close the window to exit.")
    plt.ioff()
    plt.show()


def export_compare_animation(
    repent_cycle: Optional[int] = None,
    frames_dir: Optional[str] = None,
    gif_path: Optional[str] = None,
    duration_ms: int = 900,
) -> None:
    """Headless render of the side-by-side battlespace -- one frame per cycle,
    centralized (naive mean) LEFT vs RYUJIN (robust fusion) RIGHT -- then stitch
    an animated GIF. This is the moving version of the filmstrip's top two rows.

    Reviewer framing baked into the legend + caption: both panels ingest the
    IDENTICAL reports each cycle, so the only difference is the fusion RULE (robust
    trust / direction weighting vs naive average) -- not privileged information the
    baseline is denied. The trusted anchor is intentionally NOT drawn in these
    spatial panels (it lands on the fused star); its anti-capture role is evidenced
    in the --compare figure's "anchor vs truth" error line instead."""
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")  # headless: write files, open no window
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        print("Export needs matplotlib.  Install with:  pip install matplotlib")
        return

    import os
    import tempfile

    states = _collect_states(repent_cycle)
    handles = _compare_legend_handles()

    own_tmp = False
    if frames_dir is None:
        frames_dir = tempfile.mkdtemp(prefix="ryujin_cmp_frames_")
        own_tmp = True
    os.makedirs(frames_dir, exist_ok=True)

    paths: List[str] = []
    for state in states:
        fig = plt.figure(figsize=(12, 6.8))
        gs = fig.add_gridspec(
            1, 2, left=0.04, right=0.98, top=0.84, bottom=0.30, wspace=0.08
        )
        _paint_compare(fig, gs, state)
        fig.suptitle(_compare_banner(state), fontweight="bold", fontsize=12)
        _ev = _compare_events(state)
        if _ev:
            fig.text(
                0.5,
                0.90,
                _ev,
                ha="center",
                va="top",
                fontsize=8.5,
                color="0.25",
                wrap=True,
            )
        fig.legend(
            handles=handles,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.105),
            ncol=2,
            fontsize=8,
            frameon=True,
        )
        fig.text(
            0.5,
            0.015,
            _COMPARE_CAPTION,
            ha="center",
            fontsize=7.5,
            style="italic",
            wrap=True,
        )
        p = os.path.join(frames_dir, f"cmp_frame_{state['cycle']:02d}.png")
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)

    if gif_path:
        try:
            from PIL import Image  # type: ignore[import-not-found]
        except Exception:
            print("GIF assembly needs Pillow.  Install with:  pip install pillow")
        else:
            imgs = [Image.open(p) for p in paths]
            durations = [duration_ms] * len(imgs)
            if durations:
                durations[-1] = duration_ms * 3  # hold the final frame
            imgs[0].save(
                gif_path,
                save_all=True,
                append_images=imgs[1:],
                duration=durations,
                loop=0,
            )
            print(f"Wrote compare GIF: {gif_path}  ({len(imgs)} frames)")

    if not own_tmp:
        print(f"Wrote {len(paths)} compare frames to: {frames_dir}")
    else:
        import shutil

        shutil.rmtree(frames_dir, ignore_errors=True)


def _draw_mini(ax, state: Dict, tag: str = "") -> None:
    """Compact battlespace snapshot for the static filmstrip (no axes ticks)."""
    m = state["metrics"]
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-2.0, 2.5)
    ax.set_xticks([])
    ax.set_yticks([])
    distrusted_pids = {p["pid"] for p in state["platforms"] if p["distrusted"]}
    for pid, fix, honest in m["fixes"]:
        ax.scatter(
            fix[0],
            fix[1],
            c=("tab:green" if honest else "tab:red"),
            marker=("o" if honest else "X"),
            s=42,
            alpha=0.85,
            edgecolors="k",
            linewidths=0.3,
            zorder=3,
        )
        if pid in distrusted_pids:
            ax.scatter(
                fix[0],
                fix[1],
                s=120,
                facecolors="none",
                edgecolors="red",
                linewidths=1.3,
                marker="o",
                zorder=7,
            )
    ax.scatter(
        *m["fused_track"], c="tab:blue", marker="*", s=150, edgecolors="k", zorder=5
    )
    # NOTE: trusted anchor deliberately not plotted in the spatial view -- see the
    # rationale in _paint_panels. The anchor's anti-capture story lives in the
    # "anchor vs truth" error line of the --compare figure, not here.
    ax.scatter(
        *state["target"],
        facecolors="none",
        edgecolors="k",
        marker="o",
        s=90,
        linewidths=1.3,
        zorder=6,
    )
    title = f"cycle {state['cycle']}"
    if tag:
        title += f"\n{tag}"
    ax.set_title(title, fontsize=8)


def _draw_mini_centralized(ax, state: Dict, tag: str = "") -> None:
    """Same battlespace frame for the OLD centralized approach (the contrast row).

    Key differences from the RYUJIN mini:
      * the spoofed fix (red X) is NEVER ringed -- the centralized averager has no
        robust-trust mechanism, so it never identifies the insider;
      * the shown estimate (blue star) is the NAIVE AVERAGE, which the spoof drags
        off the true target -- the shared picture decoheres;
      * once the single orchestrator is lost (the baseline's single point of
        failure), there is no estimate at all -> "control lost".
    """
    b = state["base"]
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-2.0, 2.5)
    ax.set_xticks([])
    ax.set_yticks([])
    for _pid, fix, honest in b["fixes"]:
        ax.scatter(
            fix[0],
            fix[1],
            c=("tab:green" if honest else "tab:red"),
            marker=("o" if honest else "X"),
            s=42,
            alpha=0.85,
            edgecolors="k",
            linewidths=0.3,
            zorder=3,
        )
        # NOTE: deliberately NO distrust ring -- centralized never catches it.
    if b.get("fused") is not None:
        ax.scatter(
            *b["fused"], c="tab:blue", marker="*", s=150, edgecolors="k", zorder=5
        )
    ax.scatter(
        *state["target"],
        facecolors="none",
        edgecolors="k",
        marker="o",
        s=90,
        linewidths=1.3,
        zorder=6,
    )
    if b.get("down"):
        ax.text(
            0.5,
            0.5,
            "CONTROL LOST\n(single orchestrator down)",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=7,
            fontweight="bold",
            color="tab:red",
            bbox=dict(boxstyle="round", fc="white", ec="tab:red", alpha=0.9),
            zorder=8,
        )
    title = f"cycle {state['cycle']}"
    if tag:
        title += f"\n{tag}"
    ax.set_title(title, fontsize=8)


def render_filmstrip(path: str, repent_cycle: Optional[int] = None) -> None:
    """Static, abstract-ready composite: a row of key battlespace frames over the
    full coherence/horizon, backlog, and final-trust panels. PDF-safe (no motion).
    """
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        print("Filmstrip needs matplotlib.  Install with:  pip install matplotlib")
        return

    states = _collect_states(repent_cycle)
    by_cycle = {s["cycle"]: s for s in states}

    if repent_cycle is not None:
        picks = [COMPROMISE_CYCLE, 6, REPENT_CYCLE, CYCLES]
        tags = [
            "spoofed report injected",
            "spoofer cut off",
            "attacker stops spoofing",
            "trust earned back",
        ]
        cen_tags = [
            "spoof drags the estimate",
            "estimate still off target",
            "orchestrator lost",
            "no coordination",
        ]
        story = (
            "Recoverable trust -- a compromised agent stops attacking "
            "and is healed back in"
        )
    else:
        picks = [2, COMPROMISE_CYCLE + 1, LOSS_CYCLE, CYCLES]
        tags = [
            "calm: agents agree",
            "spoofed report injected",
            "spoofed report distrusted",
            "after the loss: RYUJIN keeps coordinating",
        ]
        cen_tags = [
            "calm: estimate on target",
            "spoof drags the estimate off target",
            "orchestrator lost",
            "no coordination",
        ]
        story = (
            "Persistent insider -- the spoofer is cut off and the team keeps "
            "coordinating after losing an agent"
        )

    pairs = [(c, t) for c, t in zip(picks, tags) if c in by_cycle][:4]
    cen_pairs = [(c, t) for c, t in zip(picks, cen_tags) if c in by_cycle][:4]
    map_legend = _map_legend()

    # Four stacked rows: (A) the OLD centralized approach on the same cycles
    # (contrast), (B) RYUJIN on the same cycles, (C) the full-run dynamic
    # role-allocation heatmap, (D) coherence/horizon, ledger, and final trust.
    # Separate sub-gridspecs keep each row's spacing independent. `top` is held
    # below the suptitle + the shared battlespace legend (drawn outside the
    # panels so it never crowds the cycle frames). The figure is intentionally
    # tall so all four rows stay legible when scaled onto an 8.5x11 page.
    fig = plt.figure(figsize=(14, 13.2))
    outer = fig.add_gridspec(
        4, 1, height_ratios=[0.95, 0.95, 0.5, 0.9], hspace=0.62, top=0.88
    )
    gs_cen = outer[0].subgridspec(1, max(1, len(cen_pairs)), wspace=0.25)
    gs_top = outer[1].subgridspec(1, max(1, len(pairs)), wspace=0.25)
    gs_mid = outer[2].subgridspec(1, 1)
    gs_bot = outer[3].subgridspec(1, 3, wspace=0.7)

    # Row A -- OLD centralized approach (same four cycles): the red X is never
    # ringed, the averaged estimate is dragged off target, then control is lost.
    for j, (c, t) in enumerate(cen_pairs):
        ax = fig.add_subplot(gs_cen[0, j])
        _draw_mini_centralized(ax, by_cycle[c], t)
        if j == 0:
            ax.set_ylabel(
                "OLD: centralized\n(single orchestrator)",
                fontsize=8.5,
                fontweight="bold",
                color="tab:red",
            )

    # Row B -- RYUJIN on the same four cycles.
    for j, (c, t) in enumerate(pairs):
        ax = fig.add_subplot(gs_top[0, j])
        _draw_mini(ax, by_cycle[c], t)
        if j == 0:
            ax.set_ylabel(
                "RYUJIN\n(decentralized)",
                fontsize=8.5,
                fontweight="bold",
                color="tab:green",
            )

    # Shared battlespace legend, lifted out of the plot area into the top margin
    # and given generous row spacing so the six entries are easy to read.
    fig.legend(
        handles=map_legend,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.945),
        ncol=3,
        fontsize=8,
        labelspacing=1.1,
        columnspacing=2.4,
        handletextpad=0.7,
        frameon=True,
    )

    ax_role = fig.add_subplot(gs_mid[0, 0])
    _draw_role_heatmap(ax_role, states)

    hist = _empty_hist()
    for s in states:
        _push_hist(hist, s)

    ax_coh = fig.add_subplot(gs_bot[0, 0])
    ax_hz = ax_coh.twinx()
    ax_coh.set_title("Coherence drives horizon", fontsize=9)
    ax_coh.set_xlim(1, CYCLES)
    ax_coh.set_ylim(0, 1.05)
    ax_coh.set_xlabel("cycle")
    ax_coh.set_ylabel("coherence [0,1]", color="tab:blue")
    ax_coh.plot(hist["cycle"], hist["coh"], "-o", color="tab:blue")
    ax_hz.set_ylim(0, MAX_HORIZON_CYCLES + 0.5)
    ax_hz.set_ylabel("horizon (cycles)", color="tab:orange")
    ax_hz.plot(
        hist["cycle"],
        hist["hz"],
        drawstyle="steps-post",
        marker="s",
        color="tab:orange",
    )
    ax_hz.axhline(MAX_HORIZON_CYCLES, color="tab:orange", ls=":", lw=0.8)
    ax_hz.set_yticks(range(0, MAX_HORIZON_CYCLES + 1, 2))
    _int_cycle_axis(ax_coh, CYCLES)

    ax_back = fig.add_subplot(gs_bot[0, 1])
    ax_back.set_title(
        "Conservation ledger (work is deferred, never hidden)", fontsize=9
    )
    ax_back.set_xlim(1, CYCLES)
    ax_back.set_xlabel("cycle")
    ax_back.set_ylabel("orders")
    ax_back.bar(
        hist["cycle"],
        hist["done"],
        color="tab:green",
        alpha=0.4,
        label="completed/cycle",
    )
    ax_back.plot(
        hist["cycle"], hist["back"], "-o", color="tab:red", label="deferred backlog"
    )
    ax_back.axhline(
        BACKLOG_ESCALATION,
        color="r",
        ls="--",
        lw=0.8,
        label="operator-review threshold",
    )
    ax_back.legend(loc="upper left", fontsize=6)
    _int_cycle_axis(ax_back, CYCLES)

    ax_tr = fig.add_subplot(gs_bot[0, 2])
    final = states[-1]
    ax_tr.set_title(f"Final trust (cycle {final['cycle']})", fontsize=9)
    snaps = final["platforms"]
    names = [p["pid"] for p in snaps]
    colors = [
        "0.6" if not p["online"] else ("tab:red" if p["distrusted"] else "tab:green")
        for p in snaps
    ]
    ax_tr.bar(range(len(names)), [p["trust"] for p in snaps], color=colors)
    _trust_band(ax_tr, legend=True)
    ax_tr.set_ylim(0, 1.05)
    ax_tr.set_ylabel("trust score [0,1]")
    ax_tr.set_xticks(range(len(names)))
    ax_tr.set_xticklabels(names, rotation=30, ha="right", fontsize=5)
    # [RW] tag the lost node: its trust is frozen high but it is off-net, so the
    # grey bar would otherwise read like a trusted agent. Place "offline" INSIDE
    # the bar, above the reinstate ceiling, so it never pokes past the frame.
    for i, p in enumerate(snaps):
        if not p["online"]:
            y_lbl = (RETRUST_CEILING + min(1.0, p["trust"])) / 2.0
            ax_tr.text(
                i,
                y_lbl,
                "offline",
                ha="center",
                va="center",
                fontsize=6,
                color="black",
                rotation=90,
                zorder=6,
            )

    fig.suptitle(
        "RYUJIN single-host model -- " + story,
        fontweight="bold",
        fontsize=12,
        y=0.985,
    )
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote filmstrip: {path}")


def build_compare(path: str, repent_cycle: Optional[int] = None) -> None:
    """Static 3-row head-to-head figure for the proposal / oral slide.

    Row 1 -- RYUJIN: battlespace (robust fusion holds), coherence->horizon,
             per-platform trust with the recoverable-reputation band.
    Row 2 -- centralized baseline: its naive-average battlespace (the spoof
             drags the estimate off-target), then coherence and cumulative
             throughput plotted head-to-head against RYUJIN; the orchestrator
             loss is marked, after which the baseline collapses to zero.
    Row 3 -- supporting EMA signals that drive the behavior: FLTrust fusion
             weights (the adversary is driven to ~0), the shared success signal
             per tactic, and anchor/fused tracking error (anti-capture).

    PDF-safe (no motion). matplotlib is imported lazily (headless Agg backend).
    """
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        print("Compare figure needs matplotlib.  Install:  pip install matplotlib")
        return

    states = _collect_states(repent_cycle)
    pids = [p["pid"] for p in states[0]["platforms"]]
    cycles = [s["cycle"] for s in states]
    final = states[-1]
    coh = [s["metrics"]["coherence"] for s in states]
    hz = [s["metrics"]["horizon"] for s in states]
    base_live = [s for s in states if not s["base"]["down"]]
    base_snap = base_live[-1] if base_live else states[0]

    fig = plt.figure(figsize=(15, 11))
    gs = fig.add_gridspec(3, 3, hspace=0.5, wspace=0.34)

    # ---------------- ROW 1: RYUJIN ----------------
    ax = fig.add_subplot(gs[0, 0])
    _draw_mini(ax, final, "")
    ax.legend(handles=_map_legend(), loc="upper left", fontsize=5)
    ax.set_title(
        f"RYUJIN battlespace (cycle {final['cycle']})\nrobust fusion holds on truth",
        fontsize=9,
    )

    ax = fig.add_subplot(gs[0, 1])
    axh = ax.twinx()
    ax.plot(cycles, coh, "-o", color="tab:blue")
    ax.set_xlim(1, CYCLES)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("cycle")
    ax.set_ylabel("coherence [0,1]", color="tab:blue")
    axh.plot(cycles, hz, drawstyle="steps-post", marker="s", color="tab:orange")
    axh.axhline(MAX_HORIZON_CYCLES, color="tab:orange", ls=":", lw=0.8)
    axh.set_ylim(0, MAX_HORIZON_CYCLES + 0.5)
    axh.set_yticks(range(0, MAX_HORIZON_CYCLES + 1, 2))
    axh.set_ylabel("horizon (cycles)", color="tab:orange")
    _int_cycle_axis(ax, CYCLES)
    ax.set_title("RYUJIN: coherence drives planning horizon", fontsize=9)

    ax = fig.add_subplot(gs[0, 2])
    snaps = final["platforms"]
    names = [p["pid"] for p in snaps]
    colors = [
        "0.6" if not p["online"] else ("tab:red" if p["distrusted"] else "tab:green")
        for p in snaps
    ]
    ax.bar(range(len(names)), [p["trust"] for p in snaps], color=colors)
    _trust_band(ax, legend=True)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("trust score [0,1]")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=6)
    ax.set_title("RYUJIN per-platform trust (hysteresis band)", fontsize=9)

    # ---------------- ROW 2: CENTRALIZED BASELINE ----------------
    ax = fig.add_subplot(gs[1, 0])
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-2.0, 2.5)
    ax.set_xticks([])
    ax.set_yticks([])
    for _pid, fix, honest in base_snap["base"]["fixes"]:
        ax.scatter(
            fix[0],
            fix[1],
            c=("tab:green" if honest else "tab:red"),
            marker=("o" if honest else "X"),
            s=42,
            alpha=0.85,
            edgecolors="k",
            linewidths=0.3,
            zorder=3,
        )
    if base_snap["base"]["fused"] is not None:
        ax.scatter(
            *base_snap["base"]["fused"],
            c="tab:blue",
            marker="*",
            s=150,
            edgecolors="k",
            zorder=5,
        )
    ax.scatter(
        *base_snap["target"],
        facecolors="none",
        edgecolors="k",
        marker="o",
        s=90,
        linewidths=1.3,
        zorder=6,
    )
    ax.set_title(
        f"Centralized battlespace (cycle {base_snap['cycle']})\n"
        "the single averaged estimate is dragged toward the spoof",
        fontsize=9,
    )
    if final["base"]["down"]:
        ax.text(
            0.5,
            0.92,
            "CENTRALIZED CONTROL FAILED by the final cycle\n(single point of failure)",
            transform=ax.transAxes,
            ha="center",
            va="top",
            color="tab:red",
            fontsize=8,
            fontweight="bold",
            bbox=dict(boxstyle="round", fc="white", ec="tab:red", alpha=0.9),
        )

    ax = fig.add_subplot(gs[1, 1])
    base_coh = [s["base"]["coherence"] for s in states]
    ax.plot(cycles, coh, "-o", color="tab:blue", label="RYUJIN")
    ax.plot(cycles, base_coh, "--s", color="0.45", label="centralized")
    ax.axvline(LOSS_CYCLE, color="r", ls=":", lw=0.8, label="centralized control lost")
    ax.set_xlim(1, CYCLES)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("cycle")
    ax.set_ylabel("coherence [0,1]")
    ax.legend(loc="lower left", fontsize=7)
    _int_cycle_axis(ax, CYCLES)
    ax.set_title("Coherence: RYUJIN vs centralized", fontsize=9)

    ax = fig.add_subplot(gs[1, 2])
    ryu_cum: List[int] = []
    base_cum: List[int] = []
    r_acc = 0
    b_acc = 0
    for s in states:
        r_acc += s["metrics"]["completed"]
        b_acc += s["base"]["completed"]
        ryu_cum.append(r_acc)
        base_cum.append(b_acc)
    ax.plot(cycles, ryu_cum, "-o", color="tab:blue", label="RYUJIN")
    ax.plot(cycles, base_cum, "--s", color="0.45", label="centralized")
    ax.axvline(LOSS_CYCLE, color="r", ls=":", lw=0.8)
    ax.set_xlim(1, CYCLES)
    ax.set_xlabel("cycle")
    ax.set_ylabel("orders completed (cumulative)")
    ax.legend(loc="upper left", fontsize=7)
    _int_cycle_axis(ax, CYCLES)
    ax.set_title("Throughput: RYUJIN vs centralized", fontsize=9)

    # ---------------- ROW 3: SUPPORTING EMA SIGNALS ----------------
    ax = fig.add_subplot(gs[2, 0])
    for pid in pids:
        w = [s["metrics"]["weights"].get(pid, 0.0) for s in states]
        is_adv = pid in final["adversary_set"]
        ax.plot(
            cycles,
            w,
            marker=("x" if is_adv else "."),
            lw=(1.8 if is_adv else 1.0),
            color=("tab:red" if is_adv else None),
            label=(pid + (" (adversary)" if is_adv else "")),
        )
    ax.set_xlim(1, CYCLES)
    ax.set_xlabel("cycle")
    ax.set_ylabel("FLTrust weight (unnormalized)")
    ax.legend(loc="upper right", fontsize=5)
    _int_cycle_axis(ax, CYCLES)
    ax.set_title("Robust fusion weights: adversary driven to ~0", fontsize=9)

    ax = fig.add_subplot(gs[2, 1])
    for ot in ORDER_TYPES:
        ax.plot(
            cycles,
            [s["metrics"]["tactic_success"].get(ot, 0.0) for s in states],
            "-o",
            label=ot,
        )
    ax.set_xlim(1, CYCLES)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("cycle")
    ax.set_ylabel("success-signal EMA [0,1]")
    ax.legend(loc="upper left", fontsize=6)
    _int_cycle_axis(ax, CYCLES)
    ax.set_title("Shared success signal (tactic EMA)", fontsize=9)

    ax = fig.add_subplot(gs[2, 2])
    fused_err = [vdist(s["metrics"]["fused_track"], s["target"]) for s in states]
    anchor_err = [vdist(s["metrics"]["trusted_track"], s["target"]) for s in states]
    ax.plot(cycles, fused_err, "-o", color="tab:blue", label="fused track vs truth")
    ax.plot(
        cycles,
        anchor_err,
        "-D",
        color="tab:purple",
        label="anchor (RYUJIN internal reference) vs truth",
    )
    ax.set_xlim(1, CYCLES)
    ax.set_xlabel("cycle")
    ax.set_ylabel("error (map-units)")
    ax.legend(loc="upper right", fontsize=7)
    _int_cycle_axis(ax, CYCLES)
    ax.set_title("Anti-capture: the internal anchor's error stays bounded", fontsize=9)

    story = (
        "recoverable trust (attacker stops, earns trust back)"
        if repent_cycle is not None
        else "persistent insider + loss of an agent"
    )
    fig.suptitle(
        "RYUJIN vs centralized baseline -- "
        + story
        + "\nRow 1: RYUJIN    |    Row 2: centralized baseline    "
        "|    Row 3: supporting EMA signals",
        fontweight="bold",
        fontsize=12,
    )
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote compare figure: {path}")


def _has_flag(name: str) -> bool:
    return any(a == name or a.startswith(name + "=") for a in sys.argv)


def _flag_value(name: str, default: Optional[str] = None) -> Optional[str]:
    # supports both "--flag value" and "--flag=value"
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return default


def main() -> None:
    # See the module docstring "HOW TO RUN" for all flags. Add --heal to any
    # scripted/viz/export run to make the adversary repent and recover.
    repent = REPENT_CYCLE if "--heal" in sys.argv else None
    # [RW] trust posture: --zero-trust starts every peer at the distrust floor
    # (earn-your-standing) instead of fully trusted (innocent-until-proven-guilty).
    init_trust = ZERO_TRUST_START if _has_flag("--zero-trust") else INITIAL_TRUST
    if "--trust-tradeoff" in sys.argv:
        run_trust_tradeoff(int(_flag_value("--trials", "200")))
    elif "--sweep" in sys.argv:
        run_sweep(int(_flag_value("--trials", "200")))
    elif _has_flag("--save-gif-compare"):
        export_compare_animation(
            repent, gif_path=_flag_value("--save-gif-compare", "ryujin_compare.gif")
        )
    elif _has_flag("--save-frames-compare"):
        export_compare_animation(
            repent, frames_dir=_flag_value("--save-frames-compare", "compare_frames")
        )
    elif "--viz-compare" in sys.argv:
        run_viz_compare(
            float(_flag_value("--delay", "0.9")),
            repent_cycle=repent,
            initial_trust=init_trust,
        )
    elif _has_flag("--save-gif"):
        export_animation(repent, gif_path=_flag_value("--save-gif", "ryujin.gif"))
    elif _has_flag("--save-frames"):
        export_animation(repent, frames_dir=_flag_value("--save-frames", "frames"))
    elif _has_flag("--filmstrip"):
        render_filmstrip(_flag_value("--filmstrip", "ryujin_filmstrip.png"), repent)
    elif _has_flag("--compare"):
        build_compare(_flag_value("--compare", "ryujin_compare.png"), repent)
    elif "--viz" in sys.argv:
        run_viz(
            float(_flag_value("--delay", "0.6")),
            repent_cycle=repent,
            initial_trust=init_trust,
        )
    elif "--quiet" in sys.argv:
        simulate(verbose=False, repent_cycle=repent, initial_trust=init_trust)
    else:
        simulate(verbose=True, repent_cycle=repent, initial_trust=init_trust)


if __name__ == "__main__":
    main()
