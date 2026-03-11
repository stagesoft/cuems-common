# =============================================================================
# CUEMS Multi-Package Build System
# =============================================================================
#
# Usage:
#   make                       Build all packages in dependency order
#   make cuems-engine          Build a single package
#   make OUTPUT=/path/to/dir   Override output dir (default: rc1_packages/)
#   make BUMP=1                Increment Debian revision (dch -i) before building
#   make VERSION=0.1.1-1       Set specific version (dch -v) before building
#   make cuems-engine BUMP=1   Bump + build a single package
#   make list                  Show all available package targets
#   make clean                 Remove build worktrees and debuild artifacts
#
# How it works:
#   Packages on a dev branch (main, rc_1, etc.) are built via a temporary
#   git worktree that checks out the debian/bookworm branch. Packages already
#   on debian/bookworm are built in-place. All resulting .deb files are moved
#   to OUTPUT after each successful build.
# =============================================================================

WORKSPACE   := $(CURDIR)
OUTPUT      ?= $(WORKSPACE)/rc1_packages
WTREE_BASE  := /tmp/cuems-build
BUMP        ?= 0
VERSION     ?=
CLEAN       ?= 0

DEBFULLNAME ?= Ion Reguera
DEBEMAIL    ?= ion@stagelab.coop
export DEBFULLNAME DEBEMAIL

# -----------------------------------------------------------------------------
# Package → source directory mappings (relative to WORKSPACE)
# -----------------------------------------------------------------------------

cuems-utils_SRC          := cuems-utils
cuems-common_SRC         := cuems-common
cuems-editor_SRC         := cuems-editor
cuems-engine_SRC         := python/cuems-engine
cuems-nodeconf_SRC       := cuems-nodeconf
cuems-audioplayer_SRC    := cuems-audioplayer
cuems-videocomposer_SRC  := cuems-videocomposer
cuems-midi-connector_SRC := cuems-midi-connector
cuems-dmxplayer_SRC      := cuems-dmxplayer
cuems-jack-volume_SRC    := jack-osc/jack-volume
libmtcmaster_SRC         := libmtcmaster
liboscpack_SRC           := oscpack
python3-pyossia_SRC      := libossia/src/ossia-python
rtpmidid_SRC             := rtpmidid
jackd2_SRC               := jackd2
xjadeo_SRC               := xjadeo

# Packages needing a worktree (currently NOT on debian/bookworm)
WORKTREE_PKGS := \
	cuems-utils \
	cuems-common \
	cuems-editor \
	cuems-engine \
	cuems-nodeconf \
	cuems-audioplayer \
	cuems-videocomposer

# Packages already on debian/bookworm (built in-place)
INPLACE_PKGS := \
	cuems-midi-connector \
	cuems-dmxplayer \
	cuems-jack-volume \
	libmtcmaster \
	liboscpack \
	python3-pyossia

# Build order for 'make all': lower-level libs first, then CUEMS packages
# liboscpack excluded from default build (use 'make liboscpack' to build manually)
ALL_PKGS := \
	libmtcmaster \
	python3-pyossia \
	cuems-utils \
	cuems-editor \
	cuems-engine \
	cuems-nodeconf \
	cuems-midi-connector \
	cuems-audioplayer \
	cuems-dmxplayer \
	cuems-videocomposer \
	cuems-jack-volume

# Manual-only targets (excluded from 'make all')
MANUAL_PKGS := liboscpack rtpmidid jackd2 xjadeo cuems-common

.PHONY: all clean list $(ALL_PKGS) $(MANUAL_PKGS)

all: $(ALL_PKGS)

