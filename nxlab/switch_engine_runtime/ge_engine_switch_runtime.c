#define GE_SWITCH_PLATFORM_TU 1
#include "ge_switch_vm.h"
#include <stdio.h>
#include "hoststdlib.h"
static unsigned char ram[0x800000] __attribute__((aligned(4096)));
static unsigned char cart[0x6000000] __attribute__((aligned(4096)));
static unsigned char stacks[16][0x800000] __attribute__((aligned(4096)));
static GeSwitchMapping ram_map, cart_map, stack_maps[16];
static unsigned stack_count;
static Handle callback_handles[16];
static void *map(GeSwitchMapping *m, void *backing, size_t size, uintptr_t a, uintptr_t b)
{
    Result rc = geSwitchMapViews(m, backing, size, (void *)a, (void *)b);
    fprintf(stderr,"Switch map %lx/%lx size=%lx result=%08x\n",a,b,size,rc);
    fflush(stderr);
    if (R_FAILED(rc)) abort();
    return (void *)a;
}
void *geEngineReserveDram(void) { return map(&ram_map,ram,sizeof ram,0x70000000,0x60000000); }
void *geEngineMapCart(unsigned long size) {
    if (size > sizeof cart) return NULL;
    return map(&cart_map,cart,(size+4095)&~4095UL,0x10000000,0x30000000);
}
void geEngineUnmapCart(void) { (void)geSwitchUnmapViews(&cart_map); }
void *geEngineLowStack(unsigned long size) {
    if(size>sizeof stacks[0] || stack_count==16) abort();
    unsigned i=stack_count++;
    return map(&stack_maps[i],stacks[i],sizeof stacks[0],0x40000000+i*0x800000,0x50000000+i*0x800000);
}

#include <sys/stat.h>
#include <unistd.h>
void geEngineBoot(void) {
    fsdevMountSdmc();
    mkdir("sdmc:/switch",0777);
    mkdir("sdmc:/switch/lab-nx",0777);
    mkdir("sdmc:/switch/lab-nx/goldeneye",0777);
    mkdir("sdmc:/switch/lab-nx/goldeneye/data",0777);
    chdir("sdmc:/switch/lab-nx/goldeneye");
    freopen("engine.log","w",stderr);
    freopen("engine-stdout.log","w",stdout);
    setvbuf(stderr,NULL,_IONBF,0);
    setvbuf(stdout,NULL,_IONBF,0);
    fprintf(stderr,"Switch ARM64 full engine entry; target Dam; gameplay not confirmed\n");
}

#include <pthread.h>
#include <errno.h>
/* The libnx pthread owns its normal TLS/startup/cleanup stack. The game
 * callback runs on a low alias so its deliberate u32 stack casts survive.
 * This AAPCS64 trampoline preserves callee-saved state and returns to the
 * original stack before pthread cleanup. Cancellation/unwinding across it
 * is unsupported; this engine uses cooperative thread termination. */
extern void *geSwitchCallOnLowStack(void *(*entry)(void *), void *argument,
                                    void *stack, size_t size);
__asm__(".text\n.align 2\n.global geSwitchCallOnLowStack\n"
        ".type geSwitchCallOnLowStack, %function\n"
        "geSwitchCallOnLowStack:\n"
        "stp x19, x20, [sp, #-32]!\n"
        "stp x29, x30, [sp, #16]\n"
        "mov x19, sp\nmov x20, x0\n"
        "add x9, x2, x3\nand x9, x9, #-16\nmov sp, x9\n"
        "mov x0, x1\nblr x20\nmov sp, x19\n"
        "ldp x29, x30, [sp, #16]\nldp x19, x20, [sp], #32\nret\n"
        ".size geSwitchCallOnLowStack, .-geSwitchCallOnLowStack\n");
typedef struct { void *(*entry)(void *); void *arg; void *stack; } GeThreadLaunch;
static void *geEngineThreadEntry(void *opaque) {
    GeThreadLaunch launch = *(GeThreadLaunch *)opaque;
    free(opaque);
    unsigned slot = ((uintptr_t)launch.stack - 0x40000000) / sizeof stacks[0];
    __atomic_store_n(&callback_handles[slot], threadGetCurHandle(), __ATOMIC_RELEASE);
    void *result = geSwitchCallOnLowStack(launch.entry, launch.arg, launch.stack, sizeof stacks[0]);
    __atomic_store_n(&callback_handles[slot], 0, __ATOMIC_RELEASE);
    return result;
}
int geEnginePthreadCreate(pthread_t *thread, const pthread_attr_t *attr,
                         void *(*entry)(void *), void *argument) {
    GeThreadLaunch *launch = malloc(sizeof *launch);
    if (!launch) return ENOMEM;
    *launch = (GeThreadLaunch){entry,argument,geEngineLowStack(sizeof stacks[0])};
    int rc = pthread_create(thread,attr,geEngineThreadEntry,launch);
    if (rc) free(launch);
    return rc;
}

void geEngineCheckpoint(const char *name) { fprintf(stderr,"[ENGINE] entering %s\n",name); }


void geEngineDumpRegisters(void) {
    for (unsigned i=0;i<16;++i) {
        Handle handle=__atomic_load_n(&callback_handles[i],__ATOMIC_ACQUIRE);
        if (!handle || handle==threadGetCurHandle()) continue;
        ThreadContext ctx={0};
        Result pause=svcSetThreadActivity(handle,ThreadActivity_Paused);
        Result read=pause, resume=0;
        if (R_SUCCEEDED(pause)) {
            read=svcGetThreadContext3(&ctx,handle);
            resume=svcSetThreadActivity(handle,ThreadActivity_Runnable);
        }
        fprintf(stderr,"[ENGINE] registers slot=%u pause=%08x read=%08x resume=%08x pc=%lx lr=%lx sp=%lx fp=%lx x0=%lx x1=%lx x2=%lx anchor=%p\n",
            i,pause,read,resume,ctx.pc.x,ctx.lr,ctx.sp,ctx.fp,ctx.cpu_gprs[0].x,ctx.cpu_gprs[1].x,ctx.cpu_gprs[2].x,(void *)geEngineCheckpoint);
    }
}
