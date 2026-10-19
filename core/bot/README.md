# Yuna Bot Adapter

Enforces **ADR-010**: Discord is exclusively an adapter, not the application brain.
This module translates external API inputs seamlessly into internal `EventBus` payloads for isolated Service execution.
