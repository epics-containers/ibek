TOPTARGETS := all clean

include configure/MODULES

$(TOPTARGETS): $(MODULES)
$(MODULES):
	$(MAKE) -j $(nproc) -C $@ $(MAKECMDGOALS)

.PHONY: $(TOPTARGETS) $(MODULES)
