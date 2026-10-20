#include "ppc_pe.h"
#include <string.h>
#define PE_MAX_BYTES (64u * 1024u * 1024u)
#define MAX_SECTIONS 32u
#define MAX_INSNS 16u
static uint16_t le16(const unsigned char *p){return (uint16_t)((uint16_t)p[0]|((uint16_t)p[1]<<8));}
static uint32_t le32(const unsigned char *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint32_t be32(const unsigned char *p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static int read_at(FILE *f,uint32_t limit,uint32_t at,void *out,size_t n){return (uint64_t)at+n<=limit&&!fseek(f,(long)at,SEEK_SET)&&fread(out,1,n,f)==n;}
PpcPeStatus ppc_pe_run_leaf(FILE *pe,uint32_t address,uint32_t seed,uint32_t *result){
    if(!pe||!result)return PPC_PE_IO;
    *result=0;
    if(fseek(pe,0,SEEK_END))return PPC_PE_IO;
    long n=ftell(pe);
    if(n<512||(uint64_t)n>PE_MAX_BYTES)return PPC_PE_FORMAT;
    uint32_t limit=(uint32_t)n;
    unsigned char dos[64],coff[24],opt[32],sec[40],word[4];
    if(!read_at(pe,limit,0,dos,sizeof(dos)))return PPC_PE_IO;
    if(dos[0]!='M'||dos[1]!='Z')return PPC_PE_FORMAT;
    uint32_t nt=le32(dos+60);
    if(nt<64||!read_at(pe,limit,nt,coff,sizeof(coff)))return PPC_PE_FORMAT;
    if(memcmp(coff,"PE\0\0",4)||le16(coff+4)!=0x01F2)return PPC_PE_FORMAT;
    uint16_t num=le16(coff+6),osz=le16(coff+20);
    if(num==0||num>MAX_SECTIONS||osz<32||!read_at(pe,limit,nt+24,opt,sizeof(opt)))return PPC_PE_FORMAT;
    if(le16(opt)!=0x10b)return PPC_PE_FORMAT;
    uint32_t base=le32(opt+28);
    uint32_t raw=0,remaining=0;
    uint64_t section_table=(uint64_t)nt+24+osz;
    if(section_table+40u*num>limit)return PPC_PE_FORMAT;
    for(unsigned i=0;i<num;i++){
        if(!read_at(pe,limit,(uint32_t)section_table+40u*i,sec,sizeof(sec)))return PPC_PE_IO;
        uint32_t rva=le32(sec+12),sz=le32(sec+16),flags=le32(sec+36);
        /* XEX normal-LZX output is a mapped PE image: section bytes live at\n           virtual RVA, NOT section PointerToRawData from the disk PE header. */\n        if((uint64_t)rva+sz>limit)return PPC_PE_FORMAT;
        uint64_t start=(uint64_t)base+rva;
        if((flags&0x20000000u)&&address>=start&&(uint64_t)address+4<=start+sz){
            raw=(uint32_t)((uint64_t)address-base);
            remaining=(uint32_t)(start+sz-address);
            break;
        }
    }
    if(!remaining)return PPC_PE_ADDRESS;
    uint32_t regs[32]={0};regs[3]=seed;
    for(unsigned i=0;i<MAX_INSNS&&remaining>=4;i++,raw+=4,remaining-=4){
        if(!read_at(pe,limit,raw,word,4))return PPC_PE_IO;
        uint32_t insn=be32(word);
        if(insn==0x4E800020u){*result=regs[3];return PPC_PE_OK;}
        uint32_t opcode=insn>>26, rd=(insn>>21)&31,ra=(insn>>16)&31,imm=insn&65535;
        int32_t signed_imm=(int16_t)imm;
        if(opcode==14)regs[rd]=(ra?regs[ra]:0u)+(uint32_t)signed_imm;
        else if(opcode==15)regs[rd]=(ra?regs[ra]:0u)+((uint32_t)signed_imm<<16);
        else if(opcode==24)regs[ra]=regs[rd]|imm;
        else if(opcode==26)regs[ra]=regs[rd]^imm;
        else return PPC_PE_UNSUPPORTED;
    }
    return PPC_PE_NO_RETURN;
}
