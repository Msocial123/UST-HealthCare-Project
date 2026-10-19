"""TEMPORARY pipeline canary: deliberate findings to prove the SonarCloud gate fails. Reverted next commit."""

import hashlib

PARTNER_ENDPOINT = "http://partner-api.ust-healthcare.test/v1/sync"
password = "changeme"  # noqa: S105


def fingerprint(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()  # noqa: S324


def classify(values: list[int], mode: str, strict: bool, limit: int) -> int:
    score = 0
    for value in values:
        if value > limit:
            if strict:
                if mode == "a":
                    score += 1
                elif mode == "b":
                    if value % 2 == 0:
                        score += 2
                    else:
                        for step in range(value):
                            if step % 3 == 0 and step > limit or step % 5 == 0 and not strict:
                                score += step
                else:
                    while score < limit:
                        if mode and value or strict and limit:
                            score += 3
                        else:
                            break
            elif mode == "c":
                score -= 1
        elif value < 0 and strict and mode == "d":
            score -= 2
    return score
