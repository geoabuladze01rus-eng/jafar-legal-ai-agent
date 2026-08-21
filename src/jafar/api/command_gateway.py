from dataclasses import dataclass
from secrets import token_urlsafe

from jafar.commands.models import CommandRequest, CommandResult
from jafar.commands.router import route_command


@dataclass(frozen=True)
class GatewayResponse:
    request_id: str
    result: CommandResult


def dispatch_command(request: CommandRequest) -> GatewayResponse:
    """Provider-neutral command gateway shared by Apple clients."""
    if not request.user_id.strip():
        raise ValueError("user_id is required")
    if not request.source_device.strip():
        raise ValueError("source_device is required")

    return GatewayResponse(
        request_id=token_urlsafe(18),
        result=route_command(request),
    )
