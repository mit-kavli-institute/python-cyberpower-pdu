# Core dependencies
import asyncio

# Project dependencies
from cyberpower_pdu import CyberPowerPDU

IP_ADDRESS = "192.168.1.132"
OUTLET = 7


async def main() -> None:
    pdu = CyberPowerPDU(ip_address=IP_ADDRESS, simulated=False)

    try:
        await pdu.initialize()
        print(f"Outlet {OUTLET} state: {await pdu.get_outlet_state(OUTLET)}")

    finally:
        await pdu.close()


if __name__ == "__main__":
    asyncio.run(main())
