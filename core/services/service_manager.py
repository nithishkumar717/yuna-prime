from core.container.container import Container
from core.services.guild_service import GuildService
from core.services.member_service import MemberService
from core.services.role_service import RoleService
from core.services.channel_service import ChannelService


class ServiceManager:
    """
    Registers all internal core services to the Dependency Injection Container.
    """

    @staticmethod
    def register_services():
        Container.register_singleton(GuildService, GuildService())
        Container.register_singleton(MemberService, MemberService())
        Container.register_singleton(RoleService, RoleService())
        Container.register_singleton(ChannelService, ChannelService())
