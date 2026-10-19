/* Stage-1: bounded PowerPC snippet execution, NOT full game emulation. */
#include <switch.h>
#include <stdio.h>
#include <string.h>
#include "xex_probe.h"
#include "ppc_pe.h"
#define GAME_XEX "sdmc:/switch/labnx/castle/default.xex"
int main(int argc,char **argv) {
    (void)argc; (void)argv;
    /* Separate proof of ARM64 homebrew main from Eden GUI startup. */
    static const char guest_enter[] = "LABNX_CASTLE_STAGE0_MAIN_ENTERED";
    svcOutputDebugString(guest_enter, sizeof(guest_enter)-1);
    consoleInit(NULL);
    padConfigureInput(1,HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);
    XexProbeInfo info;
    memset(&info,0,sizeof(info));
    XexProbeStatus status=XEX_PROBE_IO;
    FILE *f=fopen(GAME_XEX,"rb");
    if(f) {status=xex_probe_file(f,&info);fclose(f);}
    /* Privately decoded genuine Xbox PE, never embedded in public NRO. */
    uint32_t ppc_result=0;
    PpcPeStatus ppc_status=PPC_PE_IO;
    FILE *guest=fopen("sdmc:/switch/labnx/castle/decoded-powerpc.bin","rb");
    if(guest) {
        ppc_status=ppc_pe_run_leaf(guest,0x8208EE10u,17u,&ppc_result);
        fclose(guest);
    }
    /* Success means only a restricted guest instruction stream terminated.
       It does NOT prove authentic function boundaries or gameplay. */
    if(ppc_status==PPC_PE_OK) {
        static const char marker[]="LABNX_GUEST_PPC_LEAF_EXECUTED";
        svcOutputDebugString(marker,sizeof(marker)-1);
    }
    while(appletMainLoop()) {
        padUpdate(&pad);
        u64 keys=padGetButtonsDown(&pad);
        consoleClear();
        printf("lab-NX / Castle Crashers Switch bootstrap\n");
        printf("======================================\n");
        printf("STAGE-1: PPC SNIPPET / NOT PLAYABLE\n\n");
        printf("Source: %s\n",GAME_XEX);
        if(status==XEX_PROBE_OK) {
            printf("Original Castle Crashers XEX: FOUND\n");
            printf("Title ID: %08lX\n",(unsigned long)info.title_id);
            printf("PowerPC entry: %08lX\n",(unsigned long)info.entry_point);
            printf("Image base: %08lX\n",(unsigned long)info.image_base);
            printf("Image size: %lu bytes\n",(unsigned long)info.image_size);
            printf("XEX encryption=%u compression=%u\n",info.encryption,info.compression);
        } else if(status==XEX_PROBE_NOT_CASTLE) printf("XEX is not Castle Crashers!\n");
        else if(status==XEX_PROBE_FORMAT) printf("Invalid/truncated XEX2 file.\n");
        else printf("No XEX: copy your own file to SD card.\n");
        printf("\nPrivate PowerPC PE: %s\n",
            ppc_status==PPC_PE_OK?"LEAF EXECUTED":"NOT EXECUTED");
        if(ppc_status==PPC_PE_OK)
            printf("PPC snippet at 8208EE10: r3=%lu (seed=17)\n",
                   (unsigned long)ppc_result);
        else
            printf("PPC snippet status: %u\n",(unsigned)ppc_status);
        printf("No complete Xbox game runtime yet.\n");
        printf("\nController A: %s\n",(keys&HidNpadButton_A)?"PRESSED":"-");
        printf("Controller Plus: %s\n",(keys&HidNpadButton_Plus)?"PRESSED":"-");
        printf("\nPress + to exit this diagnostic.\n");
        printf("NO XBOX RUNTIME / NO GAME GRAPHICS YET\n");
        consoleUpdate(NULL);
        if(keys&HidNpadButton_Plus) break;
    }
    consoleExit(NULL);
    return 0;
}