# -----------------------------------------------------------------------------
# Core build function
#   $(1)  make target name (package name)
#   $(2)  source directory relative to WORKSPACE
#   $(3)  "worktree" or "inplace"
# -----------------------------------------------------------------------------
define DO_BUILD
	@set -e; \
	\
	printf '\n\033[1;34m══════════════════════════════════════════════\033[0m\n'; \
	printf '\033[1;34m  Building: $(1)\033[0m\n'; \
	printf '\033[1;34m══════════════════════════════════════════════\033[0m\n'; \
	\
	PKG_SRC="$(WORKSPACE)/$(2)"; \
	CURRENT_BRANCH=$$(git -C "$$PKG_SRC" branch --show-current 2>/dev/null); \
	\
	if [ "$$CURRENT_BRANCH" != "debian/bookworm" ]; then \
		BUILD_DIR="$(WTREE_BASE)/$(1)"; \
		OUT_DIR="$(WTREE_BASE)"; \
		mkdir -p "$(WTREE_BASE)"; \
		printf 'Creating worktree at %s ...\n' "$$BUILD_DIR"; \
		git -C "$$PKG_SRC" worktree remove --force "$$BUILD_DIR" 2>/dev/null || true; \
		git -C "$$PKG_SRC" worktree add "$$BUILD_DIR" debian/bookworm; \
		if [ -f "$$BUILD_DIR/.gitmodules" ]; then \
			printf 'Copying submodules from main working tree...\n'; \
			grep 'path = ' "$$BUILD_DIR/.gitmodules" | sed 's/.*path = //;s/[[:space:]]*//' | \
			while IFS= read -r subpath; do \
				src_sub="$$PKG_SRC/$$subpath"; \
				dst_sub="$$BUILD_DIR/$$subpath"; \
				if [ -d "$$src_sub" ]; then \
					printf '  %s\n' "$$subpath"; \
					mkdir -p "$$dst_sub"; \
					cp -a "$$src_sub/." "$$dst_sub/"; \
				fi; \
			done; \
		fi; \
		USE_WORKTREE=1; \
	else \
		printf 'Already on debian/bookworm, building in-place.\n'; \
		BUILD_DIR="$$PKG_SRC"; \
		OUT_DIR="$(WORKSPACE)"; \
		USE_WORKTREE=0; \
	fi; \
	\
	if [ -n "$(VERSION)" ]; then \
		printf 'Setting version to $(VERSION) ...\n'; \
		cd "$$BUILD_DIR" && dch -v "$(VERSION)" "Development build"; \
		if ! git -C "$$BUILD_DIR" diff --quiet debian/changelog 2>/dev/null; then \
			git -C "$$BUILD_DIR" add debian/changelog; \
			git -C "$$BUILD_DIR" commit -m "Bump version to $(VERSION)"; \
		fi; \
	elif [ "$(BUMP)" = "1" ]; then \
		printf 'Incrementing Debian revision ...\n'; \
		cd "$$BUILD_DIR" && dch -i "Development build"; \
		git -C "$$BUILD_DIR" add debian/changelog; \
		git -C "$$BUILD_DIR" commit -m "Bump Debian revision"; \
	fi; \
	\
	mkdir -p "$(WTREE_BASE)"; \
	MARK="$(WTREE_BASE)/.mark-$(1)"; \
	touch "$$MARK"; \
	\
	rm -f "$$BUILD_DIR/debian/files"; \
	if [ "$(CLEAN)" = "1" ]; then \
		DEBUILD_FLAGS="-b -uc -us"; \
	else \
		DEBUILD_FLAGS="-b -uc -us -nc"; \
	fi; \
	printf 'Running debuild in %s (flags: %s) ...\n' "$$BUILD_DIR" "$$DEBUILD_FLAGS"; \
	if ! (cd "$$BUILD_DIR" && debuild $$DEBUILD_FLAGS); then \
		printf '\033[1;31m  ✗ debuild failed for $(1)\033[0m\n'; \
		rm -f "$$MARK"; \
		if [ "$$USE_WORKTREE" = "1" ]; then \
			git -C "$$PKG_SRC" worktree remove --force "$$BUILD_DIR" 2>/dev/null || true; \
		fi; \
		exit 1; \
	fi; \
	\
	mkdir -p "$(OUTPUT)"; \
	find "$$OUT_DIR" -maxdepth 1 \
		-name "*.deb" ! -name "*-dbgsym_*" \
		-newer "$$MARK" -exec mv -v {} "$(OUTPUT)/" \;; \
	rm -f "$$MARK"; \
	\
	if [ "$$USE_WORKTREE" = "1" ]; then \
		git -C "$$PKG_SRC" worktree remove --force "$$BUILD_DIR" 2>/dev/null || true; \
	fi; \
	\
	printf '\033[1;32m  ✓ $(1) built successfully → $(OUTPUT)/\033[0m\n'
