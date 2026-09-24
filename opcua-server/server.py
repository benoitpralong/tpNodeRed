import asyncio
import logging
import os

from asyncua import Server, ua


NAMESPACE_INDEX = 1
NAMESPACE_URI = "http://demo.local/opcua"
ENDPOINT = os.getenv("OPCUA_ENDPOINT", "opc.tcp://localhost:53880/UA/MinimalServer")
LOGGER = logging.getLogger(__name__)


async def log_tag_changes(tag_nodes):
    previous_values = {
        name: await node.read_value() for name, node in tag_nodes.items()
    }

    while True:
        await asyncio.sleep(1)

        for name, node in tag_nodes.items():
            value = await node.read_value()
            if value != previous_values[name]:
                LOGGER.info("Tag %s changed from %s to %s", name, previous_values[name], value)
                previous_values[name] = value

async def main():
    server = Server()
    await server.init()

    server.set_endpoint(ENDPOINT)

    await server.register_namespace(NAMESPACE_URI)

    objects = server.nodes.objects
    demo_tp = await objects.add_object(
        ua.NodeId("DemoTP", NAMESPACE_INDEX),
        ua.QualifiedName("DemoTP", NAMESPACE_INDEX),
    )

    tags = (
        ("CAB", ua.VariantType.Int16),
        ("Direction", ua.VariantType.Int16),
        ("Speed", ua.VariantType.Int16),
    )

    tag_nodes = {}
    for name, variant_type in tags:
        tag_nodes[name] = await demo_tp.add_variable(
            ua.NodeId(name, NAMESPACE_INDEX),
            ua.QualifiedName(name, NAMESPACE_INDEX),
            ua.Variant(0, variant_type),
        )
        await tag_nodes[name].set_writable()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("asyncua.server.subscription_service").setLevel(logging.WARNING)
    LOGGER.info("Serveur OPC UA démarré sur %s", ENDPOINT)

    async with server:
        tag_logger_task = asyncio.create_task(log_tag_changes(tag_nodes))
        try:
            await asyncio.Event().wait()
        finally:
            tag_logger_task.cancel()
            await asyncio.gather(tag_logger_task, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())