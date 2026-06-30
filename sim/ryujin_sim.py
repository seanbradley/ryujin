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

The scripted run is verbose by default, so there is no --verbose flag; use
--quiet to suppress the per-cycle trace. --heal can be added to any scripted or
--viz run to make the adversary stop spoofing partway through, so you can watch
recoverable-trust hysteresis bring it back above the reinstate ceiling. Only
--viz needs a third-party package (matplotlib); every other mode is stdlib-only.

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
CYCLES = 12  # unit: cycles (OODA decision loops), not wall-clock time
SENSOR_NOISE = 0.40  # unit: map-units, 1-sigma Gaussian fix error vs true target
TASK_SUCCESS_BASE = 0.92  # unit: probability [0,1] a tasked platform succeeds
DISTRUST_FLOOR = 0.30  # unit: trust score [0,1]; below this, influence revoked
RETRUST_CEILING = 0.55  # unit: trust score [0,1]; above this, platform rejoins
TRUST_GAIN = 0.40  # unit: EMA weight [0,1] per cycle (trust reaction speed)
SIGNAL_GAIN = 0.30  # unit: EMA weight [0,1] per cycle (success-signal speed)
ANCHOR_GAIN = 0.25  # unit: EMA weight [0,1] per cycle (anchor tracking speed)
MAX_ORDERS_PER_PLATFORM = 2  # unit: orders per platform per cycle (doctrine cap)
MAX_HORIZON_CYCLES = 10  # unit: cycles (longest planning lookahead sanctioned)
COMPROMISE_CYCLE = 3  # unit: cycle index at which one platform is compromised
LOSS_CYCLE = 7  # unit: cycle index at which a platform is lost off-net
REPENT_CYCLE = 9  # unit: cycle index; with --heal, adversary stops spoofing here
BACKLOG_ESCALATION = 6  # unit: orders (unmet-obligation backlog that escalates)
NEW_ORDERS_PER_CYCLE = 5  # unit: orders per cycle (incoming tasking tempo)
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
def build_platforms(adversary_ids: Optional[Set[str]] = None) -> List[Platform]:
    # [RW] CONSTRUCT a small heterogeneous force. Names describe what each thing
    # IS. By default "compute_node" is the platform that will be compromised.
    advs = {"compute_node"} if adversary_ids is None else adversary_ids
    roster = [
        ("scout_drone", {"camera"}),
        ("scout_relay_drone", {"camera", "radio"}),
        ("relay_drone", {"radio"}),
        ("compute_node", {"processor"}),
        ("scout_compute_drone", {"camera", "processor"}),
        ("relay_compute_node", {"radio", "processor"}),
    ]
    return [Platform(pid, eq, honest=(pid not in advs)) for pid, eq in roster]


