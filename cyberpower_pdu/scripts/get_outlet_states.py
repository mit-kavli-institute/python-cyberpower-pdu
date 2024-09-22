# Core dependencies
import asyncio
import time

# Project dependencies
from cyberpower_pdu import CyberPowerPDU

IP_ADDRESS = "192.168.1.132"


async def main() -> None:
    pdu = CyberPowerPDU(ip_address=IP_ADDRESS, simulated=False)

    try:
        await pdu.initialize()

        start_time = time.monotonic()

        for outlet in range(1, pdu.number_of_outlets + 1):
            print(f"Outlet {outlet} state: {await pdu.get_outlet_state(outlet)}")

    finally:
        print(f"Script execution time: {time.monotonic() - start_time:.3f} seconds")

        await pdu.close()


if __name__ == "__main__":
    asyncio.run(main())
