#ifndef LABNX_XEX_PROBE_H
#define LABNX_XEX_PROBE_H
#include <stdint.h>
#include <stdio.h>
typedef enum { XEX_PROBE_OK=0, XEX_PROBE_IO=1, XEX_PROBE_FORMAT=2, XEX_PROBE_NOT_CASTLE=3 } XexProbeStatus;
typedef struct {
    uint32_t title_id, entry_point, image_base, image_size;
    uint16_t encryption, compression;
    uint32_t optional_headers;
} XexProbeInfo;
XexProbeStatus xex_probe_file(FILE *file, XexProbeInfo *info);
#endif
