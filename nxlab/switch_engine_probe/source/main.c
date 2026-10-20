#include <switch.h>
#include <stdio.h>
#include <sys/stat.h>
#include "ge_switch_vm.h"

static unsigned char rdram[0x800000] __attribute__((aligned(0x1000)));

int main(void)
{
    fsdevMountSdmc();
    mkdir("sdmc:/switch", 0777);
    mkdir("sdmc:/switch/lab-nx", 0777);
    FILE *log = fopen("sdmc:/switch/lab-nx/goldeneye-engine-vm.txt", "w");
    if (!log) return 1;
    fprintf(log, "probe-entered; no game code or ROM\n"); fflush(log);
    fprintf(log, "env-process=%08x\n", envGetOwnProcessHandle()); fflush(log);
    for (unsigned id = 2; id <= 15; ++id) {
        if (id > 5 && id < 12) continue;
        u64 value = 0;
        Result info_rc = svcGetInfo(&value, id, CUR_PROCESS_HANDLE, 0);
        fprintf(log, "region-info-%u=%016lx result=%08x\n", id, value, info_rc);
    }
    fflush(log);
    for (unsigned i = 0; i < 3; ++i) {
        u64 address = i == 0 ? 0x10000000 : i == 1 ? 0x70000000 : 0x80000000;
        MemoryInfo info = {0}; u32 page = 0;
        Result query_rc = svcQueryMemory(&info, &page, address);
        fprintf(log, "query-%lx: base=%lx size=%lx type=%u perm=%u rc=%08x\n",
                address, info.addr, info.size, info.type, info.perm, query_rc);
    }
    fflush(log);
    GeSwitchMapping mapping = {0};
    Result rc = geSwitchMapViews(&mapping, rdram, sizeof rdram,
                               (void *)0x70000000, (void *)0x60000000);
    fprintf(log, "fixed-rdram-map-result=%08x\n", rc); fflush(log);
    bool passed = R_SUCCEEDED(rc);
    if (R_SUCCEEDED(rc)) {
        volatile u32 *v1 = (volatile u32 *)0x70000000;
        volatile u32 *v2 = (volatile u32 *)0x60000000;
        volatile u32 *source = mapping.backing;
        v1[0] = 0x1234abcd;
        source[0x7ffffc / 4] = 0xdeadbeef;
        bool aliases = v2[0] == 0x1234abcd && source[0] == 0x1234abcd &&
                       v1[0x7ffffc / 4] == 0xdeadbeef && v2[0x7ffffc / 4] == 0xdeadbeef;
        fprintf(log, "fixed-rdram-bidirectional-alias=%s\n", aliases ? "PASS" : "FAIL");
        fflush(log);
        passed = passed && aliases;
        Result busy = geSwitchMapViews(&mapping, rdram, sizeof rdram,
                                     (void *)0x70000000, (void *)0x60000000);
        fprintf(log, "live-remap-rejected=%s\n", R_FAILED(busy) ? "PASS" : "FAIL");
        passed = passed && R_FAILED(busy);
        Result cleanup = geSwitchUnmapViews(&mapping);
        fprintf(log, "cleanup=%08x retained=%u\n", cleanup, mapping.mapped);
        passed = passed && R_SUCCEEDED(cleanup) && !mapping.mapped;
        MemoryInfo info = {0}; u32 page = 0;
        Result query = svcQueryMemory(&info, &page, 0x70000000);
        bool released = R_SUCCEEDED(query) && info.type == MemType_Unmapped;
        fprintf(log, "released-view=%s\n", released ? "PASS" : "FAIL");
        passed = passed && released;
        Result overlap = geSwitchMapViews(&mapping, rdram, sizeof rdram,
                                         (void *)0x70000000, (void *)0x70001000);
        fprintf(log, "overlap-rejected=%s\n", R_FAILED(overlap) ? "PASS" : "FAIL");
        passed = passed && R_FAILED(overlap);
    }
    (void)geSwitchUnmapViews(&mapping);
    fprintf(log, "memory-probe=%s; no gameplay\n", passed ? "PASS" : "FAIL");
    fclose(log);
    return passed ? 0 : 2;
}
