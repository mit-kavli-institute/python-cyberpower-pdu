# Core dependencies
import asyncio

# Project dependencies
from cyberpower_pdu import CyberPowerPDU

IP_ADDRESS = "192.168.1.132"


async def main() -> None:
    pdu = CyberPowerPDU(ip_address=IP_ADDRESS, simulate=False)

    try:
        await pdu.initialize()

        outlet_states = await pdu.get_all_outlet_states()

        for index, outlet_state in enumerate(outlet_states):
            print(f"Outlet {index + 1} state: {outlet_state}")

    finally:
        await pdu.close()


if __name__ == "__main__":
    asyncio.run(main())
