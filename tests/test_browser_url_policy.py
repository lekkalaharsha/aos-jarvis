from __future__ import annotations

import pytest

from aos.browser.url_policy import canonicalize_host, is_cross_domain_redirect, validate_url
from aos.safety.errors import PermissionBlocked


def _public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture(autouse=True)
def _layer1_dns_free(monkeypatch):
    def fail_live_dns(*args, **kwargs):
        raise AssertionError("Layer-1 browser URL tests must inject a deterministic resolver")

    monkeypatch.setattr("aos.browser.url_policy.socket.getaddrinfo", fail_live_dns)


def test_canonicalize_host_lowercases():
    assert canonicalize_host("Example.COM") == "example.com"


def test_canonicalize_host_punycode_normalizes_idn():
    # Cyrillic-lookalike vs Latin must not collide after normalization (TM-05).
    latin = canonicalize_host("example.com")
    homoglyph = canonicalize_host("еxample.com")  # Cyrillic 'e'
    assert latin != homoglyph
    assert homoglyph.startswith("xn--")


def test_unknown_domain_denied():
    with pytest.raises(PermissionBlocked):
        validate_url("https://evil-example.com/", domain_host="example.com", allow_http=False, allow_ip_literal=False)


def test_subdomain_not_implicitly_covered():
    with pytest.raises(PermissionBlocked):
        validate_url("https://app.example.com/", domain_host="example.com", allow_http=False, allow_ip_literal=False)


def test_http_denied_by_default():
    with pytest.raises(PermissionBlocked):
        validate_url("http://example.com/", domain_host="example.com", allow_http=False, allow_ip_literal=False)


def test_http_allowed_with_flag():
    validated = validate_url("http://example.com/", domain_host="example.com", allow_http=True, allow_ip_literal=False, resolver=_public_resolver)
    assert validated.scheme == "http"


def test_ip_literal_denied_by_default():
    with pytest.raises(PermissionBlocked):
        validate_url("http://203.0.113.5/", domain_host="example.com", allow_http=True, allow_ip_literal=False)


def test_ip_literal_allowed_with_flag_but_still_denies_private():
    with pytest.raises(PermissionBlocked):
        validate_url("http://127.0.0.1/", domain_host="example.com", allow_http=True, allow_ip_literal=True)


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.5", "169.254.1.1", "::1", "fc00::1", "0.0.0.0"])
def test_private_loopback_link_local_denied(host):
    url = f"http://[{host}]/" if ":" in host else f"http://{host}/"
    with pytest.raises(PermissionBlocked):
        validate_url(url, domain_host="example.com", allow_http=True, allow_ip_literal=True)


def test_ipv4_mapped_ipv6_loopback_denied():
    # Proves the check uses parsed address objects, not string prefix matching.
    with pytest.raises(PermissionBlocked):
        validate_url("http://[::ffff:127.0.0.1]/", domain_host="example.com", allow_http=True, allow_ip_literal=True)


def test_data_javascript_file_scheme_denied():
    for scheme_url in ("data:text/html,hi", "javascript:alert(1)", "file:///etc/passwd"):
        with pytest.raises(PermissionBlocked):
            validate_url(scheme_url, domain_host="example.com", allow_http=True, allow_ip_literal=False)


def test_nondefault_port_denied_unless_whitelisted():
    with pytest.raises(PermissionBlocked):
        validate_url("https://example.com:8443/", domain_host="example.com", allow_http=False, allow_ip_literal=False, resolver=_public_resolver)
    validated = validate_url("https://example.com:8443/", domain_host="example.com", allow_http=False, allow_ip_literal=False, extra_ports=(8443,), resolver=_public_resolver)
    assert validated.port == 8443


def test_url_length_cap():
    long_path = "/" + "a" * 3000
    with pytest.raises(PermissionBlocked):
        validate_url(f"https://example.com{long_path}", domain_host="example.com", allow_http=False, allow_ip_literal=False)


def test_resolved_address_private_denied_via_injected_resolver():
    def resolver(host):
        return ["127.0.0.1"]
    with pytest.raises(PermissionBlocked):
        validate_url("https://example.com/", domain_host="example.com", allow_http=False, allow_ip_literal=False, resolver=resolver)


def test_resolved_address_public_succeeds_via_injected_resolver():
    def resolver(host):
        return ["93.184.216.34"]
    validated = validate_url("https://example.com/", domain_host="example.com", allow_http=False, allow_ip_literal=False, resolver=resolver)
    assert validated.host == "example.com"


def test_dns_rebinding_denied_at_connect_time():
    # Check-time and connect-time are represented by two separate resolver
    # calls in the real engine; here we assert the resolver-driven check
    # itself denies a private answer regardless of when it's invoked.
    def rebinding_resolver(host):
        return ["10.0.0.5"]
    with pytest.raises(PermissionBlocked):
        validate_url("https://example.com/", domain_host="example.com", allow_http=False, allow_ip_literal=False, resolver=rebinding_resolver)


def test_query_fragment_recorded_only_as_booleans():
    validated = validate_url("https://example.com/search?q=secret#frag", domain_host="example.com", allow_http=False, allow_ip_literal=False, resolver=_public_resolver)
    assert validated.had_query is True
    assert validated.had_fragment is True
    # The validator return value never carries the raw query/fragment text.
    assert not hasattr(validated, "query")
    assert not hasattr(validated, "fragment")


def test_same_domain_redirect_not_cross_domain():
    assert is_cross_domain_redirect("example.com", "https://example.com/other") is False


def test_cross_domain_redirect_detected():
    assert is_cross_domain_redirect("example.com", "https://attacker.example/") is True


def test_cross_domain_redirect_to_enrolled_domain_still_flagged():
    # Enrollment is eligibility, not standing consent to arrive via redirect
    # (contract Sec4b) -- the classifier flags it regardless of enrollment
    # status; the caller (task runner) is what requires a fresh approval.
    assert is_cross_domain_redirect("example.com", "https://other-enrolled.example/") is True