endef

# -----------------------------------------------------------------------------
# Worktree package targets
# -----------------------------------------------------------------------------

cuems-utils:
	$(call DO_BUILD,cuems-utils,$(cuems-utils_SRC),worktree)

cuems-common:
	$(call DO_BUILD,cuems-common,$(cuems-common_SRC),worktree)

cuems-editor:
	$(call DO_BUILD,cuems-editor,$(cuems-editor_SRC),worktree)

cuems-engine:
	$(call DO_BUILD,cuems-engine,$(cuems-engine_SRC),worktree)

cuems-nodeconf:
	$(call DO_BUILD,cuems-nodeconf,$(cuems-nodeconf_SRC),worktree)

cuems-audioplayer:
	$(call DO_BUILD,cuems-audioplayer,$(cuems-audioplayer_SRC),worktree)

cuems-videocomposer:
	$(call DO_BUILD,cuems-videocomposer,$(cuems-videocomposer_SRC),worktree)

# -----------------------------------------------------------------------------
# In-place package targets (already on debian/bookworm)
# -----------------------------------------------------------------------------

cuems-midi-connector:
	$(call DO_BUILD,cuems-midi-connector,$(cuems-midi-connector_SRC),inplace)

cuems-dmxplayer:
	$(call DO_BUILD,cuems-dmxplayer,$(cuems-dmxplayer_SRC),inplace)

cuems-jack-volume:
	$(call DO_BUILD,cuems-jack-volume,$(cuems-jack-volume_SRC),inplace)

libmtcmaster:
	$(call DO_BUILD,libmtcmaster,$(libmtcmaster_SRC),inplace)

liboscpack:
	$(call DO_BUILD,liboscpack,$(liboscpack_SRC),inplace)

python3-pyossia:
	$(call DO_BUILD,python3-pyossia,$(python3-pyossia_SRC),inplace)

rtpmidid:
	$(call DO_BUILD,rtpmidid,$(rtpmidid_SRC),inplace)

jackd2:
	$(call DO_BUILD,jackd2,$(jackd2_SRC),inplace)

xjadeo:
	$(call DO_BUILD,xjadeo,$(xjadeo_SRC),inplace)

# -----------------------------------------------------------------------------
# Utility targets
# -----------------------------------------------------------------------------

