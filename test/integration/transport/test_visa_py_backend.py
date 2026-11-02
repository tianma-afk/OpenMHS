import os

import pytest

from src.server.discover.discover import Discovery
from src.transport.visa.resource_discovery import IPv4SubnetVisaResourceDiscovery
from src.transport.visa.visa import VisaTransportModule


pytestmark = pytest.mark.skipif(
    os.getenv("MHS_REAL_VISA") != "1",
    reason="set MHS_REAL_VISA=1 to run against a real PyVISA-py backend",
)


pyvisa = pytest.importorskip("pyvisa")


class TestPyVisaPyBackend:
    def test_configured_resource_uses_pyvisa_py(self):
        resource_name = os.getenv("MHS_VISA_RESOURCE")
        manager = pyvisa.ResourceManager("@py")
        manager.list_resources()
        assert type(manager.visalib).__module__.startswith("pyvisa_py")

        if not resource_name:
            return

        result = Discovery(
            [
                VisaTransportModule(
                    resources=(resource_name,),
                    auto_discover_local_networks=False,
                )
            ]
        ).discover()

        assert len(result.endpoints) == 1
        assert result.endpoints[0].resource == resource_name
        assert result.errors == ()
        assert isinstance(manager.list_resources(), tuple)

    def test_subnet_discovery_finds_configured_instrument(self):
        resource_name = os.getenv("MHS_VISA_RESOURCE")
        subnet = os.getenv("MHS_VISA_SUBNET")
        if not resource_name or not subnet:
            pytest.skip("set MHS_VISA_RESOURCE and MHS_VISA_SUBNET for LAN discovery")

        result = Discovery(
            [
                VisaTransportModule(
                    resource_discoveries=(
                        IPv4SubnetVisaResourceDiscovery((subnet,)),
                    )
                )
            ]
        ).discover()

        assert resource_name in {
            endpoint.resource for endpoint in result.endpoints
        }
        assert result.errors == ()
