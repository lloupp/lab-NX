.SUFFIXES:
ifeq ($(strip $(DEVKITPRO)),)
$(error Set DEVKITPRO)
endif
include $(DEVKITPRO)/libnx/switch_rules
TARGET := goldeneye-engine-vm-probe
BUILD := build
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS := -g -O2 -Wall -Wextra -Werror $(ARCH) $(INCLUDE) -D__SWITCH__
LDFLAGS = -specs=$(DEVKITPRO)/libnx/switch.specs -g $(ARCH) -Wl,-Map,$(notdir $*.map)
LIBS := -lnx
APP_TITLE := GoldenEye engine memory probe
APP_AUTHOR := lab-NX
APP_VERSION := 0.2.0
ifneq ($(BUILD),$(notdir $(CURDIR)))
export OUTPUT := $(CURDIR)/$(TARGET)
export VPATH := $(CURDIR)/source:$(CURDIR)/../switch_engine_runtime
export INCLUDE := -I$(CURDIR)/../switch_engine_runtime -I$(LIBNX)/include
export LIBPATHS := -L$(LIBNX)/lib
export LD := $(CC)
export OFILES := main.o ge_switch_vm.o
export DEPSDIR := $(CURDIR)/$(BUILD)
export NROFLAGS := --nacp=$(CURDIR)/$(TARGET).nacp
.PHONY: all clean
all:
	@mkdir -p $(BUILD)
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile
clean:
	rm -rf $(BUILD) $(TARGET).elf $(TARGET).nro $(TARGET).nacp
else
all: $(OUTPUT).nro
$(OUTPUT).nro: $(OUTPUT).elf $(OUTPUT).nacp
$(OUTPUT).elf: $(OFILES)
-include $(OFILES:.o=.d)
endif
