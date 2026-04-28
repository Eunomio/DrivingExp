import random


START_BATT_PCT = 30.0
DISPLAY_START_RANGE_M = 5000.0
W1_END_DIST_M = 1800.0
W2_END_DIST_M = 2300.0
REACH_END_PROBABILITY = 0.3
FINISH_BUFFER_DIST_M = 100.0
BREAKDOWN_BUFFER_DIST_M = 500.0


def sample_finish_outcome(reach_end_probability=REACH_END_PROBABILITY):
    return random.random() < reach_end_probability


def _get_soc_zero_distance(total_route_dist_m, breakdown_margin_m, can_reach_finish):
    if can_reach_finish:
        return total_route_dist_m + FINISH_BUFFER_DIST_M
    return max(W2_END_DIST_M + 1.0, total_route_dist_m - breakdown_margin_m)


def calculate_virtual_soc(
    dist_driven_m,
    total_route_dist_m,
    can_reach_finish,
    breakdown_buffer_dist_m=BREAKDOWN_BUFFER_DIST_M,
    breakdown_margin_m=None,
    start_batt_pct=START_BATT_PCT,
    w1_end_dist_m=W1_END_DIST_M,
    w2_end_dist_m=W2_END_DIST_M,
):
    if breakdown_margin_m is not None:
        breakdown_buffer_dist_m = breakdown_margin_m
    soc_zero_dist_m = _get_soc_zero_distance(
        total_route_dist_m,
        breakdown_buffer_dist_m,
        can_reach_finish,
    )
    rate_w1 = 10.0 / max(w1_end_dist_m, 1.0)
    rate_w2 = 10.0 / max(w2_end_dist_m - w1_end_dist_m, 1.0)
    rate_w3 = 10.0 / max(soc_zero_dist_m - w2_end_dist_m, 1.0)

    if dist_driven_m <= 0:
        return start_batt_pct
    if dist_driven_m < w1_end_dist_m:
        return start_batt_pct - dist_driven_m * rate_w1
    if dist_driven_m < w2_end_dist_m:
        return 20.0 - (dist_driven_m - w1_end_dist_m) * rate_w2
    return max(0.0, 10.0 - (dist_driven_m - w2_end_dist_m) * rate_w3)


def calculate_estimated_range_m(
    virtual_soc_pct,
    display_start_range_m=DISPLAY_START_RANGE_M,
    start_batt_pct=START_BATT_PCT,
):
    soc_ratio = max(0.0, min(1.0, virtual_soc_pct / max(start_batt_pct, 1.0)))
    return display_start_range_m * soc_ratio