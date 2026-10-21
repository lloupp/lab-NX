#ifndef GOLDENEYE_N64_MEMORY_H
#define GOLDENEYE_N64_MEMORY_H
#include <stdbool.h>
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
 * The additive compatibility API below preserves the d932006 helper contract.
 */
typedef struct {
    uint8_t *bytes;
    size_t size;
    const uint8_t *rom;
    size_t rom_size;
    struct { uint8_t *bytes; size_t size; } segments[16];
} ge_n64_memory;

/* Compatibility result/API from the local d932006 memory layer. Kept
 * alongside the arena/segment API so callers can migrate incrementally. */
typedef enum {
    GE_N64_MEM_OK = 0,
    GE_N64_MEM_INVALID = -1,
    GE_N64_MEM_BOUNDS = -2,
    GE_N64_MEM_ALIGNMENT = -3,
    GE_N64_MEM_READ_ONLY = -4,
    GE_N64_MEM_UNMAPPED = -5
} ge_n64_mem_result;

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

/* Legacy d932006 interface. ROM mappings are read-only; the DRAM aliases and
 * bounds checks delegate to the same checked span implementation. */
ge_n64_mem_result ge_n64_memory_bind(ge_n64_memory *memory,
    uint8_t *dram, size_t dram_size, const uint8_t *rom, size_t rom_size);
ge_n64_mem_result ge_n64_memory_resolve(const ge_n64_memory *memory,
    uint32_t address, size_t length, bool write_access, void **host_pointer);
ge_n64_mem_result ge_n64_memory_read_u8(const ge_n64_memory *memory,
    uint32_t address, uint8_t *value);
ge_n64_mem_result ge_n64_memory_read_be16(const ge_n64_memory *memory,
    uint32_t address, uint16_t *value);
ge_n64_mem_result ge_n64_memory_read_be32(const ge_n64_memory *memory,
    uint32_t address, uint32_t *value);
ge_n64_mem_result ge_n64_memory_write_u8(const ge_n64_memory *memory,
    uint32_t address, uint8_t value);
ge_n64_mem_result ge_n64_memory_write_be16(const ge_n64_memory *memory,
    uint32_t address, uint16_t value);
ge_n64_mem_result ge_n64_memory_write_be32(const ge_n64_memory *memory,
    uint32_t address, uint32_t value);

#ifdef __cplusplus
}
#endif
#endif
