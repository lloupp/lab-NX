# Standalone Switch deko3d smoke NRO. Does not read/distribute the GoldenEye ROM.
.SUFFIXES:
ifeq ($(strip $(DEVKITPRO)),)
$(error Set DEVKITPRO to your devkitPro directory)
endif
TOPDIR ?= $(CURDIR)
include $(DEVKITPRO)/libnx/switch_rules

TARGET := goldeneye-deko-smoke
BUILD := build
SOURCES := source ../native
ifneq ($(strip $(GE_UPSTREAM)),)
SOURCES += ../engine_adapter
ADAPTER_FLAGS := -DGE_GFX_ADAPTER
endif
ROMFS := romfs
APP_TITLE := GoldenEye NX deko3d (diagnostic)
APP_AUTHOR := lab-NX
APP_VERSION := 0.1.0
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS := -g -Wall -Wextra -Werror -O2 -ffunction-sections $(ARCH) $(DEFINES)
CFLAGS += $(INCLUDE) -D__SWITCH__ $(ADAPTER_FLAGS)
ifneq ($(strip $(GE_QUEUE_CMD_BYTES)),)
CFLAGS += -DGE_QUEUE_CMD_BYTES=$(GE_QUEUE_CMD_BYTES)
endif
CXXFLAGS := $(CFLAGS) -std=gnu++20 -fno-exceptions -fno-rtti
ASFLAGS := -g $(ARCH)
LDFLAGS = -specs=$(DEVKITPRO)/libnx/switch.specs -g $(ARCH) -Wl,-Map,$(notdir $*.map)
LIBS := -ldeko3d -lnx
LIBDIRS := $(PORTLIBS) $(LIBNX)
SHADER_FOLDER := $(ROMFS)/shaders
SHADER_OUTPUTS := $(SHADER_FOLDER)/triangle_vsh.dksh $(SHADER_FOLDER)/color_fsh.dksh

ifneq ($(BUILD),$(notdir $(CURDIR)))
export OUTPUT := $(CURDIR)/$(TARGET)
export TOPDIR := $(CURDIR)
export VPATH := $(foreach dir,$(SOURCES),$(CURDIR)/$(dir))
export DEPSDIR := $(CURDIR)/$(BUILD)
export LD := $(CC)
export OFILES := main.o goldeneye_fast3d_bridge.o goldeneye_n64_memory.o
export INCLUDE := -I$(CURDIR)/../native $(foreach dir,$(LIBDIRS),-I$(dir)/include) -I$(CURDIR)/$(BUILD)
ifneq ($(strip $(GE_UPSTREAM)),)
export LD := $(CXX)
export OFILES += goldeneye_gfx_subset.o
export INCLUDE += -I$(CURDIR)/../engine_adapter -I$(GE_UPSTREAM)/port/fast3d
endif
export LIBPATHS := $(foreach dir,$(LIBDIRS),-L$(dir)/lib)
ifneq ($(strip $(GE_DEKO_LIBDIR)),)
export LIBPATHS := -L$(GE_DEKO_LIBDIR) $(LIBPATHS)
endif
export NROFLAGS := --nacp=$(CURDIR)/$(TARGET).nacp --romfsdir=$(CURDIR)/$(ROMFS)
export ROMFS_DEPS := $(addprefix $(CURDIR)/,$(SHADER_OUTPUTS))
.PHONY: all clean
all: $(SHADER_OUTPUTS) | $(BUILD)
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile
$(BUILD):
	@mkdir -p $@
$(SHADER_FOLDER):
	@mkdir -p $@
$(SHADER_FOLDER)/%_vsh.dksh: source/%_vsh.glsl | $(SHADER_FOLDER)
	uam -s vert -o $@ $<
$(SHADER_FOLDER)/%_fsh.dksh: source/%_fsh.glsl | $(SHADER_FOLDER)
	uam -s frag -o $@ $<
clean:
	rm -rf $(BUILD) $(SHADER_FOLDER) $(TARGET).elf $(TARGET).nro $(TARGET).nacp
else
.PHONY: all
all: $(OUTPUT).nro
$(OUTPUT).nro: $(OUTPUT).elf $(OUTPUT).nacp $(ROMFS_DEPS)
$(OUTPUT).elf: $(OFILES)
ifneq ($(strip $(GE_DEKO_LIBDIR)),)
$(OUTPUT).elf: $(GE_DEKO_LIBDIR)/libdeko3d.a
endif
-include $(OFILES:.o=.d)
endif
