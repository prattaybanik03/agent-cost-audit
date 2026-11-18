from __future__ import annotations

import threading

import pytest

from aca.budget import Budget, BudgetExceeded


def test_reserve_then_settle_records_actual_spend() -> None:
    budget = Budget(cap_usd=1.00)
    reservation = budget.reserve(0.30)
    assert budget.reserved_usd == pytest.approx(0.30)
    assert budget.remaining_usd == pytest.approx(0.70)

    budget.settle(reservation, 0.05)
    assert budget.spent_usd == pytest.approx(0.05)
    assert budget.reserved_usd == 0
    assert budget.remaining_usd == pytest.approx(0.95)


def test_call_that_could_pass_the_cap_is_refused() -> None:
    budget = Budget(cap_usd=1.00)
    budget.settle(budget.reserve(0.90), 0.90)

    with pytest.raises(BudgetExceeded, match="Stopping"):
        budget.reserve(0.20)

    # The refusal changes nothing.
    assert budget.spent_usd == pytest.approx(0.90)
    assert budget.reserved_usd == 0


def test_outstanding_reservations_count_against_the_cap() -> None:
    budget = Budget(cap_usd=1.00)
    budget.reserve(0.60)
    with pytest.raises(BudgetExceeded):
        budget.reserve(0.60)


def test_reservation_exactly_at_the_cap_is_allowed() -> None:
    budget = Budget(cap_usd=1.00)
    budget.reserve(1.00)
    assert budget.remaining_usd == pytest.approx(0.0)


def test_release_frees_a_failed_call() -> None:
    budget = Budget(cap_usd=1.00)
    reservation = budget.reserve(0.80)
    budget.release(reservation)
    assert budget.remaining_usd == pytest.approx(1.00)
    budget.reserve(0.80)


def test_settling_twice_is_an_error() -> None:
    budget = Budget(cap_usd=1.00)
    reservation = budget.reserve(0.10)
    budget.settle(reservation, 0.10)
    with pytest.raises(ValueError):
        budget.settle(reservation, 0.10)


def test_invalid_amounts_are_rejected() -> None:
    with pytest.raises(ValueError):
        Budget(cap_usd=0)
    budget = Budget(cap_usd=1.00)
    with pytest.raises(ValueError):
        budget.reserve(-0.01)
    with pytest.raises(ValueError):
        budget.settle(budget.reserve(0.10), -0.01)


def test_cap_holds_under_concurrent_reservations() -> None:
    budget = Budget(cap_usd=5.00)
    granted: list[int] = []
    refused: list[int] = []
    barrier = threading.Barrier(100)

    def worker(index: int) -> None:
        barrier.wait()
        try:
            budget.reserve(0.10)
            granted.append(index)
        except BudgetExceeded:
            refused.append(index)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(granted) + len(refused) == 100
    assert budget.reserved_usd <= 5.00 + 1e-9
    assert 49 <= len(granted) <= 50  # 50 x $0.10 fits; float rounding may refuse the last one
