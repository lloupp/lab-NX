#include "xex_probe.h"
#include <stddef.h>
#include <string.h>
#define XEX_MAX_FILE (256u*1024u*1024u)
#define XEX_MAX_HEADERS 1024u
#define CASTLE_TITLE_ID 0x584108b7u
static uint16_t be16(const unsigned char *p) { return (uint16_t)(((uint16_t)p[0]<<8)|p[1]); }
static uint32_t be32(const unsigned char *p) {return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static int read_at(FILE *f,long limit,uint32_t pos,void *out,size_t size) {
    if((uint64_t)pos+size>(uint64_t)limit || fseek(f,(long)pos,SEEK_SET))return 0;
    return fread(out,1,size,f)==size;
}
XexProbeStatus xex_probe_file(FILE *f,XexProbeInfo *out) {
    if(!f||!out)return XEX_PROBE_IO;
    memset(out,0,sizeof(*out));
    if(fseek(f,0,SEEK_END))return XEX_PROBE_IO;
    long length=ftell(f);
    if(length<24||(uint64_t)length>XEX_MAX_FILE)return XEX_PROBE_FORMAT;
    unsigned char header[24];
    if(!read_at(f,length,0,header,24))return XEX_PROBE_IO;
    if(memcmp(header,"XEX2",4))return XEX_PROBE_FORMAT;
    uint32_t image_offset=be32(header+8), security=be32(header+16),count=be32(header+20);
    if(count>XEX_MAX_HEADERS||image_offset>(uint32_t)length||image_offset<24u+count*8u||
       security<24u+count*8u||(uint64_t)security+0x184u>image_offset)return XEX_PROBE_FORMAT;
    uint32_t fmt=0,exec=0;
    int has_fmt=0,has_exec=0,has_entry=0,has_base=0;
    out->optional_headers=count;
    for(uint32_t i=0;i<count;i++){
        unsigned char entry[8];
        if(!read_at(f,length,24+8*i,entry,8))return XEX_PROBE_IO;
        uint32_t key=be32(entry),val=be32(entry+4);
        if(key==0x3ff){if(has_fmt++)return XEX_PROBE_FORMAT;fmt=val;}
        else if(key==0x40006){if(has_exec++)return XEX_PROBE_FORMAT;exec=val;}
        else if(key==0x10100){if(has_entry++)return XEX_PROBE_FORMAT;out->entry_point=val;}
        else if(key==0x10201){if(has_base++)return XEX_PROBE_FORMAT;out->image_base=val;}
    }
    if(!has_fmt||!has_exec||!has_entry||!has_base)return XEX_PROBE_FORMAT;
    unsigned char ff[8],ex[24],sec[8];
    if(fmt<24u+8*count||(uint64_t)fmt+8u>image_offset||
       exec<24u+8*count||(uint64_t)exec+24u>image_offset||
       !read_at(f,length,fmt,ff,8)||!read_at(f,length,exec,ex,24)||
       !read_at(f,length,security,sec,8))return XEX_PROBE_FORMAT;
    if(be32(ff)<8||(uint64_t)fmt+be32(ff)>image_offset||
       be32(sec)<0x184u||(uint64_t)security+be32(sec)>image_offset)return XEX_PROBE_FORMAT;
    out->title_id=be32(ex+12);
    out->encryption=be16(ff+4);
    out->compression=be16(ff+6);
    out->image_size=be32(sec+4);
    if(!out->image_size||out->image_size>XEX_MAX_FILE||
       out->encryption>1||out->compression>3)return XEX_PROBE_FORMAT;
    return out->title_id==CASTLE_TITLE_ID?XEX_PROBE_OK:XEX_PROBE_NOT_CASTLE;
}
