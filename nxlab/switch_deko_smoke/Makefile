# Standalone Switch deko3d smoke NRO. Does not read/distribute the GoldenEye ROM.
.SUFFIXES:
ifeq ($(strip $(DEVKITPRO)),)
$(error Set DEVKITPRO to your devkitPro directory)
endif
TOPDIR ?= $(CURDIR)
include $(DEVKITPRO)/libnx/switch_rules

TARGET := goldeneye-deko-smoke
BUILD := build
SOURCES := source
ROMFS := romfs
APP_TITLE := GoldenEye NX deko3d (diagnostic)
APP_AUTHOR := lab-NX
APP_VERSION := 0.1.0
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS := -g -Wall -Wextra -Werror -O2 -ffunction-sections $(ARCH) $(DEFINES)
CFLAGS += $(INCLUDE) -D__SWITCH__
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
export OFILES := main.o
export INCLUDE := $(foreach dir,$(LIBDIRS),-I$(dir)/include) -I$(CURDIR)/$(BUILD)
export LIBPATHS := $(foreach dir,$(LIBDIRS),-L$(dir)/lib)
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
-include $(OFILES:.o=.d)
endif
