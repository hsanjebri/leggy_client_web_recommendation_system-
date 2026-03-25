import numpy as np

def apply_mmr(items, relevance_scores, categories, lambda_param, top_n):
    """
    Maximal Marginal Relevance (MMR) algorithm.
    """

    selected = []          # indices of items already chosen
    selected_ids = set()   # set of chosen item IDs (avoid duplicates)
    candidate_indices = list(range(len(items)))  # all candidate indices

    # Iteratively select items until we have top_n recommendations
    while len(selected) < top_n and candidate_indices:
        mmr_scores = []  # store (item_index, mmr_score)

        for i in candidate_indices:
            relevance = relevance_scores[i]

            # Compute diversity penalty:
            # if categories match with already selected items, reduce score
            if not selected:
                diversity = 0  # no penalty for first item
            else:
                diversity = max([1 if categories[i] == categories[j] else 0 for j in selected])

            # MMR formula: weighted combination of relevance and diversity
            mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity
            mmr_scores.append((i, mmr_score))

        # Select the candidate with the highest MMR score
        best_idx, _ = max(mmr_scores, key=lambda x: x[1])
        selected.append(best_idx)
        selected_ids.add(items[best_idx])

        # Remove it from the pool of candidates
        candidate_indices.remove(best_idx)

    # Return the final list of selected items
    return [items[i] for i in selected]
