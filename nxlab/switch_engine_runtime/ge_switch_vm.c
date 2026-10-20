#include "ge_switch_vm.h"
#include <stdlib.h>
#include <string.h>

typedef struct {
    Handle server;
    Handle process;
    Result result;
} GeHandleRequest;

static void geReceiveSelfHandle(void *argument)
{
    GeHandleRequest *r = argument;
    s32 index = -1;
    r->result = svcReplyAndReceive(&index, &r->server, 1, INVALID_HANDLE, 5000000000LL);
    if (R_SUCCEEDED(r->result)) {
        HipcParsedRequest message = hipcParseRequest(armGetTls());
        if (message.meta.num_copy_handles == 1)
            r->process = message.data.copy_handles[0];
        else r->result = MAKERESULT(Module_Libnx, LibnxError_BadInput);
    }
    /* The synchronous client intentionally receives SessionClosed. The
     * copied handle remains in this process's table after server close. */
    svcCloseHandle(r->server);
}

static Result geGetProcessHandle(Handle *out, bool *owned)
{
    Handle supplied = envGetOwnProcessHandle();
    if (supplied != INVALID_HANDLE && supplied != CUR_PROCESS_HANDLE) {
        *out = supplied;
        *owned = false;
        return 0;
    }
    GeHandleRequest request = {0};
    Handle client = INVALID_HANDLE;
    Result rc = svcCreateSession(&request.server, &client, false, 0);
    if (R_FAILED(rc)) return rc;
    Thread thread;
    rc = threadCreate(&thread, geReceiveSelfHandle, &request, NULL, 0x10000, 0x2c, -2);
    if (R_FAILED(rc)) {
        svcCloseHandle(client); svcCloseHandle(request.server); return rc;
    }
    rc = threadStart(&thread);
    if (R_FAILED(rc)) {
        threadClose(&thread); svcCloseHandle(client); svcCloseHandle(request.server); return rc;
    }
    HipcRequest message = hipcMakeRequestInline(armGetTls(),
        .type = 4, .num_copy_handles = 1, .num_data_words = 4);
    message.copy_handles[0] = CUR_PROCESS_HANDLE;
    memset(message.data_words, 0, 4 * sizeof(u32));
    (void)svcSendSyncRequest(client);
    threadWaitForExit(&thread);
    threadClose(&thread);
    svcCloseHandle(client);
    if (R_FAILED(request.result)) return request.result;
    u64 expected = 0, actual = 0;
    rc = svcGetProcessId(&expected, CUR_PROCESS_HANDLE);
    if (R_SUCCEEDED(rc)) rc = svcGetProcessId(&actual, request.process);
    if (R_FAILED(rc) || actual != expected) {
        if (request.process) svcCloseHandle(request.process);
        return R_FAILED(rc) ? rc : MAKERESULT(Module_Libnx, LibnxError_BadInput);
    }
    *out = request.process;
    *owned = true;
    return 0;
}

Result geSwitchUnmapViews(GeSwitchMapping *m)
{
    if (!m) return MAKERESULT(Module_Libnx, LibnxError_BadInput);
    Result result = 0;
    for (unsigned i = 0; i < 2; ++i) {
        if (!(m->mapped & (1u << i))) continue;
        Result rc = svcUnmapProcessMemory(m->views[i], m->process,
                                         (u64)m->backing, m->size);
        if (R_SUCCEEDED(rc)) m->mapped &= ~(1u << i);
        else if (R_SUCCEEDED(result)) result = rc;
    }
    /* Retain live mappings and their handle after an unsuccessful unmap.
     * The caller must keep the backing alive and may retry cleanup. */
    if (m->mapped) return result;
    if (m->owns_process && m->process) svcCloseHandle(m->process);
    memset(m, 0, sizeof *m);
    return result;
}

static bool geRangesOverlap(uintptr_t a, uintptr_t b, size_t size)
{
    return a < b + size && b < a + size;
}

Result geSwitchMapViews(GeSwitchMapping *m, void *backing, size_t size,
                       void *first, void *second)
{
    uintptr_t source = (uintptr_t)backing, a = (uintptr_t)first, b = (uintptr_t)second;
    if (!m || m->backing || m->mapped || m->process || !size ||
        !source || !a || !b || (source | a | b | size) % 0x1000 ||
        size > UINTPTR_MAX - source || size > UINTPTR_MAX - a || size > UINTPTR_MAX - b ||
        geRangesOverlap(a, b, size) || geRangesOverlap(source, a, size) ||
        geRangesOverlap(source, b, size))
        return MAKERESULT(Module_Libnx, LibnxError_BadInput);
    m->size = size; m->views[0] = first; m->views[1] = second;
    Result rc = geGetProcessHandle(&m->process, &m->owns_process);
    if (R_FAILED(rc)) { memset(m, 0, sizeof *m); return rc; }
    m->backing = backing;
    for (unsigned i = 0; i < 2; ++i) {
        rc = svcMapProcessMemory(m->views[i], m->process, (u64)m->backing, size);
        if (R_FAILED(rc)) { (void)geSwitchUnmapViews(m); return rc; }
        m->mapped |= 1u << i;
    }
    return 0;
}
