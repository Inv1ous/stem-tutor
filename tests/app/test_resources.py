"""System memory readings include model allocations outside the tutor process."""
from subprocess import CompletedProcess


def test_mac_ram_uses_reported_page_size_and_available_pages(monkeypatch):
    from tutor_app import resources

    monkeypatch.setattr(resources.sys, "platform", "darwin")

    def run(args, **kwargs):
        if args[0] == "sysctl":
            return CompletedProcess(args, 0, str(32 * 1024 ** 3), "")
        return CompletedProcess(args, 0, '''Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free: 262144.
Pages inactive: 262144.
Pages speculative: 131072.
Pages occupied by compressor: 65536.
''', "")

    monkeypatch.setattr(resources.subprocess, "run", run)
    assert resources.ram_text() == "RAM 22.0/32.0 GiB"


def test_unreadable_ram_is_unavailable_not_zero(monkeypatch):
    from tutor_app import resources

    monkeypatch.setattr(resources.sys, "platform", "darwin")

    def fail(*args, **kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr(resources.subprocess, "run", fail)
    assert resources.ram_text() == "RAM unavailable"
