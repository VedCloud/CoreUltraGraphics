"""Offline GPU VA reservation core. Does NOT program page tables or map DMA.

Single-threaded ownership; caller must serialize operations. Reservations are
separate from CPU physical addresses and from hardware binding/completion.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Reservation:
    token: int
    gpu_va: int
    size: int


class AddressSpace:
    def __init__(self, start=4096, end=1 << 48, page_size=4096):
        if type(page_size) is not int or page_size <= 0 or page_size & (page_size - 1):
            raise ValueError('page size must be a power of two')
        if type(start) is not int or type(end) is not int:
            raise ValueError('integer address bounds required')
        if not 0 < start < end <= 1 << 48 or start % page_size or end % page_size:
            raise ValueError('invalid GPU VA range')
        self.start, self.end, self.page_size = start, end, page_size
        self._active = {}
        self._next = 1

    def reserve(self, size, alignment=None):
        alignment = self.page_size if alignment is None else alignment
        if type(size) is not int or not 0 < size <= self.end - self.start:
            raise ValueError('invalid allocation size')
        if type(alignment) is not int or alignment < self.page_size or alignment & (alignment - 1):
            raise ValueError('invalid alignment')
        size = (size + self.page_size - 1) & ~(self.page_size - 1)
        cursor = self.start
        for occupied in sorted(self._active.values(), key=lambda r: r.gpu_va):
            candidate = (cursor + alignment - 1) & ~(alignment - 1)
            if candidate + size <= occupied.gpu_va:
                break
            cursor = occupied.gpu_va + occupied.size
        else:
            candidate = (cursor + alignment - 1) & ~(alignment - 1)
        if candidate + size > self.end:
            raise MemoryError('GPU VA exhausted')
        reservation = Reservation(self._next, candidate, size)
        self._next += 1
        self._active[reservation.token] = reservation
        return reservation

    def release(self, reservation):
        # Identity prevents a foreign/forged token or stale reservation freeing
        # a current mapping. Never recycle tokens within this address-space object.
        if not isinstance(reservation, Reservation) or self._active.get(reservation.token) is not reservation:
            raise ValueError('unknown or stale reservation')
        del self._active[reservation.token]

    def contains(self, reservation, offset, length):
        if not isinstance(reservation, Reservation) or self._active.get(reservation.token) is not reservation:
            return False
        return (type(offset) is int and type(length) is int and offset >= 0 and length > 0
                and offset <= reservation.size and length <= reservation.size - offset)
