"""Live spend tracking with a hard cap.

Before each call the caller reserves the call's worst-case cost. If the reservation would take
committed spend past the cap, `BudgetExceeded` is raised and the call is never made. After the
call the reservation is settled with the actual cost. Reservations make the cap hold when calls
run concurrently.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


class BudgetExceeded(Exception):
    """The next call could exceed the cap, so it was not made."""


@dataclass(frozen=True)
class Reservation:
    amount_usd: float
    token: int


class Budget:
    def __init__(self, cap_usd: float) -> None:
        if cap_usd <= 0:
            raise ValueError("Budget cap must be positive.")
        self.cap_usd = cap_usd
        self._spent = 0.0
        self._reserved: dict[int, float] = {}
        self._next_token = 0
        self._lock = threading.Lock()

    @property
    def spent_usd(self) -> float:
        with self._lock:
            return self._spent

    @property
    def reserved_usd(self) -> float:
        with self._lock:
            return sum(self._reserved.values())

    @property
    def remaining_usd(self) -> float:
        with self._lock:
            return self.cap_usd - self._spent - sum(self._reserved.values())

    def reserve(self, worst_case_usd: float) -> Reservation:
        """Hold `worst_case_usd` for a call that is about to be made."""
        if worst_case_usd < 0:
            raise ValueError("A reservation cannot be negative.")
        with self._lock:
            committed = self._spent + sum(self._reserved.values())
            if committed + worst_case_usd > self.cap_usd:
                raise BudgetExceeded(
                    f"Next call could cost up to ${worst_case_usd:.4f}. "
                    f"Spent ${self._spent:.4f} of the ${self.cap_usd:.2f} cap "
                    f"with ${committed - self._spent:.4f} reserved. Stopping."
                )
            token = self._next_token
            self._next_token += 1
            self._reserved[token] = worst_case_usd
            return Reservation(amount_usd=worst_case_usd, token=token)

    def settle(self, reservation: Reservation, actual_usd: float) -> None:
        """Replace a reservation with what the call actually cost."""
        if actual_usd < 0:
            raise ValueError("Actual cost cannot be negative.")
        with self._lock:
            if reservation.token not in self._reserved:
                raise ValueError("Reservation was already settled or released.")
            del self._reserved[reservation.token]
            self._spent += actual_usd

    def release(self, reservation: Reservation) -> None:
        """Drop a reservation for a call that failed before it was billed."""
        with self._lock:
            self._reserved.pop(reservation.token, None)
