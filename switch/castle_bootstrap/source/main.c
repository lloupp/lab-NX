/* Stage-0 Switch bootstrap only. Does NOT execute PowerPC game code. */
#include <switch.h>
#include <stdio.h>
#include <string.h>
#include "xex_probe.h"
#define GAME_XEX "sdmc:/switch/labnx/castle/default.xex"
int main(int argc,char **argv) {
    (void)argc; (void)argv;
    consoleInit(NULL);
    padConfigureInput(1,HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);
    XexProbeInfo info;
    memset(&info,0,sizeof(info));
    XexProbeStatus status=XEX_PROBE_IO;
    FILE *f=fopen(GAME_XEX,"rb");
    if(f) {status=xex_probe_file(f,&info);fclose(f);}
    while(appletMainLoop()) {
        padUpdate(&pad);
        u64 keys=padGetButtonsDown(&pad);
        consoleClear();
        printf("lab-NX / Castle Crashers Switch bootstrap\n");
        printf("======================================\n");
        printf("STAGE-0: NOT A PLAYABLE GAME PORT\n\n");
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
        printf("\nController A: %s\n",(keys&HidNpadButton_A)?"PRESSED":"-");
        printf("Controller Plus: %s\n",(keys&HidNpadButton_Plus)?"PRESSED":"-");
        printf("\nPress + to exit this diagnostic.\n");
        printf("NO PPC RUNTIME / NO GAME GRAPHICS YET\n");
        consoleUpdate(NULL);
        if(keys&HidNpadButton_Plus) break;
    }
    consoleExit(NULL);
    return 0;
}
