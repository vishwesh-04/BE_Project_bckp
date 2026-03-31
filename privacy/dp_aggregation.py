from __future__ import annotations

from typing import Sequence

import numpy as np

ArrayList = list[np.ndarray]


def clip_update(update: Sequence[np.ndarray], max_norm: float) -> ArrayList:
    if max_norm <= 0:
        return [np.asarray(layer, dtype=np.float32) for layer in update]

    update_arrays = [np.asarray(layer, dtype=np.float32) for layer in update]
    total_norm_sq = 0.0
    for layer in update_arrays:
        total_norm_sq += float(np.sum(np.square(layer, dtype=np.float32)))
    total_norm = float(np.sqrt(total_norm_sq))
    if total_norm == 0.0 or total_norm <= max_norm:
        return [layer.copy() for layer in update_arrays]

    scale = max_norm / (total_norm + 1e-12)
    return [layer * scale for layer in update_arrays]



def aggregate_updates(updates: Sequence[Sequence[np.ndarray]], weights: Sequence[float] | None = None) -> ArrayList:
    if not updates:
        return []

    update_arrays = [[np.asarray(layer, dtype=np.float32) for layer in update] for update in updates]
    if weights is None:
        normalized_weights = np.full(len(update_arrays), 1.0 / len(update_arrays), dtype=np.float32)
    else:
        weight_array = np.asarray(weights, dtype=np.float32)
        total = float(np.sum(weight_array))
        if total <= 0:
            normalized_weights = np.full(len(update_arrays), 1.0 / len(update_arrays), dtype=np.float32)
        else:
            normalized_weights = weight_array / total

    aggregated: ArrayList = []
    for layer_idx in range(len(update_arrays[0])):
        weighted_sum = np.zeros_like(update_arrays[0][layer_idx], dtype=np.float32)
        for update_idx, update in enumerate(update_arrays):
            weighted_sum += update[layer_idx] * normalized_weights[update_idx]
        aggregated.append(weighted_sum)
    return aggregated



def add_dp_noise(update: Sequence[np.ndarray], max_norm: float, noise_multiplier: float, seed: int | None = None) -> ArrayList:
    if noise_multiplier <= 0:
        return [np.asarray(layer, dtype=np.float32) for layer in update]

    rng = np.random.default_rng(seed)
    stddev = max_norm * noise_multiplier
    noised: ArrayList = []
    for layer in update:
        layer_array = np.asarray(layer, dtype=np.float32)
        noise = rng.normal(0.0, stddev, size=layer_array.shape).astype(np.float32)
        noised.append(layer_array + noise)
    return noised



def dp_aggregate(
    updates: Sequence[Sequence[np.ndarray]],
    max_norm: float,
    noise_multiplier: float,
    seed: int | None = None,
    weights: Sequence[float] | None = None,
) -> ArrayList:
    clipped = [clip_update(update, max_norm=max_norm) for update in updates]
    aggregated = aggregate_updates(clipped, weights=weights)
    return add_dp_noise(aggregated, max_norm=max_norm, noise_multiplier=noise_multiplier, seed=seed)



def apply_dp_to_aggregate(
    aggregated_update: Sequence[np.ndarray],
    max_norm: float,
    noise_multiplier: float,
    seed: int | None = None,
) -> ArrayList:
    clipped = clip_update(aggregated_update, max_norm=max_norm)
    return add_dp_noise(clipped, max_norm=max_norm, noise_multiplier=noise_multiplier, seed=seed)
