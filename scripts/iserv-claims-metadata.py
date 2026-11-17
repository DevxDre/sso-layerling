#!/usr/bin/env python3
"""Historical IServ-only probe with fixed filters. Read selected group/role metadata from IServ's localhost IDM API.

Run on the IServ itself, NOT the webhoster. No credentials, cookies, user lists,
configuration reads, writes, or package installations. Never a web endpoint.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:987/iserv/idm/api/v1/"
LIMIT = 65536


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def collect(opener, label, resource, filters, fields):
    query = urllib.parse.urlencode({**filters, "_attributes": ",".join(fields)})
    request = urllib.request.Request(BASE + resource + "?" + query, headers={"Accept": "application/json"}, method="GET")
    result = {"probe": label, "http": None, "records": []}
    try:
        with opener.open(request, timeout=5) as response:
            result["http"] = response.status
            body = response.read(LIMIT + 1)
        if len(body) > LIMIT:
            result["error"] = "response_too_large"
            return result
        data = json.loads(body)
        rows = data if isinstance(data, list) else data.get("hydra:member") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            result["error"] = "unexpected_json_shape"
            return result
        for row in rows:
            if not isinstance(row, dict) or any(row.get(k) != v for k, v in filters.items()):
                continue
            # Deliberately discard all fields outside this metadata allowlist,
            # even if the server ignores the requested attribute projection.
            result["records"].append({key: row[key] for key in fields if isinstance(row.get(key), str)})
        if len(result["records"]) != 1:
            result["error"] = "no_unique_match"
        elif not any(result["records"][0].get(key) for key in ["uuid", "hexUuid"]):
            result["error"] = "missing_identifier"
    except urllib.error.HTTPError as error:
        result["http"] = error.code
        result["error"] = "http_error"
    except (urllib.error.URLError, TimeoutError, OSError):
        result["error"] = "local_api_unreachable"
    except (ValueError, UnicodeError):
        result["error"] = "invalid_json"
    return result


def main():
    # Never use a system-configured HTTP proxy for this loopback-only request.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    probes = [
        ("makerspace-betreuung", "groups", {"group": "makerspace-betreuung"}, ["uuid", "hexUuid", "group", "name"]),
        ("Admins", "groups", {"name": "Admins"}, ["uuid", "hexUuid", "group", "name"]),
        ("Students", "roles", {"role": "ROLE_STUDENT"}, ["uuid", "hexUuid", "role", "name"]),
    ]
    results = [collect(opener, *probe) for probe in probes]
    print(json.dumps({"source": "IServ localhost IDM metadata", "results": results}, indent=2, ensure_ascii=False))
    return 0 if all(not row.get("error") for row in results) else 1


if __name__ == "__main__":
    sys.exit(main())
