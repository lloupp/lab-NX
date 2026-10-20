#ifndef GOLDENEYE_N64_MEMORY_H
#define GOLDENEYE_N64_MEMORY_H
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GE_N64_RDRAM_SIZE 0x00800000u
#define GE_N64_V1_BASE 0x70000000u
#define GE_N64_K0_BASE 0x80000000u
#define GE_N64_K1_BASE 0xa0000000u

/* Explicit translation, NOT fixed-address virtual memory. Engine code that
 * directly dereferences N64 addresses still needs a port-side adaptation.
 * Does not replace the unavailable Linux Mint commit d932006.
 */
typedef struct {
    uint8_t *bytes;
    size_t size;
    struct { uint8_t *bytes; size_t size; } segments[16];
} ge_n64_memory;

typedef enum {
    GE_N64_OK, GE_N64_ARGUMENT, GE_N64_ADDRESS, GE_N64_RANGE,
    GE_N64_SEGMENT_UNBOUND
} ge_n64_result;

ge_n64_result ge_n64_memory_init(ge_n64_memory *memory, void *backing, size_t size);
/* Span length must be nonzero; output is preserved on failure. Physical,
 * PC-port V1, KSEG0 and KSEG1 addresses all alias the same backing bytes. */
ge_n64_result ge_n64_memory_span(const ge_n64_memory *memory, uint32_t address,
                               size_t length, void **out);
ge_n64_result ge_n64_memory_physical(const ge_n64_memory *memory,
                                   const void *host, size_t length, uint32_t *out);
/* Segment zero is reserved, matching the PC port's seg_addr convention. */
ge_n64_result ge_n64_memory_bind_segment(ge_n64_memory *memory, unsigned segment,
                                       void *backing, size_t size);
/* Matches marked (bit zero) and unmarked segment refs in gfx_pc.cpp.
 * Unknown addresses never fall through to an unchecked host-pointer cast. */
ge_n64_result ge_n64_memory_display_span(const ge_n64_memory *memory,
                                       uint32_t word, size_t length, void **out);

#ifdef __cplusplus
}
#endif
#endif