def simulate(
    seed: int = SEED,
    compromise_cycle: int = COMPROMISE_CYCLE,
    loss_cycle: int = LOSS_CYCLE,
    adversary_ids: Optional[Set[str]] = None,
    verbose: bool = False,
    on_cycle=None,
    repent_cycle: Optional[int] = None,
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
    ryu_platforms = build_platforms(adversary_ids)
    base_platforms = build_platforms(adversary_ids)
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
            on_cycle(
                {
                    "cycle": c,
                    "cycles": CYCLES,
                    "target": target,
                    "metrics": m,
                    "events": events,
                    "base_down": b.get("down", False),
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


def run_sweep(trials: int = 200) -> None:
    """Monte Carlo over randomized seed, fault timing, and adversary fraction.

    This is the honest answer to "your scripted run looks lucky": timing and
    adversary identities are randomized each trial, so the table below brackets
    average-case behavior instead of one hand-picked scenario.
    """
    rng = random.Random(SEED)
    roster_ids = [p.pid for p in build_platforms()]
    rows: List[Dict] = []
    for t in range(trials):
        comp = rng.randint(2, CYCLES - 2)  # compromise can begin almost anytime
        loss = rng.randint(comp + 1, CYCLES)  # loss always after the compromise
        n_adv = rng.randint(0, 2)  # 0, 1, or 2 of 6 platforms compromised
        advs = set(rng.sample(roster_ids, n_adv)) if n_adv else set()
        rows.append(simulate(SEED + 1 + t, comp, loss, advs, verbose=False))

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


def run_viz(delay: float = 0.6, repent_cycle: Optional[int] = None) -> None:
    """Live matplotlib animation of one scripted run.

    Renders four panels per cycle: the battlespace (platform fixes, fused track,
    trusted anchor, ground truth), the TA2->TA1 coupling (coherence + horizon),
    per-platform trust, and the conservation ledger (backlog + completions).
    matplotlib is the ONLY non-stdlib dependency, imported lazily here so the
    other run modes stay dependency-free.

    delay -- unit: seconds of wall-clock pause per cycle (animation speed).
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
        from matplotlib.lines import Line2D  # type: ignore[import-not-found]
    except Exception:
        print("Visualization needs matplotlib.  Install with:  pip install matplotlib")
        print("Then re-run:  python sim/ryujin_sim.py --viz")
        return

    plt.ion()
    fig, ((ax_map, ax_coh), (ax_trust, ax_back)) = plt.subplots(2, 2, figsize=(13, 8))

    # [RW] explicit legend so EVERY marker -- including the red spoof X -- is named.
    # The fixes are scatter-plotted in a loop, so we hand-build proxy handles here.
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

    map_legend = [
        _h("o", "tab:green", "honest fix (one agent's estimate)"),
        _h("X", "tab:red", "spoofed fix (compromised agent)"),
        _h("*", "tab:blue", "fused track (defended consensus)", ms=14),
        _h("D", "tab:purple", "trusted anchor (slow, anti-capture)"),
        _h("o", "none", "ground truth (true target state)", ms=10),
    ]

    truth_trail: List[Vec] = []
    h_cycle: List[int] = []
    h_coh: List[float] = []
    h_hz: List[int] = []
    h_back: List[int] = []
    h_done: List[int] = []

    def on_cycle(state: Dict) -> None:
        m = state["metrics"]
        truth_trail.append(state["target"])
        h_cycle.append(state["cycle"])
        h_coh.append(m["coherence"])
        h_hz.append(m["horizon"])
        h_back.append(m["backlog"])
        h_done.append(m["completed"])

        # --- battlespace map ---
        ax_map.clear()
        ax_map.set_title("Battlespace: fixes / fused track / anchor / truth")
        ax_map.set_xlim(-3.5, 3.5)
        ax_map.set_ylim(-2.0, 2.5)
        ax_map.set_xlabel("map-units (x)")
        ax_map.set_ylabel("map-units (y)")
        if len(truth_trail) > 1:
            ax_map.plot(
                [p[0] for p in truth_trail],
                [p[1] for p in truth_trail],
                color="0.75",
                lw=1,
                zorder=1,
            )
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
        ax_map.scatter(
            *m["fused_track"], c="tab:blue", marker="*", s=280, edgecolors="k", zorder=5
        )
        ax_map.scatter(
            *m["trusted_track"],
            c="tab:purple",
            marker="D",
            s=90,
            edgecolors="k",
            zorder=4,
        )
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
        # [RW] caption so a reviewer cannot mistake this for a terrain/GPS map.
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
        ax_coh.set_title("TA2->TA1 coupling: coherence drives horizon")
        ax_coh.set_xlim(1, state["cycles"])
        ax_coh.set_ylim(0, 1.05)
        ax_coh.set_xlabel("cycle")
        ax_coh.set_ylabel("coherence [0,1]", color="tab:blue")
        ax_coh.plot(h_cycle, h_coh, "-o", color="tab:blue")
        ax_hz = ax_coh.twinx()
        ax_hz.set_ylim(0, MAX_HORIZON_CYCLES + 0.5)
        ax_hz.set_ylabel("horizon (cycles)", color="tab:orange")
        ax_hz.plot(h_cycle, h_hz, "-s", color="tab:orange")

        # --- per-platform trust ---
        ax_trust.clear()
        ax_trust.set_title("Per-platform trust (red=distrusted, grey=off-net)")
        snaps = state["platforms"]
        names = [p["pid"] for p in snaps]
        colors = [
            (
                "0.6"
                if not p["online"]
                else ("tab:red" if p["distrusted"] else "tab:green")
            )
            for p in snaps
        ]
        ax_trust.bar(range(len(names)), [p["trust"] for p in snaps], color=colors)
        ax_trust.axhline(DISTRUST_FLOOR, color="r", ls="--", lw=0.8)
        ax_trust.set_ylim(0, 1.05)
        ax_trust.set_ylabel("trust [0,1]")
        ax_trust.set_xticks(range(len(names)))
        ax_trust.set_xticklabels(names, rotation=30, ha="right", fontsize=6)

        # --- conservation ledger ---
        ax_back.clear()
        ax_back.set_title("Conservation ledger: backlog & completions")
        ax_back.set_xlim(1, state["cycles"])
        ax_back.set_xlabel("cycle")
        ax_back.set_ylabel("orders")
        ax_back.bar(
            h_cycle, h_done, color="tab:green", alpha=0.4, label="completed/cycle"
        )
        ax_back.plot(h_cycle, h_back, "-o", color="tab:red", label="backlog")
        ax_back.axhline(
            BACKLOG_ESCALATION, color="r", ls="--", lw=0.8, label="escalation"
        )
        ax_back.legend(loc="upper left", fontsize=7)

        banner = f"cycle {state['cycle']}/{state['cycles']}"
        if state["events"]:
            banner += "  |  " + "  ".join(state["events"])
        if state["base_down"]:
            banner += "  |  CENTRAL BASELINE DOWN"
        fig.suptitle(
            "RYUJIN -- live TA1/TA2 simulation\n" + banner,
            fontweight="bold",
            fontsize=10,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        plt.pause(max(0.01, delay))

    simulate(verbose=False, on_cycle=on_cycle, repent_cycle=repent_cycle)
    print("Visualization complete. Close the window to exit.")
    plt.ioff()
    plt.show()


def main() -> None:
    # `python sim/ryujin_sim.py`          -> one verbose scripted run (default)
    # `python sim/ryujin_sim.py --quiet`  -> scripted run, summary only
    # `python sim/ryujin_sim.py --sweep`  -> 200-trial Monte Carlo
    # `python sim/ryujin_sim.py --sweep --trials=500`
    # `python sim/ryujin_sim.py --viz [--delay=0.3]` -> live animation
    # add `--heal` to any scripted/viz run -> adversary repents and recovers
    repent = REPENT_CYCLE if "--heal" in sys.argv else None
    if "--sweep" in sys.argv:
        trials = 200
        for arg in sys.argv:
            if arg.startswith("--trials="):
                trials = int(arg.split("=", 1)[1])
        run_sweep(trials)
    elif "--viz" in sys.argv:
        delay = 0.6
        for arg in sys.argv:
            if arg.startswith("--delay="):
                delay = float(arg.split("=", 1)[1])
        run_viz(delay, repent_cycle=repent)
    elif "--quiet" in sys.argv:
        simulate(verbose=False, repent_cycle=repent)
    else:
        simulate(verbose=True, repent_cycle=repent)


if __name__ == "__main__":
    main()
