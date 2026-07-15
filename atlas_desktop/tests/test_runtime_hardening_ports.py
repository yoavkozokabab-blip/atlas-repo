from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from atlas_desktop import data_paths, runtime_startup, server


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path / "atlas-data"))
    data_paths.reset_desktop_data_dir_cache()
    yield
    data_paths.reset_desktop_data_dir_cache()


def _serve(httpd):
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread


def test_preferred_port_free_binds_preferred(monkeypatch):
    probe = ThreadingHTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    port = int(probe.server_address[1])
    probe.server_close()
    monkeypatch.setattr(runtime_startup, "controlled_ports", lambda _preferred: [port])
    httpd, selected, existing = server._select_runtime("127.0.0.1", port)
    try:
        assert selected == port
        assert existing is None
    finally:
        httpd.server_close()


def test_preferred_port_occupied_by_verified_atlas_uses_fallback_without_probe(monkeypatch):
    httpd = server.AtlasHTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    port = int(httpd.server_address[1])
    httpd.atlas_runtime_identity = runtime_startup.new_instance_identity(port)
    fallback_probe = ThreadingHTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    fallback_port = int(fallback_probe.server_address[1])
    fallback_probe.server_close()
    thread = _serve(httpd)
    probe_calls = []
    monkeypatch.setattr(
        runtime_startup, "controlled_ports", lambda _preferred: [port, fallback_port]
    )
    monkeypatch.setattr(
        runtime_startup,
        "probe_atlas",
        lambda _host, candidate, **_kwargs: probe_calls.append(candidate) or None,
    )
    try:
        selected_httpd, selected, existing = server._select_runtime("127.0.0.1", port)
        assert selected_httpd is not None
        assert selected == fallback_port
        assert existing is None
        assert port not in probe_calls
        selected_httpd.server_close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_foreign_health_service_is_never_accepted(monkeypatch):
    class ForeignHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = json.dumps({"ok": True, "product": "Aurora"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    foreign = ThreadingHTTPServer(("127.0.0.1", 0), ForeignHandler)
    foreign_port = int(foreign.server_address[1])
    fallback_probe = ThreadingHTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    fallback_port = int(fallback_probe.server_address[1])
    fallback_probe.server_close()
    thread = _serve(foreign)
    monkeypatch.setattr(
        runtime_startup, "controlled_ports", lambda _preferred: [foreign_port, fallback_port]
    )
    try:
        httpd, selected, existing = server._select_runtime("127.0.0.1", foreign_port)
        assert selected == fallback_port
        assert existing is None
        httpd.server_close()
    finally:
        foreign.shutdown()
        foreign.server_close()
        thread.join(timeout=2)


def test_multiple_occupied_fallbacks_are_skipped(monkeypatch):
    occupied = [server.AtlasHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) for _ in range(3)]
    ports = [int(item.server_address[1]) for item in occupied]
    free_probe = ThreadingHTTPServer(("127.0.0.1", 0), server.AtlasHandler)
    free_port = int(free_probe.server_address[1])
    free_probe.server_close()
    monkeypatch.setattr(runtime_startup, "controlled_ports", lambda _preferred: [*ports, free_port])
    monkeypatch.setattr(runtime_startup, "probe_atlas", lambda *_args, **_kwargs: None)
    try:
        httpd, selected, existing = server._select_runtime("127.0.0.1", ports[0])
        assert selected == free_port
        assert existing is None
        httpd.server_close()
    finally:
        for item in occupied:
            item.server_close()


def test_backend_startup_failure_is_reported_after_controlled_range(monkeypatch):
    monkeypatch.setattr(runtime_startup, "controlled_ports", lambda _preferred: [8777, 8778])
    monkeypatch.setattr(runtime_startup, "probe_atlas", lambda *_args, **_kwargs: None)

    def fail(*_args, **_kwargs):
        raise OSError(10048, "occupied")

    monkeypatch.setattr(server, "AtlasHTTPServer", fail)
    with pytest.raises(OSError):
        server._select_runtime("127.0.0.1", 8777)


def test_controlled_range_skips_accounts_port():
    ports = runtime_startup.controlled_ports()
    assert ports[0] == 8777
    assert 8788 not in ports
    assert ports[-1] == 8797


def test_runtime_descriptor_is_signed_and_tamper_evident(tmp_path):
    data_dir = str(tmp_path / "descriptor")
    identity = runtime_startup.new_instance_identity(8779)
    path = runtime_startup.write_runtime_descriptor(identity, data_dir=data_dir)
    assert runtime_startup.read_runtime_descriptor(data_dir=data_dir)["port"] == 8779
    record = json.loads(open(path, encoding="utf-8").read())
    record["port"] = 8780
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    assert runtime_startup.read_runtime_descriptor(data_dir=data_dir) is None


def test_forged_handshake_is_rejected(tmp_path):
    payload = {
        "product": runtime_startup.PRODUCT,
        "protocol": runtime_startup.PROTOCOL,
        "challenge": "nonce",
        "port": 8777,
        "pid": 1,
        "instance_id": "foreign",
        "proof": "0" * 64,
    }
    assert not runtime_startup.verify_handshake(
        payload, "nonce", 8777, data_dir=str(tmp_path / "secret")
    )