list:
	@printf '\nCUEMS package targets:\n\n'
	@printf '  Worktree builds (debian/bookworm checked out to /tmp/cuems-build/):\n'
	@printf '    %-30s %s\n' "cuems-utils"          "cuems-utils/"
	@printf '    %-30s %s\n' "cuems-common"         "cuems-common/"
	@printf '    %-30s %s\n' "cuems-editor"         "cuems-editor/"
	@printf '    %-30s %s\n' "cuems-engine"         "python/cuems-engine/"
	@printf '    %-30s %s\n' "cuems-nodeconf"       "cuems-nodeconf/"
	@printf '    %-30s %s\n' "cuems-audioplayer"    "cuems-audioplayer/"
	@printf '    %-30s %s\n' "cuems-videocomposer"  "cuems-videocomposer/"
	@printf '\n  In-place builds (already on debian/bookworm):\n'
	@printf '    %-30s %s\n' "cuems-midi-connector" "cuems-midi-connector/"
	@printf '    %-30s %s\n' "cuems-dmxplayer"      "cuems-dmxplayer/"
	@printf '    %-30s %s\n' "cuems-jack-volume"    "jack-osc/jack-volume/"
	@printf '    %-30s %s\n' "libmtcmaster"         "libmtcmaster/"
	@printf '    %-30s %s\n' "liboscpack"           "oscpack/"
	@printf '    %-30s %s\n' "python3-pyossia"      "libossia/src/ossia-python/"
	@printf '\n  Manually buildable (not in "make all"):\n'
	@printf '    %-30s %s\n' "cuems-common" "cuems-common/"
	@printf '    %-30s %s\n' "liboscpack"   "oscpack/"
	@printf '    %-30s %s\n' "rtpmidid"     "rtpmidid/"
	@printf '    %-30s %s\n' "jackd2"       "jackd2/"
	@printf '    %-30s %s\n' "xjadeo"       "xjadeo/  (deprecated)"
	@printf '\nBuild order for "make all":\n'
	@printf '  libmtcmaster → python3-pyossia\n'
	@printf '  → cuems-utils → cuems-editor → cuems-engine\n'
	@printf '  → cuems-nodeconf → cuems-midi-connector → cuems-audioplayer\n'
	@printf '  → cuems-dmxplayer → cuems-videocomposer → cuems-jack-volume\n'
	@printf '\nVariables:\n'
	@printf '  OUTPUT  = %s\n'  "$(OUTPUT)"
	@printf '  BUMP    = %s   (set to 1 to increment Debian revision via dch -i)\n' "$(BUMP)"
	@printf '  VERSION = %s   (set to e.g. 0.1.1-1 to pin a specific version)\n' "$(VERSION)"
	@printf '  CLEAN   = %s   (set to 1 for a full clean build, drops -nc flag)\n' "$(CLEAN)"
	@printf '\nExamples:\n'
	@printf '  make                          # build everything\n'
	@printf '  make cuems-engine             # build one package\n'
	@printf '  make cuems-engine BUMP=1      # bump revision then build\n'
	@printf '  make cuems-engine VERSION=0.1.0rc3-1   # set version then build\n'
	@printf '  make OUTPUT=./dist            # send .deb files to ./dist/\n'
	@printf '  make cuems-nodeconf CLEAN=1   # clean build (no -nc, re-runs pip/virtualenv)\n\n'

clean:
	@printf '\nRemoving git worktrees...\n'
	@for pkg in $(WORKTREE_PKGS); do \
		wt="$(WTREE_BASE)/$$pkg"; \
		if [ -d "$$wt" ]; then \
			printf '  Removing: %s\n' "$$wt"; \
			rm -rf "$$wt"; \
		fi; \
	done
	@printf 'Pruning stale worktree references from git repos...\n'
	@for src in \
		$(cuems-utils_SRC) \
		$(cuems-common_SRC) \
		$(cuems-editor_SRC) \
		$(cuems-engine_SRC) \
		$(cuems-nodeconf_SRC) \
		$(cuems-audioplayer_SRC) \
		$(cuems-videocomposer_SRC); do \
		git -C "$(WORKSPACE)/$$src" worktree prune 2>/dev/null || true; \
	done
	@printf 'Removing stale debian/files from all packages...\n'
	@find "$(WORKSPACE)" -maxdepth 3 -name "files" -path "*/debian/files" \
		-delete -print | sed 's|^|  Removed: |'
	@printf 'Removing debuild artifacts from workspace root...\n'
	@find "$(WORKSPACE)" -maxdepth 1 \
		\( -name "*.build" -o -name "*.buildinfo" -o -name "*.changes" -o -name "*.dsc" \
		   -o -name "*-dbgsym_*.deb" \) \
		-delete -print | sed 's|^|  Removed: |'
	@rm -f "$(WTREE_BASE)"/.mark-*
	@printf 'Done.\n\n'
