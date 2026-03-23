"""Message bus module for decoupled channel-agent communication."""

# Import directly from submodules to avoid circular import via claw.interactive
from claw.interactive.bus.queue import MessageBus
from claw.interactive.bus.events import InboundMessage, OutboundMessage

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
