# Switch stage-0 diagnostic: NOT the playable Castle Crashers game.
ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is not set)
endif
include $(DEVKITPRO)/libnx/switch_rules
TARGET := castle_nx_bootstrap
CC := $(DEVKITPRO)/devkitA64/bin/aarch64-none-elf-gcc
ELF2NRO := $(DEVKITPRO)/tools/bin/elf2nro
LIBNX := $(DEVKITPRO)/libnx
CFLAGS := -O2 -g -Wall -Wextra -Werror -ffunction-sections -fdata-sections -march=armv8-a+crc+crypto -mtune=cortex-a57 -fPIE -Iinclude -I$(LIBNX)/include
LDFLAGS := -specs=$(LIBNX)/switch.specs -Wl,--gc-sections -L$(LIBNX)/lib
LDLIBS := -lnx -lm
OBJS := build/main.o build/xex_probe.o build/ppc_pe.o
.PHONY: all clean
all: $(TARGET).nro
build:
	mkdir -p build
build/main.o: source/main.c include/xex_probe.h | build
	$(CC) $(CFLAGS) -c $< -o $@
build/xex_probe.o: source/xex_probe.c include/xex_probe.h | build
	$(CC) $(CFLAGS) -c $< -o $@
build/ppc_pe.o: source/ppc_pe.c include/ppc_pe.h | build
	$(CC) $(CFLAGS) -c $< -o $@
$(TARGET).elf: $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) $(LDFLAGS) $(LDLIBS) -o $@
$(TARGET).nro: $(TARGET).elf
	$(ELF2NRO) $< $@
clean:
	rm -rf build $(TARGET).elf $(TARGET).nro
