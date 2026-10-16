#include <assert.h>
#include <string.h>
#include "../port/mi_batch.h"

int main(void)
{
    uint32_t result[6];
    const uint32_t expected[] = {
        0x10000002, 0x23456780, 1, 0xdeadbeef, 0x05000000, 0
    };
    assert(im_store_dword_batch(UINT64_C(0x123456780), 0xdeadbeef, result, 6));
    assert(memcmp(result, expected, sizeof(result)) == 0);
    assert(!im_store_dword_batch(1, 0, result, 6));
    assert(!im_store_dword_batch(UINT64_C(1) << 48, 0, result, 6));
    assert(!im_store_dword_batch(4096, 0, result, 5));
    assert(!im_store_dword_batch(4096, 0, NULL, 6));
    assert(memcmp(result, expected, sizeof(result)) == 0);
    assert(im_store_dword_batch((UINT64_C(1) << 48) - 4, UINT32_MAX, result, 6));
    assert(result[1] == 0xfffffffc && result[2] == 0xffff);
    return 0;
}
