"""Bound context excerpts while reserving space for selected implementation files."""

from __future__ import annotations

from bisect import bisect_right


def distribute(lengths: list[int], budget: int) -> list[int]:
    """Share space fairly, reusing the space that short documents do not need."""
    allocated = [0] * len(lengths)
    active = [index for index, length in enumerate(lengths) if length]
    while budget and active:
        share = max(1, budget // len(active))
        for index in active:
            amount = min(share, lengths[index] - allocated[index], budget)
            allocated[index] += amount
            budget -= amount
        active = [index for index in active if allocated[index] < lengths[index]]
    return allocated


def excerpt(item: dict, limit: int, anchor: int | None = None) -> None:
    content = item['content']
    start = 0
    if anchor is not None and len(content) > limit and limit:
        # Keep surrounding context on both sides of the match, including for
        # long single-line files. Prefer starting at a line boundary when possible.
        start = max(0, min(anchor - limit // 2, len(content) - limit))
        boundary = content.find('\n', start, anchor)
        if boundary >= 0:
            start = boundary + 1
    end = min(len(content), start + limit)
    item['original_chars'] = len(content)
    item['content'] = content[start:end]
    item['truncated'] = end - start < len(content)
    item['excerpt'] = None
    if end > start:
        starts = [0] + [index + 1 for index, char in enumerate(content) if char == '\n']
        first = bisect_right(starts, start) - 1
        last = bisect_right(starts, end - 1) - 1
        item['excerpt'] = {
            'start_offset': start, 'end_offset': end,
            'start_line': first + 1, 'end_line': last + 1,
            'start_column': start - starts[first] + 1,
            'end_column': end - starts[last],
        }


def apply_budget(selected: dict, max_chars: int, anchors: list[int | None]) -> dict:
    files = selected['files']
    protected = selected['instructions'] + selected['playbook']
    guidance = selected['principles'] + selected['architecture'] + selected['skills']
    file_lengths = [len(item['content']) for item in files]
    guidance_length = sum(len(item['content']) for item in protected + guidance)

    # Reserve half for files; either side can use capacity the other does not need.
    file_budget = min(sum(file_lengths), (max_chars + 1) // 2)
    guidance_budget = min(guidance_length, max_chars - file_budget)
    file_budget = min(sum(file_lengths), max_chars - guidance_budget)
    for item, limit, anchor in zip(files, distribute(file_lengths, file_budget), anchors):
        excerpt(item, limit, anchor)
    remaining = guidance_budget
    for item in protected:
        limit = min(len(item['content']), remaining)
        excerpt(item, limit)
        remaining -= limit
    lengths = [len(item['content']) for item in guidance]
    for item, limit in zip(guidance, distribute(lengths, remaining)):
        # Guidance remains in original order to avoid hiding unrelated constraints.
        excerpt(item, limit)
    used = {kind: sum(len(item['content']) for item in items)
            for kind, items in selected.items()}
    return {'max_chars': max_chars, 'used_chars': sum(used.values()),
            'by_kind': used, 'file_budget': file_budget, 'guidance_budget': guidance_budget}
