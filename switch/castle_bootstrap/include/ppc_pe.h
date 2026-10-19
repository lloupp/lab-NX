#ifndef LABNX_PPC_PE_H
#define LABNX_PPC_PE_H
#include <stdio.h>
#include <stdint.h>
typedef enum {PPC_PE_OK=0,PPC_PE_IO=1,PPC_PE_FORMAT=2,PPC_PE_ADDRESS=3,PPC_PE_UNSUPPORTED=4,PPC_PE_NO_RETURN=5} PpcPeStatus;
/* Runs a restricted PowerPC snippet loaded from a private decoded Xbox PE.
   Not full game execution or a proof of any function boundary. */
PpcPeStatus ppc_pe_run_leaf(FILE *pe,uint32_t address,uint32_t seed,uint32_t *result);
#endif
