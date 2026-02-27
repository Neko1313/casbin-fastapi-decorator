"""Casdoor integration and authorization guard."""
import os

from casbin_fastapi_decorator_casdoor import CasdoorEnforceTarget, CasdoorIntegration

# ---------------------------------------------------------------------------
# Certificate generated for this example (public part only, used to verify
# JWTs issued by Casdoor).  The matching private key is stored in
# casdoor/init_data.json under the "cert-example" certificate entry.
# ---------------------------------------------------------------------------
_CERTIFICATE = """\
-----BEGIN CERTIFICATE-----
MIIC2DCCAcCgAwIBAgIUdehFSHCw9b3QUw7Kg+UfTADcEQEwDQYJKoZIhvcNAQEL
BQAwJjEkMCIGA1UEAwwbQ2FzZG9vciBFeGFtcGxlIENlcnRpZmljYXRlMB4XDTI2
MDIyNzAzMDQ0M1oXDTM2MDIyNTAzMDQ0M1owJjEkMCIGA1UEAwwbQ2FzZG9vciBF
eGFtcGxlIENlcnRpZmljYXRlMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKC
AQEAsG1LaxcbNp17HhFLyj0Byt9xFp5kFi/YIrzIpei+PIXCcSVAbGGy9yM18Liv
JNygXDErYS8+qZOZr047o/8HCTQBcw8vuAOZL5TFLSqYBJMbPmRmwnNxnVs37/17
uVh80kjeunzfgXtIYIbzm67Dwo5Qp64mBoFpoyzPbcoKGSaBbrh+yjHtevokWu2s
x48qweDZwKKhxz2nFU76Zcm9KUh/Wj7w3kDqWfFTzSfGCUWePudkoVddpwin9clz
tGgIf/b5L9seWJVwFX0SdDoPjiT0nkGtgXGkwqROvMLw4XI7MPmQnERmPpZxbS95
7o7tnckVxvca83mF2YBY0B3mSwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQCUPK4D
+u9uT/AtrHftJbuDo8ITRg+URNC9CRefghtRMM5oZy8FWBVxAE9So8eSZ6myIJQJ
tQDzth9OO7u6bScCUjNh/lkLhMCVqbC2J9qXODQs6mR+A5BKMnQDD/gaxkzFEjPb
6o6F5SchtaeOikCYngvJP2/f5E9QS5QZ9wN7zG/u7JlqWdNM9OuyASqQPGsQJ5W4
wbNjVtrDLli2a4TnrH2Wl584BWuoT5ENZlpv7aHuA+LZVKLrMJ0BciyaRdfStkEj
1gqHjx6e6gQo9vTC445XxskxPgPppTP+hoGhI5tmz7jVpYqxwlUteb8zcXsrAF+d
QcFAyxahEu3iZGWD
-----END CERTIFICATE-----
"""

# ---------------------------------------------------------------------------
# All values below match what is declared in casdoor/init_data.json.
# ---------------------------------------------------------------------------
_ENDPOINT = os.getenv("CASDOOR_ENDPOINT", "http://localhost:8000")
_CLIENT_ID = "example-client-id"
_CLIENT_SECRET = "example-client-secret"  # noqa: S105
_ORG = "example-org"
_APP = "app-example"

casdoor = CasdoorIntegration(
    endpoint=_ENDPOINT,
    client_id=_CLIENT_ID,
    client_secret=_CLIENT_SECRET,
    certificate=_CERTIFICATE,
    org_name=_ORG,
    application_name=_APP,
    # Enforce using the ACL enforcer seeded in init_data.json.
    # The user identity passed to Casbin is "{owner}/{name}" by default,
    # e.g. "example-org/alice".
    target=CasdoorEnforceTarget(enforce_id=f"{_ORG}/enforcer-example"),
    redirect_after_login="/",
    # Use Secure=False for local HTTP development.
    cookie_secure=False,
    cookie_samesite="lax",
)

guard = casdoor.create_guard()
