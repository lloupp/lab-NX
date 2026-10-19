#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "xex_probe.h"
static void store32(unsigned char *p,uint32_t v) {
    p[0]=(unsigned char)(v>>24);p[1]=(unsigned char)(v>>16);p[2]=(unsigned char)(v>>8);p[3]=(unsigned char)v;
}
int main(void) {
    unsigned char data[0x600]={0};
    memcpy(data,"XEX2",4);
    store32(data+8,0x600);
    store32(data+16,0x100);
    store32(data+20,4);
    uint32_t keys[4]={0x3ff,0x40006,0x10100,0x10201};
    uint32_t values[4]={0x290,0x2c0,0x820b7090,0x82000000};
    for(int i=0;i<4;i++) {store32(data+24+8*i,keys[i]);store32(data+28+8*i,values[i]);}
    store32(data+0x100,0x184);store32(data+0x104,2949120);
    store32(data+0x290,36);data[0x295]=1;data[0x297]=2;
    store32(data+0x2c0+12,0x584108b7);
    FILE *f=tmpfile();if(!f)return 9;
    if(fwrite(data,1,sizeof(data),f)!=sizeof(data))return 8;
    XexProbeInfo info;
    if(xex_probe_file(f,&info)!=XEX_PROBE_OK)return 1;
    if(info.title_id!=0x584108b7||info.entry_point!=0x820b7090||
       info.image_size!=2949120)return 2;
    store32(data+0x2c0+12,0xdeadbeef);
    rewind(f);fwrite(data,1,sizeof(data),f);fflush(f);
    if(xex_probe_file(f,&info)!=XEX_PROBE_NOT_CASTLE)return 3;
    rewind(f);fwrite("BAD!",1,4,f);fflush(f);
    if(xex_probe_file(f,&info)!=XEX_PROBE_FORMAT)return 4;
    fclose(f);
    puts("XEX parser: 3 synthetic negative/positive fixtures PASS");
    return 0;
}
