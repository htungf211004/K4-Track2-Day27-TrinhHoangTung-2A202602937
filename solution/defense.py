"""Stream detectors using only the documented, metered toolkit.

Each event needs at most one measurement RPC. Thresholds refer to measured
properties, never event identifiers, phase names, or an answer-key lookup.
"""
from api import Verdict


# Starting margins from the supplied detection guide, frozen before Public.
FEATURE_SHIFT_LIMIT = 0.65
EMBEDDING_SHIFT_LIMIT = 0.040
CORPUS_AGE_LIMIT = 45.0
COMPOSITE_LIMIT = 1.30


def _unavailable(pillar, measurement):
    # An unavailable measurement is not evidence of a pipeline fault.
    return Verdict(alert=False, confidence=0.0, pillar=pillar,
                   reason="measurement unavailable: " + str(measurement["error"]))


def _verdict(pillar, reasons):
    return Verdict(alert=bool(reasons), pillar=pillar, reason="; ".join(reasons))


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    profile = ctx.tools.batch_profile(payload["batch_id"])
    if "error" in profile:
        return _unavailable("checks", profile)
    baseline = ctx.baseline
    reasons = []
    for metric, lower, upper in (
        ("row_count", "row_count_min", "row_count_max"),
        ("mean_amount", "mean_amount_min", "mean_amount_max"),
    ):
        if not baseline[lower] <= profile[metric] <= baseline[upper]:
            reasons.append("%s outside baseline: %.4f" % (metric, profile[metric]))
    null_rate = profile["null_rate"]["customer_id"]
    staleness = profile["staleness_min"]
    if null_rate > baseline["null_rate_max"]:
        reasons.append("customer_id null rate: %.4f" % null_rate)
    if staleness > baseline["staleness_min_max"]:
        reasons.append("staleness: %.4f min" % staleness)

    # A half-range is a historical 3-sigma bound, not a one-sigma scale.
    # Use bound-normalized coordinates for all four terms consistently.
    components = []
    for metric, lower, upper in (
        ("row_count", "row_count_min", "row_count_max"),
        ("mean_amount", "mean_amount_min", "mean_amount_max"),
    ):
        center = (baseline[lower] + baseline[upper]) / 2.0
        half_range = (baseline[upper] - baseline[lower]) / 2.0
        components.append((profile[metric] - center) / half_range)
    components.extend((null_rate / baseline["null_rate_max"],
                       staleness / baseline["staleness_min_max"]))
    distance = sum(value * value for value in components) ** 0.5
    if distance > COMPOSITE_LIMIT:
        reasons.append("joint bound-normalized distance: %.4f" % distance)
    return _verdict("checks", reasons)


def check_contract_checkpoint(payload, ctx):
    diff = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if "error" in diff:
        return _unavailable("contracts", diff)
    reasons = list(diff["violations"])
    delay = diff["freshness_delay_min"]
    sla = payload.get("declared_sla", {}).get("freshness_min")
    if sla is not None and delay > sla:
        reasons.append("freshness %.4f exceeds declared SLA %.4f min" % (delay, sla))
    if delay > ctx.baseline["freshness_delay_max_min"]:
        reasons.append("freshness %.4f exceeds historical bound" % delay)
    return _verdict("contracts", reasons)


def check_lineage_run(payload, ctx):
    graph = ctx.tools.lineage_graph_slice(payload["run_id"])
    if "error" in graph:
        return _unavailable("lineage", graph)
    reasons = []
    if graph["actual_downstream_count"] == 0:
        reasons.append("orphan output: no downstream consumers")
    # The fallback is the lab's stg_orders topology, not a rule for every DAG.
    required = payload.get("expected_upstream", ["raw.orders", "raw.customers"])
    missing = sorted(set(required) - set(graph["actual_upstream"]))
    if missing:
        reasons.append("missing upstream: " + ", ".join(missing))
    if graph["duration_ms"] > ctx.baseline["lineage_duration_ms_max"]:
        reasons.append("runtime exceeds historical bound: %.4f ms" % graph["duration_ms"])
    return _verdict("lineage", reasons)


def check_feature_materialization(payload, ctx):
    drift = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if "error" in drift:
        return _unavailable("ai_infra", drift)
    reasons = []
    if drift["mean_shift_sigma"] > FEATURE_SHIFT_LIMIT:
        reasons.append("training-serving mean shift: %.4f sigma" % drift["mean_shift_sigma"])
    return _verdict("ai_infra", reasons)


def check_embedding_batch(payload, ctx):
    drift = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if "error" in drift:
        return _unavailable("ai_infra", drift)
    reasons = []
    if drift["centroid_shift"] > EMBEDDING_SHIFT_LIMIT:
        reasons.append("embedding centroid shift: %.4f" % drift["centroid_shift"])
    if drift["avg_doc_age_days"] > CORPUS_AGE_LIMIT:
        reasons.append("corpus average age: %.4f days" % drift["avg_doc_age_days"])
    return _verdict("ai_infra", reasons)
