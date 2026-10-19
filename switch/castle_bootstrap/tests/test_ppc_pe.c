#include "ppc_pe.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static void wr16(unsigned char *b,uint32_t off,uint16_t v){b[off]=v;b[off+1]=v>>8;}
static void wr32(unsigned char *b,uint32_t off,uint32_t v){for(int i=0;i<4;i++)b[off+i]=(unsigned char)(v>>(8*i));}
static void be32(unsigned char *b,uint32_t off,uint32_t v){for(int i=0;i<4;i++)b[off+i]=(unsigned char)(v>>(24-8*i));}
static FILE *mkpe(uint32_t a,uint32_t b){
    unsigned char data[4096]={0};
    memcpy(data,"MZ",2);wr32(data,0x3c,0x80);
    memcpy(data+0x80,"PE\0\0",4);wr16(data,0x84,0x1F2);wr16(data,0x86,1);wr16(data,0x94,224);
    wr16(data,0x98,0x10b);wr32(data,0x98+28,0x82000000);
    unsigned sec=0x80+24+224;
    memcpy(data+sec,".text",5);wr32(data,sec+12,0x50000);wr32(data,sec+16,0x200);
    wr32(data,sec+20,0x400);wr32(data,sec+36,0x60000020);
    be32(data,0x400,a);be32(data,0x404,b);
    FILE *f=tmpfile();assert(f);assert(fwrite(data,1,sizeof(data),f)==sizeof(data));rewind(f);return f;
}
int main(void){
    FILE *f=mkpe(0x38630068u,0x4E800020u);uint32_t r=0;
    assert(ppc_pe_run_leaf(f,0x82050000u,17,&r)==PPC_PE_OK&&r==121);
    assert(ppc_pe_run_leaf(f,0x82050000u,UINT32_MAX,&r)==PPC_PE_OK&&r==103);
    assert(ppc_pe_run_leaf(f,0x82060000u,17,&r)==PPC_PE_ADDRESS);
    fclose(f);
    f=mkpe(0x48000000u,0x4E800020u);
    assert(ppc_pe_run_leaf(f,0x82050000u,17,&r)==PPC_PE_UNSUPPORTED);
    fclose(f);
    puts("PASS: synthetic PowerPC PE interpreter, overflow and rejection");return 0;
}
