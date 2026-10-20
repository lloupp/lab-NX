#ifndef GE_SWITCH_VM_H
#define GE_SWITCH_VM_H
#include <switch.h>
#include <stddef.h>

typedef struct {
    void *backing;
    size_t size;
    void *views[2];
    Handle process;
    bool owns_process;
    unsigned mapped;
} GeSwitchMapping;

/* Initialize mapping to {0}. Backing must be page-aligned static CodeData
 * (BSS/data), not malloc/heap Normal memory. Its lifetime must exceed all views.
 * Maps the same pages at both addresses without copying or clearing their data.
 * Failure is reported; callers must not dereference an unsuccessful mapping.
 * Always call cleanup after a failed map: partial cleanup can itself fail. */
Result geSwitchMapViews(GeSwitchMapping *mapping, void *backing, size_t size, void *first, void *second);
Result geSwitchUnmapViews(GeSwitchMapping *mapping);
#endif
