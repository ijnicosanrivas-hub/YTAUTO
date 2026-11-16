"""Provider Registry: catálogo, credenciales cifradas, cadena principal/alternativos y presupuesto."""
from .budget import BudgetManager
from .catalog import discover, register_adapter, unregister_adapter
from .gateway import RegistryGateway
from .registry import ProviderConfig, ProviderRegistry, ProviderView, RegistryError
from .vault import CredentialVault, load_or_create_master_key

__all__ = ["BudgetManager", "CredentialVault", "ProviderConfig", "ProviderRegistry", "ProviderView",
           "RegistryError", "RegistryGateway", "discover", "load_or_create_master_key", "register_adapter",
           "unregister_adapter"]
