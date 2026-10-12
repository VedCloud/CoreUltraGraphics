import random
import unittest
from gpu_address_space import AddressSpace, Reservation


class AddressSpaceTests(unittest.TestCase):
    def test_alignment_holes_and_exhaustion(self):
        space = AddressSpace(end=5 * 4096)
        a, b, c = [space.reserve(1) for _ in range(3)]
        self.assertEqual(a.size, 4096)
        space.release(b)
        replacement = space.reserve(4096)
        self.assertEqual(replacement.gpu_va, b.gpu_va)
        space.reserve(4096)
        with self.assertRaises(MemoryError):
            space.reserve(4096)

    def test_foreign_forged_and_stale_handles(self):
        space = AddressSpace()
        a = space.reserve(4096)
        for invalid in (Reservation(a.token, a.gpu_va, a.size), AddressSpace().reserve(4096)):
            with self.assertRaises(ValueError):
                space.release(invalid)
        space.release(a)
        space.reserve(4096)
        with self.assertRaises(ValueError):
            space.release(a)

    def test_submission_bounds(self):
        space = AddressSpace()
        a = space.reserve(4096)
        self.assertTrue(space.contains(a, 4092, 4))
        for offset, length in ((4093, 4), (-1, 4), (0, 0), (0, 1 << 64)):
            self.assertFalse(space.contains(a, offset, length))
        space.release(a)
        self.assertFalse(space.contains(a, 0, 4))

    def test_invalid_inputs(self):
        for kwargs in ({'start': 0}, {'page_size': 3}, {'end': 1 << 49}):
            with self.assertRaises(ValueError):
                AddressSpace(**kwargs)
        space = AddressSpace()
        for size in (0, -1, True, 1 << 64):
            with self.assertRaises(ValueError):
                space.reserve(size)
        with self.assertRaises(ValueError):
            space.reserve(4096, 6000)

    def test_randomised_nonoverlap_and_range(self):
        rng = random.Random(135)
        space = AddressSpace(end=256 * 4096)
        active = []
        for _ in range(1500):
            if active and rng.random() < 0.5:
                space.release(active.pop(rng.randrange(len(active))))
            else:
                try:
                    active.append(space.reserve(rng.randint(1, 8) * 4096,
                                                4096 << rng.randrange(4)))
                except MemoryError:
                    pass
            ordered = sorted(active, key=lambda r: r.gpu_va)
            for r in ordered:
                self.assertGreaterEqual(r.gpu_va, space.start)
                self.assertLessEqual(r.gpu_va + r.size, space.end)
            for left, right in zip(ordered, ordered[1:]):
                self.assertLessEqual(left.gpu_va + left.size, right.gpu_va)
