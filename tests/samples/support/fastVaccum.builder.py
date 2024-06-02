# type: ignore

"""
This is the builder code that was used to generate the same ioc.subst as
the fastVacuum.ioc.ibek.yaml does. The snippet is included here for easy
comparison with the equivalent in fastVacuum.support.ibek.yaml.
"""


class _dlsPLC_fastVacuumChannel(AutoSubstitution):
    TemplateFile = "dlsPLC_fastVacuumChannel.template"


class _dlsPLC_fastVacuumMaster(AutoSubstitution):
    TemplateFile = "dlsPLC_fastVacuumMaster.template"


class _dlsPLC_fastVacuumLink(AutoSubstitution):
    TemplateFile = "dlsPLC_fastVacuumLink.template"


class fastVacuumMaster(Device):
    Dependencies = (dlsPLCLib,)

    def __init__(self, name, dom, fins_port, eip_port):
        self.__super.__init__()
        self.name = name
        self.device = dom + "-VA-VFAST-01"
        self.fins_port = fins_port
        self.eip_port = eip_port
        self.waveform_nelm = 500
        self.combined_nelm = self.waveform_nelm * 6
        self.noOfGauges = 0
        self.gauges = list()

        _dlsPLC_fastVacuumMaster(device=self.device, eip_port=self.eip_port)

    # Method called be each gauge to add them to the processing chain
    def registerGauge(self, id):
        self.noOfGauges += 1
        self.gauges.append(id)
        mask = 0
        # Determine the paramters for the FAN records
        gaugePV = self.device + ":GAUGE" + id + "_0"
        fanNo = int(self.noOfGauges / 7) + 1
        lnk_no = ((self.noOfGauges - 1) % 6) + 1

        # Determine the mask
        for gauge in self.gauges:
            mask += pow(2, int(gauge))

        _dlsPLC_fastVacuumLink(
            device=self.device,
            fan="%02d" % (fanNo),
            lnk_no=lnk_no,
            lnk=gaugePV,
            mask=mask,
        )

    ArgInfo = makeArgInfo(
        __init__,
        name=Simple("Gui tag", str),
        dom=Simple("Domain, eg, FE06I", str),
        fins_port=Ident("FINS port", AsynIP),
        eip_port=Simple("EtherIP port", str),
    )


class fastVacuumChannel(
    Device,
):
    def __init__(self, name, master, img, id, em=0):
        self.__super.__init__()
        self.name = name
        self.device = master.device
        self.fins_port = master.fins_port
        self.eip_port = master.eip_port
        self.id = id
        self.img = img
        self.em = em
        self.waveform_nelm = master.waveform_nelm
        self.combined_nelm = master.combined_nelm
        self.addr_offset = (int(id) - 1) * 3000
        self.tagidx = int(self.id)
        self.rwList = list()
        self.rList = list()

        master.registerGauge(id)

        # List of addresses for the 6 waveform records based on the ID and chunk size
        wave_addr = [self.addr_offset + (self.waveform_nelm * a) for a in range(6)]

        _dlsPLC_fastVacuumChannel(
            device=self.device,
            img=self.img,
            fins_port=self.fins_port,
            eip_port=self.eip_port,
            tagidx=str(int(self.id)),
            id=self.id,
            em=self.em,
            waveform_nelm=self.waveform_nelm,
            combined_nelm=self.combined_nelm,
            wave0_addr=wave_addr[0],
            wave1_addr=wave_addr[1],
            wave2_addr=wave_addr[2],
            wave3_addr=wave_addr[3],
            wave4_addr=wave_addr[4],
            wave5_addr=wave_addr[5],
        )

    ArgInfo = makeArgInfo(
        __init__,
        name=Simple("Gui tag", str),
        master=Ident("Master", fastVacuumMaster),
        img=Simple("Base IMG PV", str),
        id=Choice("FV PLC gauge number", ["%02d" % (a) for a in range(1, 11)]),
        em=Choice("EM block to use", range(3)),
    )
