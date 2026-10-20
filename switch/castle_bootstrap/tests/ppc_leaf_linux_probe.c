/* Cross-architecture proof: run an ORIGINAL private Xbox PPC PE snippet using
 * the exact C interpreter that is linked into the libnx Switch NRO.
 *
 * Compile Linux host x86_64 / aarch64 and execute in native Linux / QEMU user.
 * No commercial code or image is embedded or uploaded to CI.
 * This is an instruction subset (addi/addis/ori/xori/blr), not a full game.
 */
#include "ppc_pe.h"
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int parse_hex(const char *s, uint32_t *out) {
    if (!s || !*s || *s == '-') return 0;
    errno = 0;
    char *end = NULL;
    unsigned long long n = strtoull(s, &end, 0);
    if (errno || !end || *end || n > UINT32_MAX) return 0;
    *out = (uint32_t)n;
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 5) {
        fprintf(stderr, "usage: %s PRIVATE_POWERPC_PE guest_address seed expected_r3\n",
                argv[0]);
        return 2;
    }
    uint32_t address, seed, expected, actual = 0;
    if (!parse_hex(argv[2], &address) || !parse_hex(argv[3], &seed) ||
        !parse_hex(argv[4], &expected)) {
        fprintf(stderr, "Invalid 32-bit address/input/expected value\n");
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        fprintf(stderr, "Cannot open guest PE: %s\n", strerror(errno));
        return 2;
    }
    PpcPeStatus status = ppc_pe_run_leaf(f, address, seed, &actual);
    fclose(f);
    int match = status == PPC_PE_OK && actual == expected;
    printf("{\"arch\":\"%s\",\"original_ppc_bytes_supplied_at_runtime\":true,"
           "\"guest_address\":\"0x%08" PRIX32 "\",\"seed_r3\":%" PRIu32 ","
           "\"expected_r3\":%" PRIu32 ",\"actual_r3\":%" PRIu32 ","
           "\"ppc_status\":%u,\"match\":%s,"
           "\"guest_full_function_verified\":false,"
           "\"switch_nro_executed\":false,\"eden_executed\":false,"
           "\"game_playable\":false}\n",
#if defined(__aarch64__)
           "aarch64",
#elif defined(__x86_64__)
           "x86_64",
#else
           "other",
#endif
           address, seed, expected, actual, (unsigned)status,
           match ? "true" : "false");
    return match ? 0 : 1;
}
