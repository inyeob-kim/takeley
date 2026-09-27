"""Shared outbound headers for discovery providers."""

TAKELEY_USER_AGENT = "TAKELEY/1.0 (+https://takeley.co; hello@takeley.co)"


def takeley_headers() -> dict[str, str]:
    return {"User-Agent": TAKELEY_USER_AGENT, "Accept": "*/*"}
