# Core dependencies
import asyncio
import time

# Project dependencies
from cyberpower_pdu import CyberPowerPDU, OutletCommand


# Script settings
IP_ADDRESS = "192.168.1.132"
OUTLET = 7
COMMAND = OutletCommand.IMMEDIATE_OFF


async def main() -> None:
    pdu = CyberPowerPDU(ip_address=IP_ADDRESS, simulate=False)

    try:
        await pdu.initialize()

        start_time = time.monotonic()

        print(f"Outlet {OUTLET} state: {await pdu.get_outlet_state(OUTLET)}")

        print(f"Setting outlet {OUTLET} to {COMMAND}")
        await pdu.send_outlet_command(OUTLET, COMMAND)

        print("Waiting for 3 seconds ...")
        await asyncio.sleep(3)

        print(f"Outlet {OUTLET} state: {await pdu.get_outlet_state(OUTLET)}")

    finally:
        print(f"Script execution time: {time.monotonic() - start_time:.3f} seconds")

        await pdu.close()


if __name__ == "__main__":
    asyncio.run(main())
