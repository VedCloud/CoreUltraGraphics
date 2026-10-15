// SPDX-License-Identifier: GPL-2.0-or-later
// Adapted behavior from Linux i2c-designware-master.c: wait for master idle
// after STOP before disabling, and reject unfinished transfers.
#pragma once

template<class ReadStatus, class Delay>
bool latitudeWaitMasterIdle(ReadStatus readStatus, Delay delay,
                            unsigned &lastStatus, unsigned &waitedUs) {
    waitedUs = 0;
    for (;;) {
        lastStatus = readStatus();
        if (lastStatus == 0xffffffffU) return false;
        if (!(lastStatus & (1U << 5))) return true;
        if (waitedUs >= 20000) return false;
        unsigned step = 20000 - waitedUs;
        if (step > 1100) step = 1100;
        delay(step);
        waitedUs += step;
    }
}

inline bool latitudeTransferComplete(unsigned status, int queued, int total,
                                      int readIndex, int outstanding, bool hasRead) {
    return total > 0 && status == 0 && queued == total && outstanding == 0 &&
        (!hasRead || readIndex == total);
}
