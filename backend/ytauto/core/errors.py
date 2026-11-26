"""Errores de dominio."""


class YtautoError(Exception):
    """Base de errores del sistema."""


class AcceptanceError(YtautoError):
    """La salida de un agente no cumple sus criterios de aceptación."""

    def __init__(self, agent: str, issues: list[str]):
        self.agent = agent
        self.issues = issues
        super().__init__(f"{agent}: " + "; ".join(issues))


class PhaseBlocked(YtautoError):
    """La fase no puede continuar sin intervención (aprobación, gasto, límite de uso)."""

    def __init__(self, reason: str, code: str = "blocked"):
        self.reason = reason
        self.code = code
        super().__init__(reason)


class BudgetExceeded(PhaseBlocked):
    def __init__(self, reason: str):
        super().__init__(reason, code="budget_exceeded")


class SpendNotAuthorized(PhaseBlocked):
    def __init__(self, reason: str):
        super().__init__(reason, code="spend_not_authorized")


class ProviderError(YtautoError):
    """Fallo de un proveedor audiovisual."""

    def __init__(self, provider: str, message: str, transient: bool = True, retry_after_s: float | None = None):
        self.provider = provider
        self.transient = transient
        self.retry_after_s = retry_after_s  # límite de uso del proveedor (rate limit)
        super().__init__(f"[{provider}] {message}")


class ProviderSkip(ProviderError):
    """El proveedor no se ocupa de esta petición (p. ej. un efecto genérico para el generador de efectos con IA):
    se pasa al siguiente sin contarlo como fallo ni gastar nada."""

    def __init__(self, provider: str, message: str):
        super().__init__(provider, message, transient=False)


class ProviderNotConfigured(YtautoError):
    pass
